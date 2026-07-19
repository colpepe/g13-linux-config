"""Per-key binding editor: key/combo, macro, mouse pan, or unbound."""
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QRadioButton, QSpinBox, QVBoxLayout,
)

from . import keycodes, model
from .capture import KeyCaptureField
from .macros import Macro


class BindingEditorDialog(QDialog):
    def __init__(self, phys: str, current: model.Binding | None,
                 macro_pool: dict[int, Macro], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Bind {phys.replace('_', ' ')}")
        self._macro_ids = sorted(macro_pool)

        self.r_key = QRadioButton("Key or combo")
        self.r_macro = QRadioButton("Macro")
        self.r_pan = QRadioButton("Mouse pan")
        self.r_none = QRadioButton("Unbound")

        self.capture = KeyCaptureField()
        self.key_list = QComboBox()
        self.key_list.setEditable(True)
        self.key_list.setPlaceholderText("or pick a key by name…")
        for code, name in keycodes.search(""):
            self.key_list.addItem(name, userData=code)
        self.key_list.setCurrentIndex(-1)
        self.key_list.activated.connect(self._key_picked_from_list)

        self.macro_box = QComboBox()
        for mid in self._macro_ids:
            m = macro_pool[mid]
            self.macro_box.addItem(f"{mid}: {m.name or '(unnamed)'}", userData=mid)
        self.repeats = QSpinBox()
        self.repeats.setRange(0, 100)

        self.pan_dx = QSpinBox(); self.pan_dx.setRange(-100, 100)
        self.pan_dy = QSpinBox(); self.pan_dy.setRange(-100, 100)
        self.pan_hold = KeyCaptureField()

        form = QVBoxLayout(self)
        form.addWidget(self.r_key)
        key_row = QHBoxLayout()
        key_row.addWidget(self.capture); key_row.addWidget(self.key_list)
        form.addLayout(key_row)
        form.addWidget(self.r_macro)
        macro_row = QHBoxLayout()
        macro_row.addWidget(self.macro_box); macro_row.addWidget(QLabel("repeats")); macro_row.addWidget(self.repeats)
        form.addLayout(macro_row)
        form.addWidget(self.r_pan)
        pan_form = QFormLayout()
        pan_form.addRow("dx", self.pan_dx); pan_form.addRow("dy", self.pan_dy)
        pan_form.addRow("hold", self.pan_hold)
        form.addLayout(pan_form)
        form.addWidget(self.r_none)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)

        self._load_current(current)

    def _load_current(self, b: model.Binding | None):
        if isinstance(b, model.KeyBinding):
            self.r_key.setChecked(True)
            self.capture.codes = list(b.codes)
            self.capture._render()
        elif isinstance(b, model.MacroBinding):
            self.r_macro.setChecked(True)
            if b.macro_id in self._macro_ids:
                self.macro_box.setCurrentIndex(self._macro_ids.index(b.macro_id))
            self.repeats.setValue(b.repeats)
        elif isinstance(b, model.MousePanBinding):
            self.r_pan.setChecked(True)
            self.pan_dx.setValue(b.dx); self.pan_dy.setValue(b.dy)
            self.pan_hold.codes = list(b.hold or [])
            self.pan_hold._render()
        else:
            self.r_none.setChecked(True)

    def _key_picked_from_list(self, index: int):
        code = self.key_list.itemData(index)
        if code is not None:
            self.capture.codes = [code]
            self.capture._render()
            self.r_key.setChecked(True)

    def result_binding(self) -> model.Binding | None:
        if self.r_key.isChecked() and self.capture.codes:
            return model.KeyBinding(codes=list(self.capture.codes))
        if self.r_macro.isChecked() and self.macro_box.currentData() is not None:
            return model.MacroBinding(macro_id=self.macro_box.currentData(),
                                      repeats=self.repeats.value())
        if self.r_pan.isChecked():
            hold = list(self.pan_hold.codes) or None
            return model.MousePanBinding(dx=self.pan_dx.value(), dy=self.pan_dy.value(), hold=hold)
        return None
