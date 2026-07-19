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
