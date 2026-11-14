import sys
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN

path = sys.argv[1]
# target file-offset range of the keys table (approx). We'll resolve its VA.
tbl_off_lo = int(sys.argv[2], 16)
tbl_off_hi = int(sys.argv[3], 16)

f = open(path, "rb")
elf = ELFFile(f)

segs = []
for seg in elf.iter_segments():
    if seg['p_type'] == 'PT_LOAD':
        segs.append((seg['p_offset'], seg['p_filesz'], seg['p_vaddr'], seg['p_flags']))

def off_to_va(off):
    for po, fsz, va, fl in segs:
        if po <= off < po + fsz:
            return va + (off - po)
    return None

def va_to_off(va):
    for po, fsz, vad, fl in segs:
        if vad <= va < vad + fsz:
            return po + (va - vad)
    return None

tbl_va_lo = off_to_va(tbl_off_lo)
tbl_va_hi = off_to_va(tbl_off_hi)
print(f"table VA range: {hex(tbl_va_lo)} .. {hex(tbl_va_hi)}")
page_lo = tbl_va_lo & ~0xfff
page_hi = (tbl_va_hi + 0xfff) & ~0xfff
print(f"pages: {hex(page_lo)} .. {hex(page_hi)}")

# Gather executable PT_LOAD regions
md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
md.detail = True
f.seek(0)
blob = f.read()

# Track adrp results per register, then add/ldr computing into table range.
hits = []
for po, fsz, va, fl in segs:
    if not (fl & 0x1):  # PF_X
        continue
    code = blob[po:po+fsz]
    base = va
    adrp_reg = {}  # reg -> page value
    for insn in md.disasm(code, base):
        m = insn.mnemonic
        ops = insn.op_str
        if m == 'adrp':
            try:
                parts = ops.split(', ')
                reg = parts[0]
                imm = int(parts[1], 0)
                adrp_reg[reg] = imm
            except Exception:
                pass
        elif m == 'add' and '#' in ops:
            parts = ops.split(', ')
            if len(parts) == 3:
                dst, src, imms = parts
                if src in adrp_reg and imms.startswith('#'):
                    try:
                        imm = int(imms[1:], 0)
                        addr = adrp_reg[src] + imm
                        if tbl_va_lo - 0x40 <= addr <= tbl_va_hi:
                            hits.append((insn.address, 'add', hex(addr), f"{insn.mnemonic} {insn.op_str}"))
                        adrp_reg[dst] = None
                    except Exception:
                        pass
        elif m in ('ldr',) and '[' in ops:
            # ldr Xd, [Xn, #imm]
            try:
                inside = ops.split('[',1)[1].split(']',1)[0]
                sp = inside.split(', ')
                base_reg = sp[0]
                immv = 0
                if len(sp) > 1 and sp[1].startswith('#'):
                    immv = int(sp[1][1:], 0)
                if base_reg in adrp_reg and adrp_reg[base_reg] is not None:
                    addr = adrp_reg[base_reg] + immv
                    if tbl_va_lo - 0x40 <= addr <= tbl_va_hi:
                        hits.append((insn.address, 'ldr', hex(addr), f"{insn.mnemonic} {insn.op_str}"))
            except Exception:
                pass

print(f"\n{len(hits)} references into table range:")
for addr, kind, tgt, text in hits:
    print(f"  code 0x{addr:x} [{kind}] -> {tgt}   {text}")
