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
