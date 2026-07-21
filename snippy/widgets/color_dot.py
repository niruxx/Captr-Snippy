"""ColorSwatch / WidthSwatch - small circular selectors for the annotation
toolbar's color and stroke-width palettes. Replaces ColorDot/WidthDot;
QPainter's native antialiasing means no supersample-then-downsample trick
is needed to get a smooth circle at any size.
"""

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QColor, QPainter, QPen

from ..theme import get_palette


class ColorSwatch(QWidget):
    clicked = Signal(str)

    def __init__(self, color, size=24, parent=None):
        super().__init__(parent)
        self.color = color
        self.selected = False
        self._col = get_palette(False)
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_palette(self, col):
        self._col = col
        self.update()

    def set_selected(self, selected):
        self.selected = selected
        self.update()

    def mousePressEvent(self, event):
        self.clicked.emit(self.color)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = min(self.width(), self.height())
        d = s - 10
        cx, cy = self.width() / 2, self.height() / 2
        if self.selected:
            pen = QPen(QColor(self._col["accent"]))
            pen.setWidthF(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(cx - d / 2 - 3, cy - d / 2 - 3, d + 6, d + 6))
        pen = QPen(QColor(self._col["border"]))
        pen.setWidthF(1)
        painter.setPen(pen)
        painter.setBrush(QColor(self.color))
        painter.drawEllipse(QRectF(cx - d / 2, cy - d / 2, d, d))


class WidthSwatch(QWidget):
    clicked = Signal(int)

    def __init__(self, width_value, size=24, parent=None):
        super().__init__(parent)
        self.width_value = width_value
        self.selected = False
        self._col = get_palette(False)
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_palette(self, col):
        self._col = col
        self.update()

    def set_selected(self, selected):
        self.selected = selected
        self.update()

    def mousePressEvent(self, event):
        self.clicked.emit(self.width_value)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2
        if self.selected:
            pen = QPen(QColor(self._col["accent"]))
            pen.setWidthF(1.5)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            inset = 3
            painter.drawEllipse(QRectF(inset, inset, self.width() - 2 * inset,
                                       self.height() - 2 * inset))
        d = 2 * (2 + self.width_value)
        fill = self._col["text"] if self.selected else self._col["text_secondary"]
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(fill))
        painter.drawEllipse(QRectF(cx - d / 2, cy - d / 2, d, d))
