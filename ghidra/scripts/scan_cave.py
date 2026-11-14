import sys, struct
path=sys.argv[1]
data=open(path,'rb').read()
e_phoff=struct.unpack_from('<Q',data,0x20)[0]; e_phentsize=struct.unpack_from('<H',data,0x36)[0]; e_phnum=struct.unpack_from('<H',data,0x38)[0]
segs=[]
for i in range(e_phnum):
    b=e_phoff+i*e_phentsize
    if struct.unpack_from('<I',data,b)[0]!=1: continue
    po=struct.unpack_from('<Q',data,b+8)[0]; va=struct.unpack_from('<Q',data,b+0x10)[0]; fs=struct.unpack_from('<Q',data,b+0x20)[0]; fl=struct.unpack_from('<I',data,b+4)[0]
    segs.append((po,fs,va,fl,b))
# exec seg
ex=[s for s in segs if s[3]&1][0]
po,fs,va,fl,phoff=ex
end=po+fs
# largest zero runs in exec seg
runs=[]
i=po; n=end
while i<n:
    if data[i]==0:
        s=i
        while i<n and data[i]==0: i+=1
        runs.append((s,i-s))
    else: i+=1
runs.sort(key=lambda r:-r[1])
print("Top zero runs in exec seg (file-off, len, va):")
for s,l in runs[:8]:
    print(f"  off=0x{s:x} len={l} va=0x{va+(s-po):x}")
# inter-segment gap after exec seg
nxt=min((s[0] for s in segs if s[0]>end), default=len(data))
gap=data[end:nxt]
nz=sum(1 for x in gap if x!=0)
print(f"\nInter-seg file gap: [0x{end:x}, 0x{nxt:x}) len={nxt-end} nonzero_bytes={nz}")
print(f"exec seg phdr file-off=0x{phoff:x}; current filesz=0x{fs:x} memsz likely same; va_end=0x{va+fs:x}")
print("first 32 bytes of gap:", gap[:32].hex())
