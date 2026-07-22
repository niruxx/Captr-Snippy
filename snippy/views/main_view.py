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
        root.setContentsMargins(20, 14, 20, 12)
        root.setSpacing(10)

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
        header.setSpacing(8)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        title = QLabel("Snippy")
        title.setStyleSheet("font-size: 16pt; font-weight: 700;")
        titles.addWidget(title)
        header.addLayout(titles)
        header.addSpacing(14)

        snip_btn = ModernButton("  Snip region", command=self.snipRequested.emit,
                                variant="primary", width=144, height=36,
                                icon_name="plus", icon_size=14)
        header.addWidget(snip_btn)
        full_btn = ModernButton("Full screen", command=self.fullscreenRequested.emit,
                                variant="glass", width=104, height=36,
                                icon_name="fullscreen", icon_size=13)
        header.addWidget(full_btn)
        record_btn = ModernButton("  Record", command=self.recordToggleRequested.emit,
                                  variant="glass", width=110, height=36,
                                  icon_name="record", icon_size=12,
                                  icon_color_role="error")
        record_btn.setToolTip("Start screen recording (Ctrl+Alt+R)")
        header.addWidget(record_btn)
        self.record_btn = record_btn

        header.addSpacing(6)
        self.delay_menu_button, self.delay_seg = self._build_delay_control()
        header.addWidget(self.delay_menu_button)

        header.addStretch(1)

        overflow_btn = ModernButton(variant="plain", width=38, height=36,
                                    pill=True, icon_name="more", icon_size=18)
        overflow_btn.setToolTip("More actions")
        overflow_btn.clicked.connect(lambda: self._show_overflow_menu(overflow_btn))
        header.addWidget(overflow_btn)

        settings_btn = ModernButton(command=self.settingsRequested.emit,
                                    variant="plain", width=36, height=36,
                                    pill=True, icon_name="settings", icon_size=17)
        settings_btn.setToolTip("Settings")
        header.addWidget(settings_btn)

        return header

    def _build_delay_control(self):
        # Deferred import avoids a cycle (float_toolbar imports theme, which
        # is fine, but keeps SegmentedControl next to its only remaining use).
        from ..widgets.segmented import SegmentedControl
        wrapper = QWidget()
        box = QVBoxLayout(wrapper)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(2)
        label = QLabel("Delay")
        label.setStyleSheet("color: palette(mid); font-size: 8pt;")
        box.addWidget(label)
        seg = SegmentedControl(["0s", "3s", "10s"], value="0s", seg_width=38, height=23)
        seg.valueChanged.connect(self.delayChanged.emit)
        box.addWidget(seg)
        return wrapper, seg

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
