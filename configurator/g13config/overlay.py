"""Custom-painted G13 device overlay with clickable keys."""
from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

_KW, _KH, _GAP = 64, 46, 8          # keycap geometry
_ROW_X = {0: 20, 1: 20, 2: 92, 3: 164}  # row left offsets (rows 3/4 centered)


def _build_key_rects() -> dict[str, QRect]:
    rects: dict[str, QRect] = {}
    rows = [(1, 7, 0, 130), (8, 14, 1, 184), (15, 19, 2, 238), (20, 22, 3, 292)]
    for first, last, row, y in rows:
        for i, n in enumerate(range(first, last + 1)):
            rects[f"G{n}"] = QRect(_ROW_X[row] + i * (_KW + _GAP), y, _KW, _KH)
    rects["THUMB_LEFT"] = QRect(330, 356, 58, 34)
    rects["THUMB_DOWN"] = QRect(330, 398, 58, 34)
    rects["STICK_CLICK"] = QRect(398, 356, 58, 34)
    rects["STICK_UP"] = QRect(430, 398, 44, 26)
    rects["STICK_LEFT"] = QRect(398, 430, 44, 26)
    rects["STICK_RIGHT"] = QRect(462, 430, 44, 26)
    rects["STICK_DOWN"] = QRect(430, 462, 44, 26)
    return rects


class G13OverlayWidget(QWidget):
    keyClicked = Signal(str)

    KEY_RECTS = _build_key_rects()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._labels: dict[str, str] = {}
        self._tooltips: dict[str, str] = {}
        self._accent = QColor("#ff5000")
        self._hover: str | None = None
        self.setFixedSize(540, 505)
        self.setMouseTracking(True)

    def set_labels(self, labels: dict[str, str], tooltips: dict[str, str], accent: QColor):
        self._labels, self._tooltips, self._accent = labels, tooltips, accent
        self.update()

    def _key_at(self, pos) -> str | None:
        for name, rect in self.KEY_RECTS.items():
            if rect.contains(pos):
                return name
        return None

    def mouseMoveEvent(self, event):
        name = self._key_at(event.position().toPoint())
        if name != self._hover:
            self._hover = name
            self.setToolTip(self._tooltips.get(name, "") if name else "")
            self.update()

    def mousePressEvent(self, event):
        name = self._key_at(event.position().toPoint())
        if name:
            self.keyClicked.emit(name)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # Device body
        p.setBrush(QColor("#1b1d20"))
        p.setPen(QPen(QColor("#000000")))
        p.drawRoundedRect(4, 4, 532, 497, 24, 24)
        # LCD strip + M-row hint (orientation only, not interactive)
        p.setBrush(QColor("#0a0f08"))
        p.drawRoundedRect(110, 20, 320, 56, 4, 4)
        p.setPen(QColor(self._accent))
        p.setFont(QFont(self.font().family(), 10))
        p.drawText(QRect(110, 20, 320, 56), Qt.AlignCenter, self._labels.get("__lcd__", ""))
        p.setPen(QColor("#9aa0a8"))
        p.drawText(QRect(110, 84, 320, 20), Qt.AlignCenter, "M1    M2    M3    MR")
        # Keys
        small = QFont(self.font().family(), 7)
        big = QFont(self.font().family(), 9, QFont.Bold)
        for name, rect in self.KEY_RECTS.items():
            hovered = name == self._hover
            p.setBrush(QColor("#31353b") if hovered else QColor("#26292d"))
            p.setPen(QPen(QColor("#3daee9") if hovered else QColor("#101214"), 1.5))
            p.drawRoundedRect(rect, 6, 6)
            label = self._labels.get(name, "")
            p.setFont(small)
            p.setPen(QColor("#9aa0a8"))
            p.drawText(rect.adjusted(0, 3, 0, 0), Qt.AlignHCenter | Qt.AlignTop, name.replace("_", " "))
            p.setFont(big)
            p.setPen(self._accent if label else QColor("#565c64"))
            p.drawText(rect.adjusted(0, 10, 0, -2), Qt.AlignCenter, label or "·")
