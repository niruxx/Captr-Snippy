"""Toast - replaces show_toast(). A small rounded glass pill, child of the
main window, that slides up from the bottom edge and auto-dismisses. Uses
QPropertyAnimation on the widget's native `pos` property instead of a
hand-rolled `after()` loop. Paints its own translucent rounded background
(a plain QWidget won't render QSS `border-radius` without WA_StyledBackground,
so it self-paints like the other floating glass pills).
"""

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (QGraphicsDropShadowEffect, QLabel,
                               QVBoxLayout, QWidget)

from ..anim import animate
from ..theme import GLASS_STRONG, get_palette, qcolor

DISMISS_DELAY_MS = 2400


class Toast(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("Toast")
        self._col = get_palette(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 10)
        self._label = QLabel("")
        layout.addWidget(self._label)
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self._slide_out)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.setGraphicsEffect(shadow)
        self.hide()

    def set_palette(self, col):
        self._col = col
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = self._col
        path = QPainterPath()
        radius = self.height() / 2
        path.addRoundedRect(QRectF(0, 0, self.width(), self.height()), radius, radius)
        painter.fillPath(path, qcolor(col["tint"], GLASS_STRONG))
        pen = painter.pen()
        pen.setColor(QColor(col["highlight_edge"]))
        painter.setPen(pen)
        painter.drawPath(path)

    def show_message(self, message):
        self._dismiss_timer.stop()
        self._label.setText(message)
        self.adjustSize()
        parent = self.parentWidget()
        if parent is None:
            return
        x = (parent.width() - self.width()) // 2
        rest_y = parent.height() - self.height() - 28
        start_y = parent.height() + 10
        self.move(x, start_y)
        self.show()
        self.raise_()
        animate(self, b"pos", QPoint(x, start_y), QPoint(x, rest_y), duration=200,
                on_finished=lambda: self._dismiss_timer.start(DISMISS_DELAY_MS))

    def _slide_out(self):
        parent = self.parentWidget()
        if parent is None:
            self.hide()
            return
        start = self.pos()
        end = QPoint(start.x(), parent.height() + 10)
        animate(self, b"pos", start, end, duration=200, on_finished=self.hide)
