import sys, struct

path = sys.argv[1]
start = int(sys.argv[2], 16)
end = int(sys.argv[3], 16)
with open(path, "rb") as f:
    data = f.read()

SECT = {0:"COLOR_CORR",1:"CONTROL",2:"DEMOSAIC",3:"EDGE",4:"FLASH",5:"FLASH_INFO",
6:"HOT_PIXEL",7:"JPEG",8:"LENS",9:"LENS_INFO",0xA:"NOISE_RED",0xB:"QUIRKS",
0xC:"REQUEST",0xD:"SCALER",0xE:"SENSOR",0xF:"SENSOR_INFO",0x10:"SHADING",
0x11:"STATS",0x12:"STATS_INFO",0x13:"TONEMAP",0x14:"LED",0x15:"INFO",
0x16:"BLACK_LEVEL",0x17:"SYNC",0x18:"REPROCESS",0x19:"DEPTH",0x1A:"LOGICAL_MULTI",
0x1B:"DISTORTION_CORR",0x1C:"HEIC",0x1D:"HEIC_INFO",0x1E:"AUTOMOTIVE",0x1F:"AUTOMOTIVE_LENS",
0x20:"EXTENSION",0x21:"JPEGR"}

off = start
while off < end:
    v = struct.unpack_from("<I", data, off)[0]
    sec = v >> 16
    idx = v & 0xffff
    name = SECT.get(sec, f"0x{sec:x}")
    plausible = sec in SECT and idx < 0x200
    mark = "  <-- TAG" if plausible else ""
    print(f"0x{off:06x}: 0x{v:08x}  sec={name}[{idx}]{mark}")
    off += 4
