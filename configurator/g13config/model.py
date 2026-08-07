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
# M1/M2/M3/MR are the silkscreened bottom row between the LCD and the keypad.
# The unlabeled top row (indices 25-28) switches profiles in the driver and is
# deliberately not mapped here.
PHYS_TO_INDEX: dict[str, int] = {f"G{n}": n - 1 for n in range(1, 23)}
PHYS_TO_INDEX.update({
    "M1": 29, "M2": 30, "M3": 31, "MR": 32,
    "THUMB_LEFT": 33, "THUMB_DOWN": 34, "STICK_CLICK": 35,
    "STICK_UP": 36, "STICK_LEFT": 37, "STICK_RIGHT": 38, "STICK_DOWN": 39,
})
INDEX_TO_PHYS: dict[int, str] = {v: k for k, v in PHYS_TO_INDEX.items()}
