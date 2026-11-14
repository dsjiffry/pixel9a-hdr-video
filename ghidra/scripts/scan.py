import sys, re, struct

path = sys.argv[1]
with open(path, "rb") as f:
    data = f.read()
print(f"size={len(data)}")

# Little-endian 4-byte tag constants of interest
tags = {
    "ANDROID_REQUEST_AVAILABLE_CAPABILITIES 0xC000C": 0x000C000C,
    "ANDROID_REQUEST_AVAILABLE_DYNAMIC_RANGE_PROFILES_MAP 0xC0013": 0x000C0013,
    "ANDROID_REQUEST_AVAILABLE_COLOR_SPACE_PROFILES_MAP 0xC0014": 0x000C0014,
    "ANDROID_SCALER (section) 0xD0000": 0x000D0000,
}
for name, val in tags.items():
    pat = struct.pack("<I", val)
    offs = [m.start() for m in re.finditer(re.escape(pat), data)]
    print(f"{name}: {len(offs)} hits -> {[hex(o) for o in offs[:20]]}")

# ASCII string keyword scan
kw = [b"DynamicRange", b"dynamic_range", b"Hlg", b"HLG", b"hlg", b"TenBit", b"ten_bit",
      b"10bit", b"10-bit", b"P010", b"Hdr10", b"HDR10", b"hdr10", b"bt2020", b"BT2020",
      b"DynamicRangeProfile", b"profiles_map", b"ProfilesMap", b"HDR", b"SupportedDynamicRange"]
strings = re.findall(rb"[\x20-\x7e]{4,}", data)
seen = {}
for s in strings:
    for k in kw:
        if k in s:
            seen.setdefault(k.decode(), set()).add(s.decode(errors="replace"))
for k in kw:
    kk = k.decode()
    if kk in seen:
        vals = sorted(seen[kk])
        print(f"\n== {kk}: {len(vals)} distinct ==")
        for v in vals[:40]:
            print("   ", v)
