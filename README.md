# Pixel 9a — 10-bit HLG HDR video (tegu)

The Pixel 9a's camera HAL can record **10-bit HLG HDR video**; Google just doesn't expose it on the
a-series. This repo is the **method** to unlock it on a rooted 9a via a KernelSU module: grafted HLG
tuning, a patched camera HAL lib, an EdgeTPU unlock, and a companion "Camera HDR" app for the toggle.

Output is genuine **HEVC Main 10 / yuv420p10le / HLG (arib-std-b67) / BT.2020** at **4K30** —
verified on-device (`ffprobe` a sample and see for yourself).

> **No binaries here.** This repo ships only scripts and instructions. You reproduce every patch on
> files pulled from **your own** phone and OTA, so you never download Google's proprietary HAL lib,
> tuning data, or Pixel Camera app from anyone. See [`BUILD_GUIDE.md`](BUILD_GUIDE.md).

## Status

- ✅ 4K30 10-bit HLG video, rear main + ultrawide — working, verified.
- ⚠️ Build-locked. Reference build is `CP4A.261105.040.A1`; every offset and the app patch must be
  re-derived per OTA. The module refuses to install on any other build and self-disables if it
  survives an OTA.
- ❌ 4K Active stabilization — not achievable (Google caps Active at 1080p across the whole Pixel 9
  line, 9 Pro included). It's 4K+HDR *or* 1080p+Active.
- ⚠️ No dedicated 9a HDR-video white-balance tuning, so color can be slightly off.

## How it works (short version)

Runtime KernelSU bind-mounts only — nothing is written to `/vendor` or the camera APEX, so it's
reversible and can't taint an OTA:

1. Overlay the camera tuning dir with grafted HLG graphs.
2. Bind-mount a patched `liblyric_hwl.so` that advertises HLG10 and force-passes the HAL's
   stream-config validator (which otherwise rejects the 10-bit stream with `-22`).
3. Flip a vendor prop to let a re-signed camera app use the Tensor EdgeTPU (the HDR path needs it).
4. Install a patched Pixel Camera as a **separate** app so the toggle appears; stock is untouched.

Full step-by-step, including every edit and where to make it: **[`BUILD_GUIDE.md`](BUILD_GUIDE.md)**.

## Build / update for a new OTA

`BUILD_GUIDE.md` covers it end to end. In brief: pull your own camera files, graft HLG graphs from
the matching Pixel Fold OTA, re-derive and apply the two `liblyric_hwl.so` patches, re-apply the
camera-app toggle patch (re-signed with your own key), update the `EXPECT_*` build guards, and
`python -I tools/build_module.py`.

## Credits & disclaimer

Figured out and built by the repo owner, with a lot of reverse-engineering help from **Claude**
(Anthropic's AI) on the Ghidra/smali grind. Shared in case it's useful to other 9a owners.

Root-level camera-HAL tinkering — **use at your own risk**. No warranty. Everything is reversible
(disable the module and reboot), but you're responsible for your own device.

## License

Scripts and docs: see [`LICENSE`](LICENSE). This repo contains **no** Google code; see
[`NOTICE`](NOTICE).
