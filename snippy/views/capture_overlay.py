"""CaptureOverlay - replaces _create_overlay()/_on_mouse_down/drag/up. A
frameless, dimmed, translucent window spanning the full virtual desktop,
for dragging out a region-capture rectangle with a live width x height
readout. Coordinates emitted are in the same virtual-desktop space
`capture.virtual_screen()`/`ImageGrab.grab(all_screens=True)` use.
"""

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..capture import virtual_screen


class CaptureOverlay(QWidget):
    regionSelected = Signal(int, int, int, int)   # x1, y1, x2, y2 (global)
    cancelled = Signal()

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setWindowOpacity(0.35)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        virtual = virtual_screen()
        if virtual:
            vx, vy, vw, vh = virtual
        else:
            geo = self.screen().geometry() if self.screen() else QRect(0, 0, 1920, 1080)
            vx, vy, vw, vh = geo.x(), geo.y(), geo.width(), geo.height()
        self._origin = (vx, vy)
        self.setGeometry(vx, vy, vw, vh)

        self._start = None
        self._end = None
        self._active = False

    def showEvent(self, event):
        super().showEvent(event)
        self.activateWindow()
        self.setFocus()

    def mousePressEvent(self, event):
        pos = event.position()
        self._start = (pos.x(), pos.y())
        self._end = self._start
        self._active = True
        self.update()

    def mouseMoveEvent(self, event):
        if not self._active:
            return
        pos = event.position()
        self._end = (pos.x(), pos.y())
        self.update()

    def mouseReleaseEvent(self, event):
        if not self._active:
            return
        self._active = False
        pos = event.position()
        self._end = (pos.x(), pos.y())
        ox, oy = self._origin
        x1, x2 = sorted((self._start[0], self._end[0]))
        y1, y2 = sorted((self._start[1], self._end[1]))
        self.regionSelected.emit(int(x1 + ox), int(y1 + oy),
                                 int(x2 + ox), int(y2 + oy))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("black"))
        if not self._start or not self._end:
            return
        x0, y0 = self._start
        x1, y1 = self._end
        rect = QRect(int(min(x0, x1)), int(min(y0, y1)),
                     int(abs(x1 - x0)), int(abs(y1 - y0)))
        painter.fillRect(rect, QColor(255, 255, 255, 60))
        pen = QPen(QColor("white"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRect(rect)
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect.left() + 6, rect.top() - 8,
                         f"{rect.width()} × {rect.height()}")
