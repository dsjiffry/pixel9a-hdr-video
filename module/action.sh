#!/system/bin/sh
# KernelSU "Action" button: toggles the overlay without rebooting and prints the current status.
MODDIR=${0%/*}
. "$MODDIR/common.sh"

if is_active || lib_active; then
  echo "Overlay is ON -> turning it OFF and restarting the camera HAL..."
  deactivate
else
  echo "Overlay is OFF -> turning it ON and restarting the camera HAL..."
  preflight && activate
fi
echo
echo "---- $LOG ----"
tail -n 40 "$LOG"
