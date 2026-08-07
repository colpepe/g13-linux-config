import pytest

from g13config.main_window import MainWindow
from g13config.store import ConfigStore


@pytest.fixture
def window(qapp, tmp_path):
    (tmp_path / "bindings-0.properties").write_text("name=FUSION 360\nG0=p,k.30\n")
    (tmp_path / "bindings-1.properties").write_text("name=GAMING\n")
    w = MainWindow(ConfigStore(tmp_path))
    yield w
    w.close()


def test_renaming_a_tab_updates_the_profile_and_marks_dirty(window):
    assert window.tabs.tabText(1) == "GAMING"

    window.tabs._begin_edit(1)
    window.tabs._editor.setText("Gaming 2")
    window.tabs._editor.returnPressed.emit()

    assert window.profiles[1].name == "Gaming 2"
    assert window.tabs.tabText(1) == "Gaming 2"
    assert 1 in window._dirty_slots()


def test_renaming_syncs_the_settings_panel_name_field(window):
    window.tabs.setCurrentIndex(1)
    window.tabs._begin_edit(1)
    window.tabs._editor.setText("Renamed")
    window.tabs._editor.returnPressed.emit()

    assert window.settings.name_edit.text() == "Renamed"


def test_clearing_a_name_falls_back_to_the_slot_label(window):
    window.tabs._begin_edit(1)
    window.tabs._editor.setText("")
    window.tabs._editor.returnPressed.emit()

    assert window.profiles[1].name == ""
    assert window.tabs.tabText(1) == "Slot 2"


def test_cancelled_rename_leaves_the_profile_untouched(window):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent

    window.tabs._begin_edit(0)
    window.tabs._editor.setText("discard me")
    window.tabs._editor.keyPressEvent(
        QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))

    assert window.profiles[0].name == "FUSION 360"
    assert window._dirty_slots() == []
