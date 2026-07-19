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
