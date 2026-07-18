#!/usr/bin/env bash
# Installs the patched G13 driver, profiles, and LCD monitor for the current user.
set -euo pipefail
cd "$(dirname "$0")"

BIN_DIR="$HOME/.local/bin"
CFG_DIR="$HOME/.config/g13"
UNIT_DIR="$HOME/.config/systemd/user"
DRIVER_SRC="driver/g13-driver"

echo "--- Building driver ---"
make -C "$DRIVER_SRC/src" build-driver

echo "--- Installing binary and monitor ---"
mkdir -p "$BIN_DIR" "$CFG_DIR" "$UNIT_DIR"
install -m 755 "$DRIVER_SRC/Linux-G13-Driver" "$BIN_DIR/linux-g13-driver"
install -m 755 monitor/g13_monitor.py "$BIN_DIR/g13_monitor.py"

echo "--- Installing profiles (overwrites bindings-0..3 and macro-0..2) ---"
install -m 644 config/*.properties "$CFG_DIR/"

echo "--- Installing systemd user units ---"
sed 's|/usr/bin/linux-g13-driver|'"$BIN_DIR"'/linux-g13-driver|' \
    "$DRIVER_SRC/src/systemd/g13.service" > "$UNIT_DIR/g13.service"
install -m 644 monitor/g13-monitor.service "$UNIT_DIR/g13-monitor.service"

echo "--- Installing udev rule ---"
if cmp -s "$DRIVER_SRC/src/udev/99-g13.rules" /etc/udev/rules.d/99-g13.rules; then
    echo "udev rule already installed, skipping."
else
    echo "(sudo required)"
    sudo cp "$DRIVER_SRC/src/udev/99-g13.rules" /etc/udev/rules.d/
    sudo udevadm control --reload-rules && sudo udevadm trigger
fi

echo "--- Starting services ---"
systemctl --user daemon-reload
systemctl --user enable --now g13.service
systemctl --user enable --now g13-monitor.service

echo "Done. Softkey 1 = Fusion 360 (orange), softkey 2 = Gaming (blue), 3/4 = Gaming clones."
