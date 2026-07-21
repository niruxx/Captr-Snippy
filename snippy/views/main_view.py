"""MainView - replaces _build_main_view(). Header (title, capture actions,
delay, icon actions), annotation toolbar, status row, history rail, and
the preview canvas. Owns no app state itself beyond the shared
CaptureState/settings references it's given; all actions are exposed as
Qt signals for MainWindow to wire up.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QVBoxLayout,
                               QWidget)

from ..settings import ANNOT_COLORS, ANNOT_WIDTHS
from ..widgets.buttons import ModernButton
from ..widgets.card import Card
from ..widgets.color_dot import ColorSwatch, WidthSwatch
from ..widgets.segmented import SegmentedControl
from .history_rail import HistoryRail
from .preview_canvas import PreviewCanvas

TOOLS = (
    ("pen",       "✎", "Pen"),
    ("highlight", "▨", "Highlighter"),
    ("line",      "╱", "Line"),
    ("arrow",     "↗", "Arrow"),
    ("rect",      "▭", "Rectangle"),
    ("ellipse",   "◯", "Ellipse"),
    ("text",      "T", "Text"),
    ("redact",    "▓", "Redact / pixelate"),
    ("picker",    "🎨", "Color picker"),
    ("crop",      "⬚", "Crop"),
)


class MainView(QWidget):
    snipRequested = Signal()
    fullscreenRequested = Signal()
    recordToggleRequested = Signal()
    settingsRequested = Signal()
    quickSaveRequested = Signal()
    saveRequested = Signal()
    copyRequested = Signal()
    clearRequested = Signal()
    undoRequested = Signal()
    toolSelected = Signal(str)
    colorSelected = Signal(str)
    widthSelected = Signal(int)
    delayChanged = Signal(str)

    def __init__(self, capture_state, parent=None):
        super().__init__(parent)
        self.state = capture_state
        self.tool_buttons = {}
        self.color_swatches = {}
        self.width_swatches = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 12)
        root.setSpacing(10)

        root.addLayout(self._build_header())
        root.addWidget(self._build_toolbar())

        self.preview = PreviewCanvas(capture_state)
        root.addWidget(self.preview, 1)

        self.history_rail = HistoryRail()
        root.addWidget(self.history_rail)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Ready")
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)
        status_row.addWidget(QLabel("Ctrl+N region · Ctrl+F full screen · Ctrl+Z undo"))
        root.addLayout(status_row)

    def _build_header(self):
        header = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel("Snippy")
        title.setStyleSheet("font-size: 18pt; font-weight: 600;")
        subtitle = QLabel("Screenshot studio")
        subtitle.setStyleSheet("color: palette(mid);")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles)
        header.addSpacing(20)

        snip_btn = ModernButton("＋  Snip region", command=self.snipRequested.emit,
                                variant="primary", width=160, height=40)
        header.addWidget(snip_btn)
        full_btn = ModernButton("Full screen", command=self.fullscreenRequested.emit,
                                variant="glass", width=120, height=40)
        header.addWidget(full_btn)
        record_btn = ModernButton("⏺  Record", command=self.recordToggleRequested.emit,
                                  variant="glass", width=120, height=40)
        record_btn.setToolTip("Start screen recording (Ctrl+Alt+R)")
        header.addWidget(record_btn)
        self.record_btn = record_btn

        header.addSpacing(12)
        delay_box = QVBoxLayout()
        delay_label = QLabel("Delay")
        delay_label.setStyleSheet("color: palette(mid); font-size: 8pt;")
        delay_box.addWidget(delay_label)
        self.delay_seg = SegmentedControl(["0s", "3s", "10s"], value="0s",
                                          seg_width=44, height=26)
        self.delay_seg.valueChanged.connect(self.delayChanged.emit)
        delay_box.addWidget(self.delay_seg)
        header.addLayout(delay_box)

        header.addStretch(1)

        for tip, command in (
                ("Remove capture (Del)", self.clearRequested.emit),
                ("Copy (Ctrl+C)", self.copyRequested.emit),
                ("Save as… (Ctrl+S)", self.saveRequested.emit),
                ("Quick save (Ctrl+Q)", self.quickSaveRequested.emit),
                ("Settings", self.settingsRequested.emit)):
            glyph = {"Remove capture (Del)": "×", "Copy (Ctrl+C)": "⧉",
                    "Save as… (Ctrl+S)": "💾", "Quick save (Ctrl+Q)": "↓",
                    "Settings": "⚙"}[tip]
            btn = ModernButton(glyph, command=command, variant="plain",
                              width=40, height=40)
            btn.setToolTip(tip)
            header.addWidget(btn)

        return header

    def _build_toolbar(self):
        card = Card(padding=8)
        row = QHBoxLayout()
        row.setSpacing(2)
        card.addLayout(row)

        for name, glyph, tip in TOOLS:
            btn = ModernButton(glyph, command=lambda n=name: self.toolSelected.emit(n),
                              variant="plain", width=38, height=38)
            btn.setToolTip(tip)
            row.addWidget(btn)
            self.tool_buttons[name] = btn

        row.addWidget(self._divider())
        for color in ANNOT_COLORS:
            dot = ColorSwatch(color)
            dot.clicked.connect(self.colorSelected.emit)
            row.addWidget(dot)
            self.color_swatches[color] = dot

        row.addWidget(self._divider())
        for width in ANNOT_WIDTHS:
            dot = WidthSwatch(width)
            dot.clicked.connect(self.widthSelected.emit)
            row.addWidget(dot)
            self.width_swatches[width] = dot

        row.addStretch(1)
        undo_btn = ModernButton("↺", command=self.undoRequested.emit,
                                variant="plain", width=38, height=38)
        undo_btn.setToolTip("Undo (Ctrl+Z)")
        row.addWidget(undo_btn)
        return card

    @staticmethod
    def _divider():
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFixedWidth(1)
        line.setStyleSheet("background: palette(mid);")
        return line

    # -- selection visuals, driven by MainWindow after mutating shared state --
    def set_active_tool(self, tool):
        for name, btn in self.tool_buttons.items():
            btn.set_selected(name == tool)

    def set_active_color(self, color):
        for c, dot in self.color_swatches.items():
            dot.set_selected(c == color)

    def set_active_width(self, width):
        for w, dot in self.width_swatches.items():
            dot.set_selected(w == width)

    def set_status(self, message):
        self.status_label.setText(message)
