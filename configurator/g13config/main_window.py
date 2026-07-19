"""Main window: profile tabs, toolbar, overlay + settings panel row."""
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QTabBar, QToolBar, QVBoxLayout, QWidget

from . import labels as labels_mod
from .model import PHYS_TO_INDEX
from .overlay import G13OverlayWidget
from .store import ConfigStore

SLOTS = range(4)


class MainWindow(QMainWindow):
    def __init__(self, store: ConfigStore):
        super().__init__()
        self.store = store
        self.profiles = [store.load_profile(s) for s in SLOTS]
        self.macro_pool = store.load_macros()
        self.current_slot = 0

        self.setWindowTitle("G13 Configurator")
        self.toolbar = QToolBar("Main")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

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
        column.addLayout(self.central_row)
        column.addStretch()
        self.setCentralWidget(central)
        self.refresh_ui()

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
        from .model import PHYS_TO_INDEX
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

    def mark_dirty(self):
        """Dirty tracking arrives in Task 13."""
