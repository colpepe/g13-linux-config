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
