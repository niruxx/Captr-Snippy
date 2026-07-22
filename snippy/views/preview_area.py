"""PreviewArea - wraps PreviewCanvas and overlays the floating
ContextualToolbar on top of it (bottom-center), fading it in only while
there's a capture to annotate and fading it out otherwise, so an empty
main page stays minimal.
"""

from PySide6.QtCore import QPropertyAnimation, Qt
from PySide6.QtWidgets import QGraphicsOpacityEffect, QVBoxLayout, QWidget

from ..widgets.float_toolbar import ContextualToolbar
from .preview_canvas import PreviewCanvas

BOTTOM_MARGIN = 18


class PreviewArea(QWidget):
    def __init__(self, capture_state, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.preview = PreviewCanvas(capture_state)
        layout.addWidget(self.preview)

        self.toolbar = ContextualToolbar(self)
        self._opacity = QGraphicsOpacityEffect(self.toolbar)
        self._opacity.setOpacity(0.0)
        self.toolbar.setGraphicsEffect(self._opacity)
        self.toolbar.hide()
        self._visible = False
        self._anim = None
        self._reposition_toolbar()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_toolbar()

    def _reposition_toolbar(self):
        bar = self.toolbar
        bar.adjustSize()
        x = (self.width() - bar.width()) // 2
        y = self.height() - bar.height() - BOTTOM_MARGIN
        bar.move(max(0, x), max(0, y))
        bar.raise_()

    def set_toolbar_visible(self, visible):
        if visible == self._visible:
            return
        self._visible = visible
        self._reposition_toolbar()
        if self._anim:
            self._anim.stop()
        if visible:
            self.toolbar.show()
        target = 1.0 if visible else 0.0
        anim = QPropertyAnimation(self._opacity, b"opacity", self)
        anim.setDuration(180)
        anim.setStartValue(self._opacity.opacity())
        anim.setEndValue(target)
        if not visible:
            anim.finished.connect(self.toolbar.hide)
        anim.start()
        self._anim = anim
