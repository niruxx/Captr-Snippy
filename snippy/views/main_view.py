"""MainView - the minimal capture page. Header has just the capture
actions (Snip/Full screen/Record), the delay control, Settings, and a
single "..." overflow menu for less-central actions (Save As, Quick Save,
Copy, Remove capture) - the annotation toolbar lives in the floating
ContextualToolbar (see widgets/float_toolbar.py + preview_area.py) and only
appears once there's something to edit.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QVBoxLayout, QWidget

from ..widgets.buttons import ModernButton
from .history_rail import HistoryRail
from .preview_area import PreviewArea

# Re-exported for main_window.py's tool-name -> tooltip lookup.
from ..widgets.float_toolbar import TOOLS  # noqa: F401


class _DelayButton(ModernButton):
    """Compact icon-only stand-in for the old always-visible delay segmented
    control: a single button that pops up a small checkable menu, so the
    header doesn't spend permanent width/height on a control most captures
    never touch. Exposes `.value` (a "0s"/"3s"/"10s" string) the same way
    the old SegmentedControl did, so MainWindow's `_delay_ms()` needs no
    changes."""
    valueChanged = Signal(str)

    def __init__(self, options, value, parent=None):
        super().__init__(variant="plain", width=36, height=36, pill=True,
                         icon_name="timer", icon_size=16, parent=parent)
        self.options = list(options)
        self.value = value
        self._refresh_tip()
        self.clicked.connect(self._show_menu)

    def _refresh_tip(self):
        label = "none" if self.value == "0s" else self.value
        self.setToolTip(f"Capture delay: {label}")

    def _show_menu(self):
        menu = QMenu(self)
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        for opt in self.options:
            action = menu.addAction("No delay" if opt == "0s" else opt)
            action.setCheckable(True)
            action.setChecked(opt == self.value)
            action.triggered.connect(lambda _checked=False, o=opt: self._pick(o))
        pos = self.mapToGlobal(self.rect().bottomLeft())
        menu.exec(pos)

    def _pick(self, value):
        if value == self.value:
            return
        self.value = value
        self._refresh_tip()
        self.valueChanged.emit(value)


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

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 10)
        root.setSpacing(8)

        root.addLayout(self._build_header())

        self.preview_area = PreviewArea(capture_state)
        root.addWidget(self.preview_area, 1)

        self.history_rail = HistoryRail()
        root.addWidget(self.history_rail)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Ready")
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)
        status_row.addWidget(QLabel("Ctrl+N region · Ctrl+F full screen · Ctrl+Z undo"))
        root.addLayout(status_row)

        # wire the floating annotation toolbar's signals straight through
        toolbar = self.preview_area.toolbar
        toolbar.toolSelected.connect(self.toolSelected.emit)
        toolbar.colorSelected.connect(self.colorSelected.emit)
        toolbar.widthSelected.connect(self.widthSelected.emit)
        toolbar.undoRequested.connect(self.undoRequested.emit)

    def _build_header(self):
        header = QHBoxLayout()
        header.setSpacing(6)
        title = QLabel("Snippy")
        title.setStyleSheet("font-size: 15pt; font-weight: 700;")
        header.addWidget(title)
        header.addSpacing(10)

        snip_btn = ModernButton("  Snip region", command=self.snipRequested.emit,
                                variant="primary", width=136, height=34,
                                icon_name="plus", icon_size=14)
        header.addWidget(snip_btn)
        full_btn = ModernButton(command=self.fullscreenRequested.emit,
                                variant="glass", width=34, height=34,
                                pill=True, icon_name="fullscreen", icon_size=15)
        full_btn.setToolTip("Full screen capture (Ctrl+F)")
        header.addWidget(full_btn)
        record_btn = ModernButton("  Record", command=self.recordToggleRequested.emit,
                                  variant="glass", width=104, height=34,
                                  icon_name="record", icon_size=12,
                                  icon_color_role="error")
        record_btn.setToolTip("Start screen recording (Ctrl+Alt+R)")
        header.addWidget(record_btn)
        self.record_btn = record_btn

        self.delay_seg = _DelayButton(["0s", "3s", "10s"], "0s")
        self.delay_seg.valueChanged.connect(self.delayChanged.emit)
        header.addWidget(self.delay_seg)

        header.addStretch(1)

        overflow_btn = ModernButton(variant="plain", width=36, height=34,
                                    pill=True, icon_name="more", icon_size=17)
        overflow_btn.setToolTip("More actions")
        overflow_btn.clicked.connect(lambda: self._show_overflow_menu(overflow_btn))
        header.addWidget(overflow_btn)

        settings_btn = ModernButton(command=self.settingsRequested.emit,
                                    variant="plain", width=34, height=34,
                                    pill=True, icon_name="settings", icon_size=16)
        settings_btn.setToolTip("Settings")
        header.addWidget(settings_btn)

        return header

    def _show_overflow_menu(self, anchor_button):
        menu = QMenu(self)
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        menu.addAction("Save As…  (Ctrl+S)", self.saveRequested.emit)
        menu.addAction("Quick Save  (Ctrl+Q)", self.quickSaveRequested.emit)
        menu.addAction("Copy to Clipboard  (Ctrl+C)", self.copyRequested.emit)
        menu.addSeparator()
        menu.addAction("Remove Capture  (Del)", self.clearRequested.emit)
        pos = anchor_button.mapToGlobal(anchor_button.rect().bottomLeft())
        menu.exec(pos)

    # -- selection visuals, driven by MainWindow after mutating shared state --
    @property
    def preview(self):
        return self.preview_area.preview

    def set_active_tool(self, tool):
        self.preview_area.toolbar.set_active_tool(tool)

    def set_active_color(self, color):
        self.preview_area.toolbar.set_active_color(color)

    def set_active_width(self, width):
        self.preview_area.toolbar.set_active_width(width)

    def set_status(self, message):
        self.status_label.setText(message)

    def update_capture_presence(self, has_capture):
        self.preview_area.set_toolbar_visible(has_capture)
