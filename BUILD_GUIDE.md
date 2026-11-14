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

## Re-locating the patch points on a new build (anchors, not names)

Obfuscation renames the GCam classes/methods (`htb`, `Lhrj`, `Lhqs`, …) and every `liblyric_hwl.so`
address shifts with each build, so **never reuse the symbol names or offsets from this guide** —
re-derive them from stable anchors that *don't* change between builds:

- **GCam HDR toggle:** the flag strings `camcorder.amethyst` and `camcorder.amethyst_opt`.
- **HAL validator (Step 3b):** the log string `ValidateStreams failed, camera_id:`.
- **HAL characteristics (Step 3a):** Android tag `0xC0013` (`ANDROID_REQUEST_AVAILABLE_DYNAMIC_RANGE_PROFILES_MAP`).

Minimal-token hunt — in each case it's *string → single xref → patch the function tail*, a couple of
RE calls, not a full-binary sweep:

1. **GCam toggle (Step 5):** `grep` the decoded smali for `camcorder.amethyst` → the two flag fields
   (their class is `Lhrj` here but will differ). Then find the boolean flag-evaluator that
   early-returns `true` for a small hard-coded whitelist of flag objects — it's the method the
   toggle's visibility check calls (`htb.o(Lhqs;)Z` here). Add your two fields to that whitelist.
   Match by **structure** (`sget-object` compares against each flag → a `:cond` that does
   `const/4 p0, 0x1; return p0`), never by the obfuscated name, which changes every build.
2. **HAL validator (Step 3b):** string-search `liblyric_hwl.so` for `ValidateStreams failed, camera_id:`,
   follow the one code xref to its function, and NOP the final conditional branch at the function
   tail that routes to the `-22` return (a `tbz`/`cbz` on the validity flag here). File offset =
   Ghidra vaddr − `0x100000`.
3. **HAL characteristics (Step 3a):** locate the HWL `GetCameraCharacteristics` routine — the one
   that serializes the static camera metadata (it's the function whose output you augment; no stable
   name, but it's reachable from the camera-device-session HWL vtable). Find a code cave, and detour
   it to append the `TEN_BIT` capability + a `0xC0013` map `{STANDARD, HLG10}` +
   `recommendedTenBit = HLG10`, gated to `LENS_FACING == BACK`.

An RE agent driving Ghidra headless (or an MCP reverse-engineering tool) can do each of these in 1–2
calls: pull the string, jump to its one xref, read the function tail, apply the patch. Don't
enumerate the whole binary.

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

### Where to download the inputs

Match everything to **your** phone's exact build. Download from the official sources:

- **Pixel full OTA images** (contains the camera HAL APEX → `liblyric_hwl.so` + tuning):
  <https://developers.google.com/android/ota> — grab your `tegu` build, and the **matching**
  `comet` (Pixel Fold) build for the HLG-graph donor.
- **Pixel factory images** (alternative, full image incl. vendor):
  <https://developers.google.com/android/images>
- **Pixel Camera / Google Camera APK + splits** (if you'd rather not pull it off the device):
  APKMirror — <https://www.apkmirror.com/apk/google-inc/camera/>. The reference patch in this
  guide targets **Google Camera `10.4.117`** (full versionName `10.4.117.936816638.14`,
  versionCode `69481630`) — the version that shipped on `CP4A.261105.040.A1`. Download the
  "bundle"/split download so you get `base.apk` plus all the split APKs.

> **This version tracks the OTA.** A new build may ship a newer Pixel Camera, and the smali method
> you patch (`htb.o`) can move or change between versions. For each new OTA: check the Pixel Camera
> version on your phone (`dumpsys package com.google.android.GoogleCamera | grep versionName`), grab
> that same version, and re-locate the amethyst flag whitelist before patching (see Step 5).

Pull-from-device is still the surest way to match versions; the links above are for when you
want the files without touching the phone, or to line up a specific build.

---

## 1. Get your own camera files (from the OTA, or live from the phone)

From the camera HAL APEX `com.google.pixel.camera.hal` you need:
- `lib64/liblyric_hwl.so` — the stock HAL lib (the patch target), and
- `etc/lib64/camera/` — the tuning dir (incl. `tegu_fallback_map.binarypb`),

plus the same `etc/lib64/camera/` from the matching **Fold (comet)** build (the HLG-graph donor).

**Option A — straight from the OTA/factory zip (no phone needed).** This is the easiest way to line
up an exact build, and the only way to get the Fold's files if you don't own one:
1. Unzip the download. If it's a full OTA, run `payload-dumper-go payload.bin` (or AOSP
   `payload_dumper`) to get the partition images; if the images are packed in a `super.img`, run
   `lpunpack super.img` to split out `system.img` / `system_ext.img` / `vendor.img`.
2. The camera HAL APEX sits inside one of those partitions as
   `.../apex/com.google.pixel.camera.hal.apex` (or `.capex`, a compressed APEX). Read the partition
   image (mount read-only, `debugfs`, or 7-Zip) and pull the APEX file out.
3. `deapexer extract com.google.pixel.camera.hal.apex out/` — it handles the `.capex` decompression
   and the inner `apex_payload.img`, leaving you `out/lib64/liblyric_hwl.so` and
   `out/etc/lib64/camera/`. Do this for **both** the `tegu` and the `comet` OTA.

**Option B — live from a rooted phone (quickest if you have it):**

```
adb exec-out "su -c 'cat /apex/com.google.pixel.camera.hal/lib64/liblyric_hwl.so'" > liblyric_hwl.so
adb exec-out "su -c 'tar -C /apex/com.google.pixel.camera.hal/etc/lib64 -cf - camera'" > camera.tar
```

(The Fold's `etc/lib64/camera/` almost always comes from its OTA via Option A, since you likely
don't have a Fold to pull from.)

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

Stock Pixel Camera hides the HDR-video ("amethyst") toggle on tegu. Get the Pixel Camera APK set
(`base.apk` + splits) either by pulling it from your device (`pm path com.google.android.GoogleCamera`
→ `adb pull`) or from APKMirror (<https://www.apkmirror.com/apk/google-inc/camera/> — the reference
build used Google Camera `10.4.117`, versionCode `69481630`; match whatever is on your phone).
Decode **your** `base.apk` **sources-only**:

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

## Legal / redistribution

The patches above modify Google's proprietary camera HAL lib, tuning data, and Pixel Camera app.
**This repo contains none of those binaries** and you should not redistribute yours — build from
your own device's files. The scripts and documentation here are the only thing under this repo's
license.
