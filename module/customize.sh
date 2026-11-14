# KernelSU install-time script. Only checks compatibility; changes nothing on the system.
EXPECT_FP="google/tegu/tegu:17/CP4A.261105.040.A1/16581829:user/release-keys"

ui_print "- Pixel 9a HLG HDR video overlay v1.0.0"
[ "$(getprop ro.product.device)" = tegu ] || abort "! This module is only for the Pixel 9a (tegu)."
if [ "$(getprop ro.build.fingerprint)" != "$EXPECT_FP" ]; then
  abort "! Built for CP4A.261105.040.A1 only. This phone runs $(getprop ro.build.id). Rebuild the module for this build."
fi
ui_print "- Build-locked to CP4A.261105.040.A1. If a later OTA changes the build while this"
ui_print "  module is still enabled, it detects the mismatch at boot, leaves the camera"
ui_print "  untouched, and self-disables (delete the module's 'disable' file to re-enable)."
ui_print "- Nothing is written to /vendor or the camera APEX."
ui_print "- At boot it bind-mounts a RAM copy of the camera tuning folder"
ui_print "  (with the HLG graphs) AND a patched liblyric_hwl.so that"
ui_print "  advertises HLG10 in the static camera characteristics, then"
ui_print "  restarts the camera HAL."
ui_print "- At first boot it also installs a bundled patched Pixel Camera as a"
ui_print "  SEPARATE app ('Camera HDR', com.google.android.Gcam10BitHdr) that"
ui_print "  exposes the HDR video toggle. Stock Google Camera is left untouched."
ui_print "- Result: module description in KernelSU, and hdr.log in the module folder."
ui_print "- Undo: disable or remove the module and reboot, or press Action to toggle"
ui_print "  the HAL overlay. The Camera HDR app stays installed; uninstall it normally."
set_perm_recursive "$MODPATH" 0 0 0755 0644
set_perm "$MODPATH/service.sh" 0 0 0755
set_perm "$MODPATH/action.sh" 0 0 0755
