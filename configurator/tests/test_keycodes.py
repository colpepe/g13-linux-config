from g13config import keycodes


def test_name_for_known_code():
    assert keycodes.name_for(30) == "KEY_A"
    assert keycodes.name_for(29) == "KEY_LEFTCTRL"


def test_name_for_unknown_code_falls_back():
    assert keycodes.name_for(9999) == "KEY_9999"


def test_label_for_pretty_names():
    assert keycodes.label_for(30) == "A"
    assert keycodes.label_for(29) == "Ctrl"
    assert keycodes.label_for(125) == "Super"
    assert keycodes.label_for(42) == "Shift"
    assert keycodes.label_for(111) == "Del"


def test_code_for_name():
    assert keycodes.code_for_name("KEY_A") == 30
    assert keycodes.code_for_name("NOPE") is None


def test_search_matches_substring_case_insensitive():
    results = keycodes.search("volume")
    codes = [c for c, _ in results]
    assert 114 in codes and 115 in codes  # VOLUMEDOWN, VOLUMEUP


def test_is_modifier():
    assert keycodes.is_modifier(29)      # LEFTCTRL
    assert keycodes.is_modifier(54)      # RIGHTSHIFT
    assert not keycodes.is_modifier(30)  # A


def test_qt_native_to_evdev_subtracts_xkb_offset():
    # xkb keycode = evdev + 8 on both X11 and Wayland
    assert keycodes.qt_native_to_evdev(38) == 30  # A
