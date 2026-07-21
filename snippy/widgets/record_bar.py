"""RecordControlBar - replaces _show_record_bar(). A small frameless,
translucent floating HUD (timer, pause/stop) shown while recording;
excluded from the recording itself via SetWindowDisplayAffinity. Dragging
uses Qt's native `startSystemMove()`.
"""

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from ..theme import get_palette
from ..win_integration import exclude_from_capture

WIDTH, HEIGHT = 240, 52


class RecordControlBar(QWidget):
    pauseClicked = Signal()
    stopClicked = Signal()

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(WIDTH, HEIGHT)
        self._col = get_palette(False)
        self._paused = False
        self._blink_on = True

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 8, 10, 8)
        self._dot = QLabel("●")
        layout.addWidget(self._dot)
        self._timer_label = QLabel("00:00")
        layout.addWidget(self._timer_label)
        layout.addStretch(1)
        self._pause_btn = QPushButton("⏸")
        self._pause_btn.setFixedSize(32, 32)
        self._pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pause_btn.clicked.connect(self.pauseClicked.emit)
        layout.addWidget(self._pause_btn)
        self._stop_btn = QPushButton("⏹")
        self._stop_btn.setFixedSize(32, 32)
        self._stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_btn.clicked.connect(self.stopClicked.emit)
        layout.addWidget(self._stop_btn)

        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink)
        self._blink_timer.start(500)

        self._apply_palette()

    def set_palette(self, col):
        self._col = col
        self._apply_palette()
        self.update()

    def _apply_palette(self):
        col = self._col
        style = f"""
            QLabel {{ background: transparent; color: {col['text']}; font-weight: 600; }}
            QPushButton {{ background: transparent; border: none; border-radius: 16px;
                          color: {col['text']}; font-size: 13px; }}
            QPushButton:hover {{ background: {col['hover']}; }}
        """
        self.setStyleSheet(style)

    def show_at_top_center(self, screen_geometry):
        x = screen_geometry.x() + (screen_geometry.width() - self.width()) // 2
        y = screen_geometry.y() + 18
        self.move(x, y)
        self.show()
        self.raise_()
        exclude_from_capture(self)

    def set_elapsed(self, seconds):
        self._timer_label.setText(f"{seconds // 60:02d}:{seconds % 60:02d}")

    def set_paused(self, paused):
        self._paused = paused
        self._pause_btn.setText("▶" if paused else "⏸")

    def _blink(self):
        col = self._col
        if self._paused:
            color = col["text_tertiary"]
        else:
            self._blink_on = not self._blink_on
            color = col["error"] if self._blink_on else col["surface_raised"]
        self._dot.setStyleSheet(f"color: {color}; background: transparent;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, self.width(), self.height()),
                            self.height() / 2, self.height() / 2)
        painter.fillPath(path, QColor(self._col["surface_raised"]))
        pen = painter.pen()
        pen.setColor(QColor(self._col["border"]))
        painter.setPen(pen)
        painter.drawPath(path)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.windowHandle()
            if handle is not None:
                handle.startSystemMove()
