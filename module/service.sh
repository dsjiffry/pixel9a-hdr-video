#!/system/bin/sh
# Runs once per boot (KernelSU late_start service stage).
MODDIR=${0%/*}
. "$MODDIR/common.sh"

: > "$LOG"
until [ "$(getprop sys.boot_completed)" = 1 ]; do sleep 2; done
sleep 5
log "boot completed; starting"

# Hard build lock. This module is built for exactly ONE device + OS build (EXPECT_DEVICE /
# EXPECT_FP). If the running build is anything else -- most likely because an OTA updated the OS
# while the module was still enabled (user forgot to disable it first) -- do NOT touch the camera,
# and SELF-DISABLE so KernelSU skips the module from the next boot onward. Reversible: delete
# /data/adb/modules/hdr_video_tegu/disable, or reinstall a module rebuilt for the new build.
dev=$(getprop ro.product.device)
fp=$(getprop ro.build.fingerprint)
if [ "$dev" != "$EXPECT_DEVICE" ] || [ "$fp" != "$EXPECT_FP" ]; then
  log "BUILD MISMATCH: device='$dev' fp='$fp'"
  log "expected: device='$EXPECT_DEVICE' fp='$EXPECT_FP'"
  log "camera left untouched; self-disabling (likely a post-OTA boot)"
  set_status "DISABLED: wrong build $(getprop ro.build.id); camera untouched. Rebuild module for this build."
  touch "$MODDIR/disable"
  log "done (disabled)"
  exit 0
fi

if preflight; then
  activate
  install_gcam
fi
log "done"
