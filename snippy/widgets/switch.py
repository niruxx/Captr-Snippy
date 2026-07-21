"""ToggleSwitch - replaces GlassSwitch. QSS alone can't animate a sliding
knob position, so this stays a small custom-painted QWidget; everything
else (the track color blend, hover) is left to plain fills since the knob
slide is the only motion worth keeping from the original.
"""

from PySide6.QtCore import Property, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from ..anim import animate
from ..theme import blend, get_palette


class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, value=False, parent=None, width=44, height=26):
        super().__init__(parent)
        self.value = bool(value)
        self._pos = 1.0 if self.value else 0.0
        self._col = get_palette(False)
        self.setFixedSize(width, height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_palette(self, col):
        self._col = col
        self.update()

    def _get_pos(self):
        return self._pos

    def _set_pos(self, p):
        self._pos = p
        self.update()

    knobPos = Property(float, _get_pos, _set_pos)

    def toggle(self):
        self.value = not self.value
        animate(self, b"knobPos", self._pos, 1.0 if self.value else 0.0, duration=160)
        self.toggled.emit(self.value)

    def mousePressEvent(self, event):
        self.toggle()

    def paintEvent(self, event):
        col = self._col
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = h / 2
        track = blend(col["border_soft"], col["accent"], self._pos)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(track))
        painter.drawRoundedRect(QRectF(0, 0, w, h), r, r)

        kr = r - 3
        kx = r + self._pos * (w - 2 * r)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(kx - kr, h / 2 - kr, 2 * kr, 2 * kr))
