# M-row bindings and capture UX — design

Date: 2026-08-06
Status: approved

Three changes to `g13-config`, all confined to the configurator. No driver
change is required.

## Background

The G13 has two rows of buttons between the LCD and the G1 keypad:

- **Top row** — four unlabeled thin bars. Driver enum `G13_KEY_L1`..`L4`,
  property indices **25–28**. `G13::parse_key` (`driver/g13-driver/src/cpp/G13.cpp:492`)
  intercepts these to switch the active profile and `return`s before consulting
  `actions[key]`, so they cannot hold bindings. This behavior is unchanged.
- **Bottom row** — four larger keys, silkscreened **M1 / M2 / M3 / MR**. Driver
  enum `G13_KEY_M1`..`MR`, property indices **29–32**. `parse_keys()` already
  polls them and `parse_key()` already dispatches them through
  `actions[key]->set(pressed)`. The driver has always supported bindings here;
  the configurator simply never exposed the indices.

`model.PHYS_TO_INDEX` maps `G1`..`G22` to 0–21 and then jumps to the thumb keys
at 33, leaving 22–32 unmapped. `serializer._ROWS` groups 22–32 under a single
"no physical key; preserved verbatim" comment.

## 1. Bindable M1–MR

**Hardware precondition.** Source confirms the driver *would* dispatch indices
29–32, but not that the device actually *reports* those bits — the enum has
`UNDEF1`/`UNDEF3` dead bits in the same region. Before any UI work, hand-write a
binding on index 29 into a profile file, press M1, and confirm it fires. If the
bits are dead, this feature is not possible and the remaining two changes
proceed independently.

Given the precondition holds:

- `model.py` — extend `PHYS_TO_INDEX` with `M1: 29, M2: 30, M3: 31, MR: 32`.
  `INDEX_TO_PHYS` is derived by inversion and needs no edit.
- `overlay.py` — add four `KEY_RECTS` entries for the M row, in 645×1000 photo
  coordinates. Starting estimates: `y=248`, `h=32`, `w≈72`, `x ≈ 152 / 232 /
  320 / 408`. The printed bars are only ~22 px tall; the hit-rect is
  deliberately taller so the target is clickable and the label chip is
  readable, consistent with the other rows. **These coordinates are estimates
  and must be verified visually against the running app**, as the existing rows
  were.
- `serializer.py` — split `_ROWS` entry `range(22, 33)` into `range(22, 29)`
  ("Indices 22-28 (no physical key; preserved verbatim)") and `range(29, 33)`
  ("M row: M1-M3, MR"). Cosmetic only: `serialize_profile` already emits any
  index present in `p.bindings`.

Everything downstream — `labels`, tooltips, the binding dialog, Apply/Revert,
templates — is keyed off `PHYS_TO_INDEX` and needs no change.

## 2. Tab is capturable

`KeyCaptureField` never sees Tab. Two mechanisms consume it, and both must be
addressed:

- Qt handles Tab as focus navigation inside `QWidget::event()`, so
  `keyPressEvent` is never invoked for it. Override `event()` on
  `KeyCaptureField` and, **while armed**, handle `QEvent.Type.KeyPress`
  directly, before focus handling sees it.
- `focusOutEvent` (`capture.py:70`) disarms on focus loss, which would silently
  cancel the capture if a Tab did leak through.

This also covers Backtab (Shift+Tab). When not armed, focus navigation behaves
normally.

## 3. Dialog opens ready to bind; Escape is capturable

**Auto-arm.** In `BindingEditorDialog._load_current`, the `else` branch (an
unbound key) checks `r_none`; change it to check `r_key`. Additionally, arm
`self.capture` on open so the flow is: click a key on the overlay, press the
combo, OK.

Auto-arm applies **only when the dialog lands on the "Key or combo" radio** —
that is, when the current binding is `None` or a `KeyBinding`. A key already
holding a `MacroBinding` or `MousePanBinding` opens on its own radio and does
**not** auto-arm, because a stray keypress would otherwise capture a chord,
flip the selection to `r_key`, and silently destroy the existing macro or pan
binding. Only the main capture field ever auto-arms — never `self.pan_hold`.

**Escape.** Delete the `Qt.Key_Escape` special case at `capture.py:49`. Escape's
evdev code is 1 and `keycodes.qt_native_to_evdev()` already derives it from the
scancode, so it flows through as an ordinary non-modifier key: it is captured
and the field disarms. The resulting rule is:

- **Armed** → Escape is captured as the binding, field disarms.
- **Not armed** → Escape closes the dialog via the standard `QDialog` reject.

Because capturing disarms the field, pressing Escape twice binds Escape and then
discards the dialog without saving — the intended quick exit from a key clicked
by accident. No timer is involved: Escape retains its normal "close" meaning at
any later point rather than dying after a fixed window.

`done()` already disarms both capture fields, so nothing leaks a keyboard grab.

## Testing

- `model` — `PHYS_TO_INDEX` / `INDEX_TO_PHYS` round-trip for the four M keys.
- `serializer` — a profile with M-row bindings serializes under the new comment
  and survives a parse/serialize round-trip; indices 22–28 are still preserved
  verbatim.
- `capture` — armed field captures Tab, Backtab, and Escape as ordinary codes;
  an unarmed field does not swallow them.
- `binding_dialog` — opening on an unbound key selects "Key or combo" and arms
  the main capture field but not the pan-hold field; opening on a macro or
  mouse-pan binding arms neither.
- Existing golden round-trip tests against the real configs must still pass.

Manual, on hardware: the index-29 precondition check above; overlay rect
alignment and hover/tooltip behavior on the M row; Escape-Escape exits without
writing.
