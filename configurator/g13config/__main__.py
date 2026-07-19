import sys

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .store import ConfigStore


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("G13 Configurator")
    window = MainWindow(ConfigStore())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
