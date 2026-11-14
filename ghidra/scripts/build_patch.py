import sys, struct, hashlib
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN

IN  = sys.argv[1]
OUT = sys.argv[2]
STOCK_SHA = "97faa97aa3ca488287392470407158dba31041c91e1818491c998fce959df028"

data = bytearray(open(IN, "rb").read())
h = hashlib.sha256(data).hexdigest()
assert h == STOCK_SHA, f"input hash mismatch: {h}"

# ---- addresses: FILE OFFSETS (== runtime vaddr; Ghidra shows these +0x100000) ----
# Target = DEVICE-level CameraDeviceHwlImpl::GetCameraCharacteristics (camera_device_hwl_impl.cc),
# the function GCH calls for the static characteristics the framework caches / apps query.
# Success path: ...; bl FUN_00cea520(*param_2); [DET] mov w19,wzr; b <epilogue>. x19=param_2 here.
DET      = 0xbea394      # detour site: 'mov w19,wzr' (return 0) on success path
DET_NEXT = 0xbea398      # instruction after detour site ('b 0xbea42c' -> epilogue)
CAVE     = 0x149d2c0     # start of code cave (zero inter-seg gap)
SET_I64  = 0x1496eb8     # HalCameraMetadata::Set(this, tag, int64* data, count) PLT stub
TAG_MAP  = 0xC0013       # availableDynamicRangeProfilesMap
TAG_REC  = 0xC0014       # recommendedTenBitDynamicRangeProfile
PHOFF_EXEC = 0xb0        # exec PT_LOAD program header file offset
NEW_FILESZ = 0x10f6000   # extend exec seg to cover cave (page-aligned va_end 0x149e000)

# ---- AArch64 encoders (validated against this binary's own bytes) ----
def b(frm, to):   return 0x14000000 | (((to-frm) >> 2) & 0x3FFFFFF)
def bl(frm, to):  return 0x94000000 | (((to-frm) >> 2) & 0x3FFFFFF)
def cbz_x(frm, to, rt): return 0xB4000000 | ((((to-frm) >> 2) & 0x7FFFF) << 5) | rt
def adrp(frm, target, rd):
    imm = ((target & ~0xFFF) - (frm & ~0xFFF)) >> 12
    return 0x90000000 | ((imm & 3) << 29) | (((imm >> 2) & 0x7FFFF) << 5) | rd
def add_imm(rd, rn, imm): return 0x91000000 | ((imm & 0xFFF) << 10) | (rn << 5) | rd
def movz_w(rd, imm16):    return 0x52800000 | ((imm16 & 0xFFFF) << 5) | rd
def movk_w16(rd, imm16):  return 0x72A00000 | ((imm16 & 0xFFFF) << 5) | rd
def ldr_x(rt, rn, off):   return 0xF9400000 | (((off // 8) & 0xFFF) << 10) | (rn << 5) | rt
MOV_W19_WZR = 0x2A1F03F3

# ---- cave layout ----
# 17 instructions (68 bytes) + 4 pad -> data at CAVE+0x48
code_addr = CAVE
# placeholders; we know fixed sizes: 17 insns -> data starts at CAVE+68, pad to 8 -> CAVE+0x48
MAP_OFF = 0x48
REC_OFF = 0x48 + 6*8           # 0x78
MAP_VA = CAVE + MAP_OFF
REC_VA = CAVE + REC_OFF
DONE_VA = CAVE + 15*4          # idx15

A = CAVE
insns = []
def put(enc): insns.append(enc)
put(ldr_x(0, 19, 0))                       # 0  ldr x0,[x19]
put(cbz_x(CAVE+1*4, DONE_VA, 0))           # 1  cbz x0, DONE
put(adrp(CAVE+2*4, MAP_VA, 2))             # 2  adrp x2, MAP
put(add_imm(2, 2, MAP_VA & 0xFFF))         # 3  add  x2,x2,#(MAP&0xfff)
put(movz_w(1, TAG_MAP & 0xFFFF))           # 4  movz w1,#0x0013
put(movk_w16(1, (TAG_MAP >> 16) & 0xFFFF)) # 5  movk w1,#0x000c,lsl16
put(movz_w(3, 6))                          # 6  movz w3,#6
put(bl(CAVE+7*4, SET_I64))                 # 7  bl Set
put(ldr_x(0, 19, 0))                       # 8  ldr x0,[x19]
put(adrp(CAVE+9*4, REC_VA, 2))             # 9  adrp x2, REC
put(add_imm(2, 2, REC_VA & 0xFFF))         # 10 add x2,x2,#(REC&0xfff)
put(movz_w(1, TAG_REC & 0xFFFF))           # 11 movz w1,#0x0014
put(movk_w16(1, (TAG_REC >> 16) & 0xFFFF)) # 12 movk w1,#0x000c,lsl16
put(movz_w(3, 1))                          # 13 movz w3,#1
put(bl(CAVE+14*4, SET_I64))                # 14 bl Set
put(MOV_W19_WZR)                           # 15 DONE: mov w19,wzr
put(b(CAVE+16*4, DET_NEXT))                # 16 b 0x95e57c
assert len(insns) == 17

cave = bytearray()
for e in insns:
    cave += struct.pack("<I", e)
while len(cave) < MAP_OFF:
    cave += struct.pack("<I", 0xD503201F)   # NOP padding
assert len(cave) == MAP_OFF, len(cave)
cave += struct.pack("<6q", 1, 0, 0, 2, 0, 0)   # MAP
assert len(cave) == REC_OFF
cave += struct.pack("<q", 2)                    # REC
assert len(cave) == REC_OFF + 8

# ---- verify cave region in file is currently all zero ----
assert all(x == 0 for x in data[CAVE:CAVE+len(cave)]), "cave not zero!"

# ---- apply: cave, detour, phdr extend ----
data[CAVE:CAVE+len(cave)] = cave
det = struct.pack("<I", b(DET, CAVE))
orig_det = bytes(data[DET:DET+4])
assert orig_det == struct.pack("<I", MOV_W19_WZR), f"detour site not mov w19,wzr: {orig_det.hex()}"
data[DET:DET+4] = det
# extend exec segment filesz and memsz
old_filesz = struct.unpack_from("<Q", data, PHOFF_EXEC+0x20)[0]
old_memsz  = struct.unpack_from("<Q", data, PHOFF_EXEC+0x28)[0]
assert old_filesz == 0x10f52c0 and old_memsz == 0x10f52c0, (hex(old_filesz), hex(old_memsz))
struct.pack_into("<Q", data, PHOFF_EXEC+0x20, NEW_FILESZ)
struct.pack_into("<Q", data, PHOFF_EXEC+0x28, NEW_FILESZ)

open(OUT, "wb").write(data)
print("wrote", OUT, "size", len(data))
print("patched sha256:", hashlib.sha256(data).hexdigest())

# ---- self-verify with capstone ----
md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
print("\n== detour site 0x%x ==" % DET)
for i in md.disasm(bytes(data[DET:DET+4]), DET):
    print(f"  0x{i.address:x}: {i.mnemonic} {i.op_str}")
print("\n== cave 0x%x ==" % CAVE)
for i in md.disasm(bytes(data[CAVE:CAVE+MAP_OFF]), CAVE):
    print(f"  0x{i.address:x}: {i.mnemonic} {i.op_str}")
print("\n== data ==")
m = struct.unpack_from("<6q", data, CAVE+MAP_OFF)
r = struct.unpack_from("<q", data, CAVE+REC_OFF)
print("  MAP @0x%x =" % MAP_VA, m)
print("  REC @0x%x =" % REC_VA, r)
def bl_target(frm, word):
    imm = (word & 0x3FFFFFF) << 2
    if imm & 0x8000000:              # sign-extend 28-bit
        imm -= 0x10000000
    return frm + imm
print("\n== Set target check ==")
print("  BL#7 ->0x%x, BL#14 ->0x%x (want 0x%x)" % (
    bl_target(CAVE+7*4, struct.unpack_from('<I',cave,7*4)[0]),
    bl_target(CAVE+14*4, struct.unpack_from('<I',cave,14*4)[0]),
    SET_I64))
