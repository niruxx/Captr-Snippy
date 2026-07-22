"""ContextualToolbar - the annotation tool row, recolor/rewidth swatches,
and undo button, pulled out of the always-visible header into a floating
glass pill that only appears over the preview while there's a capture to
edit (like iOS Photos' edit toolbar) - keeping the main page minimal.
"""

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
                               QWidget)

from ..settings import ANNOT_COLORS, ANNOT_WIDTHS
from ..theme import GLASS_STRONG, get_palette, qcolor
from .buttons import ModernButton
from .color_dot import ColorSwatch, WidthSwatch

# tool name doubles as its icons.py drawer name
TOOLS = (
    ("pen",       "Pen"),
    ("highlight", "Highlighter"),
    ("line",      "Line"),
    ("arrow",     "Arrow"),
    ("rect",      "Rectangle"),
    ("ellipse",   "Ellipse"),
    ("text",      "Text"),
    ("redact",    "Redact / pixelate"),
    ("picker",    "Color picker"),
    ("crop",      "Crop"),
)


class ContextualToolbar(QWidget):
    toolSelected = Signal(str)
    colorSelected = Signal(str)
    widthSelected = Signal(int)
    undoRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._col = get_palette(False)
        self.tool_buttons = {}
        self.color_swatches = {}
        self.width_swatches = {}
        self.setFixedHeight(50)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        for name, tip in TOOLS:
            btn = ModernButton(command=lambda n=name: self.toolSelected.emit(n),
                              variant="plain", width=32, height=32,
                              pill=True, icon_name=name, icon_size=17)
            btn.setToolTip(tip)
            layout.addWidget(btn)
            self.tool_buttons[name] = btn

        layout.addWidget(self._divider())
        for color in ANNOT_COLORS:
            dot = ColorSwatch(color)
            dot.clicked.connect(self.colorSelected.emit)
            layout.addWidget(dot)
            self.color_swatches[color] = dot

        layout.addWidget(self._divider())
        for width in ANNOT_WIDTHS:
            dot = WidthSwatch(width)
            dot.clicked.connect(self.widthSelected.emit)
            layout.addWidget(dot)
            self.width_swatches[width] = dot

        layout.addWidget(self._divider())
        undo_btn = ModernButton(command=self.undoRequested.emit,
                                variant="plain", width=32, height=32,
                                pill=True, icon_name="undo", icon_size=17)
        undo_btn.setToolTip("Undo (Ctrl+Z)")
        layout.addWidget(undo_btn)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)
        self.adjustSize()

    @staticmethod
    def _divider():
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFixedWidth(1)
        line.setStyleSheet("background: palette(mid);")
        return line

    def set_palette(self, col):
        self._col = col
        self.update()

    def set_active_tool(self, tool):
        for name, btn in self.tool_buttons.items():
            btn.set_selected(name == tool)

    def set_active_color(self, color):
        for c, dot in self.color_swatches.items():
            dot.set_selected(c == color)

    def set_active_width(self, width):
        for w, dot in self.width_swatches.items():
            dot.set_selected(w == width)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = self._col
        path = QPainterPath()
        radius = self.height() / 2
        path.addRoundedRect(QRectF(0, 0, self.width(), self.height()), radius, radius)
        painter.fillPath(path, qcolor(col["tint"], GLASS_STRONG))
        pen = painter.pen()
        pen.setColor(QColor(col["highlight_edge"]))
        painter.setPen(pen)
        painter.drawPath(path)
