"""ModernButton - replaces the old GlassButton. A plain QPushButton with a
`variant` dynamic property (primary/glass/plain) driving its QSS look, and
an optional `selected` toggle state (used for the annotation tool row).
Hover/press feedback comes from QSS `:hover`/`:pressed` pseudo-states - no
hand-rolled glow animation needed.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton


class ModernButton(QPushButton):
    def __init__(self, text="", command=None, variant="glass",
                 width=None, height=36, parent=None):
        super().__init__(text, parent)
        self.setProperty("variant", variant)
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if height:
            self.setFixedHeight(height)
        if width:
            self.setFixedWidth(width)
        if command:
            self.clicked.connect(command)
        self._repolish()

    def _repolish(self):
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()

    def set_selected(self, selected):
        self.setProperty("selected", bool(selected))
        self._repolish()

    def is_selected(self):
        return bool(self.property("selected"))
