import sys, struct
path = sys.argv[1]
lo = int(sys.argv[2], 16)
hi = int(sys.argv[3], 16)
with open(path, "rb") as f:
    data = f.read()
n = len(data)
# scan 8-byte aligned little-endian values pointing into [lo,hi)
for off in range(0, n - 8, 8):
    v = struct.unpack_from("<Q", data, off)[0]
    if lo <= v < hi:
        print(f"ptr @0x{off:x} -> 0x{v:x}")
