"""RecordControlBar - replaces _show_record_bar(). A small frameless,
translucent floating HUD (timer, pause/stop) shown while recording;
excluded from the recording itself via SetWindowDisplayAffinity. Dragging
uses Qt's native `startSystemMove()`.
"""

from PySide6.QtCore import QRectF, Qt, QSize, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
                               QPushButton, QWidget)

from .. import icons
from ..theme import GLASS_STRONG, get_palette, qcolor
from ..win_integration import exclude_from_capture

WIDTH, HEIGHT = 208, 46


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
        layout.setContentsMargins(16, 6, 8, 6)
        self._dot = QLabel()
        self._dot.setFixedSize(12, 12)
        layout.addWidget(self._dot)
        self._timer_label = QLabel("00:00")
        layout.addWidget(self._timer_label)
        layout.addStretch(1)
        self._pause_btn = QPushButton()
        self._pause_btn.setIconSize(QSize(12, 12))
        self._pause_btn.setFixedSize(28, 28)
        self._pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pause_btn.clicked.connect(self.pauseClicked.emit)
        layout.addWidget(self._pause_btn)
        self._stop_btn = QPushButton()
        self._stop_btn.setIconSize(QSize(12, 12))
        self._stop_btn.setFixedSize(28, 28)
        self._stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_btn.clicked.connect(self.stopClicked.emit)
        layout.addWidget(self._stop_btn)

        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink)
        self._blink_timer.start(500)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.setGraphicsEffect(shadow)

        self._apply_palette()
        self._refresh_icons()

    def set_palette(self, col):
        self._col = col
        self._apply_palette()
        self._refresh_icons()
        self.update()

    def _apply_palette(self):
        col = self._col
        style = f"""
            QLabel {{ background: transparent; }}
            QPushButton {{ background: transparent; border: none; border-radius: 16px; }}
            QPushButton:hover {{ background: {col['hover']}; }}
        """
        self.setStyleSheet(style)

    def _refresh_icons(self):
        col = self._col
        self._pause_btn.setIcon(icons.make_icon("play" if self._paused else "pause", col["text"]))
        self._stop_btn.setIcon(icons.make_icon("stop", col["text"]))
        if self._paused:
            dot_color = col["text_tertiary"]
        else:
            dot_color = col["error"] if self._blink_on else col["text_tertiary"]
        self._dot.setPixmap(icons.make_pixmap("record", dot_color, size=12))

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
        self._refresh_icons()

    def _blink(self):
        if not self._paused:
            self._blink_on = not self._blink_on
        self._refresh_icons()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, self.width(), self.height()),
                            self.height() / 2, self.height() / 2)
        painter.fillPath(path, qcolor(self._col["tint"], GLASS_STRONG))
        pen = painter.pen()
        pen.setColor(QColor(self._col["highlight_edge"]))
        painter.setPen(pen)
        painter.drawPath(path)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.windowHandle()
            if handle is not None:
                handle.startSystemMove()
