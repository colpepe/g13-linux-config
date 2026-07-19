"""Macro pool editor: steps (down/up/delay) with record mode."""
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QInputDialog, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QVBoxLayout,
)

from . import keycodes
from .macros import Macro, MacroStep, serialize_macro


def _step_text(s: MacroStep) -> str:
    if s.kind == "delay":
        return f"⏱ delay {s.value} ms"
    arrow = "↓" if s.kind == "down" else "↑"
    return f"{arrow} {s.kind} {keycodes.label_for(s.value)}"


class MacroEditorDialog(QDialog):
    def __init__(self, store, macro_pool: dict[int, Macro], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Macro editor")
        self.store = store
        self.pool = macro_pool
        self._current: Macro | None = None
        self._recording = False
        self._last_event = 0.0

        self.macro_list = QListWidget()
        self.name_edit = QLineEdit()
        self.steps = QListWidget()
        self.new_btn = QPushButton("New macro")
        self.record_btn = QPushButton("● Record")
        self.add_delay_btn = QPushButton("＋ Delay")
        self.del_step_btn = QPushButton("− Step")
        self.save_btn = QPushButton("Save macro")

        left = QVBoxLayout()
        left.addWidget(self.macro_list)
        left.addWidget(self.new_btn)
        right = QVBoxLayout()
        right.addWidget(self.name_edit)
        right.addWidget(self.steps)
        step_row = QHBoxLayout()
        for b in (self.record_btn, self.add_delay_btn, self.del_step_btn, self.save_btn):
            step_row.addWidget(b)
        right.addLayout(step_row)
        row = QHBoxLayout()
        row.addLayout(left)
        row.addLayout(right)
        root = QVBoxLayout(self)
        root.addLayout(row)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.reject)
        root.addWidget(close)

        self.macro_list.currentItemChanged.connect(self._select_macro)
        self.new_btn.clicked.connect(self._new_macro)
        self.record_btn.clicked.connect(self._toggle_record)
        self.add_delay_btn.clicked.connect(self._add_delay)
        self.del_step_btn.clicked.connect(self._delete_step)
        self.save_btn.clicked.connect(self._save)
        self._reload_list()

    def _reload_list(self):
        self.macro_list.clear()
        for mid in sorted(self.pool):
            item = QListWidgetItem(f"{mid}: {self.pool[mid].name or '(unnamed)'}")
            item.setData(Qt.UserRole, mid)
            self.macro_list.addItem(item)

    def _select_macro(self, item, _prev=None):
        if item is None:
            return
        self._current = self.pool[item.data(Qt.UserRole)]
        self.name_edit.setText(self._current.name)
        self._reload_steps()

    def _reload_steps(self):
        self.steps.clear()
        if self._current:
            for s in self._current.steps:
                self.steps.addItem(_step_text(s))

    def _new_macro(self):
        mid = self.store.next_free_macro_id()
        name, ok = QInputDialog.getText(self, "New macro", "Name:")
        if not ok:
            return
        self.pool[mid] = Macro(id=mid, name=name)
        self._reload_list()
        self.macro_list.setCurrentRow(sorted(self.pool).index(mid))

    def _toggle_record(self):
        if self._current is None:
            return
        self._recording = not self._recording
        if self._recording:
            self._current.steps = []
            self._last_event = time.monotonic()
            self.record_btn.setText("■ Stop")
            self.grabKeyboard()
        else:
            self.record_btn.setText("● Record")
            self.releaseKeyboard()
            self._reload_steps()

    def _record_step(self, kind: str, code: int):
        now = time.monotonic()
        gap_ms = int((now - self._last_event) * 1000)
        self._last_event = now
        if self._current.steps and gap_ms >= 5:
            self._current.steps.append(MacroStep("delay", min(gap_ms, 5000)))
        self._current.steps.append(MacroStep(kind, code))
        self._reload_steps()

    def keyPressEvent(self, event):
        if self._recording and not event.isAutoRepeat():
            if event.key() == Qt.Key_Escape:
                self._toggle_record()
                return
            self._record_step("down", keycodes.qt_native_to_evdev(event.nativeScanCode()))
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if self._recording and not event.isAutoRepeat():
            self._record_step("up", keycodes.qt_native_to_evdev(event.nativeScanCode()))
            return
        super().keyReleaseEvent(event)

    def _add_delay(self):
        if self._current is None:
            return
        ms, ok = QInputDialog.getInt(self, "Delay", "Milliseconds:", 5, 1, 5000)
        if ok:
            row = self.steps.currentRow()
            pos = row + 1 if row >= 0 else len(self._current.steps)
            self._current.steps.insert(pos, MacroStep("delay", ms))
            self._reload_steps()

    def _delete_step(self):
        row = self.steps.currentRow()
        if self._current is not None and row >= 0:
            del self._current.steps[row]
            self._reload_steps()

    def _save(self):
        if self._current is None:
            return
        self._current.name = self.name_edit.text()
        self.store.save_macro(self._current)
        self._reload_list()
