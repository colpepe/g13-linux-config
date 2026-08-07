import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Must be set before any Qt module is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """The one QApplication for the whole session; Qt forbids a second."""
    app = QApplication.instance() or QApplication([])
    yield app


def key_event(scancode: int, key, modifiers=Qt.NoModifier, text="") -> QKeyEvent:
    """A KeyPress carrying a real native scancode.

    QTest.keyClick cannot be used in this codebase: it leaves
    nativeScanCode() at 0, and keycodes.qt_native_to_evdev() subtracts 8,
    so every synthesized key would capture as -8. Native scancode is the
    evdev code + 8 (Tab 23 -> 15, Esc 9 -> 1, A 38 -> 30).
    """
    return QKeyEvent(QEvent.KeyPress, key, modifiers, scancode, 0, 0, text)
