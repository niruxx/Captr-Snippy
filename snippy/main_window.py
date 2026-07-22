"""MainWindow - the SnippyApp replacement/coordinator. Owns the shared
CaptureState and settings dict, the DesktopGrabber/ScreenRecorder/
GlobalHotkeys/AppSignals instances, and hosts MainView/SettingsView in a
simple slide container (mirroring the old `_slide_to` place()-based
transition, just expressed with QPropertyAnimation).
"""

import ctypes
import os
import sys
from datetime import datetime

from PIL import ImageGrab
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import (QColor, QKeySequence, QLinearGradient, QPainter,
                           QPainterPath, QShortcut)
from PySide6.QtWidgets import (QApplication, QFileDialog, QMessageBox,
                               QSizeGrip, QVBoxLayout, QWidget)

from .anim import animate
from .capture import DesktopGrabber, list_monitors, list_windows
from .clipboard import copy_image_to_clipboard
from .hotkeys import (MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, GlobalHotkeys)
from .models import CaptureState
from .recording import ScreenRecorder
from .rounded_mask import rounded_region
from .settings import (FORMATS, LOSSY_FORMATS, PAUSE_HOTKEY_VK,
                       RECORD_HOTKEY_VK, VIDEO_FORMATS, load_settings,
                       save_settings)
from .signals import AppSignals
from .theme import build_qss, get_palette, system_dark_mode
from .views.capture_overlay import CaptureOverlay
from .views.main_view import TOOLS, MainView
from .views.settings_view import SettingsView
from .views.window_picker import WindowPickerDialog
from .widgets.record_bar import RecordControlBar
from .widgets.slide_stack import SlideStack
from .widgets.titlebar import CustomTitleBar
from .widgets.toast import Toast

WINDOW_SIZE = (960, 700)
MIN_SIZE = (820, 600)
WINDOW_RADIUS = 10
FADE_MS = 200


class MainWindow(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("Snippy")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.settings = load_settings()
        self.capture_state = CaptureState()
        self.signals = AppSignals()
        self.dark = system_dark_mode()

        self.recorder = None
        self.desktop_grabber = None
        self.record_bar = None
        self._record_tick_timer = None
        self._monitors = []
        self.overlay = None
        self._closing = False

        self._build_ui()
        self._apply_theme(self.dark, initial=True)
        self._bind_shortcuts()
        self._wire_signals()

        self.hotkeys = GlobalHotkeys([
            (1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, RECORD_HOTKEY_VK,
             self.signals.hotkey_record.emit),
            (2, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, PAUSE_HOTKEY_VK,
             self.signals.hotkey_pause.emit),
        ])
        self.signals.hotkey_record.connect(self.toggle_recording)
        self.signals.hotkey_pause.connect(self.toggle_pause_recording)
        self.signals.record_error.connect(self._handle_record_error)
        self.hotkeys.start()

        width, height = WINDOW_SIZE
        screen = self.screen().availableGeometry() if self.screen() else None
        if screen:
            x = screen.x() + (screen.width() - width) // 2
            y = screen.y() + (screen.height() - height) // 2
        else:
            x = y = 100
        self.setGeometry(x, y, width, height)
        self.setMinimumSize(*MIN_SIZE)
        self._update_mask()

    # -- UI construction ---------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.titlebar = CustomTitleBar(self)
        root.addWidget(self.titlebar)

        self.stack_container = SlideStack()
        root.addWidget(self.stack_container, 1)

        self.main_view = MainView(self.capture_state)
        self.settings_view = SettingsView(self.settings)
        self.stack_container.add_view(self.main_view)
        self.stack_container.add_view(self.settings_view)

        self.toast = Toast(self)

        grip = QSizeGrip(self)
        grip.setFixedSize(14, 14)
        self._size_grip = grip

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._size_grip.move(self.width() - 18, self.height() - 18)
        self._update_mask()

    def _update_mask(self):
        """Clips the whole window (including children) to rounded corners,
        not just the background paint - otherwise child widgets near a
        corner would poke past the rounded gradient with square edges.
        Uses an anti-aliased corner mask (see rounded_mask.py) rather than
        a raw QRegion polygon, which rasterizes curves with no
        antialiasing and looks visibly pixelated at this radius."""
        if self.isMaximized():
            self.clearMask()
            return
        self.setMask(rounded_region(self.width(), self.height(), WINDOW_RADIUS))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            self._update_mask()

    def paintEvent(self, event):
        """Paints the whole window's backdrop: a soft gradient, clipped to
        rounded corners when floating (square when maximized/snapped, since
        rounded corners against the screen edge look broken)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = get_palette(self.dark)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(col["bg_top"]))
        gradient.setColorAt(1, QColor(col["bg_bottom"]))
        radius = 0 if self.isMaximized() else WINDOW_RADIUS
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), radius, radius)
        painter.fillPath(path, gradient)

    def _bind_shortcuts(self):
        bindings = (
            ("Ctrl+N", self.start_region_capture),
            ("Ctrl+F", self.start_fullscreen_capture),
            ("Ctrl+S", self.save_screenshot),
            ("Ctrl+Q", self.quick_save),
            ("Ctrl+C", self.copy_to_clipboard),
            ("Ctrl+Z", self.undo),
            ("Del", self.remove_current),
            ("Print", self.start_region_capture),
        )
        self._shortcuts = []
        for sequence, handler in bindings:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(handler)
            self._shortcuts.append(shortcut)

    def _wire_signals(self):
        mv = self.main_view
        mv.snipRequested.connect(self.start_region_capture)
        mv.fullscreenRequested.connect(self.start_fullscreen_capture)
        mv.recordToggleRequested.connect(self.toggle_recording)
        mv.settingsRequested.connect(self.open_settings)
        mv.quickSaveRequested.connect(self.quick_save)
        mv.saveRequested.connect(self.save_screenshot)
        mv.copyRequested.connect(self.copy_to_clipboard)
        mv.clearRequested.connect(self.remove_current)
        mv.undoRequested.connect(self.undo)
        mv.toolSelected.connect(self.set_tool)
        mv.colorSelected.connect(self.set_color)
        mv.widthSelected.connect(self.set_width)

        mv.preview.committed.connect(self._on_preview_committed)
        mv.preview.statusMessage.connect(mv.set_status)
        mv.preview.toastRequested.connect(self.show_toast)
        mv.preview.colorPicked.connect(self._on_color_picked)

        mv.history_rail.selected.connect(self.select_capture)

        self.settings_view.backRequested.connect(self.close_settings)

        # initial selection visuals
        mv.set_active_color(self.capture_state.annot_color)
        mv.set_active_width(self.capture_state.annot_width)
        mv.history_rail.refresh(self.capture_state)
        mv.update_capture_presence(bool(self.capture_state.screenshot))

    # -- theme ---------------------------------------------------------------
    def _apply_theme(self, dark, initial=False):
        self.dark = dark
        col = get_palette(dark)
        self.setStyleSheet(build_qss(col))
        for widget in self.findChildren(QWidget):
            setter = getattr(widget, "set_palette", None)
            if callable(setter):
                setter(col)
        self.update()

    # -- view transitions ------------------------------------------------------
    def open_settings(self):
        self.stack_container.slide_to(self.settings_view, direction=1)

    def close_settings(self):
        self.stack_container.slide_to(self.main_view, direction=-1)

    # -- capture ---------------------------------------------------------------
    def _delay_ms(self):
        return int(self.main_view.delay_seg.value.rstrip("s")) * 1000

    def start_region_capture(self):
        delay = self._delay_ms()
        self.main_view.set_status("Click and drag to select an area · Esc to cancel")
        self.hide()
        QTimer.singleShot(200 + delay, self._create_overlay)

    def start_fullscreen_capture(self):
        delay = self._delay_ms()
        self.main_view.set_status("Capturing full screen…")
        self.hide()
        QTimer.singleShot(300 + delay, self._grab_fullscreen)

    def _grab_fullscreen(self):
        try:
            image = ImageGrab.grab(all_screens=True)
        except Exception as exc:
            self.show()
            QMessageBox.critical(self, "Error", f"Failed to capture screen: {exc}")
            self.main_view.set_status("Capture failed")
            return
        self.show()
        self._add_capture(image)
        self.main_view.set_status(
            f"Captured full screen · {image.width} × {image.height} px")

    def _create_overlay(self):
        self.overlay = CaptureOverlay()
        self.overlay.regionSelected.connect(self._capture_selection)
        self.overlay.cancelled.connect(self.cancel_capture)
        self.overlay.show()

    def cancel_capture(self):
        if self.overlay:
            self.overlay.close()
            self.overlay = None
        self.show()
        self.main_view.set_status("Capture cancelled")

    def _capture_selection(self, x1, y1, x2, y2):
        if self.overlay:
            self.overlay.close()
            self.overlay = None
        if x2 - x1 < 5 or y2 - y1 < 5:
            self.show()
            self.main_view.set_status("Selection too small")
            self.show_toast("Please select a larger area")
            return
        QTimer.singleShot(150, lambda: self._finish_region_capture(x1, y1, x2, y2))

    def _finish_region_capture(self, x1, y1, x2, y2):
        try:
            full = ImageGrab.grab(all_screens=True)
            image = full.crop((x1, y1, x2, y2))
        except Exception as exc:
            self.show()
            QMessageBox.critical(self, "Error", f"Failed to capture screenshot: {exc}")
            self.main_view.set_status("Capture failed")
            return
        self.show()
        self._add_capture(image)
        self.main_view.set_status(
            f"Captured {x2 - x1} × {y2 - y1} px · ready to annotate or save")

    def _add_capture(self, image):
        self.capture_state.add_capture(image, settings=self.settings)
        self.main_view.preview.refresh()
        self.main_view.history_rail.refresh(self.capture_state)
        self.main_view.update_capture_presence(True)
        if self.settings["auto_copy"]:
            try:
                copy_image_to_clipboard(image)
                self.show_toast("Captured · copied to clipboard")
            except Exception:
                pass

    # -- annotation ------------------------------------------------------------
    def set_tool(self, name):
        tool = None if self.capture_state.tool == name else name
        self.capture_state.tool = tool
        self.main_view.set_active_tool(tool)
        self.main_view.preview.set_tool(tool)
        if tool:
            tip = dict(TOOLS)[tool]
            self.main_view.set_status(
                f"{tip} · drag on the preview" if tool != "text"
                else "Text · click on the preview")

    def set_color(self, color):
        self.capture_state.annot_color = color
        self.main_view.set_active_color(color)

    def set_width(self, width):
        self.capture_state.annot_width = width
        self.main_view.set_active_width(width)

    def _on_color_picked(self, hex_color):
        self.main_view.set_active_color(hex_color)

    def _on_preview_committed(self):
        self.main_view.history_rail.refresh(self.capture_state)

    def undo(self):
        if not self.capture_state.undo():
            self.show_toast("Nothing to undo")
            return
        self.main_view.preview.refresh()
        self.main_view.history_rail.refresh(self.capture_state)
        self.main_view.set_status("Undid last edit")

    def select_capture(self, index):
        if not self.capture_state.select(index):
            return
        self.main_view.preview.refresh()
        self.main_view.history_rail.refresh(self.capture_state)
        self.main_view.update_capture_presence(True)
        self.main_view.set_status(
            f"Viewing capture {index + 1} of {len(self.capture_state.history)}")

    def remove_current(self):
        if not self.capture_state.history:
            return
        self.capture_state.remove_current()
        self.main_view.preview.refresh()
        self.main_view.history_rail.refresh(self.capture_state)
        self.main_view.update_capture_presence(bool(self.capture_state.screenshot))
        self.main_view.set_status("Capture removed")

    # -- save / export / clipboard -----------------------------------------------
    def save_screenshot(self):
        if not self.capture_state.screenshot:
            self.show_toast("Capture a screenshot first")
            return
        fmt = self.settings["export_format"]
        ext = FORMATS[fmt]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filters = ";;".join(
            [f"{name} image (*{fext})" for name, fext in FORMATS.items()] +
            ["All files (*.*)"])
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save As", f"snippet_{timestamp}{ext}", filters)
        if not file_path:
            return
        self._save_to(file_path)

    def quick_save(self):
        if not self.capture_state.screenshot:
            self.show_toast("Capture a screenshot first")
            return
        folder = self.settings["quick_save_dir"]
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "Error", f"Cannot create folder: {exc}")
            return
        ext = FORMATS[self.settings["export_format"]]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._save_to(os.path.join(folder, f"snippet_{timestamp}{ext}"))

    def _write_image(self, image, file_path):
        fmt = self.settings["export_format"]
        ext_map = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG",
                  ".webp": "WEBP", ".bmp": "BMP"}
        actual_fmt = ext_map.get(os.path.splitext(file_path)[1].lower(), fmt)
        img = image
        if actual_fmt in ("JPEG", "BMP") and img.mode != "RGB":
            img = img.convert("RGB")
        kwargs = {}
        if actual_fmt in LOSSY_FORMATS:
            kwargs["quality"] = self.settings["quality"]
        img.save(file_path, actual_fmt, **kwargs)
        return actual_fmt

    def _save_to(self, file_path):
        try:
            actual_fmt = self._write_image(self.capture_state.screenshot, file_path)
            self.main_view.set_status(f"Saved to {os.path.basename(file_path)}")
            self.show_toast(f"Saved as {actual_fmt} · {os.path.basename(file_path)}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save: {exc}")
            self.main_view.set_status("Save failed")

    def copy_to_clipboard(self):
        if not self.capture_state.screenshot:
            self.show_toast("Capture a screenshot first")
            return
        try:
            copy_image_to_clipboard(self.capture_state.screenshot)
            self.main_view.set_status("Copied to clipboard")
            self.show_toast("Copied to clipboard")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to copy: {exc}")
            self.main_view.set_status("Copy failed")

    # -- screen recording ---------------------------------------------------------
    def toggle_recording(self):
        if self.recorder and self.recorder.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def _make_grab_fn(self):
        grabber = DesktopGrabber()
        self.desktop_grabber = grabber
        source = self.settings.get("record_source", "all")

        if source == "window":
            hwnd = WindowPickerDialog.pick(self)
            if not hwnd:
                grabber.close()
                self.desktop_grabber = None
                return None
            user32 = ctypes.windll.user32
            from ctypes import wintypes

            def grab_window():
                if not user32.IsWindow(hwnd) or user32.IsIconic(hwnd):
                    return None
                rect = wintypes.RECT()
                if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                    return None
                if rect.right <= rect.left or rect.bottom <= rect.top:
                    return None
                return grabber.grab(
                    bbox=(rect.left, rect.top, rect.right, rect.bottom))
            return grab_window

        if source.startswith("monitor:"):
            monitors = self._monitors or list_monitors()
            try:
                left, top, right, bottom, _primary = monitors[
                    int(source.split(":", 1)[1])]
            except (ValueError, IndexError):
                return lambda: grabber.grab()
            bbox = (left, top, right, bottom)
            return lambda: grabber.grab(bbox=bbox)

        return lambda: grabber.grab()

    def start_recording(self):
        if self.recorder and self.recorder.is_recording:
            return
        folder = self.settings["quick_save_dir"]
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "Error", f"Cannot create folder: {exc}")
            return

        grab_fn = self._make_grab_fn()
        if grab_fn is None:
            return

        fmt = self.settings["video_format"]
        ext, codec_args = VIDEO_FORMATS[fmt]
        codec_args = codec_args + self.settings.get("record_extra_ffmpeg_args", [])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(folder, f"recording_{timestamp}{ext}")

        recorder = ScreenRecorder(self.settings["record_fps"], codec_args, output_path,
                                  on_error=self.signals.record_error.emit,
                                  grab_fn=grab_fn,
                                  scale=self.settings.get("record_scale", 1.0))
        try:
            recorder.start()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to start recording: {exc}")
            return
        self.recorder = recorder
        self.hide()
        self._show_record_bar()
        self.main_view.set_status("Recording…")

    def stop_recording(self, discard=False):
        if not self.recorder:
            return
        recorder = self.recorder
        self.recorder = None
        path = recorder.stop()
        if self.desktop_grabber:
            self.desktop_grabber.close()
            self.desktop_grabber = None
        self._hide_record_bar()
        self.show()
        if discard:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
            self.main_view.set_status("Recording discarded")
            return
        self.main_view.set_status(f"Recording saved · {os.path.basename(path)}")
        self.show_toast(f"Saved recording · {os.path.basename(path)}")

    def toggle_pause_recording(self):
        if not self.recorder or not self.recorder.is_recording:
            return
        if self.recorder.paused:
            self.recorder.resume()
        else:
            self.recorder.pause()
        if self.record_bar:
            self.record_bar.set_paused(self.recorder.paused)

    def _handle_record_error(self, message):
        if not self.recorder:
            return
        self.stop_recording(discard=True)
        QMessageBox.critical(self, "Recording error", message)

    def _show_record_bar(self):
        bar = RecordControlBar()
        bar.pauseClicked.connect(self.toggle_pause_recording)
        bar.stopClicked.connect(lambda: self.stop_recording())
        col = get_palette(self.dark)
        bar.set_palette(col)
        screen = self.screen().geometry() if self.screen() else bar.geometry()
        bar.show_at_top_center(screen)
        self.record_bar = bar

        self._record_tick_timer = QTimer(self)
        self._record_tick_timer.timeout.connect(self._tick_record_bar)
        self._record_tick_timer.start(500)

    def _tick_record_bar(self):
        if not self.record_bar or not self.recorder:
            return
        self.record_bar.set_elapsed(int(self.recorder.elapsed()))

    def _hide_record_bar(self):
        if self._record_tick_timer:
            self._record_tick_timer.stop()
            self._record_tick_timer = None
        if self.record_bar:
            self.record_bar.close()
            self.record_bar = None

    # -- toast -----------------------------------------------------------------
    def show_toast(self, message):
        self.toast.show_message(message)

    # -- lifecycle ---------------------------------------------------------------
    def closeEvent(self, event):
        if self._closing:
            super().closeEvent(event)
            # quitOnLastWindowClosed is disabled (see app.py) since this
            # window gets legitimately hidden - not closed - while recording,
            # and the floating RecordControlBar (a Qt::Tool window) doesn't
            # count towards that check anyway - so closing the real window
            # must explicitly end the app itself.
            QApplication.instance().quit()
            return
        self._closing = True
        event.ignore()
        if self.recorder:
            self.recorder.stop()
            self.recorder = None
        if self.desktop_grabber:
            self.desktop_grabber.close()
            self.desktop_grabber = None
        if getattr(self, "hotkeys", None):
            self.hotkeys.stop()
        animate(self, b"windowOpacity", self.windowOpacity(), 0.0,
                duration=FADE_MS, on_finished=self.close)
