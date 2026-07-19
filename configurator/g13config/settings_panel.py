"""Per-profile settings: name, LCD color, stick mode/speed/hold."""
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog, QComboBox, QFormLayout, QLineEdit, QPushButton, QSpinBox, QWidget,
)

from . import model
from .capture import KeyCaptureField


class ProfileSettingsPanel(QWidget):
    changed = Signal()
    editMacros = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._profile: model.Profile | None = None

        self.name_edit = QLineEdit()
        self.color_btn = QPushButton()
        self.mode_box = QComboBox()
        self.mode_box.addItems(["mouse", "keys"])
        self.speed = QSpinBox()
        self.speed.setRange(1, 50)
        self.hold = KeyCaptureField()
        self.macros_btn = QPushButton("Edit macros…")

        form = QFormLayout(self)
        form.addRow("Name", self.name_edit)
        form.addRow("LCD color", self.color_btn)
        form.addRow("Stick mode", self.mode_box)
        form.addRow("Stick speed", self.speed)
        form.addRow("Orbit hold", self.hold)
        form.addRow(self.macros_btn)

        self.name_edit.editingFinished.connect(self._apply)
        self.color_btn.clicked.connect(self._pick_color)
        self.mode_box.currentTextChanged.connect(lambda _t: self._apply())
        self.speed.valueChanged.connect(lambda _v: self._apply())
        self.hold.chordCaptured.connect(lambda _c: self._apply())
        self.macros_btn.clicked.connect(self.editMacros)

    def set_profile(self, p: model.Profile):
        self._profile = None  # mute _apply during sync
        self.name_edit.setText(p.name)
        self._set_swatch(p.color)
        self.mode_box.setCurrentText(p.stick.mode)
        self.speed.setValue(p.stick.speed)
        self.hold.codes = list(p.stick.hold)
        self.hold._render()
        self._profile = p

    def _set_swatch(self, color: tuple[int, int, int]):
        self.color_btn.setText(f"{color[0]}, {color[1]}, {color[2]}")
        self.color_btn.setStyleSheet(
            f"background-color: rgb({color[0]},{color[1]},{color[2]});")

    def _pick_color(self):
        if self._profile is None:
            return
        chosen = QColorDialog.getColor(QColor(*self._profile.color), self, "LCD color")
        if chosen.isValid():
            self._profile.color = (chosen.red(), chosen.green(), chosen.blue())
            self._set_swatch(self._profile.color)
            self.changed.emit()

    def _apply(self):
        p = self._profile
        if p is None:
            return
        p.name = self.name_edit.text()
        p.stick.mode = self.mode_box.currentText()
        p.stick.speed = self.speed.value()
        p.stick.hold = list(self.hold.codes)
        self.changed.emit()
