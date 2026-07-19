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
    assert (target.stat().st_mode & 0o777) == 0o644  # fresh file gets 644
    target.chmod(0o600)
    atomic_write(target, "name=Z\n")
    assert (target.stat().st_mode & 0o777) == 0o600  # existing mode preserved
