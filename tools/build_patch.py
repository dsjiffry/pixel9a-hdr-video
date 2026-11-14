#!/usr/bin/env python3
# Build the v0.4 liblyric_hwl.so HLG10-characteristics injection patch from STOCK.
#
# Detour: CameraDeviceHwlImpl::GetCameraCharacteristics (FUN_00bea2d0), at the point
# where the built GCH HalCameraMetadata object is stored in *param_2 (x19) and the
# function is about to return success (instruction `mov w19, wzr` @ 0xbea394).
#
# The cave (in the RX LOAD segment extended to vaddr 0x149e000) does, on the object [x19]:
#   Set(0xC0013 availableDynamicRangeProfilesMap, int64[6]={STANDARD,0,0, HLG10,0,0})
#   Set(0xC0014 recommendedTenBitDynamicRangeProfile, int64[1]={HLG10})
#   RMW 0xC000C availableCapabilities: Get -> memcpy -> append DYNAMIC_RANGE_TEN_BIT(17) -> Set(uint8)
# then runs the displaced `mov w19,wzr` and branches back to 0xbea398.
#
# Usage: python -E -P tools/build_patch.py <stock.so> <out.so>
import sys, struct, hashlib
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN

STOCK, OUT = sys.argv[1], sys.argv[2]

HOOK      = 0xbea394     # `mov w19, wzr` on the success path
RET       = 0xbea398     # instruction after the hook (its `b 0xbea42c`)
CAVE      = 0x149d2c0    # start of free, now-executable space
SEG_END   = 0x149e000    # RX LOAD segment end after phdr extension
PH2_SIZE  = 0x10f6000    # phdr[2] filesz/memsz covering the cave (RX base 0x3a8000)

SET_I64   = 0x1496eb8    # HalCameraMetadata::Set(uint32,const int64*,uint32)
SET_U8    = 0x1496510    # HalCameraMetadata::Set(uint32,const uint8*,uint32)
GET       = 0x1495ee0    # HalCameraMetadata::Get(uint32,camera_metadata_ro_entry*) const
MEMCPY    = 0x149bac0

TAG_CAPS  = 0xC000C      # ANDROID_REQUEST_AVAILABLE_CAPABILITIES (uint8[])
TAG_DRP   = 0xC0013      # ANDROID_REQUEST_AVAILABLE_DYNAMIC_RANGE_PROFILES_MAP (int64[])
TAG_REC   = 0xC0014      # ANDROID_REQUEST_RECOMMENDED_TEN_BIT_DYNAMIC_RANGE_PROFILE (int64)
CAP_TEN_BIT = 18         # DYNAMIC_RANGE_TEN_BIT (17 is REMOSAIC_REPROCESSING)
PROF_STANDARD, PROF_HLG10 = 1, 2

# camera_metadata_ro_entry here is 32 bytes: count @ +0x10 (size_t), data ptr @ +0x18
# (confirmed from the HAL's own Get callers, e.g. 0x698490). Not the 24-byte {count@8,data@0x10}.
ENT_COUNT = 0x10
ENT_DATA  = 0x18

TAG_FACING  = 0x80005    # ANDROID_LENS_FACING (byte); inject only when == BACK
FACING_BACK = 1          # ANDROID_LENS_FACING_BACK (FRONT=0, EXTERNAL=2)

# ---- tiny AArch64 encoders -------------------------------------------------
def movz_w(rd, imm16):            return 0x52800000 | ((imm16 & 0xffff) << 5) | rd
def movk_w_lsl16(rd, imm16):      return 0x72A00000 | ((imm16 & 0xffff) << 5) | rd
def add_imm(rd, rn, imm):         return 0x91000000 | ((imm & 0xfff) << 10) | (rn << 5) | rd      # 64-bit
def sub_imm(rd, rn, imm):         return 0xD1000000 | ((imm & 0xfff) << 10) | (rn << 5) | rd      # 64-bit
def add_shifted(rd, rn, rm):      return 0x8B000000 | (rm << 16) | (rn << 5) | rd                 # rd=rn+rm, 64-bit (rn!=sp)
def ldr_x_uimm(rt, rn, off):      return 0xF9400000 | ((off // 8) << 10) | (rn << 5) | rt
def str_x_uimm(rt, rn, off):      return 0xF9000000 | ((off // 8) << 10) | (rn << 5) | rt
def strb_uimm(rt, rn, off):       return 0x39000000 | ((off & 0xfff) << 10) | (rn << 5) | rt
def stp_xzr_sp(off):              return 0xA9000000 | (((off // 8) & 0x7f) << 15) | (31 << 10) | (31 << 5) | 31  # STP XZR,XZR,[SP,#off]
def mov_reg_x(rd, rm):            return 0xAA0003E0 | (rm << 16) | rd           # ORR Xd,XZR,Xm
def mov_reg_w(rd, rm):            return 0x2A0003E0 | (rm << 16) | rd           # ORR Wd,WZR,Wm
def mov_from_sp(rd):              return add_imm(rd, 31, 0)                      # mov Xd,sp
def cmp_imm_x(rn, imm):           return 0xF1000000 | ((imm & 0xfff) << 10) | (rn << 5) | 31      # SUBS XZR,Xn,#imm (64)
def cmp_imm_w(rn, imm):           return 0x71000000 | ((imm & 0xfff) << 10) | (rn << 5) | 31      # SUBS WZR,Wn,#imm (32)
def ldrb_uimm(rt, rn, off):       return 0x39400000 | ((off & 0xfff) << 10) | (rn << 5) | rt
def ldr_x0_x19():                 return ldr_x_uimm(0, 19, 0)
SP = 31

# PC-relative (filled in pass 2)
def adrp(rd, pc, target):
    page = (target & ~0xfff) - (pc & ~0xfff)
    imm = page >> 12
    immlo = imm & 3; immhi = (imm >> 2) & 0x7ffff
    return 0x90000000 | (immlo << 29) | (immhi << 5) | rd
def b_(pc, target):               d = (target - pc) >> 2; return 0x14000000 | (d & 0x03ffffff)
def bl_(pc, target):              d = (target - pc) >> 2; return 0x94000000 | (d & 0x03ffffff)
def cbz_x(pc, target, rt):        d = (target - pc) >> 2; return 0xB4000000 | ((d & 0x7ffff) << 5) | rt
def cbnz_w(pc, target, rt):       d = (target - pc) >> 2; return 0x35000000 | ((d & 0x7ffff) << 5) | rt
def bcond(pc, target, cond):      d = (target - pc) >> 2; return 0x54000000 | ((d & 0x7ffff) << 5) | cond
COND_HI = 8
COND_NE = 1

stock = bytearray(open(STOCK, "rb").read())
orig_mov_w19 = struct.unpack_from("<I", stock, HOOK)[0]   # displaced `mov w19, wzr`, reused verbatim

# ---- assemble the cave with a two-pass label resolver ----------------------
# Each item: ('ins', callable(pc)->word) or ('label', name) or ('data', bytes)
prog = []
def I(fn):   prog.append(('ins', fn))
def L(name): prog.append(('label', name))
def D(b):    prog.append(('data', b))

labels = {}

# --- entry: null guard, then one scratch frame for the whole cave ---
# frame 0x80: buf@sp(0x40), entry@sp+0x40(0x20), count stash@sp+0x60
I(lambda pc: ldr_x0_x19())
I(lambda pc: cbz_x(pc, labels['L_ret'], 0))        # *param_2 null -> return (no frame)
I(lambda pc: sub_imm(SP, SP, 0x80))

# --- rear-only gate: inject only when LENS_FACING == BACK ---
I(lambda pc: stp_xzr_sp(0x40))
I(lambda pc: stp_xzr_sp(0x50))
I(lambda pc: ldr_x0_x19())
I(lambda pc: movz_w(1, TAG_FACING & 0xffff))
I(lambda pc: movk_w_lsl16(1, (TAG_FACING >> 16) & 0xffff))   # 0x80005 LENS_FACING
I(lambda pc: add_imm(2, SP, 0x40))                 # &entry
I(lambda pc: bl_(pc, GET))
I(lambda pc: cbnz_w(pc, labels['L_end'], 0))       # Get failed -> skip injection
I(lambda pc: ldr_x_uimm(3, SP, 0x40 + ENT_DATA))   # facing data ptr
I(lambda pc: cbz_x(pc, labels['L_end'], 3))        # no data -> skip
I(lambda pc: ldr_x_uimm(4, SP, 0x40 + ENT_COUNT))  # count
I(lambda pc: cbz_x(pc, labels['L_end'], 4))        # count 0 -> skip
I(lambda pc: ldrb_uimm(5, 3, 0))                   # facing = data.u8[0]
I(lambda pc: cmp_imm_w(5, FACING_BACK))
I(lambda pc: bcond(pc, labels['L_end'], COND_NE))  # not BACK -> skip injection

# --- Set DRP map (0xC0013) = STANDARD + HLG10 ---
I(lambda pc: ldr_x0_x19())
I(lambda pc: adrp(2, pc, labels['DRP']))
I(lambda pc: add_imm(2, 2, labels['DRP'] & 0xfff))
I(lambda pc: movz_w(1, TAG_DRP & 0xffff))
I(lambda pc: movk_w_lsl16(1, (TAG_DRP >> 16) & 0xffff))
I(lambda pc: movz_w(3, 6))
I(lambda pc: bl_(pc, SET_I64))
# --- Set recommended (0xC0014) = HLG10 ---
I(lambda pc: ldr_x0_x19())
I(lambda pc: adrp(2, pc, labels['REC']))
I(lambda pc: add_imm(2, 2, labels['REC'] & 0xfff))
I(lambda pc: movz_w(1, TAG_REC & 0xffff))
I(lambda pc: movk_w_lsl16(1, (TAG_REC >> 16) & 0xffff))
I(lambda pc: movz_w(3, 1))
I(lambda pc: bl_(pc, SET_I64))
# --- RMW capabilities (0xC000C): append DYNAMIC_RANGE_TEN_BIT ---
I(lambda pc: stp_xzr_sp(0x40))                     # re-zero entry
I(lambda pc: stp_xzr_sp(0x50))
I(lambda pc: ldr_x0_x19())
I(lambda pc: movz_w(1, TAG_CAPS & 0xffff))
I(lambda pc: movk_w_lsl16(1, (TAG_CAPS >> 16) & 0xffff))
I(lambda pc: add_imm(2, SP, 0x40))                 # &entry
I(lambda pc: bl_(pc, GET))
I(lambda pc: cbnz_w(pc, labels['L_end'], 0))       # Get failed -> caps unchanged
I(lambda pc: ldr_x_uimm(4, SP, 0x40 + ENT_COUNT))  # count = entry.count (@ +0x10)
I(lambda pc: ldr_x_uimm(1, SP, 0x40 + ENT_DATA))   # src   = entry.data.u8 (@ +0x18)
I(lambda pc: cmp_imm_x(4, 0x20))
I(lambda pc: bcond(pc, labels['L_end'], COND_HI))  # count > 0x20 -> bail (sanity)
I(lambda pc: cbz_x(pc, labels['L_end'], 4))        # count == 0 -> bail
I(lambda pc: str_x_uimm(4, SP, 0x60))              # stash count (memcpy clobbers x4)
I(lambda pc: mov_from_sp(0))                        # dst = buf
I(lambda pc: mov_reg_x(2, 4))                       # n = count  (x1=src already)
I(lambda pc: bl_(pc, MEMCPY))
I(lambda pc: ldr_x_uimm(4, SP, 0x60))              # reload count
I(lambda pc: mov_from_sp(7))                         # x7 = sp
I(lambda pc: add_shifted(7, 7, 4))                  # x7 = &buf[count]
I(lambda pc: movz_w(6, CAP_TEN_BIT))                # 18 = DYNAMIC_RANGE_TEN_BIT
I(lambda pc: strb_uimm(6, 7, 0))                    # buf[count] = 18
I(lambda pc: add_imm(4, 4, 1))                      # newcount
I(lambda pc: ldr_x0_x19())
I(lambda pc: movz_w(1, TAG_CAPS & 0xffff))
I(lambda pc: movk_w_lsl16(1, (TAG_CAPS >> 16) & 0xffff))
I(lambda pc: mov_from_sp(2))                         # buf
I(lambda pc: mov_reg_w(3, 4))                        # count = newcount
I(lambda pc: bl_(pc, SET_U8))
L('L_end')
I(lambda pc: add_imm(SP, SP, 0x80))
L('L_ret')
I(lambda pc: orig_mov_w19)                           # displaced original
I(lambda pc: b_(pc, RET))
# data (8-byte aligned)
L('DATA')
D(struct.pack('<6q', PROF_STANDARD,0,0, PROF_HLG10,0,0))   # DRP map  (label DRP set below)
D(struct.pack('<q', PROF_HLG10))                           # recommended (label REC)

# ---- layout pass: assign addresses (code is 4B each; data block 8B-aligned) ----
def address_walk_aligned():
    pc = CAVE
    data_idx = 0
    align_pad = 0
    for kind, val in prog:
        if kind == 'label':
            labels[val] = pc
        elif kind == 'ins':
            pc += 4
        elif kind == 'data':
            if data_idx == 0:
                pad = (8 - (pc % 8)) % 8
                align_pad = pad
                pc += pad
                labels['DRP'] = pc
            elif data_idx == 1:
                labels['REC'] = pc
            pc += len(val)
            data_idx += 1
    return pc, align_pad

end, align_pad = address_walk_aligned()
assert end <= SEG_END, "cave overflow: 0x%x > 0x%x" % (end, SEG_END)

# encode
out_words = []
pc = CAVE
data_idx = 0
blob = bytearray()
for kind, val in prog:
    if kind == 'label':
        continue
    elif kind == 'ins':
        w = val(pc)
        blob += struct.pack('<I', w)
        pc += 4
    elif kind == 'data':
        if data_idx == 0 and align_pad:
            blob += b'\x00' * align_pad
            pc += align_pad
        blob += val
        pc += len(val)
        data_idx += 1

# ---- apply to a copy of STOCK ----------------------------------------------
patched = bytearray(stock)
# 1) phdr[2] (RX LOAD) filesz & memsz -> PH2_SIZE
e_phoff = struct.unpack_from('<Q', patched, 0x20)[0]; e_phent = struct.unpack_from('<H', patched, 0x36)[0]
ph2 = e_phoff + 2 * e_phent
assert struct.unpack_from('<I', patched, ph2)[0] == 1  # PT_LOAD
struct.pack_into('<Q', patched, ph2 + 0x20, PH2_SIZE)   # p_filesz
struct.pack_into('<Q', patched, ph2 + 0x28, PH2_SIZE)   # p_memsz
# 2) hook branch
struct.pack_into('<I', patched, HOOK, b_(HOOK, CAVE))
# 3) stub + data
patched[CAVE:CAVE + len(blob)] = blob

open(OUT, 'wb').write(patched)

# ---- self-verify: disassemble hook + cave ----------------------------------
md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
print("labels:", {k: hex(v) for k, v in sorted(labels.items(), key=lambda kv: kv[1])})
print("cave end=0x%x (limit 0x%x), %d bytes\n" % (end, SEG_END, len(blob)))
print("== hook @0x%x ==" % HOOK)
for ins in md.disasm(bytes(patched[HOOK:HOOK+8]), HOOK):
    print("  0x%x: %-8s %s" % (ins.address, ins.mnemonic, ins.op_str))
print("\n== cave ==")
for ins in md.disasm(bytes(blob[:end - CAVE]), CAVE):
    print("  0x%x: %-8s %s" % (ins.address, ins.mnemonic, ins.op_str))
print("\nsha256:", hashlib.sha256(patched).hexdigest())
