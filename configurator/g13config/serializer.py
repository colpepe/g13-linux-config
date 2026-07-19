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
