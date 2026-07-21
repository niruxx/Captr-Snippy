"""Toast - replaces show_toast(). A small rounded pill, child of the main
window, that slides up from the bottom edge and auto-dismisses. Uses
QPropertyAnimation on the widget's native `pos` property instead of a
hand-rolled `after()` loop.
"""

from PySide6.QtCore import QPoint, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..anim import animate

DISMISS_DELAY_MS = 2400


class Toast(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("Toast")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        self._label = QLabel("")
        layout.addWidget(self._label)
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self._slide_out)
        self.hide()

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
