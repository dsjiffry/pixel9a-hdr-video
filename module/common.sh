# Shared logic for service.sh and action.sh. Sourced, not executed.
# Overlays the camera HAL's tuning directory with: original files + our HLG graphs + patched fallback map.
# Everything is in RAM (tmpfs) and bind-mounted; nothing on /vendor or in the APEX image is written.

APEX=/apex/com.google.pixel.camera.hal
CAMDIR=$APEX/etc/lib64/camera
OVL=/dev/hdrvideo_tegu_cam
PAYLOAD=$MODDIR/camera_hlg
HWLSO=$APEX/lib64/liblyric_hwl.so
PATCHSO=$MODDIR/patch/liblyric_hwl.so
LIBOVL=/dev/hdrvideo_tegu_lib
LOG=$MODDIR/hdr.log
MODVER=$(sed -n 's/^version=//p' "$MODDIR/module.prop")
# Bundled patched Pixel Camera, installed as a SEPARATE app (renamed package) so it coexists
# with the stock Google Camera. The app only exposes the HDR toggle; the HAL overlay above is
# what actually produces HLG10.
GCAMDIR=$MODDIR/gcam
GCAM_PKG=com.google.android.Gcam10BitHdr
GCAM_STAMP=$GCAMDIR/.installed
HAL_SVC=vendor.camera-provider-2-7-google
HAL_BIN=android.hardware.camera.provider@2.7-service-google
TOYBOX=/system/bin/toybox
# GCam's HDR-video (and ML EIS) path needs the Tensor EdgeTPU, which the edgetpu_app_service
# denies to our re-signed Camera HDR app ("not in the EdgeTPU allowed list or signature
# mismatched"). The service has a built-in escape hatch: when this vendor prop is true it grants
# EdgeTPU to any unlisted app (read fresh per request; no service restart needed). It is NOT a
# persist prop, so a reboot without this module reverts it. Tradeoff: opens EdgeTPU to all apps.
EDGETPU_PROP=vendor.edgetpu.service.allow_unlisted_app

# The payload was generated from this exact device + build. Any other: do nothing (service.sh
# self-disables on a build mismatch; preflight also re-checks before activating).
EXPECT_DEVICE=tegu
EXPECT_FP="google/tegu/tegu:17/CP4A.261105.040.A1/16581829:user/release-keys"
EXPECT_HWL=97faa97aa3ca488287392470407158dba31041c91e1818491c998fce959df028
# sha256 of our patched liblyric_hwl.so (stock + HLG10 characteristics injection + ValidateStreams
# force-pass NOP at file off 0x6d9af4, so the HAL accepts the 10-bit video stream config instead of -22).
EXPECT_PATCHED=60cc084948b206fbeb56399c860918fe733407d346f7d2a6d39b30e10b266989

log() { echo "$(date '+%F %T') $*" >> "$LOG"; }

set_status() {
  # Show the result in the KernelSU manager's module list.
  sed -i "s|^description=.*|description=[$1] Pixel 9a HLG10 HDR video overlay v1.0.0 (patched HAL lib + ValidateStreams force-pass + Camera HDR app + EdgeTPU unlock). Build CP4A.261105.040.A1 ONLY. Details: $LOG|" "$MODDIR/module.prop"
}

ctx_of() {
  c=$($TOYBOX stat -c %C "$1" 2>/dev/null)
  [ -n "$c" ] && [ "$c" != "?" ] || c=$($TOYBOX ls -Zd "$1" 2>/dev/null | awk '{print $1}')
  echo "$c"
}

is_active() { grep -q " $CAMDIR " /proc/mounts; }

preflight() {
  [ "$(getprop ro.product.device)" = tegu ] || { log "SKIP: device is $(getprop ro.product.device), not tegu"; set_status "SKIPPED: not a Pixel 9a"; return 1; }
  fp=$(getprop ro.build.fingerprint)
  [ "$fp" = "$EXPECT_FP" ] || { log "SKIP: build $fp != $EXPECT_FP"; set_status "SKIPPED: different build, rebuild module"; return 1; }
  [ -d "$CAMDIR" ] || { log "SKIP: $CAMDIR missing"; set_status "SKIPPED: camera HAL APEX not found"; return 1; }
  hwl=$(sha256sum "$APEX/lib64/liblyric_hwl.so" | cut -d' ' -f1)
  [ "$hwl" = "$EXPECT_HWL" ] || { log "SKIP: liblyric_hwl.so hash $hwl unexpected"; set_status "SKIPPED: camera HAL changed"; return 1; }
  ( cd "$PAYLOAD" && sha256sum -c SHA256SUMS >/dev/null 2>&1 ) || { log "FAIL: payload checksum mismatch"; set_status "ERROR: module files corrupted"; return 1; }
  [ -f "$PATCHSO" ] || { log "SKIP: patched lib missing"; set_status "ERROR: patched lib missing"; return 1; }
  psha=$(sha256sum "$PATCHSO" | cut -d' ' -f1)
  [ "$psha" = "$EXPECT_PATCHED" ] || { log "FAIL: patched lib hash $psha != $EXPECT_PATCHED"; set_status "ERROR: patched lib corrupted"; return 1; }
  return 0
}

restart_hal() {
  old=$(pidof $HAL_BIN)
  setprop ctl.restart $HAL_SVC
  i=0; while [ $i -lt 10 ]; do sleep 1; new=$(pidof $HAL_BIN); [ -n "$new" ] && [ "$new" != "$old" ] && break; i=$((i+1)); done
  if [ -z "$new" ] || [ "$new" = "$old" ]; then
    log "ctl.restart did not restart the HAL; killing pid $old (init respawns it)"
    [ -n "$old" ] && kill -9 $old
    i=0; while [ $i -lt 10 ]; do sleep 1; new=$(pidof $HAL_BIN); [ -n "$new" ] && [ "$new" != "$old" ] && break; i=$((i+1)); done
  fi
  log "camera HAL pid: ${old:-none} -> ${new:-none}"
  sleep 4   # let cameraserver re-enumerate the cameras
}

report() {
  # What the HAL now advertises, per camera device, straight from cameraserver.
  out=$(dumpsys media.camera 2>/dev/null)
  n=$(echo "$out" | grep -c "availableDynamicRangeProfilesMap (c0013): int64\[[1-9]")
  log "cameras advertising dynamic range profiles: $n"
  # The HAL's own count of parsed tuning graphs (HDR(n) should equal the number of HLG graphs we added).
  logcat -d -s Lyric 2>/dev/null | grep "tuning_provider_base.cc:550" | tail -1 | sed 's/.*Tuning binarypb found/HAL tuning: found/' >> "$LOG"
  echo "$out" | grep -A2 -E "availableDynamicRangeProfilesMap|recommendedTenBitDynamicRangeProfile" >> "$LOG"
  if [ "$n" -gt 0 ]; then set_status "ON: HAL advertises 10-bit on $n camera(s)"; else set_status "ON: overlay active, HAL still reports no 10-bit"; fi
}

enable_edgetpu() {
  before=$(getprop "$EDGETPU_PROP")
  setprop "$EDGETPU_PROP" true 2>>"$LOG"
  after=$(getprop "$EDGETPU_PROP")
  log "edgetpu allow_unlisted_app: '${before:-unset}' -> '${after:-unset}'"
  [ "$after" = true ] || log "WARN: could not set $EDGETPU_PROP (SELinux?); EdgeTPU stays gated for the re-signed app"
}

disable_edgetpu() {
  setprop "$EDGETPU_PROP" false 2>>"$LOG"
  log "edgetpu allow_unlisted_app set to '$(getprop "$EDGETPU_PROP")'"
}

lib_active() { grep -q " $HWLSO " /proc/mounts; }

overlay_lib() {
  # Bind our patched liblyric_hwl.so over the APEX copy (RAM-only tmpfs, relabelled to the
  # original lib's SELinux context so the camera provider may still execute it). The APEX image
  # itself is untouched; this only overlays the path in the mount namespace.
  if lib_active; then log "lib overlay already active"; return 0; fi
  lctx=$(ctx_of "$HWLSO"); lowner=$($TOYBOX stat -c %u:%g "$HWLSO"); lmode=$($TOYBOX stat -c %a "$HWLSO")
  [ -n "$lctx" ] || { log "FAIL: lib label lookup"; return 1; }
  log "lib labels: ctx=$lctx owner=$lowner mode=$lmode"
  mkdir -p "$LIBOVL"
  err=$(mount -t tmpfs -o mode=0755,size=48m tmpfs "$LIBOVL" 2>&1) || { log "FAIL: lib tmpfs: $err"; rmdir "$LIBOVL" 2>/dev/null; return 1; }
  cp "$PATCHSO" "$LIBOVL/liblyric_hwl.so" || { log "FAIL: lib copy"; umount "$LIBOVL"; rmdir "$LIBOVL" 2>/dev/null; return 1; }
  chmod "${lmode:-0644}" "$LIBOVL/liblyric_hwl.so"; chown "$lowner" "$LIBOVL/liblyric_hwl.so" 2>/dev/null
  err=$($TOYBOX chcon "$lctx" "$LIBOVL/liblyric_hwl.so" 2>&1) || { log "FAIL: lib chcon $lctx: $err"; umount "$LIBOVL"; rmdir "$LIBOVL" 2>/dev/null; return 1; }
  [ "$(ctx_of "$LIBOVL/liblyric_hwl.so")" = "$lctx" ] || { log "FAIL: lib label is $(ctx_of "$LIBOVL/liblyric_hwl.so")"; umount "$LIBOVL"; rmdir "$LIBOVL" 2>/dev/null; return 1; }
  mount -o bind "$LIBOVL/liblyric_hwl.so" "$HWLSO" || { log "FAIL: lib bind mount"; umount "$LIBOVL"; rmdir "$LIBOVL" 2>/dev/null; return 1; }
  for v in $APEX@*; do [ -f "$v/lib64/liblyric_hwl.so" ] && mount -o bind "$LIBOVL/liblyric_hwl.so" "$v/lib64/liblyric_hwl.so" && log "also bound lib $v"; done
  log "lib overlay active"
  return 0
}

remove_lib() {
  for v in $APEX@*; do grep -q " $v/lib64/liblyric_hwl.so " /proc/mounts && umount "$v/lib64/liblyric_hwl.so"; done
  lib_active && umount "$HWLSO"
  grep -q " $LIBOVL " /proc/mounts && umount "$LIBOVL"
  rmdir "$LIBOVL" 2>/dev/null
}

activate() {
  enable_edgetpu
  if is_active && lib_active; then log "overlay already active"; return 0; fi
  # (1) Tuning-graph overlay: original camera dir + our HLG graphs + patched fallback map.
  if ! is_active; then
    fctx=$(ctx_of "$CAMDIR/tegu_fallback_map.binarypb"); dctx=$(ctx_of "$CAMDIR")
    owner=$($TOYBOX stat -c %u:%g "$CAMDIR/tegu_fallback_map.binarypb")
    log "labels: dir=$dctx file=$fctx owner=$owner"
    [ -n "$fctx" ] || { log "FAIL: could not read SELinux label"; set_status "ERROR: label lookup failed"; return 1; }
    mkdir -p "$OVL"
    # Plain tmpfs, then relabel. (v0.1 used mount -o context=vendor_configs_file, which policy denies:
    # "avc: denied { associate } vendor_configs_file:filesystem". Labelling files on a tmpfs-labelled
    # superblock is allowed for every file type.)
    err=$(mount -t tmpfs -o mode=0755,size=64m tmpfs "$OVL" 2>&1) || { log "FAIL: tmpfs mount: $err"; rmdir "$OVL" 2>/dev/null; set_status "ERROR: tmpfs mount failed"; return 1; }
    cp "$CAMDIR"/* "$OVL"/ && cp "$PAYLOAD"/*.binarypb "$OVL"/ || { log "FAIL: copy"; umount "$OVL"; rmdir "$OVL" 2>/dev/null; set_status "ERROR: copy failed"; return 1; }
    chmod 0755 "$OVL"; chmod 0644 "$OVL"/*; chown "$owner" "$OVL"/* 2>/dev/null
    err=$( { $TOYBOX chcon "$dctx" "$OVL" && $TOYBOX chcon "$fctx" "$OVL"/*; } 2>&1 ) \
      || { log "FAIL: chcon dir=$dctx file=$fctx: $err"; umount "$OVL"; rmdir "$OVL" 2>/dev/null; set_status "ERROR: SELinux relabel failed"; return 1; }
    [ "$(ctx_of "$OVL")" = "$dctx" ] || { log "FAIL: overlay dir label is $(ctx_of "$OVL")"; umount "$OVL"; rmdir "$OVL" 2>/dev/null; set_status "ERROR: wrong SELinux label"; return 1; }
    [ "$(ctx_of "$OVL/tegu_fallback_map.binarypb")" = "$fctx" ] || { log "FAIL: overlay label is $(ctx_of "$OVL/tegu_fallback_map.binarypb")"; umount "$OVL"; rmdir "$OVL" 2>/dev/null; set_status "ERROR: wrong SELinux label"; return 1; }
    log "overlay: $(ls "$OVL" | wc -l) files ($(ls "$CAMDIR" | wc -l) original + our $(ls "$PAYLOAD"/*.binarypb | wc -l), fallback map replaced)"
    mount -o bind "$OVL" "$CAMDIR" || { log "FAIL: bind mount"; umount "$OVL"; rmdir "$OVL" 2>/dev/null; set_status "ERROR: bind mount failed"; return 1; }
    for v in $APEX@*; do [ -d "$v/etc/lib64/camera" ] && mount -o bind "$OVL" "$v/etc/lib64/camera" && log "also bound $v"; done
  fi
  # (2) Patched HAL library: advertises HLG10 in the static camera characteristics.
  # If it fails to apply we fall back to tuning-only (v0.3 behaviour); report() reflects the result.
  overlay_lib || log "WARN: lib overlay did not apply; continuing with tuning overlay only"
  restart_hal
  report
}

install_gcam() {
  # Install the bundled patched Pixel Camera. It uses a renamed package, so it installs cleanly
  # ALONGSIDE the stock Google Camera (no uninstall, no signature conflict). Idempotent via a
  # version stamp. The camera app only shows/requests HDR; the HAL overlay produces the 10-bit.
  [ -d "$GCAMDIR" ] || { log "gcam: no payload dir; skipping"; return 0; }
  set -- "$GCAMDIR"/*.apk
  [ -e "$1" ] || { log "gcam: no apks in payload; skipping"; return 0; }
  if [ "$(cat "$GCAM_STAMP" 2>/dev/null)" = "$MODVER" ] && pm path "$GCAM_PKG" >/dev/null 2>&1; then
    log "gcam: $GCAM_PKG ($MODVER) already installed; skipping"
    return 0
  fi
  log "gcam: installing $GCAM_PKG from $# apk(s)"
  # Create a session. Retry: at boot the package service in the KernelSU (ksu) context can
  # reject install-create until it is fully ready. Capture pm's output so failures are visible.
  sid=""
  j=0
  while [ "$j" -lt 20 ]; do
    cout=$(pm install-create -r -g 2>&1)
    sid=$(printf '%s' "$cout" | sed -n 's/.*\[\([0-9]\{1,\}\)\].*/\1/p')
    [ -n "$sid" ] && break
    j=$((j + 1))
    sleep 3
  done
  if [ -z "$sid" ]; then log "gcam: install-create failed after $j tries: $cout"; return 1; fi
  log "gcam: created session $sid"
  i=0
  for f in "$@"; do
    # With a PATH arg, pm reads the size itself; no -S needed.
    wout=$(pm install-write "$sid" "s$i" "$f" 2>&1) || {
      log "gcam: install-write failed for $(basename "$f"): $wout"
      pm install-abandon "$sid" >/dev/null 2>&1
      return 1
    }
    i=$((i + 1))
  done
  cmout=$(pm install-commit "$sid" 2>&1)
  if printf '%s' "$cmout" | grep -q Success; then
    echo "$MODVER" > "$GCAM_STAMP"
    log "gcam: installed $GCAM_PKG OK (app: Camera HDR)"
  else
    log "gcam: install-commit failed: $cmout"
    pm install-abandon "$sid" >/dev/null 2>&1
    return 1
  fi
}

deactivate() {
  disable_edgetpu
  remove_lib
  for v in $APEX@*; do grep -q " $v/etc/lib64/camera " /proc/mounts && umount "$v/etc/lib64/camera"; done
  is_active && umount "$CAMDIR"
  grep -q " $OVL " /proc/mounts && umount "$OVL"
  log "overlay removed"
  restart_hal
  set_status "OFF: overlay disabled until next boot"
}
