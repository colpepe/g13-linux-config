"""Photo-realistic G13 device overlay with clickable keys.

The widget paints the real product photo (``assets/g13.png``, 645x1000)
scaled down by ``SCALE`` and draws hit-region chips/labels/hover outlines
directly over the photographed keycaps.
"""
from pathlib import Path

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

_ASSET = Path(__file__).parent / "assets" / "g13.png"

# Photo is 645x1000; the widget displays it scaled down by SCALE.
SCALE = 0.72
IMAGE_SIZE = (645, 1000)

# LCD text area, in IMAGE coordinates.
_LCD_RECT = QRect(205, 100, 240, 85)


def _build_key_rects() -> dict[str, QRect]:
    """Key hit-regions in IMAGE coordinates (645x1000 photo space)."""
    rects: dict[str, QRect] = {}

    row1_y, row1_h, row1_w = 312, 42, 62
    row1 = {"G1": 81, "G2": 152, "G3": 222, "G4": 291, "G5": 361, "G6": 429, "G7": 501}
    for name, x in row1.items():
        rects[name] = QRect(x, row1_y, row1_w, row1_h)

    row2_y = 382
    row2 = {"G8": 77, "G9": 147, "G10": 217, "G11": 291, "G12": 363, "G13": 433, "G14": 505}
    for name, x in row2.items():
        rects[name] = QRect(x, row2_y, row1_w, row1_h)

    row3_y, row3_w, row3_h = 450, 62, 44
    row3 = {"G15": 130, "G16": 214, "G17": 291, "G18": 365, "G19": 438}
    for name, x in row3.items():
        rects[name] = QRect(x, row3_y, row3_w, row3_h)

    row4_y, row4_w, row4_h = 516, 68, 40
    row4 = {"G20": 198, "G21": 287, "G22": 373}
    for name, x in row4.items():
        rects[name] = QRect(x, row4_y, row4_w, row4_h)

    rects["THUMB_LEFT"] = QRect(464, 590, 40, 70)
    rects["THUMB_DOWN"] = QRect(513, 668, 48, 60)
    rects["STICK_CLICK"] = QRect(546, 606, 44, 34)
    rects["STICK_UP"] = QRect(546, 584, 44, 20)
    rects["STICK_DOWN"] = QRect(546, 642, 44, 20)
    rects["STICK_LEFT"] = QRect(524, 606, 20, 34)
    rects["STICK_RIGHT"] = QRect(592, 606, 20, 34)

    return rects


def _scaled(rect: QRect) -> QRect:
    return QRect(
        int(rect.x() * SCALE),
        int(rect.y() * SCALE),
        int(rect.width() * SCALE),
        int(rect.height() * SCALE),
    )


class G13OverlayWidget(QWidget):
    keyClicked = Signal(str)

    KEY_RECTS = _build_key_rects()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._labels: dict[str, str] = {}
        self._tooltips: dict[str, str] = {}
        self._accent = QColor("#ff5000")
        self._hover: str | None = None
        self._pixmap: QPixmap | None = None
        self._scaled_pixmap: QPixmap | None = None
        self.setFixedSize(round(IMAGE_SIZE[0] * SCALE), round(IMAGE_SIZE[1] * SCALE))
        self.setMouseTracking(True)

    def set_labels(self, labels: dict[str, str], tooltips: dict[str, str], accent: QColor):
        self._labels, self._tooltips, self._accent = labels, tooltips, accent
        self.update()

    def _key_at(self, pos) -> str | None:
        for name, rect in self.KEY_RECTS.items():
            if _scaled(rect).contains(pos):
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

    def _ensure_pixmap(self):
        if self._pixmap is None:
            self._pixmap = QPixmap(str(_ASSET))
        if self._scaled_pixmap is None or self._scaled_pixmap.size() != self.size():
            self._scaled_pixmap = self._pixmap.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )

    def paintEvent(self, event):
        self._ensure_pixmap()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        p.drawPixmap(0, 0, self._scaled_pixmap)

        # LCD: current profile name, centered, with a small dark backdrop chip.
        lcd_rect = _scaled(_LCD_RECT)
        lcd_text = self._labels.get("__lcd__", "")
        if lcd_text:
            lcd_font = QFont(self.font().family(), 9, QFont.Bold)
            p.setFont(lcd_font)
            fm = QFontMetrics(lcd_font)
            text_w = min(lcd_rect.width() - 8, fm.horizontalAdvance(lcd_text) + 16)
            chip = QRect(0, 0, text_w, fm.height() + 6)
            chip.moveCenter(lcd_rect.center())
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 170))
            p.drawRoundedRect(chip, 4, 4)
            p.setPen(QColor(self._accent))
            elided = fm.elidedText(lcd_text, Qt.ElideRight, chip.width() - 8)
            p.drawText(chip, Qt.AlignCenter, elided)

        # Keys.
        label_font = QFont(self.font().family(), 8, QFont.Bold)
        fm = QFontMetrics(label_font)
        for name, rect in self.KEY_RECTS.items():
            disp = _scaled(rect)
            hovered = name == self._hover
            label = self._labels.get(name, "")

            if label:
                chip = QRect(
                    disp.x(),
                    disp.y() + disp.height() // 2,
                    disp.width(),
                    disp.height() - disp.height() // 2,
                )
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(0, 0, 0, 170))
                p.drawRoundedRect(chip, 4, 4)
                p.setFont(label_font)
                p.setPen(QColor(self._accent))
                elided = fm.elidedText(label, Qt.ElideRight, chip.width() - 4)
                p.drawText(chip, Qt.AlignCenter, elided)

            if hovered:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor("#3daee9"), 2))
                p.drawRoundedRect(disp.adjusted(1, 1, -1, -1), 5, 5)
