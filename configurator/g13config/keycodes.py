"""Linux evdev keycode names, display labels, and Qt scancode conversion.

Uses python3-evdev purely as a name table (no device access).
"""
from evdev import ecodes

# code -> canonical KEY_* name (ecodes.KEY maps some codes to a list of aliases)
# ecodes.BTN (mouse buttons) is a separate dict from ecodes.KEY, even though
# both share the same underlying evdev code space. Merge BTN in first so that
# any real collision leaves the KEY_* name/code as canonical.
_NAMES: dict[int, str] = {}
for code, name in ecodes.BTN.items():
    _NAMES[code] = name[0] if isinstance(name, (list, tuple)) else name
for code, name in ecodes.KEY.items():
    _NAMES[code] = name[0] if isinstance(name, (list, tuple)) else name

_CODES: dict[str, int] = {}
for code, name in ecodes.BTN.items():
    for n in name if isinstance(name, (list, tuple)) else [name]:
        _CODES.setdefault(n, code)
for code, name in ecodes.KEY.items():
    for n in name if isinstance(name, (list, tuple)) else [name]:
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
