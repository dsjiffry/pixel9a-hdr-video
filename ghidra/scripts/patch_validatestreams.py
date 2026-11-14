# Force-pass patch for liblyric_hwl.so ValidateStreams (experimental, v0.7.4).
# Applies ON TOP of the characteristics-injection patch (the .charonly lib).
# Gate: ValidateStreams (Ghidra FUN_007d7f70, camera_device_session_hwl_impl.cc:674) rejects the
# 10-bit HDR video stream config with -22. The final per-config verdict is a tbz at Ghidra 0x7d9af4
# (file offset 0x6d9af4): `tbz w20,#0, 0x7d9c14` — w20 bit0 is the validity bool; 0 => failure
# handler (-22), 1 => success continuation at 0x7d9af8. NOP it so every config falls through to
# success. Normal configs already pass (bit0=1) so they are unaffected; only otherwise-rejected
# configs (the 10-bit video session) are forced through.
# Run: python -E -P ghidra/scripts/patch_validatestreams.py module/patch/liblyric_hwl.so.charonly module/patch/liblyric_hwl.so
import sys, hashlib
IN, OUT = sys.argv[1], sys.argv[2]
CHAR_SHA = "95ba91c8e55f280ae29e7697e551495d6efeb4a06f736541bde418e90d77b544"  # char-patched input
OFF = 0x6d9af4
d = bytearray(open(IN, "rb").read())
assert hashlib.sha256(d).hexdigest() == CHAR_SHA, "input is not the characteristics-patched lib"
assert bytes(d[OFF:OFF+4]) == bytes.fromhex("14090036"), "tbz w20 bytes not at offset"
d[OFF:OFF+4] = bytes.fromhex("1f2003d5")  # NOP
open(OUT, "wb").write(d)
print("wrote", OUT, "sha256", hashlib.sha256(d).hexdigest())
