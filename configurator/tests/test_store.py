import pytest

from g13config import macros, model
from g13config.store import ConfigStore


@pytest.fixture
def store(tmp_path):
    return ConfigStore(config_dir=tmp_path)


def test_load_missing_profile_returns_empty(store):
    p = store.load_profile(2)
    assert p.slot == 2 and p.bindings == {} and p.name == ""


def test_profile_save_load_round_trip(store):
    p = model.Profile(slot=0, name="X", color=(1, 2, 3))
    p.bindings[5] = model.KeyBinding([29, 46])
    store.save_profile(p)
    loaded = store.load_profile(0)
    assert loaded.name == "X" and loaded.bindings == p.bindings


def test_macro_save_load(store):
    m = macros.Macro(id=7, name="M", steps=[macros.MacroStep("down", 30), macros.MacroStep("up", 30)])
    store.save_macro(m)
    assert store.load_macros() == {7: m}


def test_next_free_macro_id_skips_used(store):
    store.save_macro(macros.Macro(id=0, name="a"))
    store.save_macro(macros.Macro(id=1, name="b"))
    assert store.next_free_macro_id() == 2


def test_templates_save_list_load(store):
    p = model.Profile(slot=1, name="FUSION 360")
    p.bindings[0] = model.KeyBinding([30])
    store.save_template(p, "fusion-360")
    assert store.list_templates() == ["fusion-360"]
    t = store.load_template("fusion-360")
    assert t.slot == -1
    assert t.name == "FUSION 360" and t.bindings == p.bindings


def test_list_templates_empty_when_no_dir(store):
    assert store.list_templates() == []
