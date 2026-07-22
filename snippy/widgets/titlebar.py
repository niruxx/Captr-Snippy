"""CustomTitleBar - replaces the old hand-drawn macOS-style TrafficLights.
Flat Windows-style minimize/maximize/close vector-icon buttons (see
icons.py); dragging uses Qt's native `startSystemMove()` instead of the
old manual Win32 PostMessage(WM_NCLBUTTONDOWN) hack.
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from .. import icons
from ..theme import get_palette

ICON_SIZE = 13


class CustomTitleBar(QWidget):
    def __init__(self, window, title="Snippy", parent=None):
        super().__init__(parent)
        self._window = window
        self._col = get_palette(False)
        self.setObjectName("TitleBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(34)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 0, 0)
        layout.setSpacing(0)

        self._title_label = QLabel(title)
        self._title_label.setObjectName("TitleBarLabel")
        layout.addWidget(self._title_label)
        layout.addStretch(1)

        self._min_btn = self._make_button("minimize", "TitleBarButton")
        self._min_btn.clicked.connect(window.showMinimized)
        self._max_btn = self._make_button("maximize", "TitleBarButton")
        self._max_btn.clicked.connect(self._toggle_max)
        self._close_btn = self._make_button("close", "TitleBarCloseButton")
        self._close_btn.clicked.connect(window.close)

        for btn in (self._min_btn, self._max_btn, self._close_btn):
            layout.addWidget(btn)

        self._refresh_icons()

    def _make_button(self, icon_name, object_name):
        btn = QPushButton()
        btn.setObjectName(object_name)
        btn.setProperty("icon_name", icon_name)
        btn.setFixedSize(38, 34)
        btn.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        btn.setCursor(Qt.CursorShape.ArrowCursor)
        return btn

    def _refresh_icons(self):
        # the close button's icon turns white on hover (its background goes
        # red), but we only have a resting-state color here - QSS can't
        # drive an icon repaint on :hover, so we keep the icon in the
        # neutral text color and let the red fill do the contrast work.
        color = self._col["text_secondary"]
        for btn in (self._min_btn, self._max_btn, self._close_btn):
            btn.setIcon(icons.make_icon(btn.property("icon_name"), color))

    def set_palette(self, col):
        self._col = col
        self._refresh_icons()

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
