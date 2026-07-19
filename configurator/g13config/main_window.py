"""Main window: profile tabs, toolbar, overlay + settings panel row."""
from PySide6.QtCore import QFileSystemWatcher
from PySide6.QtGui import QAction, QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QTabBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from . import labels as labels_mod
from .model import PHYS_TO_INDEX
from .overlay import G13OverlayWidget
from .serializer import serialize_profile
from .store import ConfigStore

SLOTS = range(4)


class MainWindow(QMainWindow):
    def __init__(self, store: ConfigStore):
        super().__init__()
        self.store = store
        self.profiles = [store.load_profile(s) for s in SLOTS]
        self.macro_pool = store.load_macros()
        self.current_slot = 0
        self._baseline = {p.slot: serialize_profile(p) for p in self.profiles}

        self.setWindowTitle("G13 Configurator")
        self.toolbar = QToolBar("Main")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        self.dirty_label = QLabel("")
        self.act_revert = QAction("Revert", self)
        self.act_apply = QAction("Apply", self)
        self.act_revert.triggered.connect(self.revert)
        self.act_apply.triggered.connect(self.apply)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(spacer)
        self.toolbar.addWidget(self.dirty_label)
        self.toolbar.addAction(self.act_revert)
        self.toolbar.addAction(self.act_apply)

        self.tabs = QTabBar()
        for p in self.profiles:
            self.tabs.addTab(p.name or f"Slot {p.slot + 1}")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        central = QWidget()
        column = QVBoxLayout(central)
        column.addWidget(self.tabs)
        self.central_row = QHBoxLayout()
        self.overlay = G13OverlayWidget()
        self.overlay.keyClicked.connect(self._on_key_clicked)
        self.central_row.addWidget(self.overlay)
        from .settings_panel import ProfileSettingsPanel
        self.settings = ProfileSettingsPanel()
        self.settings.changed.connect(self._on_settings_changed)
        self.settings.editMacros.connect(self._open_macro_editor)
        self.central_row.addWidget(self.settings)
        column.addLayout(self.central_row)
        column.addStretch()
        self.setCentralWidget(central)
        self.refresh_ui()

        self.watcher = QFileSystemWatcher([str(self.store.config_dir)], self)
        self.watcher.directoryChanged.connect(self._on_external_change)

        for p in self.profiles:
            if p.warnings:
                QMessageBox.warning(self, f"Slot {p.slot + 1} parse warnings", "\n".join(p.warnings))

    def current_profile(self):
        return self.profiles[self.current_slot]

    def _on_tab_changed(self, index: int):
        self.current_slot = index
        self.refresh_ui()

    def _refresh_tab_chips(self):
        for p in self.profiles:
            pix = QPixmap(12, 12)
            pix.fill(QColor(*p.color))
            self.tabs.setTabIcon(p.slot, QIcon(pix))
            self.tabs.setTabText(p.slot, p.name or f"Slot {p.slot + 1}")

    def _overlay_labels(self):
        p = self.current_profile()
        shorts = {"__lcd__": p.name}
        tips = {}
        for phys, idx in PHYS_TO_INDEX.items():
            binding = p.bindings.get(idx)
            shorts[phys] = labels_mod.short_label(binding, self.macro_pool)
            tips[phys] = labels_mod.long_label(binding, self.macro_pool)
        return shorts, tips

    def _on_key_clicked(self, phys: str):
        from .binding_dialog import BindingEditorDialog
        idx = PHYS_TO_INDEX[phys]
        profile = self.current_profile()
        dialog = BindingEditorDialog(phys, profile.bindings.get(idx), self.macro_pool, self)
        if dialog.exec():
            result = dialog.result_binding()
            if result is None:
                profile.bindings.pop(idx, None)
            else:
                profile.bindings[idx] = result
            self.mark_dirty()
            self.refresh_ui()

    def refresh_ui(self):
        self._refresh_tab_chips()
        shorts, tips = self._overlay_labels()
        self.overlay.set_labels(shorts, tips, QColor(*self.current_profile().color))
        self.settings.set_profile(self.current_profile())

    def _on_settings_changed(self):
        self.mark_dirty()
        self.refresh_ui()

    def _open_macro_editor(self):
        from .macro_editor import MacroEditorDialog
        MacroEditorDialog(self.store, self.macro_pool, self).exec()
        self.refresh_ui()  # macro names on keycaps may have changed

    def _dirty_slots(self) -> list[int]:
        return [p.slot for p in self.profiles if serialize_profile(p) != self._baseline[p.slot]]

    def mark_dirty(self):
        n = len(self._dirty_slots())
        self.dirty_label.setText(f"● {n} unsaved profile(s)  " if n else "")
        self.setWindowTitle("G13 Configurator" + (" *" if n else ""))

    def apply(self):
        for slot in self._dirty_slots():
            self.store.save_profile(self.profiles[slot])
            self._baseline[slot] = serialize_profile(self.profiles[slot])
        self.mark_dirty()

    def revert(self):
        self.profiles = [self.store.load_profile(s) for s in SLOTS]
        self._baseline = {p.slot: serialize_profile(p) for p in self.profiles}
        self.macro_pool = self.store.load_macros()
        self.mark_dirty()
        self.refresh_ui()
        for p in self.profiles:
            if p.warnings:
                QMessageBox.warning(self, f"Slot {p.slot + 1} parse warnings", "\n".join(p.warnings))

    def _on_external_change(self, _path: str):
        disk_state = {s: serialize_profile(self.store.load_profile(s)) for s in SLOTS}
        if disk_state == self._baseline:
            return  # our own write, or nothing semantically changed
        answer = QMessageBox.question(
            self, "Config changed on disk",
            "The G13 config was modified outside this tool.\n"
            "Reload from disk? (Unsaved edits here will be lost.)",
            QMessageBox.Yes | QMessageBox.No)
        if answer == QMessageBox.Yes:
            self.revert()
