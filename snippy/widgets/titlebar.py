"""CustomTitleBar - replaces the old hand-drawn macOS-style TrafficLights.
Flat Windows-style minimize/maximize/close glyph buttons; dragging uses
Qt's native `startSystemMove()` instead of the old manual Win32
PostMessage(WM_NCLBUTTONDOWN) hack.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class CustomTitleBar(QWidget):
    def __init__(self, window, title="Snippy", parent=None):
        super().__init__(parent)
        self._window = window
        self.setObjectName("TitleBar")
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 0, 0)
        layout.setSpacing(0)

        self._title_label = QLabel(title)
        layout.addWidget(self._title_label)
        layout.addStretch(1)

        self._min_btn = self._make_button("−", "TitleBarButton")
        self._min_btn.clicked.connect(window.showMinimized)
        self._max_btn = self._make_button("□", "TitleBarButton")
        self._max_btn.clicked.connect(self._toggle_max)
        self._close_btn = self._make_button("×", "TitleBarCloseButton")
        self._close_btn.clicked.connect(window.close)

        for btn in (self._min_btn, self._max_btn, self._close_btn):
            layout.addWidget(btn)

    def _make_button(self, glyph, object_name):
        btn = QPushButton(glyph)
        btn.setObjectName(object_name)
        btn.setFixedSize(44, 36)
        btn.setCursor(Qt.CursorShape.ArrowCursor)
        return btn

    def _toggle_max(self):
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._window.windowHandle()
            if handle is not None:
                handle.startSystemMove()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_max()
