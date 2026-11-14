# Build Guide — 10-bit HLG HDR video on the Pixel 9a (tegu)

This guide describes **what to change and where** to unlock 10-bit HLG HDR video on a rooted
Pixel 9a. It ships **no Google binaries** — you reproduce every patch on files pulled from **your
own** phone and OTA, so you only ever run code that was already on your device.

It's written to be followed step-by-step, including by an AI coding agent (I built the original
with a lot of help from Claude on the Ghidra/smali work — the per-build offset hunting especially
is something an agent is good at).

> **Build-specific.** Every address/offset below, and the camera-app patch, must be re-derived for
> your exact build. The reference numbers in this guide are from `CP4A.261105.040.A1` (Nov 2026)
> and will not match other builds. Treat them as "what to look for", not constants.

---

## 0. What you need

- Pixel 9a (**tegu**), KernelSU (root via `su`).
- Your current **9a OTA/factory zip** (or the ability to pull `/apex` live).
- The matching **Pixel Fold (comet) OTA** of the *same build* — it's the donor for the HLG tuning
  graphs the a-series ships but doesn't wire up. AOSP OTA URL pattern:
  `https://dl.google.com/dl/android/aosp/comet-ota-<buildid>-<hash>.zip`.
- Tools: `apktool` (2.12+), Android `build-tools` (`zipalign`, `apksigner`), Ghidra (for the HAL
  lib), Python 3 with `capstone` + `pyelftools`, `ffmpeg`/`ffprobe` to verify.
- Your own code-signing keystore (you will re-sign the camera app with it — never redistribute the
  signed result).

The helper scripts referenced below are in this repo (`tools/`, `ghidra/scripts/`, `module/`).

---

## 1. Pull your own camera files

From your 9a: the camera HAL APEX `com.google.pixel.camera.hal` →
- `etc/lib64/camera/` (tuning dir, incl. `tegu_fallback_map.binarypb`)
- `lib64/liblyric_hwl.so` (stock HAL lib — the patch target)

From the matching Fold OTA: extract its `etc/lib64/camera/` (HLG graph donor).

## 2. Graft the HLG tuning graphs

The 9a ships HLG **AE** tuning but is missing the per-sensor `*_bt2020_hlg` graphs, the HLG
fallback-map entries, and a third-party HLG viewfinder use-case that the Fold has. `tools/gen_hlg.py`
grafts the 9a-equivalent graphs from the Fold's dir and rewrites the fallback map:

```
python -I tools/gen_hlg.py <your 9a camera dir> <Fold camera dir> <out dir>
```

The output `.binarypb` graphs + patched fallback map become the module's `camera_hlg/` payload.
(`tools/pbedit.py`, `fbmap.py`, `deeprt.py`, `headers.py` are the protobuf helpers it uses.)

## 3. Patch `liblyric_hwl.so` (two edits)

This is the hard part. Load **your** stock `liblyric_hwl.so` in Ghidra. Two patches:

**(a) Advertise HLG10 in the static characteristics.**
The HAL builds the per-model camera characteristics in code (there's no editable data file). Find
the HWL `GetCameraCharacteristics` path (it fills the GCH metadata via a
`ConvertMetadataFromLyricToGch`-style serializer). Inject, for `LENS_FACING == BACK` only:
- `DYNAMIC_RANGE_TEN_BIT` into the available-capabilities list,
- the dynamic-range-profiles map (Android tag `0xC0013`) populated with `STANDARD` + `HLG10`,
- `recommendedTenBitDynamicRangeProfile = HLG10`.

`tools/build_patch.py` implements this as a code-cave detour (it finds a cave, writes the metadata
`Set` calls, and jumps back). You re-derive the addresses for your build; the script prints the new
patched-lib sha256.

**(b) Force-pass the stream-config validator.**
Even once HLG10 is advertised, the HAL's `ValidateStreams` rejects the 10-bit video stream config
with `-22`. Find it via the log string `"ValidateStreams failed, camera_id:"` (it's referenced from
`camera_device_session_hwl_impl.cc`). Locate the **final per-config verdict branch** — in the
reference build it was a `tbz w20, #0, <fail>` where `w20` bit0 is the validity flag (0 → the −22
handler). NOP that branch so otherwise-rejected configs fall through to success. Valid configs
already pass, so they're unaffected. `ghidra/scripts/patch_validatestreams.py` reproduces this.

> **Offset mapping for this lib:** file offset = Ghidra virtual address − `0x100000` (confirmed
> empirically). Re-confirm for your build.

Apply (a) then (b) on the same lib. Put the final patched `liblyric_hwl.so` in the module's
`patch/` dir and set `EXPECT_HWL` (stock sha256) and `EXPECT_PATCHED` (patched sha256) in
`module/common.sh`.

## 4. Unlock the EdgeTPU (no cert patching)

GCam's HDR-video path hard-requires the Tensor EdgeTPU, and a **re-signed** camera app gets denied
by `edgetpu_app_service`. That service has a built-in escape hatch: `IsCurrentAppAllowed` reads
`GetBoolProperty("vendor.edgetpu.service.allow_unlisted_app", false)` and, if true, allows any
unlisted app (read fresh per request — no restart). The module sets this prop at boot and clears it
on disable. It's a non-persist vendor prop, so it reverts on a reboot without the module.
Trade-off: while enabled it opens EdgeTPU to any app.

## 5. Patch the Pixel Camera app (show the HDR-video toggle)

Stock Pixel Camera hides the HDR-video ("amethyst") toggle on tegu. Decode **your** Pixel Camera
`base.apk` **sources-only**:

```
apktool d -r base.apk -o base_src
```

Find the phenotype-flag evaluator `htb.o(Lhqs;)Z` (in `smali_classes2/htb.smali` in the reference
build). It early-returns `true` for a small whitelist of flags (jump to a `:cond_4` that does
`const/4 p0, 0x1; return p0`). Add the two HDR flags to that whitelist, before the map lookup —
each as the two lines:

```
sget-object v0, L<flag-field>:Lhqs;
if-eq p1, v0, :cond_4
```

for the fields that hold:
- `camcorder.amethyst`
- `camcorder.amethyst_opt`

(Those two lines per flag are the only edit; you're adding your own instructions, not copying
Google's.) Then:

```
apktool b base_src -o base_patched.apk
zipalign -f -p 4 base_patched.apk base_aligned.apk
apksigner sign --ks <your.keystore> --ks-key-alias <alias> base_aligned.apk
```

Re-sign **every** apk (base + all splits) with the **same** key — they must share package name,
signer, and versionCode. Install as a separate package (rename the package in the manifest if you
want it to coexist with stock). **Sign with your own key; don't redistribute the signed apk.**

## 6. Package the KernelSU module

The `module/` scripts (`common.sh`, `service.sh`, `action.sh`, `customize.sh`, `module.prop`) do
everything at runtime with tmpfs bind-mounts — **nothing is written to `/vendor` or the APEX
image**, so it's fully reversible and can't taint an OTA:
- overlay the tuning dir (original files + your HLG graphs + patched fallback map),
- bind-mount your patched `liblyric_hwl.so` over the APEX copy (relabelled with `chcon` to the
  original SELinux context so the HAL may still exec it),
- restart the camera HAL, set the EdgeTPU prop, install your patched camera app.

**Build lock (do this):** set `EXPECT_FP` in both `module/common.sh` and `module/customize.sh` to
your build's `ro.build.fingerprint`. `customize.sh` aborts the flash on any other build;
`service.sh` detects a post-OTA mismatch at boot, leaves the camera untouched, and self-disables
(`touch $MODDIR/disable`). Build the zip:

```
python -I tools/build_module.py
```

## 7. Verify

Record a clip and check it:

```
ffprobe -hide_banner your_clip.mp4
```

Expect: `hevc (Main 10)`, `yuv420p10le`, `color_transfer=arib-std-b67` (HLG), `bt2020`.

---

## Limits (known, not bugs)

- **Color:** the 9a has no dedicated HDR-video auto-white-balance tuning (that ships compiled into
  the Fold's libs only), so HDR color can be slightly off.
- **Lenses/modes:** rear main + ultrawide only; no front camera, no 24fps HLG.
- **4K Active stabilization is not achievable** — and not because of this mod. Google limits
  "Active" stabilization to 1080p across the entire Pixel 9 line (the 9 Pro included; see the
  official spec pages). 4K gets Standard/Locked, same as stock. So it's 4K+HDR *or* 1080p+Active,
  not both.

## Legal / redistribution

The patches above modify Google's proprietary camera HAL lib, tuning data, and Pixel Camera app.
**This repo contains none of those binaries** and you should not redistribute yours — build from
your own device's files. The scripts and documentation here are the only thing under this repo's
license.
