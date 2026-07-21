"""SettingsView - replaces _build_settings_view(), minus the OCR/Cloud/NAS
cards (cut from this rewrite). Export/General/Screen-Recording/HDR-Capture
sections only; each control auto-commits to the shared `settings` dict and
calls save_settings() on change, same as the Tkinter build - no explicit
Save button. QScrollArea replaces the old manual Canvas+Scrollbar dance.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QScrollArea,
                               QSlider, QVBoxLayout, QWidget)

from ..capture import list_monitors
from ..hdr import displays_hdr_status
from ..settings import (FORMATS, RECORD_FPS_OPTIONS, VIDEO_FORMATS,
                        save_settings)
from ..widgets.buttons import ModernButton
from ..widgets.card import Card
from ..widgets.segmented import SegmentedControl
from ..widgets.switch import ToggleSwitch


def _section_label(text):
    label = QLabel(text)
    label.setStyleSheet("color: palette(mid); font-weight: 600; font-size: 8pt;"
                        "letter-spacing: 1px;")
    return label


def _hdr_status_text():
    status = displays_hdr_status()
    if not status:
        return "HDR status: unknown on this system/Windows version."
    on = sum(1 for _supported, enabled in status.values() if enabled)
    if on:
        return f"HDR status: {on} of {len(status)} display(s) currently in HDR mode."
    return f"HDR status: all {len(status)} display(s) are in SDR mode."


class SettingsView(QWidget):
    backRequested = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._monitors = list_monitors()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 12)

        top = QHBoxLayout()
        back_btn = ModernButton("←", command=self.backRequested.emit,
                                variant="plain", width=42, height=42)
        back_btn.setToolTip("Back")
        top.addWidget(back_btn)
        title = QLabel("Settings")
        title.setStyleSheet("font-size: 16pt; font-weight: 600;")
        top.addWidget(title)
        top.addStretch(1)
        outer.addLayout(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setSpacing(4)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        self._build_export_section()
        self._build_general_section()
        self._build_recording_section()
        self._build_hdr_section()
        self._content_layout.addStretch(1)

    def _add_card(self, title_text, card):
        self._content_layout.addWidget(_section_label(title_text))
        self._content_layout.addWidget(card)

    # -- Export ---------------------------------------------------------------
    def _build_export_section(self):
        card = Card()
        card.addWidget(QLabel("Image format"))
        seg = SegmentedControl(list(FORMATS), value=self.settings["export_format"])
        seg.valueChanged.connect(self._set_format)
        card.addWidget(seg)

        quality_row = QHBoxLayout()
        quality_row.addWidget(QLabel("Quality"))
        quality_row.addStretch(1)
        self._quality_label = QLabel(str(self.settings["quality"]))
        quality_row.addWidget(self._quality_label)
        card.addLayout(quality_row)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(40, 100)
        slider.setValue(self.settings["quality"])
        slider.valueChanged.connect(self._set_quality)
        card.addWidget(slider)
        card.addWidget(QLabel("Quality applies to JPEG and WEBP exports."))
        self._add_card("EXPORT", card)

    def _set_format(self, name):
        self.settings["export_format"] = name
        save_settings(self.settings)

    def _set_quality(self, value):
        self.settings["quality"] = value
        self._quality_label.setText(str(value))
        save_settings(self.settings)

    # -- General ----------------------------------------------------------------
    def _build_general_section(self):
        row = QHBoxLayout()

        copy_card = Card()
        copy_header = QHBoxLayout()
        copy_header.addWidget(QLabel("Copy after capture"))
        copy_header.addStretch(1)
        switch = ToggleSwitch(value=self.settings["auto_copy"])
        switch.toggled.connect(self._set_auto_copy)
        copy_header.addWidget(switch)
        copy_card.addLayout(copy_header)
        copy_card.addWidget(QLabel("Puts every new capture on the clipboard\nautomatically."))
        row.addWidget(copy_card)

        dir_card = Card()
        dir_header = QHBoxLayout()
        dir_header.addWidget(QLabel("Quick save folder"))
        dir_header.addStretch(1)
        change_btn = ModernButton("Change", command=self._choose_quick_save_dir,
                                  variant="glass", width=76, height=28)
        dir_header.addWidget(change_btn)
        dir_card.addLayout(dir_header)
        self._dir_label = QLabel(self.settings["quick_save_dir"])
        self._dir_label.setWordWrap(True)
        dir_card.addWidget(self._dir_label)
        row.addWidget(dir_card)

        self._content_layout.addWidget(_section_label("GENERAL"))
        self._content_layout.addLayout(row)

    def _set_auto_copy(self, value):
        self.settings["auto_copy"] = value
        save_settings(self.settings)

    def _choose_quick_save_dir(self):
        chosen = QFileDialog.getExistingDirectory(
            self, "Quick save folder", self.settings["quick_save_dir"])
        if chosen:
            self.settings["quick_save_dir"] = chosen
            self._dir_label.setText(chosen)
            save_settings(self.settings)

    # -- Screen recording -------------------------------------------------------
    def _build_recording_section(self):
        card = Card()
        card.addWidget(QLabel("Video format"))
        video_seg = SegmentedControl(list(VIDEO_FORMATS),
                                     value=self.settings["video_format"], seg_width=64)
        video_seg.valueChanged.connect(self._set_video_format)
        card.addWidget(video_seg)

        card.addWidget(QLabel("Frame rate"))
        fps_choices = sorted(set(RECORD_FPS_OPTIONS) | {self.settings["record_fps"]})
        fps_seg = SegmentedControl([str(v) for v in fps_choices],
                                   value=str(self.settings["record_fps"]), seg_width=52)
        fps_seg.valueChanged.connect(self._set_record_fps)
        card.addWidget(fps_seg)

        card.addWidget(QLabel("Record source"))
        source_labels = ["Entire desktop"]
        source_values = ["all"]
        for i in range(len(self._monitors)):
            source_labels.append(f"Monitor {i + 1}")
            source_values.append(f"monitor:{i}")
        source_labels.append("Choose window")
        source_values.append("window")
        self._source_value_by_label = dict(zip(source_labels, source_values))
        source_label_by_value = dict(zip(source_values, source_labels))
        current_label = source_label_by_value.get(
            self.settings["record_source"], "Entire desktop")
        source_seg = SegmentedControl(source_labels, value=current_label, seg_width=112)
        source_seg.valueChanged.connect(self._set_record_source)
        card.addWidget(source_seg)

        note = QLabel(
            "Match your display's refresh rate for the smoothest capture "
            "(higher rates need more CPU and disk space). Recording a "
            "single monitor or window crops to a smaller, lighter output; "
            "“Choose window” asks which one each time you hit "
            "Record and follows it if it moves or resizes, but will show "
            "anything on top if it's covered by another window. "
            "Ctrl+Alt+R starts/stops, Ctrl+Alt+P pauses/resumes, from "
            "anywhere.")
        note.setWordWrap(True)
        note.setStyleSheet("color: palette(mid);")
        card.addWidget(note)
        self._add_card("SCREEN RECORDING", card)

    def _set_video_format(self, name):
        self.settings["video_format"] = name
        save_settings(self.settings)

    def _set_record_fps(self, value):
        self.settings["record_fps"] = int(value)
        save_settings(self.settings)

    def _set_record_source(self, label):
        self.settings["record_source"] = self._source_value_by_label[label]
        save_settings(self.settings)

    # -- HDR --------------------------------------------------------------------
    def _build_hdr_section(self):
        card = Card()
        header = QHBoxLayout()
        header.addWidget(QLabel("Correct washed-out HDR captures"))
        header.addStretch(1)
        switch = ToggleSwitch(value=self.settings["hdr_tone_map"])
        switch.toggled.connect(self._set_hdr_tone_map)
        header.addWidget(switch)
        card.addLayout(header)

        explain = QLabel(
            "Screenshots of HDR content can look dim or washed out, "
            "because capture APIs only ever see the SDR-referenced blend "
            "Windows composites, not the brightness boost the display "
            "itself applies. When on, new captures taken while a display "
            "is in HDR mode get a brightness/contrast lift to compensate "
            "(a heuristic, not a physically accurate tone-map).")
        explain.setWordWrap(True)
        explain.setStyleSheet("color: palette(mid);")
        card.addWidget(explain)

        self._hdr_status_label = QLabel(_hdr_status_text())
        self._hdr_status_label.setStyleSheet("color: palette(mid);")
        card.addWidget(self._hdr_status_label)
        self._add_card("HDR CAPTURE", card)

    def _set_hdr_tone_map(self, value):
        self.settings["hdr_tone_map"] = value
        save_settings(self.settings)
