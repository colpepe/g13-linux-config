#!/usr/bin/env bash
# Installs the patched G13 driver, profiles, and LCD monitor for the current user.
#
# Existing profiles in ~/.config/g13 are never overwritten: reinstalling after a
# driver or configurator change leaves your bindings alone. Pass --force-profiles
# to replace them with the copies in config/ (this DISCARDS local edits).
set -euo pipefail
cd "$(dirname "$0")"

FORCE_PROFILES=0
for arg in "$@"; do
    case "$arg" in
        --force-profiles) FORCE_PROFILES=1 ;;
        -h|--help)
            sed -n '2,6p' "$0" | sed 's/^# \?//'
            exit 0 ;;
        *)
            echo "unknown option: $arg (try --help)" >&2
            exit 2 ;;
    esac
done

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

if [ "$FORCE_PROFILES" = 1 ]; then
    echo "--- Installing profiles (--force-profiles: OVERWRITING bindings-0..3 and macro-0..2) ---"
    install -m 644 config/*.properties "$CFG_DIR/"
else
    echo "--- Installing profiles (keeping any that already exist) ---"
    for src in config/*.properties; do
        dest="$CFG_DIR/$(basename "$src")"
        if [ -e "$dest" ]; then
            echo "  keeping $(basename "$dest")"
        else
            install -m 644 "$src" "$dest"
            echo "  installed $(basename "$dest")"
        fi
    done
fi

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

echo "--- Installing configurator ---"
LIB_DIR="$HOME/.local/lib/g13-configurator"
mkdir -p "$LIB_DIR" "$HOME/.local/share/applications" "$CFG_DIR/templates"
rm -rf "$LIB_DIR/g13config"
cp -r configurator/g13config "$LIB_DIR/"
cat > "$BIN_DIR/g13-config" <<'EOF'
#!/usr/bin/env bash
export PYTHONPATH="$HOME/.local/lib/g13-configurator${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m g13config "$@"
EOF
chmod 755 "$BIN_DIR/g13-config"
install -m 644 g13-config.desktop "$HOME/.local/share/applications/"
cp -n config/templates/*.properties "$CFG_DIR/templates/" || true

echo "--- Starting services ---"
systemctl --user daemon-reload
systemctl --user enable --now g13.service
systemctl --user enable --now g13-monitor.service

echo "Done. Softkey 1 = Fusion 360 (orange), softkey 2 = Gaming (blue), 3/4 = Gaming clones."
