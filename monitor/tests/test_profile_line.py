import g13_monitor as m


def _state(tmp_path, reported, names=()):
    """Set up the driver's state file and bindings files.

    ``reported`` is what the driver writes to g13-profile, which is
    1-BASED (G13::loadBindings writes bindings + 1). ``names`` is indexed
    by 0-based slot, matching the bindings-N.properties filenames.
    """
    (tmp_path / "g13-profile").write_text(f"{reported}\n")
    for slot, name in enumerate(names):
        if name is not None:
            (tmp_path / f"bindings-{slot}.properties").write_text(
                f"# comment\nname={name}\ncolor=255,80,0\nG0=p,k.30\n")
    m.PROFILE_STATE_PATH = str(tmp_path / "g13-profile")
    m.CONFIG_DIR = str(tmp_path)


def test_reported_number_is_one_based_and_maps_to_the_previous_slot(tmp_path):
    # The regression this guards: reported "3" is slot 2, not slot 3.
    _state(tmp_path, 3, ["FUSION 360", "GAMING", "Fellowship", "GAMING (L4)"])
    assert m.get_active_profile_name() == "Fellowship"


def test_first_profile_reads_slot_zero(tmp_path):
    _state(tmp_path, 1, ["FUSION 360", "GAMING", "Fellowship", "GAMING (L4)"])
    assert m.get_active_profile_name() == "FUSION 360"


def test_last_profile_reads_slot_three(tmp_path):
    _state(tmp_path, 4, ["FUSION 360", "GAMING", "Fellowship", "GAMING (L4)"])
    assert m.get_active_profile_name() == "GAMING (L4)"


def test_header_still_shows_the_one_based_number(tmp_path):
    # The LCD header intentionally shows the physical key number.
    _state(tmp_path, 2, ["FUSION 360", "GAMING"])
    assert m.get_active_profile() == "2"
    assert "G13:2" in m.format_header_line()


def test_missing_bindings_file_gives_no_name(tmp_path):
    _state(tmp_path, 4)
    assert m.get_active_profile_name() is None


def test_unnamed_profile_gives_no_name(tmp_path):
    _state(tmp_path, 2, ["FUSION 360", ""])
    assert m.get_active_profile_name() is None


def test_zero_would_be_out_of_range(tmp_path):
    # Defensive: a 0 here would mean the driver stopped adding 1.
    _state(tmp_path, 0, ["FUSION 360"])
    assert m.get_active_profile_name() is None


def test_unreadable_profile_state_gives_no_name(tmp_path):
    m.PROFILE_STATE_PATH = str(tmp_path / "does-not-exist")
    m.CONFIG_DIR = str(tmp_path)
    assert m.get_active_profile_name() is None


def test_line_is_centered_at_full_width():
    line = m.format_profile_line("Fellowship")
    assert len(line) == m.LCD_WIDTH
    assert line.strip() == "Profile: Fellowship"
    # 26 - 19 = 7 spaces of padding, 3 leading and 4 trailing.
    assert line == "   Profile: Fellowship    "


def test_line_centers_a_shorter_name():
    line = m.format_profile_line("GAMING")
    assert len(line) == m.LCD_WIDTH
    assert line.strip() == "Profile: GAMING"


def test_long_name_is_truncated_to_the_lcd_width():
    line = m.format_profile_line("A" * 40)
    assert len(line) == m.LCD_WIDTH
    assert line.startswith("Profile: ")
    assert line == "Profile: " + "A" * 17


def test_blank_when_no_name_is_available():
    assert m.format_profile_line(None) == ""
    assert m.format_profile_line("") == ""
