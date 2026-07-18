# G13 Profiles for Fusion 360 + Gaming — Design

**Date:** 2026-07-18
**Hardware:** Logitech G13 Advanced Gameboard (046d:c21c), confirmed connected
**Base software:** https://github.com/Lordbooker/linux-g13-driver (modernized C++ fork)
**Host:** Fedora Linux, KDE Wayland; Fusion 360 runs via cryinkfly wine runtime

## Goals

1. Two switchable profiles selected with the softkeys under the LCD:
   - **Softkey 1 (L1) → Fusion 360 profile**, orange backlight
   - **Softkey 2 (L2) → Gaming profile**, blue backlight
2. Fusion profile: thumbstick orbits the view (Shift + middle-drag), the
   WASD-position keys (G4/G10/G11/G12) pan the camera, remaining keys carry
   common Fusion hotkeys.
3. Gaming profile: layout mirrors the left side of a keyboard, WASD in the
   same physical positions, stick also WASD.
4. A printable reference card showing what every key does in each profile.
5. (Nice-to-have) System statistics on the G13 LCD.

## Key facts about the stock driver

- Config: plain-text `~/.config/g13/bindings-<0-3>.properties`, live-reloaded.
  Syntax: `G<n>=p,k.<linux-keycode>` (passthrough), `G<n>=m,<macroId>,<repeats>`
  (macro from `macro-<id>.properties`, sequences of `kd.<code>,ku.<code>,d.<ms>`),
  `color=R,G,B` (per-profile backlight).
- Profile switching on keys 25–28 (the four LCD softkeys) is already built in:
  L1→bindings-0 … L4→bindings-3.
- Stick is hardcoded to STICK_KEYS mode: deflection zones act as four virtual
  keys G36 (up), G37 (left), G38 (right), G39 (down).
- **Limitation:** the uinput virtual device only enables keyboard codes 0–255.
  No `EV_REL` (cursor motion) and no mouse buttons (`BTN_LEFT`=272,
  `BTN_MIDDLE`=274 are above 255). The stock driver therefore cannot do
  Fusion orbit/pan, which are mouse-drag gestures.
- LCD accepts text via named pipe `/run/user/$UID/g13-lcd`; repo ships
  `g13_monitor.py` (CPU/RAM/time), but with a stale pipe path (`/tmp/g13-lcd`)
  that must be fixed.

## Decision: patch the driver fork

Chosen over (a) an external python-evdev helper daemon translating spare
keycodes into mouse events — extra always-running service, laggier; and
(b) keyboard-only compromise — drops the headline feature.

### Patch scope (C++ driver only; Java GUI untouched)

1. **uinput device:** enable `EV_REL` (`REL_X`, `REL_Y`) and key bits
   `BTN_LEFT`, `BTN_RIGHT`, `BTN_MIDDLE`.
2. **Per-profile stick mode** — new properties keys:
   - `stick_mode=keys|mouse` (default `keys`, preserving stock behavior)
   - `stick_speed=<int>` cursor speed scale (mouse mode)
   - `stick_hold=<code>[+<code>…]` keys/buttons held while the stick is
     deflected in mouse mode (e.g. `42+274` = LShift + BTN_MIDDLE)
   Behavior in mouse mode: on leaving the dead zone, press the hold codes,
   then emit relative motion proportional to deflection each report; on
   return to center, release the hold codes. Result: stick = Fusion orbit.
3. **New "mouse-pan" key action** — binding syntax `G<n>=mp,<dx>,<dy>[,<hold>]`:
   while the key is held, press `<hold>` (default `274` = middle button) and
   emit `(dx,dy)` relative motion on a ~10 ms timer thread; release on key-up.
   Result: G4/G10/G11/G12 = Fusion pan.
4. **Profile name on LCD:** optional `name=<text>` property per bindings file;
   on profile switch the driver writes the name to the LCD (the stats script
   overwrites it on its next tick, which is fine).

## Profile 0 — Fusion 360 (softkey 1, `color=255,80,0` orange)

- `stick_mode=mouse`, `stick_hold=42+274` (Shift+MMB) → **orbit**
- Stick click (G34) → macro: double middle-click = **fit view** (Fusion's
  native gesture)
- G4/G10/G11/G12 → `mp` pan up/left/down/right
- Thumb buttons: G32 (left thumb) = **Esc**, G33 (down thumb) = **Enter**
- Remaining keys, grouped by row (draft — exact placement finalized on the
  reference card; trivially reshufflable via the text config):

  | Row | Keys | Commands |
  |-----|------|----------|
  | 1 (G1–G3, G5–G7) | Undo (Ctrl+Z), Redo (Ctrl+Y), Delete, [G4=pan↑], Measure (I), Offset (O), Joint (J) | top-row utility |
  | 2 (G8, G9, G13, G14) | S (shortcut toolbox), E (extrude), Q (press/pull), F (fillet) | modeling |
  | 3 (G15–G19) | L (line), R (rectangle), C (circle), D (dimension), X (construction) | sketching |
  | 4 (G20–G22) | T (trim), P (project), M (move/copy) | misc |

  Multi-key commands (Undo/Redo, fit view double-MMB) are macro files;
  single letters are passthrough bindings.

## Profile 1 — Gaming (softkey 2, `color=0,80,255` blue)

`stick_mode=keys`; stick zones = WASD (same as finger cluster).

| Row | Mapping |
|-----|---------|
| 1: G1–G7 | Esc, Tab, Q, **W**, E, R, T |
| 2: G8–G14 | 1, 2, **A**, **S**, **D**, F, G |
| 3: G15–G19 | LShift, Z, X, C, V |
| 4: G20–G22 | LCtrl, B, M |
| Thumb | G32 = Space, G33 = LAlt, stick click (G34) = middle mouse (BTN_MIDDLE, now available) |
| Stick | up=W, left=A, down=S, right=D |

## LCD system stats

- Install the repo's `g13_monitor.py` with the pipe path corrected to
  `/run/user/<uid>/g13-lcd`, showing CPU %, RAM, and time.
- Run as a user systemd service (`g13-monitor.service`) alongside the
  driver's `g13.service`. Requires `python3-psutil`.

## Reference card

Printable HTML artifact: one G13 diagram per profile (orange- and
blue-themed to match the backlight), each key labeled with its action;
thumb cluster and stick included. Kept in the project repo so it can be
regenerated when bindings change.

## Project layout

`~/Development/g13-linux-config/` (this repo):
- `driver/` — clone of the fork + patch commits
- `config/` — the bindings/macro properties files, installed to `~/.config/g13/`
- `monitor/` — fixed stats script + systemd unit
- `reference/` — reference card HTML
- `install.sh` — copies configs, installs services (driver itself installed
  via the fork's `sudo make install`)

## Testing

1. Build patched driver; `evtest` on the virtual "G13" device confirms
   `EV_REL` and `BTN_MIDDLE` are advertised and emitted.
2. Hardware: softkey 1/2 switches profile, backlight goes orange/blue,
   profile name appears on LCD.
3. Fusion 360: stick orbits, WASD cluster pans, hotkeys fire, stick click
   fits view.
4. Gaming profile: keys emit expected codes (verified via `evtest`/xev).
5. Stats visible on LCD; survives driver restart and profile switches.

## Error handling

- Patch preserves stock defaults: missing new properties → stock behavior.
- Malformed `mp`/`stick_*` entries are ignored with a syslog warning
  (matches existing parser style).
- Monitor service degrades gracefully if the pipe is absent (driver not
  running) — retries each tick, matching existing script behavior.

## Out of scope

- Java config GUI changes (configs are hand-maintained text files).
- Profiles at L3/L4 softkeys: installed as verbatim clones of the gaming
  profile (placeholders, blue backlight) — no further consideration for now.
- Upstreaming the patch (possible later; keep commits clean in case).
