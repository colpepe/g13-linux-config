from g13config import model


def test_phys_map_g_keys_are_zero_based():
    assert model.PHYS_TO_INDEX["G1"] == 0
    assert model.PHYS_TO_INDEX["G22"] == 21


def test_phys_map_thumb_and_stick():
    assert model.PHYS_TO_INDEX["THUMB_LEFT"] == 33
    assert model.PHYS_TO_INDEX["THUMB_DOWN"] == 34
    assert model.PHYS_TO_INDEX["STICK_CLICK"] == 35
    assert model.PHYS_TO_INDEX["STICK_UP"] == 36
    assert model.PHYS_TO_INDEX["STICK_LEFT"] == 37
    assert model.PHYS_TO_INDEX["STICK_RIGHT"] == 38
    assert model.PHYS_TO_INDEX["STICK_DOWN"] == 39


def test_phys_map_m_row():
    assert model.PHYS_TO_INDEX["M1"] == 29
    assert model.PHYS_TO_INDEX["M2"] == 30
    assert model.PHYS_TO_INDEX["M3"] == 31
    assert model.PHYS_TO_INDEX["MR"] == 32


def test_index_to_phys_is_inverse():
    for name, idx in model.PHYS_TO_INDEX.items():
        assert model.INDEX_TO_PHYS[idx] == name


def test_key_binding_is_combo():
    assert not model.KeyBinding([30]).is_combo()
    assert model.KeyBinding([29, 46]).is_combo()


def test_profile_defaults():
    p = model.Profile(slot=2)
    assert p.name == ""
    assert p.stick.mode == "keys"
    assert p.bindings == {}
    assert p.warnings == []
