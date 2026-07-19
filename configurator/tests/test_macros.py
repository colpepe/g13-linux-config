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
