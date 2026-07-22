"""ModernButton - replaces the old GlassButton. A plain QPushButton with a
`variant` dynamic property (primary/glass/plain) driving its QSS look, and
an optional `selected` toggle state (used for the annotation tool row).
Hover/press feedback comes from QSS `:hover`/`:pressed` pseudo-states - no
hand-rolled glow animation needed. Flat, modestly-rounded rectangles by
default (matching the app's DTK-style corner-radius scale); pass
`pill=True` for icon-only circular buttons (the toolbar/titlebar/overflow
icon-button convention), since the radius is set per-instance and depends
on height either way.

Icon-only buttons pass `icon_name` (see icons.py) instead of/alongside
`text`, drawing a themed vector icon rather than relying on a Unicode
glyph + font fallback (which rendered inconsistently, and wrong on
Windows for a few codepoints - see icons.py's docstring).
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QPushButton

from .. import icons
from ..theme import get_palette


class ModernButton(QPushButton):
    def __init__(self, text="", command=None, variant="glass",
                 width=None, height=32, pill=False, font=None,
                 icon_name=None, icon_size=16, icon_color_role=None, parent=None):
        super().__init__(text, parent)
        self.setProperty("variant", variant)
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._icon_name = icon_name
        self._icon_size = icon_size
        self._icon_color_role = icon_color_role
        self._col = get_palette(False)
        if font:
            self.setFont(font)
        if height:
            self.setFixedHeight(height)
        if width:
            self.setFixedWidth(width)
        radius = (height // 2) if pill else 8
        self.setStyleSheet(f"border-radius: {radius}px;")
        if command:
            self.clicked.connect(command)
        if variant == "primary":
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(20)
            shadow.setOffset(0, 5)
            shadow.setColor(QColor(0, 0, 0, 60))
            self.setGraphicsEffect(shadow)
        if icon_name:
            self.setIconSize(QSize(icon_size, icon_size))
            self._refresh_icon()
        self._repolish()

    def _repolish(self):
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()

    def _icon_color(self):
        if self._icon_color_role:
            return self._col[self._icon_color_role]
        if self.property("selected"):
            return self._col["accent"]
        if self.property("variant") == "primary":
            return self._col["accent_text"]
        return self._col["text"]

    def _refresh_icon(self):
        if not self._icon_name:
            return
        self.setIcon(icons.make_icon(self._icon_name, self._icon_color()))

    def set_palette(self, col):
        self._col = col
        self._refresh_icon()

    def set_selected(self, selected):
        self.setProperty("selected", bool(selected))
        self._repolish()
        self._refresh_icon()

    def is_selected(self):
        return bool(self.property("selected"))
