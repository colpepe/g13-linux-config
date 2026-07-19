# G13 Configurator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A PySide6 desktop app (`g13-config`) that reprograms the G13 via a clickable device overlay — key/combo capture, macro editor, templates/cloning, stick & profile settings — plus a small driver patch adding combo passthrough.

**Architecture:** The tool reads/writes `~/.config/g13/bindings-N.properties` and `macro-N.properties` (the driver's existing format) — files are the single source of truth, no IPC; the driver live-reloads on write. Pure-Python model/parser/serializer layer (fully unit-tested, no Qt) under a Qt widgets layer (overlay, dialogs, main window). Driver gains `ComboPassThroughAction` for `p,k.29+46` bindings.

**Tech Stack:** Python 3 + PySide6 (Fedora `python3-pyside6`), `python3-evdev` (keycode name table only), pytest. C++ driver patch built with the existing CMake setup.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-19-config-tool-design.md`.
- Repo: `~/Development/g13-linux-config`; all paths below relative to repo root. Work on `master` (solo repo, no PR flow) — commit after every task.
- Property key indices are 0-based: physical G1–G22 = properties `G0`–`G21`; thumb-left = `G33`, thumb-down = `G34`, stick click = `G35`, stick dirs `G36`=up `G37`=left `G38`=right `G39`=down (verified against `G13.cpp:410-422` and the WASD gaming profile). The UI must only ever show physical names.
- The driver parses leniently and skips bad lines (`G13.cpp parse_bindings_from_stream`); the tool must parse at least as leniently but surface warnings.
- Writes to `~/.config/g13/` must be atomic (temp file + `os.replace`) — the driver live-reloads on file change.
- The driver ignores SIGTERM; restart during hardware verification with `pkill -9 -f linux-g13-driver && systemctl --user restart g13`.
- Combo binding syntax: `p,k.<code>+<code>[+<code>...]` — key-down in listed order, key-up in reverse. Single-key `p,k.<code>` must keep parsing exactly as today.
- No pip installs — Fedora repo packages only (`sudo dnf install python3-pyside6 python3-evdev python3-pytest`).
- Run all Python tests from repo root: `python3 -m pytest configurator/tests -v`.

## File Structure

```
driver/g13-driver/src/cpp/ComboPassThroughAction.{h,cpp}   # new action (CMake GLOBs cpp/*.cpp — no build change)
driver/g13-driver/src/cpp/G13.cpp                          # parser: combo branch in "p" handling
configurator/
  g13config/
    __init__.py
    __main__.py          # python3 -m g13config
    keycodes.py          # evdev code<->name, pretty labels, Qt scancode conversion
    model.py             # Binding types, StickSettings, Profile, physical-key map
    parser.py            # properties text -> Profile (lenient + warnings)
    serializer.py        # Profile -> properties text; atomic_write()
    macros.py            # Macro model + sequence parse/serialize
    store.py             # ConfigStore: load/save profiles+macros, templates
    labels.py            # Binding -> short keycap label ("Ctrl+C", "Pan ←", "M: Undo")
    overlay.py           # G13OverlayWidget (painted, hit-tested)
    capture.py           # KeyCaptureField (chord capture widget)
    binding_dialog.py    # BindingEditorDialog
    settings_panel.py    # ProfileSettingsPanel
    macro_editor.py      # MacroEditorDialog (+ record mode)
    main_window.py       # MainWindow: tabs, toolbar, dirty/apply/revert, watcher, templates
  tests/
    test_keycodes.py  test_model.py  test_parser.py  test_serializer.py
    test_macros.py  test_store.py  test_labels.py
config/templates/{blank,wasd-gaming,fusion-360}.properties  # starter templates
g13-config.desktop
install.sh             # + configurator install
```

---

### Task 1: Driver combo passthrough

**Files:**
- Create: `driver/g13-driver/src/cpp/ComboPassThroughAction.h`
- Create: `driver/g13-driver/src/cpp/ComboPassThroughAction.cpp`
- Modify: `driver/g13-driver/src/cpp/G13.cpp` (the `type == "p"` branch, currently lines 208–218)

**Interfaces:**
- Consumes: `parse_plus_list(const std::string&)` from `MouseMoveAction.h` (already included by G13.cpp for `stick_hold`), `UInput::send_event` from `Output.h`, base class `G13Action`.
- Produces: bindings file syntax `p,k.29+46` accepted by the driver. No Python-side interface.

There is no C++ test harness in this repo; verification is compile + hardware check (Task 15).

- [ ] **Step 1: Create the action class header**

```cpp
// driver/g13-driver/src/cpp/ComboPassThroughAction.h
#ifndef __COMBO_PASS_THROUGH_ACTION_H__
#define __COMBO_PASS_THROUGH_ACTION_H__

#include <vector>
#include "G13Action.h"

/**
 * @class ComboPassThroughAction
 * @brief Passthrough for a key combo (e.g. Ctrl+C). While the G-key is held,
 * every code in the list is held down (pressed in listed order, released in
 * reverse), so key repeat behaves like holding the real chord.
 */
class ComboPassThroughAction : public G13Action {
private:
	std::vector<int> keycodes;

protected:
	void key_down() override;
	void key_up() override;

public:
	ComboPassThroughAction(const std::vector<int>& codes);
	virtual ~ComboPassThroughAction();
};

#endif
```

- [ ] **Step 2: Create the implementation**

```cpp
// driver/g13-driver/src/cpp/ComboPassThroughAction.cpp
#include <linux/uinput.h>

#include "ComboPassThroughAction.h"
#include "Output.h"

ComboPassThroughAction::ComboPassThroughAction(const std::vector<int>& codes) {
	this->keycodes = codes;
}

ComboPassThroughAction::~ComboPassThroughAction() {
}

void ComboPassThroughAction::key_down() {
	// Press in listed order (modifiers are written first in the binding).
	for (int code : this->keycodes) {
		UInput::send_event(EV_KEY, code, 1);
		UInput::send_event(0, 0, 0); // SYN_REPORT
	}
}

void ComboPassThroughAction::key_up() {
	// Release in reverse order so modifiers come up last.
	for (auto it = this->keycodes.rbegin(); it != this->keycodes.rend(); ++it) {
		UInput::send_event(EV_KEY, *it, 0);
		UInput::send_event(0, 0, 0); // SYN_REPORT
	}
}
```

- [ ] **Step 3: Wire the parser**

In `G13.cpp`, add the include next to the other action includes at the top of the file:

```cpp
#include "ComboPassThroughAction.h"
```

Replace the body of the `type == "p"` branch in `parse_bindings_from_stream` (currently):

```cpp
                if (type == "p") { 
                    std::string keytype_str;
                    if (!std::getline(ss, keytype_str, ',')) continue;
                    keytype_str = trim_string(keytype_str);
                    if (keytype_str.rfind("k.", 0) == 0) {
                        int keycode = std::stoi(keytype_str.substr(2));
                        if (gKey >= 0 && gKey < G13_NUM_KEYS) {
                             actions[gKey] = std::make_unique<PassThroughAction>(keycode);
                        }
                    }
                }
```

with:

```cpp
                if (type == "p") { 
                    std::string keytype_str;
                    if (!std::getline(ss, keytype_str, ',')) continue;
                    keytype_str = trim_string(keytype_str);
                    if (keytype_str.rfind("k.", 0) == 0) {
                        std::string codes_str = keytype_str.substr(2);
                        if (gKey < 0 || gKey >= G13_NUM_KEYS) continue;
                        if (codes_str.find('+') != std::string::npos) {
                            std::vector<int> codes = parse_plus_list(codes_str);
                            if (codes.size() > 1) {
                                actions[gKey] = std::make_unique<ComboPassThroughAction>(codes);
                            } else if (codes.size() == 1) {
                                actions[gKey] = std::make_unique<PassThroughAction>(codes[0]);
                            }
                        } else {
                            actions[gKey] = std::make_unique<PassThroughAction>(std::stoi(codes_str));
                        }
                    }
                }
```

- [ ] **Step 4: Build**

Run: `make -C driver/g13-driver/src build-driver`
Expected: clean compile, binary refreshed at `driver/g13-driver/Linux-G13-Driver`.

- [ ] **Step 5: Regression-check existing configs still load**

Run: `install -m 755 driver/g13-driver/Linux-G13-Driver ~/.local/bin/linux-g13-driver && pkill -9 -f linux-g13-driver; systemctl --user restart g13 && sleep 2 && journalctl --user -u g13 -n 10 --no-pager`
Expected: driver starts, no parse warnings beyond what it printed before; existing profiles work (LCD shows profile name).

- [ ] **Step 6: Commit**

```bash
git add driver/g13-driver/src/cpp/ComboPassThroughAction.h driver/g13-driver/src/cpp/ComboPassThroughAction.cpp driver/g13-driver/src/cpp/G13.cpp
git commit -m "driver: combo passthrough bindings (p,k.29+46) via ComboPassThroughAction"
```

---

### Task 2: Tooling deps, package scaffold, keycodes module

**Files:**
- Create: `configurator/g13config/__init__.py` (empty)
- Create: `configurator/g13config/keycodes.py`
- Test: `configurator/tests/test_keycodes.py`

**Interfaces:**
- Produces: `name_for(code:int)->str` ("KEY_A" style, falls back to "KEY_<n>"), `label_for(code:int)->str` (pretty: "A", "Ctrl", "Super"), `code_for_name(name:str)->int|None`, `search(text:str)->list[tuple[int,str]]`, `is_modifier(code:int)->bool`, `qt_native_to_evdev(scancode:int)->int`, `MODIFIER_ORDER:list[int]`.

- [ ] **Step 1: Install dependencies**

Run: `sudo dnf install -y python3-pyside6 python3-evdev python3-pytest`
Expected: packages installed; `python3 -c "import PySide6, evdev, pytest"` exits 0.

- [ ] **Step 2: Write the failing tests**

```python
# configurator/tests/test_keycodes.py
from g13config import keycodes


def test_name_for_known_code():
    assert keycodes.name_for(30) == "KEY_A"
    assert keycodes.name_for(29) == "KEY_LEFTCTRL"


def test_name_for_unknown_code_falls_back():
    assert keycodes.name_for(9999) == "KEY_9999"


def test_label_for_pretty_names():
    assert keycodes.label_for(30) == "A"
    assert keycodes.label_for(29) == "Ctrl"
    assert keycodes.label_for(125) == "Super"
    assert keycodes.label_for(42) == "Shift"
    assert keycodes.label_for(111) == "Del"


def test_code_for_name():
    assert keycodes.code_for_name("KEY_A") == 30
    assert keycodes.code_for_name("NOPE") is None


def test_search_matches_substring_case_insensitive():
    results = keycodes.search("volume")
    codes = [c for c, _ in results]
    assert 114 in codes and 115 in codes  # VOLUMEDOWN, VOLUMEUP


def test_is_modifier():
    assert keycodes.is_modifier(29)      # LEFTCTRL
    assert keycodes.is_modifier(54)      # RIGHTSHIFT
    assert not keycodes.is_modifier(30)  # A


def test_qt_native_to_evdev_subtracts_xkb_offset():
    # xkb keycode = evdev + 8 on both X11 and Wayland
    assert keycodes.qt_native_to_evdev(38) == 30  # A
```

Add `configurator/tests/conftest.py` so tests import the package without installing:

```python
# configurator/tests/conftest.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m pytest configurator/tests/test_keycodes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'g13config.keycodes'`.

- [ ] **Step 4: Implement keycodes.py**

```python
# configurator/g13config/keycodes.py
"""Linux evdev keycode names, display labels, and Qt scancode conversion.

Uses python3-evdev purely as a name table (no device access).
"""
from evdev import ecodes

# code -> canonical KEY_* name (ecodes.KEY maps some codes to a list of aliases)
_NAMES: dict[int, str] = {}
for code, name in ecodes.KEY.items():
    _NAMES[code] = name[0] if isinstance(name, list) else name

_CODES: dict[str, int] = {}
for code, name in ecodes.KEY.items():
    for n in name if isinstance(name, list) else [name]:
        _CODES[n] = code

# Modifiers in canonical chord order: Ctrl, Super, Alt, Shift (left/right pairs)
MODIFIER_ORDER = [29, 97, 125, 126, 56, 100, 42, 54]
_MODIFIERS = set(MODIFIER_ORDER)

_PRETTY = {
    29: "Ctrl", 97: "Ctrl", 42: "Shift", 54: "Shift",
    56: "Alt", 100: "AltGr", 125: "Super", 126: "Super",
    1: "Esc", 28: "Enter", 57: "Space", 14: "Bksp", 15: "Tab",
    111: "Del", 110: "Ins", 102: "Home", 107: "End",
    104: "PgUp", 109: "PgDn",
    103: "↑", 108: "↓", 105: "←", 106: "→",
    58: "Caps", 274: "MMB", 272: "LMB", 273: "RMB",
}


def name_for(code: int) -> str:
    return _NAMES.get(code, f"KEY_{code}")


def code_for_name(name: str) -> int | None:
    return _CODES.get(name)


def label_for(code: int) -> str:
    if code in _PRETTY:
        return _PRETTY[code]
    name = name_for(code)
    short = name.removeprefix("KEY_")
    return short.capitalize() if len(short) > 1 else short


def search(text: str) -> list[tuple[int, str]]:
    """All (code, name) pairs whose KEY_* name contains text, case-insensitive."""
    needle = text.upper()
    hits = [(c, n) for c, n in _NAMES.items() if needle in n]
    return sorted(hits)


def is_modifier(code: int) -> bool:
    return code in _MODIFIERS


def qt_native_to_evdev(scancode: int) -> int:
    """QKeyEvent.nativeScanCode() is an xkb keycode = evdev code + 8."""
    return scancode - 8
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest configurator/tests/test_keycodes.py -v`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add configurator/g13config/__init__.py configurator/g13config/keycodes.py configurator/tests/test_keycodes.py configurator/tests/conftest.py
git commit -m "configurator: package scaffold + evdev keycode tables"
```

---

### Task 3: Data model and physical key map

**Files:**
- Create: `configurator/g13config/model.py`
- Test: `configurator/tests/test_model.py`

**Interfaces:**
- Produces (used by every later task):

```python
@dataclass KeyBinding:      codes: list[int]                      # len>=1; len>1 == combo
@dataclass MacroBinding:    macro_id: int; repeats: int = 0
@dataclass MousePanBinding: dx: int; dy: int; hold: list[int] | None = None
Binding = KeyBinding | MacroBinding | MousePanBinding             # dict value; absent key == unbound
@dataclass StickSettings:   mode: str = "keys"; speed: int = 8; hold: list[int] = field(...)
@dataclass Profile:         slot: int; name: str = ""; color: tuple[int,int,int] = (255,255,255)
                            stick: StickSettings; bindings: dict[int, Binding]
                            unknown_lines: list[str]; warnings: list[str]
PHYS_TO_INDEX: dict[str, int]   # "G1".."G22", "THUMB_LEFT", "THUMB_DOWN", "STICK_CLICK",
                                # "STICK_UP", "STICK_LEFT", "STICK_RIGHT", "STICK_DOWN"
INDEX_TO_PHYS: dict[int, str]
```

- [ ] **Step 1: Write the failing tests**

```python
# configurator/tests/test_model.py
from g13config import model


def test_phys_map_g_keys_are_zero_based():
    assert model.PHYS_TO_INDEX["G1"] == 0
    assert model.PHYS_TO_INDEX["G22"] == 21


def test_phys_map_thumb_and_stick():
    assert model.PHYS_TO_INDEX["THUMB_LEFT"] == 33
    assert model.PHYS_TO_INDEX["THUMB_DOWN"] == 34
    assert model.PHYS_TO_INDEX["STICK_CLICK"] == 35
    assert model.PHYS_TO_INDEX["STICK_UP"] == 36
    assert model.PHYS_TO_INDEX["STICK_LEFT"] == 37
    assert model.PHYS_TO_INDEX["STICK_RIGHT"] == 38
    assert model.PHYS_TO_INDEX["STICK_DOWN"] == 39


def test_index_to_phys_is_inverse():
    for name, idx in model.PHYS_TO_INDEX.items():
        assert model.INDEX_TO_PHYS[idx] == name


def test_key_binding_is_combo():
    assert not model.KeyBinding([30]).is_combo()
    assert model.KeyBinding([29, 46]).is_combo()


def test_profile_defaults():
    p = model.Profile(slot=2)
    assert p.name == ""
    assert p.stick.mode == "keys"
    assert p.bindings == {}
    assert p.warnings == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest configurator/tests/test_model.py -v`
Expected: FAIL — no module `g13config.model`.

- [ ] **Step 3: Implement model.py**

```python
# configurator/g13config/model.py
"""In-memory model of a G13 profile. Files remain the source of truth."""
from dataclasses import dataclass, field


@dataclass
class KeyBinding:
    codes: list[int]  # evdev codes; modifiers first. len > 1 == combo (p,k.a+b)

    def is_combo(self) -> bool:
        return len(self.codes) > 1


@dataclass
class MacroBinding:
    macro_id: int
    repeats: int = 0


@dataclass
class MousePanBinding:
    dx: int
    dy: int
    hold: list[int] | None = None  # None == driver default (MMB)


Binding = KeyBinding | MacroBinding | MousePanBinding


@dataclass
class StickSettings:
    mode: str = "keys"  # "mouse" | "keys"
    speed: int = 8
    hold: list[int] = field(default_factory=list)  # orbit hold chord (mouse mode)


@dataclass
class Profile:
    slot: int
    name: str = ""
    color: tuple[int, int, int] = (255, 255, 255)
    stick: StickSettings = field(default_factory=StickSettings)
    bindings: dict[int, Binding] = field(default_factory=dict)  # property index -> binding
    unknown_lines: list[str] = field(default_factory=list)      # preserved verbatim on save
    warnings: list[str] = field(default_factory=list)           # parse warnings (not saved)


# Physical layout <-> 0-based property index (G1..G22 -> G0..G21 etc.)
PHYS_TO_INDEX: dict[str, int] = {f"G{n}": n - 1 for n in range(1, 23)}
PHYS_TO_INDEX.update({
    "THUMB_LEFT": 33, "THUMB_DOWN": 34, "STICK_CLICK": 35,
    "STICK_UP": 36, "STICK_LEFT": 37, "STICK_RIGHT": 38, "STICK_DOWN": 39,
})
INDEX_TO_PHYS: dict[int, str] = {v: k for k, v in PHYS_TO_INDEX.items()}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest configurator/tests/test_model.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add configurator/g13config/model.py configurator/tests/test_model.py
git commit -m "configurator: profile data model + physical key map"
```

---

### Task 4: Bindings parser

**Files:**
- Create: `configurator/g13config/parser.py`
- Test: `configurator/tests/test_parser.py`

**Interfaces:**
- Consumes: `model.*` from Task 3.
- Produces: `parse_profile(text: str, slot: int) -> model.Profile`, `parse_plus_list(value: str) -> list[int]`.

- [ ] **Step 1: Write the failing tests**

```python
# configurator/tests/test_parser.py
from g13config import model
from g13config.parser import parse_profile

SAMPLE = """\
# G13 Profile 0 - Fusion 360
name=FUSION 360
color=255,80,0
stick_mode=mouse
stick_speed=1
stick_hold=42+274
G0=m,0,0
G2=p,k.111
G3=mp,0,5
G9=mp,5,0,272+274
G13=p,k.29+46
G35=m,2,3
future_key=whatever
"""


def test_parses_header_fields():
    p = parse_profile(SAMPLE, slot=0)
    assert p.slot == 0
    assert p.name == "FUSION 360"
    assert p.color == (255, 80, 0)
    assert p.stick.mode == "mouse"
    assert p.stick.speed == 1
    assert p.stick.hold == [42, 274]


def test_parses_binding_types():
    b = parse_profile(SAMPLE, slot=0).bindings
    assert b[0] == model.MacroBinding(macro_id=0, repeats=0)
    assert b[2] == model.KeyBinding(codes=[111])
    assert b[3] == model.MousePanBinding(dx=0, dy=5, hold=None)
    assert b[9] == model.MousePanBinding(dx=5, dy=0, hold=[272, 274])
    assert b[13] == model.KeyBinding(codes=[29, 46])
    assert b[35] == model.MacroBinding(macro_id=2, repeats=3)


def test_unbound_keys_absent():
    b = parse_profile(SAMPLE, slot=0).bindings
    assert 1 not in b and 21 not in b


def test_unknown_keys_preserved_not_warned():
    p = parse_profile(SAMPLE, slot=0)
    assert "future_key=whatever" in p.unknown_lines
    assert p.warnings == []


def test_malformed_lines_warn_and_skip():
    p = parse_profile("name=X\nG5=p,k.notanumber\nG6=zz,1\ncolor=1,2\n", slot=1)
    assert 5 not in p.bindings
    assert len(p.warnings) == 3  # bad keycode, unknown type zz, bad color
    assert p.name == "X"


def test_comments_and_blanks_ignored():
    p = parse_profile("# hi\n\n  \nname=Y\n", slot=1)
    assert p.name == "Y"
    assert p.unknown_lines == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest configurator/tests/test_parser.py -v`
Expected: FAIL — no module `g13config.parser`.

- [ ] **Step 3: Implement parser.py**

```python
# configurator/g13config/parser.py
"""Lenient parser for bindings-N.properties (mirrors driver semantics, adds warnings)."""
from . import model


def parse_plus_list(value: str) -> list[int]:
    return [int(p) for p in value.split("+") if p.strip()]


def _parse_binding(value: str) -> model.Binding | None:
    """Raises ValueError on malformed input."""
    parts = [p.strip() for p in value.split(",")]
    kind = parts[0]
    if kind == "p":
        if len(parts) < 2 or not parts[1].startswith("k."):
            raise ValueError("p binding needs k.<code>")
        return model.KeyBinding(codes=parse_plus_list(parts[1][2:]))
    if kind == "m":
        if len(parts) < 3:
            raise ValueError("m binding needs macro id and repeats")
        return model.MacroBinding(macro_id=int(parts[1]), repeats=int(parts[2]))
    if kind == "mp":
        if len(parts) < 3:
            raise ValueError("mp binding needs dx,dy")
        hold = parse_plus_list(parts[3]) if len(parts) > 3 else None
        return model.MousePanBinding(dx=int(parts[1]), dy=int(parts[2]), hold=hold)
    raise ValueError(f"unknown binding type '{kind}'")


def parse_profile(text: str, slot: int) -> model.Profile:
    p = model.Profile(slot=slot)
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            p.warnings.append(f"line {lineno}: no '=' — skipped")
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        try:
            if key == "name":
                p.name = value
            elif key == "color":
                r, g, b = (int(x) for x in value.split(","))
                if not all(0 <= c <= 255 for c in (r, g, b)):
                    raise ValueError("out of range")
                p.color = (r, g, b)
            elif key == "stick_mode":
                if value not in ("mouse", "keys"):
                    raise ValueError(f"bad stick_mode '{value}'")
                p.stick.mode = value
            elif key == "stick_speed":
                p.stick.speed = int(value)
            elif key == "stick_hold":
                p.stick.hold = parse_plus_list(value)
            elif key.startswith("G") and key[1:].isdigit():
                idx = int(key[1:])
                if 0 <= idx < 40:
                    p.bindings[idx] = _parse_binding(value)
                else:
                    raise ValueError(f"key index {idx} out of range")
            else:
                p.unknown_lines.append(line)  # preserve unknown-but-valid lines
        except (ValueError, IndexError) as e:
            p.warnings.append(f"line {lineno}: {raw.strip()!r} — {e}")
    return p
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest configurator/tests/test_parser.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add configurator/g13config/parser.py configurator/tests/test_parser.py
git commit -m "configurator: lenient bindings parser with warnings"
```

---

### Task 5: Serializer, atomic write, golden round-trip

**Files:**
- Create: `configurator/g13config/serializer.py`
- Test: `configurator/tests/test_serializer.py`

**Interfaces:**
- Consumes: `model.*`, `parser.parse_profile`.
- Produces: `serialize_profile(p: model.Profile) -> str`, `atomic_write(path: Path, text: str) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
# configurator/tests/test_serializer.py
from pathlib import Path

from g13config import model
from g13config.parser import parse_profile
from g13config.serializer import atomic_write, serialize_profile

REPO_CONFIGS = sorted(Path(__file__).resolve().parents[2].glob("config/bindings-*.properties"))


def _profile() -> model.Profile:
    p = model.Profile(slot=1, name="TEST", color=(0, 80, 255))
    p.stick = model.StickSettings(mode="mouse", speed=3, hold=[42, 274])
    p.bindings[0] = model.KeyBinding([30])
    p.bindings[1] = model.KeyBinding([29, 46])
    p.bindings[2] = model.MacroBinding(macro_id=1, repeats=2)
    p.bindings[3] = model.MousePanBinding(dx=-5, dy=0)
    p.bindings[9] = model.MousePanBinding(dx=0, dy=5, hold=[272])
    p.unknown_lines.append("future_key=whatever")
    return p


def test_serialize_emits_driver_syntax():
    text = serialize_profile(_profile())
    assert "name=TEST" in text
    assert "color=0,80,255" in text
    assert "stick_mode=mouse" in text
    assert "stick_speed=3" in text
    assert "stick_hold=42+274" in text
    assert "G0=p,k.30" in text
    assert "G1=p,k.29+46" in text
    assert "G2=m,1,2" in text
    assert "G3=mp,-5,0" in text
    assert "G9=mp,0,5,272" in text
    assert "future_key=whatever" in text


def test_round_trip_is_lossless():
    original = _profile()
    reparsed = parse_profile(serialize_profile(original), slot=1)
    assert reparsed.name == original.name
    assert reparsed.color == original.color
    assert reparsed.stick == original.stick
    assert reparsed.bindings == original.bindings
    assert reparsed.unknown_lines == original.unknown_lines
    assert reparsed.warnings == []


def test_golden_round_trip_real_repo_configs():
    assert len(REPO_CONFIGS) == 4, "expected bindings-0..3 in config/"
    for path in REPO_CONFIGS:
        slot = int(path.stem.split("-")[1])
        first = parse_profile(path.read_text(), slot)
        assert first.warnings == [], f"{path.name}: {first.warnings}"
        second = parse_profile(serialize_profile(first), slot)
        assert second.bindings == first.bindings, path.name
        assert (second.name, second.color, second.stick) == (first.name, first.color, first.stick), path.name


def test_atomic_write(tmp_path):
    target = tmp_path / "bindings-0.properties"
    atomic_write(target, "name=X\n")
    assert target.read_text() == "name=X\n"
    atomic_write(target, "name=Y\n")  # overwrite existing
    assert target.read_text() == "name=Y\n"
    assert list(tmp_path.iterdir()) == [target]  # no temp file left behind
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest configurator/tests/test_serializer.py -v`
Expected: FAIL — no module `g13config.serializer`.

- [ ] **Step 3: Implement serializer.py**

```python
# configurator/g13config/serializer.py
"""Profile -> properties text, and atomic file writes for live-reload safety."""
import os
import tempfile
from pathlib import Path

from . import model

_ROWS = [
    ("Row 1: physical G1-G7", range(0, 7)),
    ("Row 2: physical G8-G14", range(7, 14)),
    ("Row 3: physical G15-G19", range(14, 19)),
    ("Row 4: physical G20-G22", range(19, 22)),
    ("Thumb: left, down, stick click", range(33, 36)),
    ("Stick directions: up, left, right, down", range(36, 40)),
]


def _binding_line(idx: int, b: model.Binding) -> str:
    if isinstance(b, model.KeyBinding):
        return f"G{idx}=p,k." + "+".join(str(c) for c in b.codes)
    if isinstance(b, model.MacroBinding):
        return f"G{idx}=m,{b.macro_id},{b.repeats}"
    if isinstance(b, model.MousePanBinding):
        line = f"G{idx}=mp,{b.dx},{b.dy}"
        if b.hold is not None:
            line += "," + "+".join(str(c) for c in b.hold)
        return line
    raise TypeError(f"unknown binding {b!r}")


def serialize_profile(p: model.Profile) -> str:
    out = [f"# G13 Profile {p.slot} - {p.name} (written by g13-config)"]
    out.append(f"name={p.name}")
    out.append(f"color={p.color[0]},{p.color[1]},{p.color[2]}")
    out.append(f"stick_mode={p.stick.mode}")
    out.append(f"stick_speed={p.stick.speed}")
    if p.stick.hold:
        out.append("stick_hold=" + "+".join(str(c) for c in p.stick.hold))
    for comment, indices in _ROWS:
        bound = [i for i in indices if i in p.bindings]
        if bound:
            out.append(f"# {comment}")
            out.extend(_binding_line(i, p.bindings[i]) for i in bound)
    out.extend(p.unknown_lines)
    return "\n".join(out) + "\n"


def atomic_write(path: Path, text: str) -> None:
    """Write via temp file + rename so the driver's live-reload never sees a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest configurator/tests/test_serializer.py -v`
Expected: 4 passed (including the golden test against all four real repo configs).

- [ ] **Step 5: Commit**

```bash
git add configurator/g13config/serializer.py configurator/tests/test_serializer.py
git commit -m "configurator: serializer with golden round-trip against real configs"
```

---

### Task 6: Macro model, sequence parse/serialize

**Files:**
- Create: `configurator/g13config/macros.py`
- Test: `configurator/tests/test_macros.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `MacroStep` (dataclass: `kind: str` in `{"down","up","delay"}`, `value: int`), `Macro` (dataclass: `id: int`, `name: str`, `steps: list[MacroStep]`), `parse_macro(text: str, macro_id: int) -> Macro`, `serialize_macro(m: Macro) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# configurator/tests/test_macros.py
from g13config.macros import Macro, MacroStep, parse_macro, serialize_macro

UNDO = "name=Undo (Ctrl+Z)\nsequence=kd.29,d.5,kd.44,d.5,ku.44,d.5,ku.29\n"


def test_parse_macro():
    m = parse_macro(UNDO, macro_id=0)
    assert m.id == 0
    assert m.name == "Undo (Ctrl+Z)"
    assert m.steps == [
        MacroStep("down", 29), MacroStep("delay", 5),
        MacroStep("down", 44), MacroStep("delay", 5),
        MacroStep("up", 44), MacroStep("delay", 5),
        MacroStep("up", 29),
    ]


def test_round_trip():
    m = parse_macro(UNDO, macro_id=3)
    again = parse_macro(serialize_macro(m), macro_id=3)
    assert again == m


def test_empty_sequence():
    m = parse_macro("name=Empty\nsequence=\n", macro_id=1)
    assert m.steps == []
    assert "sequence=" in serialize_macro(m)


def test_bad_steps_skipped():
    m = parse_macro("name=X\nsequence=kd.29,zz.9,ku.29\n", macro_id=2)
    assert m.steps == [MacroStep("down", 29), MacroStep("up", 29)]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest configurator/tests/test_macros.py -v`
Expected: FAIL — no module `g13config.macros`.

- [ ] **Step 3: Implement macros.py**

```python
# configurator/g13config/macros.py
"""Macro pool: macro-N.properties (global slots 0..199, shared across profiles)."""
from dataclasses import dataclass, field

_KINDS = {"kd": "down", "ku": "up", "d": "delay"}
_PREFIX = {v: k for k, v in _KINDS.items()}

MAX_MACROS = 200  # driver: G13_MAX_MACROS


@dataclass
class MacroStep:
    kind: str   # "down" | "up" | "delay"
    value: int  # evdev keycode, or delay in ms


@dataclass
class Macro:
    id: int
    name: str = ""
    steps: list[MacroStep] = field(default_factory=list)


def parse_macro(text: str, macro_id: int) -> Macro:
    m = Macro(id=macro_id)
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key == "name":
            m.name = value
        elif key == "sequence":
            for token in value.split(","):
                token = token.strip()
                if not token:
                    continue
                prefix, _, num = token.partition(".")
                if prefix in _KINDS and num.isdigit():
                    m.steps.append(MacroStep(_KINDS[prefix], int(num)))
    return m


def serialize_macro(m: Macro) -> str:
    seq = ",".join(f"{_PREFIX[s.kind]}.{s.value}" for s in m.steps)
    return f"name={m.name}\nsequence={seq}\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest configurator/tests/test_macros.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add configurator/g13config/macros.py configurator/tests/test_macros.py
git commit -m "configurator: macro pool model + sequence parse/serialize"
```

---

### Task 7: ConfigStore and templates backend

**Files:**
- Create: `configurator/g13config/store.py`
- Test: `configurator/tests/test_store.py`

**Interfaces:**
- Consumes: `parser.parse_profile`, `serializer.serialize_profile/atomic_write`, `macros.*`, `model.Profile`.
- Produces:

```python
class ConfigStore:
    def __init__(self, config_dir: Path | None = None)   # default ~/.config/g13
    config_dir: Path
    templates_dir: Path                                   # config_dir / "templates"
    def bindings_path(self, slot: int) -> Path
    def load_profile(self, slot: int) -> model.Profile    # missing file -> empty Profile
    def save_profile(self, p: model.Profile) -> None      # atomic
    def load_macros(self) -> dict[int, macros.Macro]      # scans macro-*.properties
    def save_macro(self, m: macros.Macro) -> None
    def next_free_macro_id(self) -> int                   # first unused 0..199, raises if full
    def list_templates(self) -> list[str]                 # sorted template names
    def save_template(self, p: model.Profile, name: str) -> None
    def load_template(self, name: str) -> model.Profile   # slot on returned profile is -1
```

Template files are ordinary profile files named `<name>.properties` in `templates_dir`; the template's display name is the filename stem (no `template_name=` line needed — YAGNI, the spec's mention of it is satisfied by filename identity; note this in the spec is a serializer-neutral detail).

- [ ] **Step 1: Write the failing tests**

```python
# configurator/tests/test_store.py
import pytest

from g13config import macros, model
from g13config.store import ConfigStore


@pytest.fixture
def store(tmp_path):
    return ConfigStore(config_dir=tmp_path)


def test_load_missing_profile_returns_empty(store):
    p = store.load_profile(2)
    assert p.slot == 2 and p.bindings == {} and p.name == ""


def test_profile_save_load_round_trip(store):
    p = model.Profile(slot=0, name="X", color=(1, 2, 3))
    p.bindings[5] = model.KeyBinding([29, 46])
    store.save_profile(p)
    loaded = store.load_profile(0)
    assert loaded.name == "X" and loaded.bindings == p.bindings


def test_macro_save_load(store):
    m = macros.Macro(id=7, name="M", steps=[macros.MacroStep("down", 30), macros.MacroStep("up", 30)])
    store.save_macro(m)
    assert store.load_macros() == {7: m}


def test_next_free_macro_id_skips_used(store):
    store.save_macro(macros.Macro(id=0, name="a"))
    store.save_macro(macros.Macro(id=1, name="b"))
    assert store.next_free_macro_id() == 2


def test_templates_save_list_load(store):
    p = model.Profile(slot=1, name="FUSION 360")
    p.bindings[0] = model.KeyBinding([30])
    store.save_template(p, "fusion-360")
    assert store.list_templates() == ["fusion-360"]
    t = store.load_template("fusion-360")
    assert t.slot == -1
    assert t.name == "FUSION 360" and t.bindings == p.bindings


def test_list_templates_empty_when_no_dir(store):
    assert store.list_templates() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest configurator/tests/test_store.py -v`
Expected: FAIL — no module `g13config.store`.

- [ ] **Step 3: Implement store.py**

```python
# configurator/g13config/store.py
"""File-backed store for ~/.config/g13: profiles, macro pool, templates."""
import re
from pathlib import Path

from . import macros, model
from .parser import parse_profile
from .serializer import atomic_write, serialize_profile

_MACRO_RE = re.compile(r"macro-(\d+)\.properties$")


class ConfigStore:
    def __init__(self, config_dir: Path | None = None):
        self.config_dir = config_dir or Path.home() / ".config" / "g13"
        self.templates_dir = self.config_dir / "templates"

    def bindings_path(self, slot: int) -> Path:
        return self.config_dir / f"bindings-{slot}.properties"

    def load_profile(self, slot: int) -> model.Profile:
        path = self.bindings_path(slot)
        if not path.exists():
            return model.Profile(slot=slot)
        return parse_profile(path.read_text(), slot)

    def save_profile(self, p: model.Profile) -> None:
        atomic_write(self.bindings_path(p.slot), serialize_profile(p))

    def load_macros(self) -> dict[int, macros.Macro]:
        pool: dict[int, macros.Macro] = {}
        for path in self.config_dir.glob("macro-*.properties"):
            match = _MACRO_RE.search(path.name)
            if match:
                mid = int(match.group(1))
                pool[mid] = macros.parse_macro(path.read_text(), mid)
        return pool

    def save_macro(self, m: macros.Macro) -> None:
        atomic_write(self.config_dir / f"macro-{m.id}.properties", macros.serialize_macro(m))

    def next_free_macro_id(self) -> int:
        used = set(self.load_macros())
        for i in range(macros.MAX_MACROS):
            if i not in used:
                return i
        raise RuntimeError("all 200 macro slots are in use")

    def list_templates(self) -> list[str]:
        if not self.templates_dir.is_dir():
            return []
        return sorted(p.stem for p in self.templates_dir.glob("*.properties"))

    def save_template(self, p: model.Profile, name: str) -> None:
        atomic_write(self.templates_dir / f"{name}.properties", serialize_profile(p))

    def load_template(self, name: str) -> model.Profile:
        text = (self.templates_dir / f"{name}.properties").read_text()
        return parse_profile(text, slot=-1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest configurator/tests/test_store.py -v`
Expected: 6 passed. Then run the full suite: `python3 -m pytest configurator/tests -v` — all green.

- [ ] **Step 5: Commit**

```bash
git add configurator/g13config/store.py configurator/tests/test_store.py
git commit -m "configurator: ConfigStore with profiles, macro pool, templates"
```

---

### Task 8: Keycap labels helper

**Files:**
- Create: `configurator/g13config/labels.py`
- Test: `configurator/tests/test_labels.py`

**Interfaces:**
- Consumes: `model.*`, `keycodes.label_for`, `macros.Macro`.
- Produces: `short_label(binding: model.Binding | None, macro_pool: dict[int, Macro]) -> str` (keycap text, "" for unbound), `long_label(...) -> str` (tooltip text).

- [ ] **Step 1: Write the failing tests**

```python
# configurator/tests/test_labels.py
from g13config import model
from g13config.labels import long_label, short_label
from g13config.macros import Macro

POOL = {0: Macro(id=0, name="Undo (Ctrl+Z)")}


def test_unbound():
    assert short_label(None, POOL) == ""
    assert long_label(None, POOL) == "Unbound"


def test_single_key():
    assert short_label(model.KeyBinding([30]), POOL) == "A"


def test_combo_joined_with_plus():
    assert short_label(model.KeyBinding([29, 42, 20]), POOL) == "Ctrl+Shift+T"


def test_macro_uses_pool_name():
    assert short_label(model.MacroBinding(0), POOL) == "M: Undo (Ctrl+Z)"
    assert short_label(model.MacroBinding(9), POOL) == "M: #9"  # missing from pool


def test_mouse_pan_arrows():
    assert short_label(model.MousePanBinding(0, 5), POOL) == "Pan ↓"
    assert short_label(model.MousePanBinding(0, -5), POOL) == "Pan ↑"
    assert short_label(model.MousePanBinding(5, 0), POOL) == "Pan →"
    assert short_label(model.MousePanBinding(-5, 0), POOL) == "Pan ←"
    assert short_label(model.MousePanBinding(3, 3), POOL) == "Pan"


def test_long_label_mentions_details():
    assert "repeats" in long_label(model.MacroBinding(0, repeats=2), POOL)
    assert "dx=3" in long_label(model.MousePanBinding(3, 3, hold=[274]), POOL)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest configurator/tests/test_labels.py -v`
Expected: FAIL — no module `g13config.labels`.

- [ ] **Step 3: Implement labels.py**

```python
# configurator/g13config/labels.py
"""Human-readable labels for bindings (keycaps and tooltips)."""
from . import keycodes, model
from .macros import Macro


def _combo_text(codes: list[int]) -> str:
    return "+".join(keycodes.label_for(c) for c in codes)


def short_label(binding: model.Binding | None, macro_pool: dict[int, Macro]) -> str:
    if binding is None:
        return ""
    if isinstance(binding, model.KeyBinding):
        return _combo_text(binding.codes)
    if isinstance(binding, model.MacroBinding):
        macro = macro_pool.get(binding.macro_id)
        return f"M: {macro.name}" if macro and macro.name else f"M: #{binding.macro_id}"
    if isinstance(binding, model.MousePanBinding):
        if binding.dx == 0 and binding.dy > 0:
            return "Pan ↓"
        if binding.dx == 0 and binding.dy < 0:
            return "Pan ↑"
        if binding.dy == 0 and binding.dx > 0:
            return "Pan →"
        if binding.dy == 0 and binding.dx < 0:
            return "Pan ←"
        return "Pan"
    return "?"


def long_label(binding: model.Binding | None, macro_pool: dict[int, Macro]) -> str:
    if binding is None:
        return "Unbound"
    if isinstance(binding, model.KeyBinding):
        names = "+".join(keycodes.name_for(c) for c in binding.codes)
        return f"Key: {_combo_text(binding.codes)} ({names})"
    if isinstance(binding, model.MacroBinding):
        return f"{short_label(binding, macro_pool)} (repeats={binding.repeats})"
    if isinstance(binding, model.MousePanBinding):
        hold = "+".join(keycodes.label_for(c) for c in binding.hold) if binding.hold else "default"
        return f"Mouse pan dx={binding.dx} dy={binding.dy} hold={hold}"
    return "?"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest configurator/tests/test_labels.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add configurator/g13config/labels.py configurator/tests/test_labels.py
git commit -m "configurator: binding label helper for keycaps and tooltips"
```

---

### Task 9: App shell — main window skeleton and entry point

**Files:**
- Create: `configurator/g13config/main_window.py`
- Create: `configurator/g13config/__main__.py`

**Interfaces:**
- Consumes: `ConfigStore`, `model.Profile`.
- Produces: `MainWindow(store: ConfigStore)` with attributes later tasks extend: `self.store`, `self.profiles: list[model.Profile]` (slots 0–3), `self.macro_pool: dict[int, Macro]`, `self.current_slot: int`, `self.tabs: QTabBar`, `self.central_row: QHBoxLayout` (overlay goes at index 0, settings panel at index 1), method `current_profile() -> model.Profile`, method `refresh_ui()` (no-op hook for now, later tasks fill it), method `mark_dirty()` (stub until Task 13). Entry point `python3 -m g13config`.

GUI tasks are verified manually (per spec: no automated Qt tests).

- [ ] **Step 1: Implement the skeleton**

```python
# configurator/g13config/main_window.py
"""Main window: profile tabs, toolbar, overlay + settings panel row."""
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QTabBar, QToolBar, QVBoxLayout, QWidget

from .store import ConfigStore

SLOTS = range(4)


class MainWindow(QMainWindow):
    def __init__(self, store: ConfigStore):
        super().__init__()
        self.store = store
        self.profiles = [store.load_profile(s) for s in SLOTS]
        self.macro_pool = store.load_macros()
        self.current_slot = 0

        self.setWindowTitle("G13 Configurator")
        self.toolbar = QToolBar("Main")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        self.tabs = QTabBar()
        for p in self.profiles:
            self.tabs.addTab(p.name or f"Slot {p.slot + 1}")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        central = QWidget()
        column = QVBoxLayout(central)
        column.addWidget(self.tabs)
        self.central_row = QHBoxLayout()
        column.addLayout(self.central_row)
        column.addStretch()
        self.setCentralWidget(central)
        self._refresh_tab_chips()

    def current_profile(self):
        return self.profiles[self.current_slot]

    def _on_tab_changed(self, index: int):
        self.current_slot = index
        self.refresh_ui()

    def _refresh_tab_chips(self):
        for p in self.profiles:
            pix = QPixmap(12, 12)
            pix.fill(QColor(*p.color))
            self.tabs.setTabIcon(p.slot, QIcon(pix))
            self.tabs.setTabText(p.slot, p.name or f"Slot {p.slot + 1}")

    def refresh_ui(self):
        """Re-sync widgets from the current profile. Later tasks extend this."""
        self._refresh_tab_chips()

    def mark_dirty(self):
        """Dirty tracking arrives in Task 13."""
```

```python
# configurator/g13config/__main__.py
import sys

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .store import ConfigStore


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("G13 Configurator")
    window = MainWindow(ConfigStore())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Manual verification**

Run: `cd configurator && python3 -m g13config`
Expected: window opens with four tabs — FUSION 360 (orange chip), GAMING, GAMING (L3), GAMING (L4) (blue chips) — loaded from your real `~/.config/g13/`. Close it.

- [ ] **Step 3: Commit**

```bash
git add configurator/g13config/main_window.py configurator/g13config/__main__.py
git commit -m "configurator: app shell with profile tabs loading live config"
```

---

### Task 10: Device overlay widget

**Files:**
- Create: `configurator/g13config/overlay.py`
- Modify: `configurator/g13config/main_window.py` (mount overlay, feed labels, connect click signal to a stub)

**Interfaces:**
- Consumes: `model.PHYS_TO_INDEX`, `labels.short_label/long_label`.
- Produces: `G13OverlayWidget(QWidget)` with `keyClicked = Signal(str)` (physical name, e.g. `"G11"` / `"STICK_UP"`), `set_labels(labels: dict[str, str], tooltips: dict[str, str], accent: QColor)`, and class constant `KEY_RECTS: dict[str, QRect]`. MainWindow gains `self.overlay` and `_overlay_labels() -> tuple[dict, dict]` and connects `keyClicked` to `self._on_key_clicked(phys: str)` (stub that `print`s until Task 11).

- [ ] **Step 1: Implement overlay.py**

```python
# configurator/g13config/overlay.py
"""Custom-painted G13 device overlay with clickable keys."""
from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

_KW, _KH, _GAP = 64, 46, 8          # keycap geometry
_ROW_X = {0: 20, 1: 20, 2: 92, 3: 164}  # row left offsets (rows 3/4 centered)


def _build_key_rects() -> dict[str, QRect]:
    rects: dict[str, QRect] = {}
    rows = [(1, 7, 0, 130), (8, 14, 1, 184), (15, 19, 2, 238), (20, 22, 3, 292)]
    for first, last, row, y in rows:
        for i, n in enumerate(range(first, last + 1)):
            rects[f"G{n}"] = QRect(_ROW_X[row] + i * (_KW + _GAP), y, _KW, _KH)
    rects["THUMB_LEFT"] = QRect(330, 356, 58, 34)
    rects["THUMB_DOWN"] = QRect(330, 398, 58, 34)
    rects["STICK_CLICK"] = QRect(398, 356, 58, 34)
    rects["STICK_UP"] = QRect(430, 398, 44, 26)
    rects["STICK_LEFT"] = QRect(398, 430, 44, 26)
    rects["STICK_RIGHT"] = QRect(462, 430, 44, 26)
    rects["STICK_DOWN"] = QRect(430, 462, 44, 26)
    return rects


class G13OverlayWidget(QWidget):
    keyClicked = Signal(str)

    KEY_RECTS = _build_key_rects()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._labels: dict[str, str] = {}
        self._tooltips: dict[str, str] = {}
        self._accent = QColor("#ff5000")
        self._hover: str | None = None
        self.setFixedSize(540, 505)
        self.setMouseTracking(True)

    def set_labels(self, labels: dict[str, str], tooltips: dict[str, str], accent: QColor):
        self._labels, self._tooltips, self._accent = labels, tooltips, accent
        self.update()

    def _key_at(self, pos) -> str | None:
        for name, rect in self.KEY_RECTS.items():
            if rect.contains(pos):
                return name
        return None

    def mouseMoveEvent(self, event):
        name = self._key_at(event.position().toPoint())
        if name != self._hover:
            self._hover = name
            self.setToolTip(self._tooltips.get(name, "") if name else "")
            self.update()

    def mousePressEvent(self, event):
        name = self._key_at(event.position().toPoint())
        if name:
            self.keyClicked.emit(name)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # Device body
        p.setBrush(QColor("#1b1d20"))
        p.setPen(QPen(QColor("#000000")))
        p.drawRoundedRect(4, 4, 532, 497, 24, 24)
        # LCD strip + M-row hint (orientation only, not interactive)
        p.setBrush(QColor("#0a0f08"))
        p.drawRoundedRect(110, 20, 320, 56, 4, 4)
        p.setPen(QColor(self._accent))
        p.setFont(QFont(self.font().family(), 10))
        p.drawText(QRect(110, 20, 320, 56), Qt.AlignCenter, self._labels.get("__lcd__", ""))
        p.setPen(QColor("#9aa0a8"))
        p.drawText(QRect(110, 84, 320, 20), Qt.AlignCenter, "M1    M2    M3    MR")
        # Keys
        small = QFont(self.font().family(), 7)
        big = QFont(self.font().family(), 9, QFont.Bold)
        for name, rect in self.KEY_RECTS.items():
            hovered = name == self._hover
            p.setBrush(QColor("#31353b") if hovered else QColor("#26292d"))
            p.setPen(QPen(QColor("#3daee9") if hovered else QColor("#101214"), 1.5))
            p.drawRoundedRect(rect, 6, 6)
            label = self._labels.get(name, "")
            p.setFont(small)
            p.setPen(QColor("#9aa0a8"))
            p.drawText(rect.adjusted(0, 3, 0, 0), Qt.AlignHCenter | Qt.AlignTop, name.replace("_", " "))
            p.setFont(big)
            p.setPen(self._accent if label else QColor("#565c64"))
            p.drawText(rect.adjusted(0, 10, 0, -2), Qt.AlignCenter, label or "·")
```

- [ ] **Step 2: Mount it in MainWindow**

In `main_window.py`, add imports and wire the overlay:

```python
from PySide6.QtGui import QColor  # already imported
from . import labels as labels_mod
from .model import PHYS_TO_INDEX
from .overlay import G13OverlayWidget
```

In `__init__`, after `self.central_row = QHBoxLayout()` add:

```python
        self.overlay = G13OverlayWidget()
        self.overlay.keyClicked.connect(self._on_key_clicked)
        self.central_row.addWidget(self.overlay)
        self.refresh_ui()
```

Add methods:

```python
    def _overlay_labels(self):
        p = self.current_profile()
        shorts = {"__lcd__": p.name}
        tips = {}
        for phys, idx in PHYS_TO_INDEX.items():
            binding = p.bindings.get(idx)
            shorts[phys] = labels_mod.short_label(binding, self.macro_pool)
            tips[phys] = labels_mod.long_label(binding, self.macro_pool)
        return shorts, tips

    def _on_key_clicked(self, phys: str):
        print(f"clicked {phys}")  # replaced by the binding dialog in Task 11
```

Extend `refresh_ui`:

```python
    def refresh_ui(self):
        self._refresh_tab_chips()
        shorts, tips = self._overlay_labels()
        self.overlay.set_labels(shorts, tips, QColor(*self.current_profile().color))
```

- [ ] **Step 3: Manual verification**

Run: `cd configurator && python3 -m g13config`
Expected: overlay shows the FUSION 360 assignments on the correct physical keys — G1 "M: Undo (Ctrl+Z)", G4 "Pan ↓", G10 "Pan →", G11 "Pan ↑", G12 "Pan ←", thumb keys Esc/Enter, stick click "M: Fit View…". Switching to GAMING tab shows the WASD mirror and stick-direction keys W/A/D/S. Hover highlights + tooltip; click prints the physical name to the terminal.

- [ ] **Step 4: Commit**

```bash
git add configurator/g13config/overlay.py configurator/g13config/main_window.py
git commit -m "configurator: painted device overlay with live assignments"
```

---

### Task 11: Chord capture field and binding editor dialog

**Files:**
- Create: `configurator/g13config/capture.py`
- Create: `configurator/g13config/binding_dialog.py`
- Modify: `configurator/g13config/main_window.py` (`_on_key_clicked` opens the dialog and applies the result)

**Interfaces:**
- Consumes: `keycodes.qt_native_to_evdev/is_modifier/label_for/search`, `model.*`, `macros.Macro`.
- Produces:
  - `KeyCaptureField(QPushButton)` — click to arm; while armed it grabs the keyboard; emits `chordCaptured = Signal(list)` (evdev codes, modifiers first in press order); Esc disarms. Property `codes: list[int]`.
  - `BindingEditorDialog(QDialog)` — `__init__(self, phys: str, current: model.Binding | None, macro_pool: dict[int, Macro], parent=None)`; after `exec()` returns `QDialog.Accepted`, `result_binding() -> model.Binding | None` (None == unbound).

- [ ] **Step 1: Implement capture.py**

```python
# configurator/g13config/capture.py
"""Chord capture: press the real keys, get evdev codes."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPushButton

from . import keycodes


class KeyCaptureField(QPushButton):
    chordCaptured = Signal(list)

    def __init__(self, codes: list[int] | None = None, parent=None):
        super().__init__(parent)
        self.codes: list[int] = list(codes or [])
        self._armed = False
        self._held_mods: list[int] = []
        self.clicked.connect(self._arm)
        self._render()

    def _render(self):
        if self._armed:
            held = "+".join(keycodes.label_for(c) for c in self._held_mods)
            self.setText(f"{held}+…" if held else "Press keys… (Esc cancels)")
        else:
            self.setText("+".join(keycodes.label_for(c) for c in self.codes) or "Click to set")

    def _arm(self):
        self._armed = True
        self._held_mods = []
        self.grabKeyboard()
        self._render()

    def _disarm(self):
        self._armed = False
        self.releaseKeyboard()
        self._render()

    def keyPressEvent(self, event):
        if not self._armed:
            return super().keyPressEvent(event)
        if event.key() == Qt.Key_Escape:
            self._disarm()
            return
        code = keycodes.qt_native_to_evdev(event.nativeScanCode())
        if keycodes.is_modifier(code):
            if code not in self._held_mods:
                self._held_mods.append(code)
            self._render()
        else:
            self.codes = self._held_mods + [code]
            self._disarm()
            self.chordCaptured.emit(self.codes)

    def keyReleaseEvent(self, event):
        if not self._armed:
            return super().keyReleaseEvent(event)
        code = keycodes.qt_native_to_evdev(event.nativeScanCode())
        if code in self._held_mods:
            self._held_mods.remove(code)
            self._render()

    def focusOutEvent(self, event):
        if self._armed:
            self._disarm()
        super().focusOutEvent(event)
```

- [ ] **Step 2: Implement binding_dialog.py**

```python
# configurator/g13config/binding_dialog.py
"""Per-key binding editor: key/combo, macro, mouse pan, or unbound."""
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QRadioButton, QSpinBox, QVBoxLayout,
)

from . import keycodes, model
from .capture import KeyCaptureField
from .macros import Macro


class BindingEditorDialog(QDialog):
    def __init__(self, phys: str, current: model.Binding | None,
                 macro_pool: dict[int, Macro], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Bind {phys.replace('_', ' ')}")
        self._macro_ids = sorted(macro_pool)

        self.r_key = QRadioButton("Key or combo")
        self.r_macro = QRadioButton("Macro")
        self.r_pan = QRadioButton("Mouse pan")
        self.r_none = QRadioButton("Unbound")

        self.capture = KeyCaptureField()
        self.key_list = QComboBox()
        self.key_list.setEditable(True)
        self.key_list.setPlaceholderText("or pick a key by name…")
        for code, name in keycodes.search(""):
            self.key_list.addItem(name, userData=code)
        self.key_list.setCurrentIndex(-1)
        self.key_list.activated.connect(self._key_picked_from_list)

        self.macro_box = QComboBox()
        for mid in self._macro_ids:
            m = macro_pool[mid]
            self.macro_box.addItem(f"{mid}: {m.name or '(unnamed)'}", userData=mid)
        self.repeats = QSpinBox()
        self.repeats.setRange(0, 100)

        self.pan_dx = QSpinBox(); self.pan_dx.setRange(-100, 100)
        self.pan_dy = QSpinBox(); self.pan_dy.setRange(-100, 100)
        self.pan_hold = KeyCaptureField()

        form = QVBoxLayout(self)
        form.addWidget(self.r_key)
        key_row = QHBoxLayout()
        key_row.addWidget(self.capture); key_row.addWidget(self.key_list)
        form.addLayout(key_row)
        form.addWidget(self.r_macro)
        macro_row = QHBoxLayout()
        macro_row.addWidget(self.macro_box); macro_row.addWidget(QLabel("repeats")); macro_row.addWidget(self.repeats)
        form.addLayout(macro_row)
        form.addWidget(self.r_pan)
        pan_form = QFormLayout()
        pan_form.addRow("dx", self.pan_dx); pan_form.addRow("dy", self.pan_dy)
        pan_form.addRow("hold", self.pan_hold)
        form.addLayout(pan_form)
        form.addWidget(self.r_none)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)

        self._load_current(current)

    def _load_current(self, b: model.Binding | None):
        if isinstance(b, model.KeyBinding):
            self.r_key.setChecked(True)
            self.capture.codes = list(b.codes)
            self.capture._render()
        elif isinstance(b, model.MacroBinding):
            self.r_macro.setChecked(True)
            if b.macro_id in self._macro_ids:
                self.macro_box.setCurrentIndex(self._macro_ids.index(b.macro_id))
            self.repeats.setValue(b.repeats)
        elif isinstance(b, model.MousePanBinding):
            self.r_pan.setChecked(True)
            self.pan_dx.setValue(b.dx); self.pan_dy.setValue(b.dy)
            self.pan_hold.codes = list(b.hold or [])
            self.pan_hold._render()
        else:
            self.r_none.setChecked(True)

    def _key_picked_from_list(self, index: int):
        code = self.key_list.itemData(index)
        if code is not None:
            self.capture.codes = [code]
            self.capture._render()
            self.r_key.setChecked(True)

    def result_binding(self) -> model.Binding | None:
        if self.r_key.isChecked() and self.capture.codes:
            return model.KeyBinding(codes=list(self.capture.codes))
        if self.r_macro.isChecked() and self.macro_box.currentData() is not None:
            return model.MacroBinding(macro_id=self.macro_box.currentData(),
                                      repeats=self.repeats.value())
        if self.r_pan.isChecked():
            hold = list(self.pan_hold.codes) or None
            return model.MousePanBinding(dx=self.pan_dx.value(), dy=self.pan_dy.value(), hold=hold)
        return None
```

- [ ] **Step 3: Wire into MainWindow**

Replace the `_on_key_clicked` stub in `main_window.py`:

```python
    def _on_key_clicked(self, phys: str):
        from .binding_dialog import BindingEditorDialog
        from .model import PHYS_TO_INDEX
        idx = PHYS_TO_INDEX[phys]
        profile = self.current_profile()
        dialog = BindingEditorDialog(phys, profile.bindings.get(idx), self.macro_pool, self)
        if dialog.exec():
            result = dialog.result_binding()
            if result is None:
                profile.bindings.pop(idx, None)
            else:
                profile.bindings[idx] = result
            self.mark_dirty()
            self.refresh_ui()
```

- [ ] **Step 4: Manual verification**

Run: `cd configurator && python3 -m g13config`
Expected: clicking G14 opens "Bind G14"; clicking the capture field then pressing `Ctrl+Shift+T` shows "Ctrl+Shift+T"; OK updates the keycap. Verify Super+X captures too (KDE may eat some Super shortcuts globally — if `Super+X` doesn't arrive, that's a known Wayland compositor grab; pick another combo to confirm the mechanism and note it). Unbound clears the cap. **No file is written yet** (Apply arrives in Task 13) — restarting the app resets edits; that's expected at this stage.

- [ ] **Step 5: Commit**

```bash
git add configurator/g13config/capture.py configurator/g13config/binding_dialog.py configurator/g13config/main_window.py
git commit -m "configurator: chord capture + binding editor dialog"
```

---

### Task 12: Settings panel and macro editor

**Files:**
- Create: `configurator/g13config/settings_panel.py`
- Create: `configurator/g13config/macro_editor.py`
- Modify: `configurator/g13config/main_window.py` (mount panel; "Edit macros…" opens the editor)

**Interfaces:**
- Consumes: `model.*`, `capture.KeyCaptureField`, `macros.*`, `store.ConfigStore` (macro editor saves macros immediately via store — macros are global, not part of profile dirty state).
- Produces:
  - `ProfileSettingsPanel(QWidget)` — `set_profile(p: model.Profile)`; `changed = Signal()` emitted after any edit (edits mutate the Profile in place); `editMacros = Signal()`.
  - `MacroEditorDialog(QDialog)` — `__init__(self, store, macro_pool: dict[int, Macro], parent=None)`; mutates `macro_pool` and saves via `store.save_macro` on Save; supports new macro (`store.next_free_macro_id`), step add/remove, delay edit, record mode.

- [ ] **Step 1: Implement settings_panel.py**

```python
# configurator/g13config/settings_panel.py
"""Per-profile settings: name, LCD color, stick mode/speed/hold."""
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog, QComboBox, QFormLayout, QLineEdit, QPushButton, QSpinBox, QWidget,
)

from . import model
from .capture import KeyCaptureField


class ProfileSettingsPanel(QWidget):
    changed = Signal()
    editMacros = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._profile: model.Profile | None = None

        self.name_edit = QLineEdit()
        self.color_btn = QPushButton()
        self.mode_box = QComboBox()
        self.mode_box.addItems(["mouse", "keys"])
        self.speed = QSpinBox()
        self.speed.setRange(1, 50)
        self.hold = KeyCaptureField()
        self.macros_btn = QPushButton("Edit macros…")

        form = QFormLayout(self)
        form.addRow("Name", self.name_edit)
        form.addRow("LCD color", self.color_btn)
        form.addRow("Stick mode", self.mode_box)
        form.addRow("Stick speed", self.speed)
        form.addRow("Orbit hold", self.hold)
        form.addRow(self.macros_btn)

        self.name_edit.editingFinished.connect(self._apply)
        self.color_btn.clicked.connect(self._pick_color)
        self.mode_box.currentTextChanged.connect(lambda _t: self._apply())
        self.speed.valueChanged.connect(lambda _v: self._apply())
        self.hold.chordCaptured.connect(lambda _c: self._apply())
        self.macros_btn.clicked.connect(self.editMacros)

    def set_profile(self, p: model.Profile):
        self._profile = None  # mute _apply during sync
        self.name_edit.setText(p.name)
        self._set_swatch(p.color)
        self.mode_box.setCurrentText(p.stick.mode)
        self.speed.setValue(p.stick.speed)
        self.hold.codes = list(p.stick.hold)
        self.hold._render()
        self._profile = p

    def _set_swatch(self, color: tuple[int, int, int]):
        self.color_btn.setText(f"{color[0]}, {color[1]}, {color[2]}")
        self.color_btn.setStyleSheet(
            f"background-color: rgb({color[0]},{color[1]},{color[2]});")

    def _pick_color(self):
        if self._profile is None:
            return
        chosen = QColorDialog.getColor(QColor(*self._profile.color), self, "LCD color")
        if chosen.isValid():
            self._profile.color = (chosen.red(), chosen.green(), chosen.blue())
            self._set_swatch(self._profile.color)
            self.changed.emit()

    def _apply(self):
        p = self._profile
        if p is None:
            return
        p.name = self.name_edit.text()
        p.stick.mode = self.mode_box.currentText()
        p.stick.speed = self.speed.value()
        p.stick.hold = list(self.hold.codes)
        self.changed.emit()
```

- [ ] **Step 2: Implement macro_editor.py**

```python
# configurator/g13config/macro_editor.py
"""Macro pool editor: steps (down/up/delay) with record mode."""
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QInputDialog, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QVBoxLayout,
)

from . import keycodes
from .macros import Macro, MacroStep, serialize_macro


def _step_text(s: MacroStep) -> str:
    if s.kind == "delay":
        return f"⏱ delay {s.value} ms"
    arrow = "↓" if s.kind == "down" else "↑"
    return f"{arrow} {s.kind} {keycodes.label_for(s.value)}"


class MacroEditorDialog(QDialog):
    def __init__(self, store, macro_pool: dict[int, Macro], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Macro editor")
        self.store = store
        self.pool = macro_pool
        self._current: Macro | None = None
        self._recording = False
        self._last_event = 0.0

        self.macro_list = QListWidget()
        self.name_edit = QLineEdit()
        self.steps = QListWidget()
        self.new_btn = QPushButton("New macro")
        self.record_btn = QPushButton("● Record")
        self.add_delay_btn = QPushButton("＋ Delay")
        self.del_step_btn = QPushButton("− Step")
        self.save_btn = QPushButton("Save macro")

        left = QVBoxLayout()
        left.addWidget(self.macro_list)
        left.addWidget(self.new_btn)
        right = QVBoxLayout()
        right.addWidget(self.name_edit)
        right.addWidget(self.steps)
        step_row = QHBoxLayout()
        for b in (self.record_btn, self.add_delay_btn, self.del_step_btn, self.save_btn):
            step_row.addWidget(b)
        right.addLayout(step_row)
        row = QHBoxLayout()
        row.addLayout(left)
        row.addLayout(right)
        root = QVBoxLayout(self)
        root.addLayout(row)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.reject)
        root.addWidget(close)

        self.macro_list.currentItemChanged.connect(self._select_macro)
        self.new_btn.clicked.connect(self._new_macro)
        self.record_btn.clicked.connect(self._toggle_record)
        self.add_delay_btn.clicked.connect(self._add_delay)
        self.del_step_btn.clicked.connect(self._delete_step)
        self.save_btn.clicked.connect(self._save)
        self._reload_list()

    def _reload_list(self):
        self.macro_list.clear()
        for mid in sorted(self.pool):
            item = QListWidgetItem(f"{mid}: {self.pool[mid].name or '(unnamed)'}")
            item.setData(Qt.UserRole, mid)
            self.macro_list.addItem(item)

    def _select_macro(self, item, _prev=None):
        if item is None:
            return
        self._current = self.pool[item.data(Qt.UserRole)]
        self.name_edit.setText(self._current.name)
        self._reload_steps()

    def _reload_steps(self):
        self.steps.clear()
        if self._current:
            for s in self._current.steps:
                self.steps.addItem(_step_text(s))

    def _new_macro(self):
        mid = self.store.next_free_macro_id()
        name, ok = QInputDialog.getText(self, "New macro", "Name:")
        if not ok:
            return
        self.pool[mid] = Macro(id=mid, name=name)
        self._reload_list()
        self.macro_list.setCurrentRow(sorted(self.pool).index(mid))

    def _toggle_record(self):
        if self._current is None:
            return
        self._recording = not self._recording
        if self._recording:
            self._current.steps = []
            self._last_event = time.monotonic()
            self.record_btn.setText("■ Stop")
            self.grabKeyboard()
        else:
            self.record_btn.setText("● Record")
            self.releaseKeyboard()
            self._reload_steps()

    def _record_step(self, kind: str, code: int):
        now = time.monotonic()
        gap_ms = int((now - self._last_event) * 1000)
        self._last_event = now
        if self._current.steps and gap_ms >= 5:
            self._current.steps.append(MacroStep("delay", min(gap_ms, 5000)))
        self._current.steps.append(MacroStep(kind, code))
        self._reload_steps()

    def keyPressEvent(self, event):
        if self._recording and not event.isAutoRepeat():
            if event.key() == Qt.Key_Escape:
                self._toggle_record()
                return
            self._record_step("down", keycodes.qt_native_to_evdev(event.nativeScanCode()))
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if self._recording and not event.isAutoRepeat():
            self._record_step("up", keycodes.qt_native_to_evdev(event.nativeScanCode()))
            return
        super().keyReleaseEvent(event)

    def _add_delay(self):
        if self._current is None:
            return
        ms, ok = QInputDialog.getInt(self, "Delay", "Milliseconds:", 5, 1, 5000)
        if ok:
            row = self.steps.currentRow()
            pos = row + 1 if row >= 0 else len(self._current.steps)
            self._current.steps.insert(pos, MacroStep("delay", ms))
            self._reload_steps()

    def _delete_step(self):
        row = self.steps.currentRow()
        if self._current is not None and row >= 0:
            del self._current.steps[row]
            self._reload_steps()

    def _save(self):
        if self._current is None:
            return
        self._current.name = self.name_edit.text()
        self.store.save_macro(self._current)
        self._reload_list()
```

- [ ] **Step 3: Mount in MainWindow**

In `main_window.py` `__init__`, after mounting the overlay:

```python
        from .settings_panel import ProfileSettingsPanel
        self.settings = ProfileSettingsPanel()
        self.settings.changed.connect(self._on_settings_changed)
        self.settings.editMacros.connect(self._open_macro_editor)
        self.central_row.addWidget(self.settings)
```

Add methods:

```python
    def _on_settings_changed(self):
        self.mark_dirty()
        self.refresh_ui()

    def _open_macro_editor(self):
        from .macro_editor import MacroEditorDialog
        MacroEditorDialog(self.store, self.macro_pool, self).exec()
        self.refresh_ui()  # macro names on keycaps may have changed
```

Extend `refresh_ui` (add as last line):

```python
        self.settings.set_profile(self.current_profile())
```

- [ ] **Step 4: Manual verification**

Run: `cd configurator && python3 -m g13config`
Expected: settings panel shows FUSION 360 / orange / mouse / 1 / Shift+MMB. Renaming updates the tab; color picker updates the chip and overlay tint. "Edit macros…" lists Undo/Redo/Fit View; recording a short macro captures downs/ups with delays; Save writes `~/.config/g13/macro-N.properties` (verify with `cat`).

- [ ] **Step 5: Commit**

```bash
git add configurator/g13config/settings_panel.py configurator/g13config/macro_editor.py configurator/g13config/main_window.py
git commit -m "configurator: settings panel + macro editor with record mode"
```

---

### Task 13: Dirty tracking, Apply/Revert, file watcher

**Files:**
- Modify: `configurator/g13config/main_window.py`

**Interfaces:**
- Consumes: `serializer.serialize_profile`, `store.save_profile`, `QFileSystemWatcher`.
- Produces: working `mark_dirty()`; toolbar Apply/Revert; window-title dirty marker; external-change banner. `self._baseline: dict[int, str]` (serialized text per slot at load/apply).

- [ ] **Step 1: Implement dirty state + apply/revert + watcher**

In `main_window.py` — add imports:

```python
from PySide6.QtCore import QFileSystemWatcher
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton
from .serializer import serialize_profile
```

In `__init__` (after `self.macro_pool = ...`):

```python
        self._baseline = {p.slot: serialize_profile(p) for p in self.profiles}
        self._applying = False
```

Toolbar setup (in `__init__`, after `self.addToolBar(self.toolbar)`):

```python
        self.dirty_label = QLabel("")
        self.act_revert = QAction("Revert", self)
        self.act_apply = QAction("Apply", self)
        self.act_revert.triggered.connect(self.revert)
        self.act_apply.triggered.connect(self.apply)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(spacer)
        self.toolbar.addWidget(self.dirty_label)
        self.toolbar.addAction(self.act_revert)
        self.toolbar.addAction(self.act_apply)
```

(`QSizePolicy` from `PySide6.QtWidgets`.) Watcher (end of `__init__`):

```python
        self.watcher = QFileSystemWatcher([str(self.store.config_dir)], self)
        self.watcher.directoryChanged.connect(self._on_external_change)
```

Methods:

```python
    def _dirty_slots(self) -> list[int]:
        return [p.slot for p in self.profiles if serialize_profile(p) != self._baseline[p.slot]]

    def mark_dirty(self):
        n = len(self._dirty_slots())
        self.dirty_label.setText(f"● {n} unsaved profile(s)  " if n else "")
        self.setWindowTitle("G13 Configurator" + (" *" if n else ""))

    def apply(self):
        self._applying = True
        try:
            for slot in self._dirty_slots():
                self.store.save_profile(self.profiles[slot])
                self._baseline[slot] = serialize_profile(self.profiles[slot])
        finally:
            self._applying = False
        self.mark_dirty()

    def revert(self):
        self.profiles = [self.store.load_profile(s) for s in SLOTS]
        self._baseline = {p.slot: serialize_profile(p) for p in self.profiles}
        self.macro_pool = self.store.load_macros()
        self.mark_dirty()
        self.refresh_ui()

    def _on_external_change(self, _path: str):
        if self._applying:
            return
        answer = QMessageBox.question(
            self, "Config changed on disk",
            "The G13 config was modified outside this tool.\n"
            "Reload from disk? (Unsaved edits here will be lost.)",
            QMessageBox.Yes | QMessageBox.No)
        if answer == QMessageBox.Yes:
            self.revert()
```

Also call `self.mark_dirty()` at the end of `_on_key_clicked`'s accepted branch and `_on_settings_changed` (already wired — verify both call it).

- [ ] **Step 2: Manual verification**

Run: `cd configurator && python3 -m g13config`
Expected: editing a binding shows "● 1 unsaved profile(s)" and title `*`. Apply writes the file — check with `cat ~/.config/g13/bindings-0.properties`; the G13's LCD reflects a profile-name change within ~a second (live-reload). Revert restores. Editing the file externally (`echo "# touch" >> ~/.config/g13/bindings-2.properties`) pops the reload prompt. **Warning check:** open a profile with a deliberately malformed line and confirm `p.warnings` surfaces (add a `QMessageBox.warning` listing `profile.warnings` after load in `revert`/`__init__` if not already visible):

```python
        for p in self.profiles:
            if p.warnings:
                QMessageBox.warning(self, f"Slot {p.slot + 1} parse warnings", "\n".join(p.warnings))
```

(Place this at the end of `__init__` and `revert`.)

- [ ] **Step 3: Commit**

```bash
git add configurator/g13config/main_window.py
git commit -m "configurator: dirty tracking, apply/revert, external-change watcher"
```

---

### Task 14: Templates UI, starter templates, install integration

**Files:**
- Create: `config/templates/blank.properties`, `config/templates/wasd-gaming.properties`, `config/templates/fusion-360.properties`
- Create: `g13-config.desktop`
- Modify: `configurator/g13config/main_window.py` (toolbar template actions)
- Modify: `install.sh`

**Interfaces:**
- Consumes: `ConfigStore.list_templates/save_template/load_template`, `serialize_profile`.
- Produces: toolbar actions New from template / Save as template / Clone to slot; installed `g13-config` launcher.

- [ ] **Step 1: Create starter templates**

`config/templates/blank.properties`:

```properties
# G13 template - blank
name=BLANK
color=128,128,128
stick_mode=keys
stick_speed=8
```

`config/templates/wasd-gaming.properties` — copy of the current gaming profile:

Run: `mkdir -p config/templates && sed 's/^name=.*/name=GAMING/' config/bindings-1.properties > config/templates/wasd-gaming.properties`

`config/templates/fusion-360.properties`:

Run: `cp config/bindings-0.properties config/templates/fusion-360.properties`

- [ ] **Step 2: Toolbar template actions**

In `main_window.py` `__init__` (before the spacer widget):

```python
        self.act_new_tpl = QAction("New from template", self)
        self.act_save_tpl = QAction("Save as template", self)
        self.act_clone = QAction("Clone to slot", self)
        self.act_new_tpl.triggered.connect(self._new_from_template)
        self.act_save_tpl.triggered.connect(self._save_as_template)
        self.act_clone.triggered.connect(self._clone_to_slot)
        for act in (self.act_new_tpl, self.act_save_tpl, self.act_clone):
            self.toolbar.addAction(act)
```

Methods (imports: `QInputDialog` from QtWidgets):

```python
    def _confirm_overwrite(self, slot: int) -> bool:
        name = self.profiles[slot].name or f"Slot {slot + 1}"
        return QMessageBox.question(
            self, "Overwrite profile",
            f"Replace '{name}' (slot {slot + 1})? This overwrites its live config on Apply.",
            QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes

    def _pick_slot(self, title: str) -> int | None:
        options = [f"{s + 1}: {self.profiles[s].name or '(empty)'}" for s in SLOTS]
        choice, ok = QInputDialog.getItem(self, title, "Target slot:", options, 0, False)
        return options.index(choice) if ok else None

    def _new_from_template(self):
        names = self.store.list_templates()
        if not names:
            QMessageBox.information(self, "No templates", "No templates in "
                                    f"{self.store.templates_dir}")
            return
        name, ok = QInputDialog.getItem(self, "New from template", "Template:", names, 0, False)
        if not ok:
            return
        slot = self._pick_slot("Apply template to slot")
        if slot is None or not self._confirm_overwrite(slot):
            return
        template = self.store.load_template(name)
        template.slot = slot
        self.profiles[slot] = template
        self.tabs.setCurrentIndex(slot)
        self.mark_dirty()
        self.refresh_ui()

    def _save_as_template(self):
        name, ok = QInputDialog.getText(self, "Save as template", "Template name:",
                                        text=self.current_profile().name.lower().replace(" ", "-"))
        if ok and name:
            self.store.save_template(self.current_profile(), name)

    def _clone_to_slot(self):
        slot = self._pick_slot("Clone current profile to slot")
        if slot is None or slot == self.current_slot or not self._confirm_overwrite(slot):
            return
        clone = parse_profile(serialize_profile(self.current_profile()), slot)
        clone.slot = slot
        self.profiles[slot] = clone
        self.mark_dirty()
        self.refresh_ui()
```

(Import `parse_profile` from `.parser` at the top of the file.)

- [ ] **Step 3: Desktop entry and install.sh**

`g13-config.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=G13 Configurator
Comment=Reprogram the Logitech G13 gameboard
Exec=g13-config
Icon=input-gaming
Categories=Utility;Settings;
Terminal=false
```

Append to `install.sh` (before the "Starting services" section):

```bash
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
```

- [ ] **Step 4: Manual verification**

Run: `./install.sh && g13-config`
Expected: installer completes (sudo only if udev rule changed); `g13-config` launches from PATH; "G13 Configurator" appears in the KDE launcher; templates blank / wasd-gaming / fusion-360 listed in New from template; cloning FUSION 360 to slot 4 (with confirmation) then Apply writes `bindings-3.properties`, and pressing M4 on the device loads it.

- [ ] **Step 5: Commit**

```bash
git add config/templates g13-config.desktop configurator/g13config/main_window.py install.sh
git commit -m "configurator: templates UI, starter templates, install integration"
```

---

### Task 15: Hardware & end-to-end verification

**Files:** none (verification checklist; fix-forward anything that fails, committing fixes individually).

- [ ] **Step 1: Full test suite**

Run: `python3 -m pytest configurator/tests -v`
Expected: all tests pass.

- [ ] **Step 2: Combo passthrough on hardware**

In `g13-config`: bind `Ctrl+C` to G19 on FUSION 360 via capture field, Apply. In a text editor select text and press G19 — expect copy. Then bind `Ctrl+Shift+T`, hold G19 in a browser — expect reopened tabs and key-repeat behavior. Verify `grep G18 ~/.config/g13/bindings-0.properties` shows `G18=p,k.29+46` style syntax.

- [ ] **Step 3: End-to-end sweep**

- Rename a profile + change color → Apply → LCD name and backlight change.
- Record a macro, bind to a spare key → fires on device.
- Stick settings round-trip: flip GAMING to mouse mode and back; Apply between; driver follows.
- Template → slot 4 (L4) → Apply → M4 loads it on the device.
- Restore your real config afterwards (Revert any experiments; `git diff` in `~/.config/g13` isn't tracked, so verify against `config/` repo copies if unsure: `diff ~/.config/g13/bindings-0.properties config/bindings-0.properties`).

- [ ] **Step 4: Docs and reference**

Update the repo README section listing components with a `configurator/` paragraph (launch command, file locations, template dir). If any *shipped profile bindings* changed during verification, sync `reference/g13-reference.html` + the reference-card artifact per the standing rule; verification-only experiments that were reverted need no sync.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "configurator: verification fixes + docs"
```

---

## Self-Review Notes

- **Spec coverage:** overlay (T10), capture/combos (T1, T11), macro editor + record (T12), templates/clone (T14), name/color/stick (T12), atomic writes + lenient parse + warnings + watcher (T5, T4, T13), fresh-machine bootstrap (install.sh `cp -n` + `atomic_write` mkdir, T14/T5), round-trip + golden tests (T5), hardware verify (T15). LCD bottom line / L3-L4 content / upstream PR: out of scope per spec.
- **Template `template_name=`:** satisfied by filename-stem identity (noted in Task 7) — simpler than an in-file field, and `parse_profile` preserves any such line via `unknown_lines` if one appears.
- **Type consistency:** `Binding` union + `PHYS_TO_INDEX` defined once in `model.py`; all UI tasks consume `short_label/long_label` from `labels.py`; store API names match between Task 7 definition and Tasks 12–14 usage.
