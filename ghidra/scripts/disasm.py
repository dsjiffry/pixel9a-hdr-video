import sys, struct
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
path = sys.argv[1]; center = int(sys.argv[2],16); before=int(sys.argv[3]); after=int(sys.argv[4])
data=open(path,'rb').read()
# map via PT_LOAD (VA==off here but do it properly)
e_phoff=struct.unpack_from('<Q',data,0x20)[0]; e_phentsize=struct.unpack_from('<H',data,0x36)[0]; e_phnum=struct.unpack_from('<H',data,0x38)[0]
segs=[]
for i in range(e_phnum):
    b=e_phoff+i*e_phentsize
    if struct.unpack_from('<I',data,b)[0]!=1: continue
    po=struct.unpack_from('<Q',data,b+8)[0]; va=struct.unpack_from('<Q',data,b+0x10)[0]; fs=struct.unpack_from('<Q',data,b+0x20)[0]
    segs.append((po,fs,va))
def va2off(v):
    for po,fs,va in segs:
        if va<=v<va+fs: return po+(v-va)
    return None
start=(center-before)&~3
off=va2off(start)
md=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN); md.detail=False
code=data[off:off+before+after]
for insn in md.disasm(code,start):
    mark=" <===" if insn.address<=center<insn.address+insn.size else ""
    print(f"0x{insn.address:x}: {insn.mnemonic:8s} {insn.op_str}{mark}")
