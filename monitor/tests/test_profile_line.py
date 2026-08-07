import g13_monitor as m


def _state(tmp_path, number, name=None, slot=None):
    """Writes the driver's profile-state file and a matching bindings file."""
    (tmp_path / "g13-profile").write_text(f"{number}\n")
    if name is not None:
        slot = number if slot is None else slot
        (tmp_path / f"bindings-{slot}.properties").write_text(
            f"# comment\nname={name}\ncolor=255,80,0\nG0=p,k.30\n")
    m.PROFILE_STATE_PATH = str(tmp_path / "g13-profile")
    m.CONFIG_DIR = str(tmp_path)


def test_reads_name_of_the_active_profile(tmp_path):
    _state(tmp_path, 2, "Fellowship")
    assert m.get_active_profile_name() == "Fellowship"


def test_follows_the_active_profile_number(tmp_path):
    _state(tmp_path, 0, "FUSION 360")
    (tmp_path / "bindings-2.properties").write_text("name=Fellowship\n")
    assert m.get_active_profile_name() == "FUSION 360"


def test_missing_bindings_file_gives_no_name(tmp_path):
    _state(tmp_path, 3)
    assert m.get_active_profile_name() is None


def test_unnamed_profile_gives_no_name(tmp_path):
    _state(tmp_path, 1, "")
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
