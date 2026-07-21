"""SegmentedControl - replaces GlassSegmented. Qt has no native segmented
control, so this stays a custom-painted QWidget (the one widget category
where hand-rolled painting is still the right call), but drawing itself is
now a few native QPainter calls instead of PIL supersample-then-downsample.
"""

from PySide6.QtCore import Property, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

from ..anim import animate
from ..theme import get_palette


class SegmentedControl(QWidget):
    valueChanged = Signal(str)

    PAD = 3

    def __init__(self, options, value=None, seg_width=86, height=32, parent=None):
        super().__init__(parent)
        self.options = list(options)
        self.value = value if value in self.options else (self.options[0] if self.options else None)
        self.seg_width = seg_width
        self._col = get_palette(False)
        self._thumb_x = float(self._target_x(self._index()))
        self.setFixedSize(seg_width * len(self.options) + 2 * self.PAD, height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_palette(self, col):
        self._col = col
        self.update()

    def _index(self):
        try:
            return self.options.index(self.value)
        except ValueError:
            return 0

    def _target_x(self, index):
        return self.PAD + index * self.seg_width

    def set_value(self, value, animated=True):
        if value not in self.options or value == self.value:
            return
        self.value = value
        target = self._target_x(self._index())
        if animated:
            animate(self, b"thumbX", self._thumb_x, target, duration=180)
        else:
            self.thumbX = target

    def _get_thumb_x(self):
        return self._thumb_x

    def _set_thumb_x(self, x):
        self._thumb_x = x
        self.update()

    thumbX = Property(float, _get_thumb_x, _set_thumb_x)

    def mousePressEvent(self, event):
        index = int((event.position().x() - self.PAD) // self.seg_width)
        index = max(0, min(len(self.options) - 1, index))
        name = self.options[index]
        if name == self.value:
            return
        self.set_value(name)
        self.valueChanged.emit(name)

    def paintEvent(self, event):
        col = self._col
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        track = QPainterPath()
        track.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), h / 2, h / 2)
        painter.fillPath(track, QColor(col["border_soft"]))

        thumb_h = h - 2 * self.PAD
        thumb = QPainterPath()
        thumb.addRoundedRect(QRectF(self._thumb_x, self.PAD, self.seg_width, thumb_h),
                             thumb_h / 2, thumb_h / 2)
        painter.fillPath(thumb, QColor(col["surface_raised"]))
        pen = painter.pen()
        pen.setColor(QColor(col["border"]))
        pen.setWidthF(1)
        painter.setPen(pen)
        painter.drawPath(thumb)

        painter.setPen(QColor(col["text"]))
        for i, name in enumerate(self.options):
            rect = QRectF(self.PAD + i * self.seg_width, 0, self.seg_width, h)
            selected = name == self.value
            painter.setPen(QColor(col["text"] if selected else col["text_secondary"]))
            font = painter.font()
            font.setBold(selected)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, name)
