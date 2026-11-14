import sys, struct
from_path = sys.argv[1]
va = int(sys.argv[2], 16)
count = int(sys.argv[3])

# Minimal ELF PT_LOAD parse (stdlib only)
with open(from_path, "rb") as f:
    data = f.read()

assert data[:4] == b"\x7fELF"
is64 = data[4] == 2
le = data[5] == 1
end = "<" if le else ">"
e_phoff = struct.unpack_from(end+"Q", data, 0x20)[0]
e_phentsize = struct.unpack_from(end+"H", data, 0x36)[0]
e_phnum = struct.unpack_from(end+"H", data, 0x38)[0]
segs = []
for i in range(e_phnum):
    base = e_phoff + i*e_phentsize
    p_type = struct.unpack_from(end+"I", data, base)[0]
    if p_type != 1:  # PT_LOAD
        continue
    p_offset = struct.unpack_from(end+"Q", data, base+0x08)[0]
    p_vaddr  = struct.unpack_from(end+"Q", data, base+0x10)[0]
    p_filesz = struct.unpack_from(end+"Q", data, base+0x20)[0]
    p_flags  = struct.unpack_from(end+"I", data, base+0x04)[0]
    segs.append((p_offset, p_filesz, p_vaddr, p_flags))

def va_to_off(v):
    for po, fsz, vad, fl in segs:
        if vad <= v < vad + fsz:
            return po + (v - vad)
    return None

# exec ranges for classifying pointers
exec_ranges = [(vad, vad+fsz) for po,fsz,vad,fl in segs if fl & 1]
def is_code(v):
    return any(lo <= v < hi for lo,hi in exec_ranges)

off = va_to_off(va)
print(f"vtable VA {hex(va)} -> file off {hex(off)}")
for i in range(count):
    p = struct.unpack_from(end+"Q", data, off + i*8)[0]
    tag = "CODE" if is_code(p) else ""
    print(f"  [{i:2d}] @0x{va+i*8:x} = 0x{p:x}  {tag}")
