# G13 Linux Configuration

A complete Linux driver and toolchain for the Logitech G13 gaming keypad, with profile management, macro support, and a GUI configurator.

## Components

### Driver

Patched userspace driver (C++, vendored fork of Lordbooker/linux-g13-driver in `driver/g13-driver/`) with config live-reload. Supports:
- Four profile slots (Softkey M1–M4)
- Key bindings and key combos via `ComboPassThroughAction` (e.g. `p,k.29+46` for Ctrl+C)
- Macro execution with timing
- Stick mode (keys or mouse panning) with configurable speed
- LCD display output

Built and installed by `./install.sh`.

### Monitor

A Python daemon (`monitor/g13_monitor.py`) that displays system stats (CPU, RAM, GPU utilization/temps, clock, active profile) on the G13's LCD. Runs as a systemd user service via `g13-monitor.service`.

### Configurator

A native Qt6 GUI application (`g13-config`), installed to `~/.local/bin/` by `./install.sh`, for visually reprogramming the G13 without editing config files. Source code in `configurator/g13config/`.

**Features:**
- **Profile editor:** Modify key bindings for all four profiles via a clickable device overlay showing the physical G13 layout
- **Binding types:** simple keys, modifier combos (Ctrl+Shift+T), macros, and mouse pan directions
- **Macro editor:** Record and edit key sequences with timing, global macro pool (200 slots shared across profiles)
- **Profile settings:** name, LCD color chip, stick mode (mouse or keys), speed, and orbit hold-chord
- **Apply/Revert:** Changes accumulate in memory; Apply writes atomically to `~/.config/g13/bindings-N.properties` and `macro-N.properties` for driver live-reload; Revert discards unsaved edits
- **Templates:** Save profiles as templates, create new profiles from templates (`~/.config/g13/templates/`). Starter templates ship with the repo: blank, wasd-gaming, fusion-360
- **External change detection:** File watcher alerts if config files change on disk, preventing silent clobbers

Requires: Python 3, `python3-pyside6` (Qt6), `python3-evdev`.

#### Bindable keys

All 22 `G` keys, the four **M1/M2/M3/MR** keys (the silkscreened row directly
below the LCD), the two thumb buttons, and the stick click and four stick
directions.

The unlabeled row of four thin bars *above* the M keys switches the active
profile. The driver handles those presses itself, so they cannot be bound.

#### Capturing a binding

Clicking a key opens the binding dialog already listening, so you can press
your key or combo straight away — no need to click the capture field first.
Every key captures literally, including **Tab** and **Escape**.

Because Escape captures rather than closing the dialog, pressing it **twice**
is the quick way out of a key you opened by mistake: the first press binds
`Esc`, the second discards the dialog without saving.

A key already holding a macro or mouse-pan binding opens on its own tab and
does *not* start listening, so a stray keypress cannot overwrite it.

### Configuration

Profile files and starter templates in `config/`. Each profile slot reads from `~/.config/g13/bindings-N.properties` (where N is 0–3) and shares a global macro pool in `macro-N.properties` files. Templates are `.properties` files in `~/.config/g13/templates/`. The driver's lenient parser preserves unknown keys and skips malformed lines; the configurator parses identically and surfaces warnings.

Combo binding syntax: `p,k.<code>+<code>[+<code>...]` — keycodes pressed in listed order, released in reverse (modifiers first). Single-key syntax `p,k.<code>` remains unchanged for backward compatibility.

## Installation

```bash
./install.sh
```

This will:
1. Build the driver from source
2. Install the driver binary, monitor daemon, and udev rule
3. Copy starter profiles and templates to `~/.config/g13/`
4. Install and enable the systemd user services
5. Install the `g13-config` GUI to `~/.local/bin/`

After installation, launch the configurator from your app menu (G13 Configurator) or run `g13-config` from the terminal. The LCD softkeys M1–M4 select the active profile on the device.

## Testing

Run the configurator's unit test suite:

```bash
python3 -m pytest configurator/tests -v
```

Expected: 38 passed.
