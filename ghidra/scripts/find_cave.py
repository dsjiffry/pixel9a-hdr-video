import sys, struct
path=sys.argv[1]
data=open(path,'rb').read()
e_phoff=struct.unpack_from('<Q',data,0x20)[0]; e_phentsize=struct.unpack_from('<H',data,0x36)[0]; e_phnum=struct.unpack_from('<H',data,0x38)[0]
print("PT_LOAD segments:")
exec_segs=[]
for i in range(e_phnum):
    b=e_phoff+i*e_phentsize
    if struct.unpack_from('<I',data,b)[0]!=1: continue
    po=struct.unpack_from('<Q',data,b+8)[0]; va=struct.unpack_from('<Q',data,b+0x10)[0]; fs=struct.unpack_from('<Q',data,b+0x20)[0]; ms=struct.unpack_from('<Q',data,b+0x28)[0]; fl=struct.unpack_from('<I',data,b+4)[0]
    print(f"  off=0x{po:x} va=0x{va:x} filesz=0x{fs:x} memsz=0x{ms:x} flags={fl}{' X' if fl&1 else ''}")
    if fl&1: exec_segs.append((po,fs,va,ms))
# find zero/padding runs at tail of each exec seg
for po,fs,va,ms in exec_segs:
    end=po+fs
    # scan backward from end for a run of 0x00
    i=end
    while i>po and data[i-1]==0: i-=1
    run=end-i
    print(f"\nExec seg end file-off=0x{end:x} (va=0x{va+fs:x}); trailing-zero run = {run} bytes starting at off 0x{i:x} (va 0x{va+(i-po):x})")
    # also show the longest zero run anywhere in last 0x2000 bytes
    region=data[end-0x4000:end]
    best=0;bi=0;cur=0;cs=0
    for j,byv in enumerate(region):
        if byv==0:
            if cur==0: cs=j
            cur+=1
            if cur>best: best=cur;bi=cs
        else: cur=0
    print(f"  longest zero run in last 0x4000 of seg: {best} bytes at file-off 0x{end-0x4000+bi:x} (va 0x{va+(end-0x4000+bi-po):x})")
