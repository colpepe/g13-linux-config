# M-row Bindings and Capture UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the G13's silkscreened M1/M2/M3/MR key row as bindable in `g13-config`, make Tab and Escape capturable as bindings, and open the binding dialog already armed for key capture.

**Architecture:** All changes are confined to the `configurator/` Python package. The driver already polls and dispatches property indices 29–32; the configurator simply never mapped them. `main_window` is fully data-driven off `model.PHYS_TO_INDEX`, so adding four entries there plus four hit-rects in `overlay.KEY_RECTS` lights up labels, tooltips, the binding dialog, Apply/Revert, and templates with no further wiring. The capture fixes are local to `capture.KeyCaptureField` and `binding_dialog.BindingEditorDialog`.

**Tech Stack:** Python 3, PySide6 6.11.1, python3-evdev (name table only), pytest.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-06-m-row-and-capture-ux-design.md`. Work on branch `m-row-bindings`.
- Working directory for all commands: `~/Development/g13-linux-config/configurator`.
- Run the suite with `python -m pytest -q`. All 39 existing tests must keep passing at every commit.
- **No new runtime or test dependencies.** `pytest-qt` is NOT installed and must not be added — Qt tests use a plain `QApplication` fixture plus hand-built `QKeyEvent`s.
- Qt tests run headless via `QT_QPA_PLATFORM=offscreen`, set in `tests/conftest.py` before any Qt import.
- **`QTest.keyClick` is unusable in this codebase.** It synthesizes events with `nativeScanCode() == 0`, and `keycodes.qt_native_to_evdev()` subtracts 8, yielding `-8`. Always construct `QKeyEvent` with an explicit native scancode.
- Native scancode = evdev code + 8. Tab: scancode 23 → evdev 15. Escape: scancode 9 → evdev 1. `A`: scancode 38 → evdev 30.
- Property indices are 0-based: physical `G1`..`G22` = indices 0–21. The M row is indices 29–32.

---

### Task 1: Hardware precondition check

Confirms the G13 actually reports key bits 29–32 before any UI is built on the assumption. If this fails, **stop and report** — Tasks 2–3 are cancelled, Tasks 4–6 still proceed independently.

**Files:**
- Modify (temporarily, reverted at the end): `~/.config/g13/bindings-0.properties`

- [ ] **Step 1: Back up the live profile**

```bash
cp ~/.config/g13/bindings-0.properties /tmp/bindings-0.backup
```

- [ ] **Step 2: Append a probe binding on index 29 (M1)**

Index 29 bound to evdev code 30 = `KEY_A`.

```bash
echo 'G29=p,k.30' >> ~/.config/g13/bindings-0.properties
```

- [ ] **Step 3: Observe the driver picking up the change**

The driver live-reloads on file change. Switch to profile 0 using the top row of buttons if not already there. Open a text editor or run `cat > /dev/null` in a terminal, press the physical **M1** key (bottom row, leftmost, silkscreened "M1"), and watch for the letter `a`.

- [ ] **Step 4: Record the result and restore the backup**

```bash
cp /tmp/bindings-0.backup ~/.config/g13/bindings-0.properties
```

**Expected:** pressing M1 types `a`.

**If it does not:** the bits are dead. Report this immediately and skip Tasks 2 and 3. Do not attempt driver changes — that is out of scope for this plan and needs a fresh design discussion.

- [ ] **Step 5: No commit** (nothing tracked was modified)

---

### Task 2: Map M1–MR to property indices 29–32

**Files:**
- Modify: `configurator/g13config/model.py:49-52`
- Test: `configurator/tests/test_model.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `model.PHYS_TO_INDEX` gains keys `"M1"`, `"M2"`, `"M3"`, `"MR"` → `29, 30, 31, 32`. `model.INDEX_TO_PHYS` inverts automatically. Task 3 uses these exact four names as `overlay.KEY_RECTS` keys — they must match character-for-character, because `main_window._on_key_clicked` does `PHYS_TO_INDEX[phys]` with the overlay's rect name and would `KeyError` on a mismatch.

- [ ] **Step 1: Write the failing test**

Add to `configurator/tests/test_model.py`:

```python
def test_phys_map_m_row():
    assert model.PHYS_TO_INDEX["M1"] == 29
    assert model.PHYS_TO_INDEX["M2"] == 30
    assert model.PHYS_TO_INDEX["M3"] == 31
    assert model.PHYS_TO_INDEX["MR"] == 32
```

`test_index_to_phys_is_inverse` already iterates the whole map, so it covers the new entries with no edit.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_model.py::test_phys_map_m_row -v`
Expected: FAIL with `KeyError: 'M1'`

- [ ] **Step 3: Write minimal implementation**

In `configurator/g13config/model.py`, extend the `PHYS_TO_INDEX.update({...})` call so it reads:

```python
PHYS_TO_INDEX.update({
    "M1": 29, "M2": 30, "M3": 31, "MR": 32,
    "THUMB_LEFT": 33, "THUMB_DOWN": 34, "STICK_CLICK": 35,
    "STICK_UP": 36, "STICK_LEFT": 37, "STICK_RIGHT": 38, "STICK_DOWN": 39,
})
```

Also update the comment on line 47 to read:

```python
# Physical layout <-> 0-based property index (G1..G22 -> G0..G21 etc.)
# M1/M2/M3/MR are the silkscreened bottom row between the LCD and the keypad.
# The unlabeled top row (indices 25-28) switches profiles in the driver and is
# deliberately not mapped here.
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS, 40 passed.

- [ ] **Step 5: Commit**

```bash
git add configurator/g13config/model.py configurator/tests/test_model.py
git commit -m "model: map M1-MR to property indices 29-32"
```

---

### Task 3: Overlay hit-rects and serializer grouping for the M row

**Files:**
- Modify: `configurator/g13config/overlay.py:42-45`
- Modify: `configurator/g13config/serializer.py:8-16`
- Test: `configurator/tests/test_serializer.py`
- Test: `configurator/tests/test_overlay.py` (create)

**Interfaces:**
- Consumes: `model.PHYS_TO_INDEX` from Task 2.
- Produces: `overlay.G13OverlayWidget.KEY_RECTS` gains `"M1"`, `"M2"`, `"M3"`, `"MR"`.

- [ ] **Step 1: Write the failing tests**

Create `configurator/tests/test_overlay.py`:

```python
from g13config import model
from g13config.overlay import IMAGE_SIZE, G13OverlayWidget


def test_every_rect_name_has_a_property_index():
    for name in G13OverlayWidget.KEY_RECTS:
        assert name in model.PHYS_TO_INDEX, f"{name} has no property index"


def test_m_row_rects_exist_and_are_inside_the_photo():
    w, h = IMAGE_SIZE
    for name in ("M1", "M2", "M3", "MR"):
        rect = G13OverlayWidget.KEY_RECTS[name]
        assert rect.left() >= 0 and rect.top() >= 0
        assert rect.right() <= w and rect.bottom() <= h


def test_m_row_rects_do_not_overlap_each_other_or_g1():
    names = ["M1", "M2", "M3", "MR", "G1"]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ra, rb = G13OverlayWidget.KEY_RECTS[a], G13OverlayWidget.KEY_RECTS[b]
            assert not ra.intersects(rb), f"{a} overlaps {b}"
```

Note: `test_every_rect_name_has_a_property_index` is a regression guard for the `KeyError` in `main_window._on_key_clicked` described in Task 2's Interfaces block. It passes today and must keep passing.

Add to `configurator/tests/test_serializer.py`, and add `p.bindings[29] = model.KeyBinding([15])` to the `_profile()` helper (evdev 15 = `KEY_TAB`):

```python
def test_m_row_binding_round_trips():
    text = serialize_profile(_profile())
    assert "G29=p,k.15" in text
    assert "# M row: M1-M3, MR" in text
    reparsed = parse_profile(text, slot=1)
    assert reparsed.bindings[29] == model.KeyBinding([15])


def test_indices_22_to_28_still_preserved():
    text = serialize_profile(_profile())
    assert "G25=p,k.30" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_overlay.py tests/test_serializer.py -v`
Expected: `test_m_row_rects_exist_and_are_inside_the_photo` and `test_m_row_rects_do_not_overlap_each_other_or_g1` FAIL with `KeyError: 'M1'`; `test_m_row_binding_round_trips` FAILS on the missing `# M row` comment.

- [ ] **Step 3: Add the M-row rects**

In `configurator/g13config/overlay.py`, inside `_build_key_rects()`, immediately after the `row4` loop and before the `rects["THUMB_LEFT"]` line, insert:

```python
    # The silkscreened M1/M2/M3/MR row between the LCD and the keypad.
    # The printed bars are only ~22px tall; the hit-rect is taller so the
    # target is clickable and the label chip stays readable.
    m_y, m_w, m_h = 248, 72, 32
    m_row = {"M1": 152, "M2": 232, "M3": 320, "MR": 408}
    for name, x in m_row.items():
        rects[name] = QRect(x, m_y, m_w, m_h)
```

- [ ] **Step 4: Split the serializer's catch-all range**

In `configurator/g13config/serializer.py`, replace the single `range(22, 33)` entry in `_ROWS` with two entries, so `_ROWS` reads:

```python
_ROWS = [
    ("Row 1: physical G1-G7", range(0, 7)),
    ("Row 2: physical G8-G14", range(7, 14)),
    ("Row 3: physical G15-G19", range(14, 19)),
    ("Row 4: physical G20-G22", range(19, 22)),
    ("Indices 22-28 (no physical key; preserved verbatim)", range(22, 29)),
    ("M row: M1-M3, MR", range(29, 33)),
    ("Thumb: left, down, stick click", range(33, 36)),
    ("Stick directions: up, left, right, down", range(36, 40)),
]
```

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS, 45 passed.

- [ ] **Step 6: Verify rect alignment visually — this is required, not optional**

The coordinates in Step 3 are estimates read off the product photo and have not been checked against a render. Launch the app:

```bash
python -m g13config
```

Confirm, on the M row: the label chips sit on the printed M1/M2/M3/MR bars rather than floating above or below them; hovering each one draws the blue outline over the correct bar; clicking each opens a dialog titled `Bind M1` (etc.). Adjust `m_y`, `m_w`, `m_h`, and the four x-offsets until it lines up, then re-run `python -m pytest -q`.

- [ ] **Step 7: Commit**

```bash
git add configurator/g13config/overlay.py configurator/g13config/serializer.py \
        configurator/tests/test_overlay.py configurator/tests/test_serializer.py
git commit -m "overlay: bindable M1-MR row; serializer: group indices 29-32"
```

---

### Task 4: Qt test harness

Adds the headless `QApplication` fixture that Tasks 5 and 6 need. No production code changes.

**Files:**
- Modify: `configurator/tests/conftest.py`

**Interfaces:**
- Produces: a session-scoped `qapp` fixture returning the singleton `QApplication`, and a module-level helper `key_event(scancode, key, modifiers=Qt.NoModifier, text="")` returning a `QKeyEvent` carrying a real native scancode. Tasks 5 and 6 import the helper via `from conftest import key_event`.

- [ ] **Step 1: Write the fixture and helper**

Replace the contents of `configurator/tests/conftest.py` with:

```python
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Must be set before any Qt module is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """The one QApplication for the whole session; Qt forbids a second."""
    app = QApplication.instance() or QApplication([])
    yield app


def key_event(scancode: int, key, modifiers=Qt.NoModifier, text="") -> QKeyEvent:
    """A KeyPress carrying a real native scancode.

    QTest.keyClick cannot be used in this codebase: it leaves
    nativeScanCode() at 0, and keycodes.qt_native_to_evdev() subtracts 8,
    so every synthesized key would capture as -8. Native scancode is the
    evdev code + 8 (Tab 23 -> 15, Esc 9 -> 1, A 38 -> 30).
    """
    return QKeyEvent(QEvent.KeyPress, key, modifiers, scancode, 0, 0, text)
```

- [ ] **Step 2: Verify the existing suite still collects and passes**

Run: `python -m pytest -q`
Expected: PASS, 45 passed. (The new fixture is unused so far; this step only proves the Qt import and `sys.path` insert did not break collection.)

- [ ] **Step 3: Commit**

```bash
git add configurator/tests/conftest.py
git commit -m "tests: headless QApplication fixture and scancode key-event helper"
```

---

### Task 5: Tab and Escape are capturable

**Files:**
- Modify: `configurator/g13config/capture.py:46-73`
- Test: `configurator/tests/test_capture.py` (create)

**Interfaces:**
- Consumes: `qapp` fixture and `key_event` helper from Task 4.
- Produces: `KeyCaptureField.event()` override. `KeyCaptureField.codes` is a `list[int]` of evdev codes; `chordCaptured` emits it.

- [ ] **Step 1: Write the failing tests**

Create `configurator/tests/test_capture.py`:

```python
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QWidget

from conftest import key_event
from g13config.capture import KeyCaptureField


def _field_with_focus_chain(qapp):
    """A capture field with a sibling to tab to.

    The sibling matters: a lone widget has nowhere to move focus, so
    QWidget::event() declines to consume Tab and the bug does not
    reproduce. With a sibling, focus navigation eats Tab before
    keyPressEvent ever runs.
    """
    host = QWidget()
    field = KeyCaptureField(parent=host)
    QLineEdit(parent=host)
    host.show()
    return host, field


def test_armed_field_captures_tab(qapp):
    host, field = _field_with_focus_chain(qapp)
    field._arm()
    qapp.sendEvent(field, key_event(23, Qt.Key_Tab, text="\t"))
    assert field.codes == [15]
    assert not field._armed


def test_armed_field_captures_escape(qapp):
    host, field = _field_with_focus_chain(qapp)
    field._arm()
    qapp.sendEvent(field, key_event(9, Qt.Key_Escape))
    assert field.codes == [1]
    assert not field._armed


def test_armed_field_captures_shift_tab_as_combo(qapp):
    host, field = _field_with_focus_chain(qapp)
    field._arm()
    qapp.sendEvent(field, key_event(50, Qt.Key_Shift, Qt.ShiftModifier))
    qapp.sendEvent(field, key_event(23, Qt.Key_Backtab, Qt.ShiftModifier, "\t"))
    assert field.codes == [42, 15]
    assert not field._armed


def test_unarmed_field_ignores_tab(qapp):
    host, field = _field_with_focus_chain(qapp)
    qapp.sendEvent(field, key_event(23, Qt.Key_Tab, text="\t"))
    assert field.codes == []


def test_capture_emits_chord_signal(qapp):
    host, field = _field_with_focus_chain(qapp)
    seen = []
    field.chordCaptured.connect(seen.append)
    field._arm()
    qapp.sendEvent(field, key_event(38, Qt.Key_A, text="a"))
    assert seen == [[30]]
```

Note on `test_armed_field_captures_shift_tab_as_combo`: X11 scancode 50 is Left Shift → evdev 42, which `keycodes.is_modifier` recognizes, so it accumulates into `_held_mods` rather than finalizing.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_capture.py -v`
Expected: `test_armed_field_captures_tab` and `test_armed_field_captures_shift_tab_as_combo` FAIL (`field.codes == []` — focus navigation ate the event). `test_armed_field_captures_escape` FAILS with `codes == []` because the current `Qt.Key_Escape` branch disarms without capturing.

- [ ] **Step 3: Intercept KeyPress while armed**

In `configurator/g13config/capture.py`, add this method to `KeyCaptureField`, directly above `keyPressEvent`:

```python
    def event(self, e):
        # Qt consumes Tab/Backtab for focus navigation inside QWidget::event(),
        # so keyPressEvent is never reached for them. While armed, every key
        # belongs to the capture, so handle KeyPress before focus sees it.
        if self._armed and e.type() == QEvent.Type.KeyPress:
            self.keyPressEvent(e)
            return True
        return super().event(e)
```

Add `QEvent` to the existing `PySide6.QtCore` import so line 2 reads:

```python
from PySide6.QtCore import QEvent, Qt, Signal
```

- [ ] **Step 4: Let Escape capture as an ordinary key**

In `keyPressEvent`, delete these three lines:

```python
        if event.key() == Qt.Key_Escape:
            self._disarm()
            return
```

Escape's evdev code is 1 and it is not a modifier, so it now falls through to the capture branch. When the field is not armed, `event()` defers to `super()`, the dialog receives Escape, and `QDialog` rejects as usual.

- [ ] **Step 5: Prevent focus loss from silently cancelling a capture**

Replace `focusOutEvent` with:

```python
    def focusOutEvent(self, event):
        # Only a real focus change (clicking another widget, closing the
        # dialog) should cancel; Tab no longer reaches focus handling while
        # armed, so this can no longer fire mid-chord.
        if self._armed and event.reason() != Qt.ActiveWindowFocusReason:
            self._disarm()
        super().focusOutEvent(event)
```

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS, 50 passed.

- [ ] **Step 7: Commit**

```bash
git add configurator/g13config/capture.py configurator/tests/test_capture.py
git commit -m "capture: Tab and Escape are bindable keys"
```

---

### Task 6: Binding dialog opens armed for capture

**Files:**
- Modify: `configurator/g13config/binding_dialog.py:73-89`
- Test: `configurator/tests/test_binding_dialog.py` (create)

**Interfaces:**
- Consumes: `KeyCaptureField._arm()` / `_armed` from Task 5; `qapp` and `key_event` from Task 4.
- Produces: `BindingEditorDialog.showEvent` override. No signature changes.

- [ ] **Step 1: Write the failing tests**

Create `configurator/tests/test_binding_dialog.py`:

```python
from PySide6.QtCore import Qt

from conftest import key_event
from g13config import model
from g13config.binding_dialog import BindingEditorDialog
from g13config.macros import Macro


def _dialog(current, qapp):
    d = BindingEditorDialog("G1", current, {1: Macro(id=1, name="test")})
    d.show()
    qapp.processEvents()
    return d


def test_unbound_key_opens_on_key_radio_and_armed(qapp):
    d = _dialog(None, qapp)
    assert d.r_key.isChecked()
    assert d.capture._armed
    assert not d.pan_hold._armed
    d.close()


def test_existing_key_binding_opens_armed(qapp):
    d = _dialog(model.KeyBinding(codes=[30]), qapp)
    assert d.r_key.isChecked()
    assert d.capture._armed
    d.close()


def test_macro_binding_does_not_auto_arm(qapp):
    d = _dialog(model.MacroBinding(macro_id=1, repeats=0), qapp)
    assert d.r_macro.isChecked()
    assert not d.capture._armed
    d.close()


def test_pan_binding_does_not_auto_arm(qapp):
    d = _dialog(model.MousePanBinding(dx=5, dy=0), qapp)
    assert d.r_pan.isChecked()
    assert not d.capture._armed
    assert not d.pan_hold._armed
    d.close()


def test_escape_captures_then_second_escape_rejects(qapp):
    d = _dialog(None, qapp)
    qapp.sendEvent(d.capture, key_event(9, Qt.Key_Escape))
    assert d.capture.codes == [1]
    assert not d.capture._armed
    assert d.isVisible()

    qapp.sendEvent(d, key_event(9, Qt.Key_Escape))
    qapp.processEvents()
    assert d.result() == BindingEditorDialog.Rejected
```

Note: `test_escape_captures_then_second_escape_rejects` is the double-tap exit from the spec — the first Escape binds Escape, the second discards the dialog. `main_window._on_key_clicked` only writes a binding when `dialog.exec()` is truthy, so a rejected dialog saves nothing.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_binding_dialog.py -v`
Expected: `test_unbound_key_opens_on_key_radio_and_armed` FAILS (`r_none` is checked, not `r_key`). The three `_armed` assertions FAIL. `test_escape_captures_then_second_escape_rejects` FAILS on `d.capture.codes == [1]` if Task 5 is not yet merged.

- [ ] **Step 3: Default an unbound key to the key radio**

In `configurator/g13config/binding_dialog.py`, in `_load_current`, change the final `else` branch from:

```python
        else:
            self.r_none.setChecked(True)
```

to:

```python
        else:
            # Unbound keys open ready to bind rather than parked on "Unbound".
            self.r_key.setChecked(True)
```

`result_binding()` needs no change: `self.r_key.isChecked() and self.capture.codes` is already falsy when nothing was captured, so the method falls through and returns `None`, which `main_window` treats as "remove the binding". Choosing "Unbound" explicitly still works.

- [ ] **Step 4: Arm the capture field on show**

Add this method to `BindingEditorDialog`, directly below `__init__`:

```python
    def showEvent(self, event):
        super().showEvent(event)
        # Arm here, not in __init__: grabKeyboard() has no effect on a widget
        # that is not yet visible. Only when the dialog landed on the key radio
        # -- arming over a macro or pan binding would let a stray keypress flip
        # the selection to r_key and silently destroy the existing binding.
        if self.r_key.isChecked() and not self.capture._armed:
            self.capture._arm()
```

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS, 55 passed.

- [ ] **Step 6: Verify the real interaction by hand**

```bash
python -m g13config
```

Confirm: clicking any key on the overlay opens a dialog already reading "Press keys…"; pressing a combo captures it without clicking the field first; pressing Tab captures `Tab` instead of moving focus; pressing Escape captures `Esc`; pressing Escape a second time closes the dialog with nothing saved (the overlay label is unchanged and the window title shows no unsaved-changes marker). Then open a key that holds a macro and confirm the dialog opens on the Macro radio with nothing armed.

- [ ] **Step 7: Commit**

```bash
git add configurator/g13config/binding_dialog.py configurator/tests/test_binding_dialog.py
git commit -m "binding dialog: open armed for key capture"
```

---

### Task 7: Document the new capability in the README

**Files:**
- Modify: `README.md`

**Not** `reference/g13-reference.html`. That card documents the *actual bindings
of each profile* (`<span class="name">G20</span><span class="action">Trim (T)</span>`),
not the set of bindable keys. This plan binds nothing — it only makes the M row
bindable. Adding an M row there now would document four empty actions. The card
needs updating when the M keys are actually assigned, which is a separate change.

- [ ] **Step 1: Find the configurator section**

```bash
grep -n "g13-config\|Configurator\|configurator" README.md | head
```

- [ ] **Step 2: Add the key-coverage and capture notes**

Add to the configurator section, matching the surrounding prose style:

```markdown
### Bindable keys

All 22 `G` keys, the four **M1/M2/M3/MR** keys (the silkscreened row directly
below the LCD), the two thumb buttons, and the stick click and four stick
directions.

The unlabeled row of four thin bars *above* the M keys switches the active
profile. The driver handles those presses itself, so they cannot be bound.

### Capturing a binding

Clicking a key opens the binding dialog already listening, so you can press
your key or combo straight away — no need to click the capture field first.
Every key captures literally, including **Tab** and **Escape**.

Because Escape captures rather than closing the dialog, pressing it **twice**
is the quick way out of a key you opened by mistake: the first press binds
`Esc`, the second discards the dialog without saving.

A key already holding a macro or mouse-pan binding opens on its own tab and
does *not* start listening, so a stray keypress cannot overwrite it.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: bindable M row and capture behavior"
```

---

## Verification

- [ ] `python -m pytest -q` from `configurator/` — 55 passed, no skips.
- [ ] `git log --oneline master..m-row-bindings` shows the spec commit plus one commit per task.
- [ ] Manual hardware pass: bind M1 through the GUI, Apply, press M1, confirm it fires. This closes the loop that Task 1 opened — Task 1 proved the driver *can* see the key, this proves the whole configurator path works end to end.
