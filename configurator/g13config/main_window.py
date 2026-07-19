"""Main window: profile tabs, toolbar, overlay + settings panel row."""
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QTabBar, QToolBar, QVBoxLayout, QWidget

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
        column.addLayout(self.central_row)
        column.addStretch()
        self.setCentralWidget(central)
        self._refresh_tab_chips()

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

    def refresh_ui(self):
        """Re-sync widgets from the current profile. Later tasks extend this."""
        self._refresh_tab_chips()

    def mark_dirty(self):
        """Dirty tracking arrives in Task 13."""
