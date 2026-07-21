"""HistoryRail - replaces _render_history()'s thumbnail strip. A plain
QHBoxLayout of clickable thumbnail buttons; Qt's own widget lifecycle
handles pixmap/QIcon caching, so no manual PhotoImage-retention dance is
needed the way Tkinter required.
"""

from PIL import Image
from PIL.ImageQt import ImageQt
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

THUMB_W, THUMB_H = 112, 70


class HistoryRail(QWidget):
    selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(THUMB_H + 16)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 6, 0, 6)
        self._layout.setSpacing(10)
        self._layout.addStretch(1)
        self._col = None

    def set_palette(self, col):
        self._col = col

    def refresh(self, capture_state):
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        if not capture_state.history:
            placeholder = QLabel("Recent captures appear here")
            self._layout.addWidget(placeholder)
            self._layout.addStretch(1)
            return

        for i, image in enumerate(capture_state.history):
            thumb = image.copy()
            thumb.thumbnail((THUMB_W - 12, THUMB_H - 12), Image.Resampling.LANCZOS)
            pixmap = QPixmap.fromImage(ImageQt(thumb.convert("RGBA")))

            btn = QPushButton()
            btn.setIcon(QIcon(pixmap))
            btn.setIconSize(pixmap.size())
            btn.setFixedSize(THUMB_W, THUMB_H)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            selected = i == capture_state.history_index
            border_color = (self._col or {}).get(
                "accent" if selected else "border", "#888888")
            btn.setStyleSheet(
                f"border-radius: 10px; border: {'2px' if selected else '1px'} "
                f"solid {border_color}; background: transparent;")
            btn.clicked.connect(lambda _checked=False, idx=i: self.selected.emit(idx))
            self._layout.addWidget(btn)
        self._layout.addStretch(1)
