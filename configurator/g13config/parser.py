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
