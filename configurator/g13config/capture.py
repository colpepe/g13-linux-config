"""Chord capture: press the real keys, get evdev codes."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPushButton

from . import keycodes


class KeyCaptureField(QPushButton):
    chordCaptured = Signal(list)

    _QT_BUTTON_CODES = {
        Qt.LeftButton: 272, Qt.RightButton: 273, Qt.MiddleButton: 274,
        Qt.BackButton: 275, Qt.ForwardButton: 276,
    }

    def __init__(self, codes: list[int] | None = None, parent=None):
        super().__init__(parent)
        self.codes: list[int] = list(codes or [])
        self._armed = False
        self._held_mods: list[int] = []
        self.clicked.connect(self._arm)
        self._render()

    def _render(self):
        if self._armed:
            held = "+".join(keycodes.label_for(c) for c in self._held_mods)
            self.setText(f"{held}+…" if held else "Press keys… (Esc cancels)")
        else:
            self.setText("+".join(keycodes.label_for(c) for c in self.codes) or "Click to set")

    def _arm(self):
        self._armed = True
        self._held_mods = []
        self.grabKeyboard()
        self._render()

    def _disarm(self):
        self._armed = False
        self.releaseKeyboard()
        self._render()

    def disarm(self):
        if self._armed:
            self._disarm()

    def keyPressEvent(self, event):
        if not self._armed:
            return super().keyPressEvent(event)
        if event.key() == Qt.Key_Escape:
            self._disarm()
            return
        code = keycodes.qt_native_to_evdev(event.nativeScanCode())
        if keycodes.is_modifier(code):
            if code not in self._held_mods:
                self._held_mods.append(code)
            self._render()
        else:
            self.codes = self._held_mods + [code]
            self._disarm()
            self.chordCaptured.emit(self.codes)

    def keyReleaseEvent(self, event):
        if not self._armed:
            return super().keyReleaseEvent(event)
        code = keycodes.qt_native_to_evdev(event.nativeScanCode())
        if code in self._held_mods:
            self._held_mods.remove(code)
            self._render()

    def focusOutEvent(self, event):
        if self._armed:
            self._disarm()
        super().focusOutEvent(event)

    def mousePressEvent(self, event):
        if self._armed:
            code = self._QT_BUTTON_CODES.get(event.button())
            if code is not None:
                self.codes = self._held_mods + [code]
                self._disarm()
                self.chordCaptured.emit(self.codes)
            return
        super().mousePressEvent(event)
