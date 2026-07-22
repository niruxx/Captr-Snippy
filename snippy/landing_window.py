"""LandingWindow - the very first thing shown on launch: a small, compact
picker for "Screenshot" or "Record", so startup doesn't dump you straight
into the full capture/annotate window before you've said what you're here
to do. Picking either emits a signal; app.py owns building the real
MainWindow and wiring the picked action to it.
"""

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .anim import animate
from .rounded_mask import rounded_region
from .theme import build_qss, get_palette, system_dark_mode
from .widgets.buttons import ModernButton

WINDOW_SIZE = (360, 260)
WINDOW_RADIUS = 16
FADE_MS = 200


class LandingWindow(QWidget):
    screenshotRequested = Signal()
    recordRequested = Signal()

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("Snippy")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.dark = system_dark_mode()
        self._closing = False
        # set by app.py once the user has picked screenshot/record, so this
        # window's own close (triggered by that pick) doesn't also end the
        # app - only a direct user dismissal (the close button) should
        self.action_taken = False

        self._build_ui()
        self._apply_theme(self.dark)

        width, height = WINDOW_SIZE
        self.setFixedSize(width, height)
        screen = self.screen().availableGeometry() if self.screen() else None
        if screen:
            x = screen.x() + (screen.width() - width) // 2
            y = screen.y() + (screen.height() - height) // 2
        else:
            x = y = 200
        self.move(x, y)
        self._update_mask()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top = QHBoxLayout()
        top.setContentsMargins(8, 8, 8, 0)
        top.addStretch(1)
        close_btn = ModernButton(variant="plain", width=26, height=26,
                                 pill=True, icon_name="close", icon_size=12)
        close_btn.clicked.connect(self.close)
        top.addWidget(close_btn)
        root.addLayout(top)

        body = QVBoxLayout()
        body.setContentsMargins(32, 0, 32, 30)
        body.setSpacing(18)
        body.addStretch(1)

        self._title = QLabel("Snippy")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet("font-size: 19pt; font-weight: 700;")
        body.addWidget(self._title)

        self._subtitle = QLabel("What would you like to do?")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.addWidget(self._subtitle)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        shot_btn = ModernButton("  Screenshot", command=self.screenshotRequested.emit,
                                variant="primary", width=148, height=52,
                                icon_name="crop", icon_size=16)
        buttons.addWidget(shot_btn)
        record_btn = ModernButton("  Record", command=self.recordRequested.emit,
                                  variant="glass", width=118, height=52,
                                  icon_name="record", icon_size=14,
                                  icon_color_role="error")
        buttons.addWidget(record_btn)
        body.addLayout(buttons)
        body.addStretch(1)

        root.addLayout(body, 1)

    def _apply_theme(self, dark):
        self.dark = dark
        col = get_palette(dark)
        self.setStyleSheet(build_qss(col) + f"""
            QLabel {{ background: transparent; }}
        """)
        self._subtitle.setStyleSheet(f"color: {col['text_secondary']};")
        for widget in self.findChildren(QWidget):
            setter = getattr(widget, "set_palette", None)
            if callable(setter):
                setter(col)
        self.update()

    def _update_mask(self):
        self.setMask(rounded_region(self.width(), self.height(), WINDOW_RADIUS))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_mask()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = get_palette(self.dark)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(col["bg_top"]))
        gradient.setColorAt(1, QColor(col["bg_bottom"]))
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), WINDOW_RADIUS, WINDOW_RADIUS)
        painter.fillPath(path, gradient)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.windowHandle()
            if handle is not None:
                handle.startSystemMove()

    def closeEvent(self, event):
        if self._closing:
            super().closeEvent(event)
            # quitOnLastWindowClosed is disabled (see app.py); only end the
            # app here if the user dismissed the picker outright rather
            # than picking an action (which closes this window itself once
            # the real MainWindow is already up).
            if not self.action_taken:
                QApplication.instance().quit()
            return
        self._closing = True
        event.ignore()
        animate(self, b"windowOpacity", self.windowOpacity(), 0.0,
                duration=FADE_MS, on_finished=self.close)
