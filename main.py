"""Snippy - a translucent screenshot studio with light and dark glass themes.

Features: region / full-screen capture (multi-monitor aware), delay timer,
annotation tools (pen, highlighter, shapes, arrow, text, crop) with undo,
a capture history rail, quick save, auto-copy and configurable exports.
The grey/white light theme follows the Windows appearance setting and
switches live to a black/grey scheme when dark mode is enabled.
"""

import ctypes
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from ctypes import wintypes
from tkinter import filedialog, messagebox, simpledialog
from tkinter import font as tkfont
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont, ImageGrab, ImageTk

import imageio_ffmpeg


def blend(hex1, hex2, t):
    """Linear blend between two hex colors, t in [0, 1]."""
    c1 = [int(hex1[i:i + 2], 16) for i in (1, 3, 5)]
    c2 = [int(hex2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(
        round(a + (b - a) * t) for a, b in zip(c1, c2))


def hex_rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


# ---------------------------------------------------------------------------
# Themes - grey/white glass by default, black/grey when Windows dark mode is on
# ---------------------------------------------------------------------------
COL = {}


def set_theme(dark):
    if dark:
        bg = "#0B0B0D"
        white = "#FFFFFF"
        COL.update({
            "alpha":           0.93,
            "bg":              bg,
            "glass":           blend(bg, white, 0.07),   # resting panel
            "glass_dim":       blend(bg, white, 0.04),   # recessed well
            "glass_high":      blend(bg, white, 0.14),   # raised / toast
            "border":          blend(bg, white, 0.14),
            "border_bright":   blend(bg, white, 0.26),
            "seg_track":       blend(bg, white, 0.05),
            "seg_thumb":       blend(bg, white, 0.18),
            "text":            "#F5F5F7",
            "text_secondary":  blend(bg, white, 0.60),
            "text_tertiary":   blend(bg, white, 0.38),
            "accent":          "#0A84FF",
            "accent_soft":     "#4DA2FF",
            "error":           "#FF453A",
        })
    else:
        COL.update({
            "alpha":           0.90,
            "bg":              "#F2F3F6",
            "glass":           "#FFFFFF",
            "glass_dim":       "#E7E8EC",
            "glass_high":      "#FFFFFF",
            "border":          "#DCDDE2",
            "border_bright":   "#C9CBD2",
            "seg_track":       "#E4E5EA",
            "seg_thumb":       "#FFFFFF",
            "text":            "#1D1D1F",
            "text_secondary":  "#6E6E73",
            "text_tertiary":   "#9C9CA3",
            "accent":          "#007AFF",
            "accent_soft":     "#007AFF",
            "error":           "#FF3B30",
        })


def system_dark_mode():
    """True when Windows apps are set to dark appearance."""
    if sys.platform == "win32":
        try:
            import winreg
            key_path = (r"Software\Microsoft\Windows\CurrentVersion"
                        r"\Themes\Personalize")
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0
        except OSError:
            pass
    return False


WS_CAPTION = 0x00C00000


def _root_hwnd(root):
    return ctypes.windll.user32.GetParent(root.winfo_id())


def strip_titlebar(root):
    """Remove the native caption bar, keeping resize borders, the taskbar
    entry and minimize behavior. Idempotent. Returns True when frameless."""
    if sys.platform != "win32":
        return False
    try:
        root.update_idletasks()
        user32 = ctypes.windll.user32
        hwnd = _root_hwnd(root)
        get_style = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        set_style = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        style = get_style(hwnd, -16)  # GWL_STYLE
        if not style & WS_CAPTION:
            return True
        set_style(hwnd, -16, style & ~WS_CAPTION)
        try:  # keep Windows 11 rounded corners on the frameless window
            preference = ctypes.c_int(2)  # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(preference), 4)
        except Exception:
            pass
        # SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# HiDPI support - every widget dimension in this file is authored for a
# 96 DPI (100% Windows scaling) screen. SCALE is the live per-monitor ratio
# to that baseline; sc() converts an authored pixel value to physical
# pixels so geometry keeps its intended size under 125/150/200%+ scaling.
# ---------------------------------------------------------------------------
SCALE = 1.0


def get_dpi_scale(hwnd=None):
    """Ratio of the current (per-monitor) DPI to the 96 DPI baseline."""
    if sys.platform != "win32":
        return 1.0
    try:
        user32 = ctypes.windll.user32
        if hwnd and hasattr(user32, "GetDpiForWindow"):
            dpi = user32.GetDpiForWindow(hwnd)
        elif hasattr(user32, "GetDpiForSystem"):
            dpi = user32.GetDpiForSystem()
        else:
            hdc = user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 90)  # LOGPIXELSY
            user32.ReleaseDC(0, hdc)
        return dpi / 96.0 if dpi else 1.0
    except Exception:
        return 1.0


def sc(px):
    """Scale an authored (96 DPI) pixel value to the current display."""
    return max(1, round(px * SCALE))


FORMATS = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp", "BMP": ".bmp"}
LOSSY_FORMATS = ("JPEG", "WEBP")

ANNOT_COLORS = ("#FF453A", "#FF9F0A", "#FFD60A", "#32D74B",
                "#0A84FF", "#FFFFFF", "#000000")
ANNOT_WIDTHS = (2, 4, 8)

HISTORY_LIMIT = 8
UNDO_LIMIT = 8

# video_ext, ffmpeg output args (codec chosen per-container: libx264 for the
# MPEG-4/Matroska/FLV muxers, libvpx for WebM)
VIDEO_FORMATS = {
    "MP4":  (".mp4",  ["-c:v", "libx264", "-preset", "ultrafast",
                        "-crf", "20", "-pix_fmt", "yuv420p"]),
    "MKV":  (".mkv",  ["-c:v", "libx264", "-preset", "ultrafast",
                        "-crf", "20", "-pix_fmt", "yuv420p"]),
    "FLV":  (".flv",  ["-c:v", "libx264", "-preset", "ultrafast",
                        "-crf", "20", "-pix_fmt", "yuv420p"]),
    "WEBM": (".webm", ["-c:v", "libvpx", "-deadline", "realtime",
                        "-cpu-used", "8", "-b:v", "6M"]),
}
RECORD_FPS_OPTIONS = (15, 30, 60, 120, 144, 165, 240)

RECORD_HOTKEY_VK = ord("R")     # Ctrl+Alt+R - start / stop recording
PAUSE_HOTKEY_VK = ord("P")      # Ctrl+Alt+P - pause / resume recording

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "settings.json")
DEFAULT_SETTINGS = {
    "export_format": "PNG",
    "quality": 90,
    "auto_copy": False,
    "quick_save_dir": os.path.join(os.path.expanduser("~"),
                                   "Pictures", "Snippy"),
    "video_format": "MP4",
    "record_fps": 30,
}


def load_settings():
    settings = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as fh:
            saved = json.load(fh)
        if saved.get("export_format") in FORMATS:
            settings["export_format"] = saved["export_format"]
        if isinstance(saved.get("quality"), int):
            settings["quality"] = max(40, min(100, saved["quality"]))
        if isinstance(saved.get("auto_copy"), bool):
            settings["auto_copy"] = saved["auto_copy"]
        if isinstance(saved.get("quick_save_dir"), str) and saved["quick_save_dir"]:
            settings["quick_save_dir"] = saved["quick_save_dir"]
        if saved.get("video_format") in VIDEO_FORMATS:
            settings["video_format"] = saved["video_format"]
        if isinstance(saved.get("record_fps"), int) and \
                saved["record_fps"] in RECORD_FPS_OPTIONS:
            settings["record_fps"] = saved["record_fps"]
    except (OSError, ValueError):
        pass
    return settings


def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(settings, fh, indent=2)
    except OSError:
        pass


def ease_out(t):
    return 1 - (1 - t) ** 3


ANNOTATION_FONT_CANDIDATES = {
    "win32":  ("segoeui.ttf", "arial.ttf"),
    "darwin": ("SFNSText", "Helvetica", "Arial"),
}
ANNOTATION_FONT_FALLBACK = ("DejaVuSans", "LiberationSans-Regular",
                            "NotoSans-Regular", "Ubuntu-R")


def load_annotation_font(size):
    """Best-effort TrueType lookup by name so annotated text isn't drawn
    with PIL's tiny bitmap default; falls back gracefully if none resolve."""
    candidates = ANNOTATION_FONT_CANDIDATES.get(sys.platform,
                                                ANNOTATION_FONT_FALLBACK)
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def set_window_alpha(window, value):
    """Best-effort window opacity; some Linux window managers reject it.
    Returns whether the attribute was actually applied."""
    try:
        window.attributes("-alpha", value)
        return True
    except tk.TclError:
        return False


def get_window_alpha(window, default=1.0):
    try:
        return float(window.attributes("-alpha"))
    except tk.TclError:
        return default


WDA_EXCLUDEFROMCAPTURE = 0x00000011


def exclude_from_capture(window):
    """Hide a Toplevel from screen-capture APIs (Windows 10 2004+), so the
    floating recording controls never end up baked into the recording."""
    if sys.platform != "win32":
        return
    try:
        hwnd = _root_hwnd(window)
        ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Global hotkeys - registered on a dedicated thread with its own Win32
# message loop, since RegisterHotKey delivers WM_HOTKEY to the *thread* that
# registered it and Tk's Tcl-driven loop never sees those messages.
# ---------------------------------------------------------------------------
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000


class GlobalHotkeys:
    """Registers a fixed set of system-wide hotkeys. `bindings` is a list of
    (id, modifiers, vk, callback) tuples; callbacks fire on the hotkey
    thread, so they should just hand off via `root.after(0, ...)`."""

    def __init__(self, bindings):
        self.bindings = bindings
        self._thread = None
        self._thread_id = None
        self._ready = threading.Event()

    def start(self):
        if sys.platform != "win32":
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(2)

    def stop(self):
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012,
                                                     0, 0)  # WM_QUIT

    def _run(self):
        user32 = ctypes.windll.user32
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        registered = []
        callbacks = {}
        for hotkey_id, mods, vk, callback in self.bindings:
            if user32.RegisterHotKey(None, hotkey_id, mods, vk):
                registered.append(hotkey_id)
                callbacks[hotkey_id] = callback
        self._ready.set()
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == WM_HOTKEY:
                    callback = callbacks.get(msg.wParam)
                    if callback:
                        callback()
        finally:
            for hotkey_id in registered:
                user32.UnregisterHotKey(None, hotkey_id)


# ---------------------------------------------------------------------------
# Screen recording - frames are grabbed on a background thread and piped
# into a bundled ffmpeg process, which handles the mp4/mkv/flv/webm muxing.
# ---------------------------------------------------------------------------
class ScreenRecorder:
    """Captures the full virtual screen to a video file. Pausing simply
    stops feeding frames to ffmpeg, so paused time never appears in the
    output (no frozen frames, no gap to edit out)."""

    def __init__(self, fps, codec_args, output_path, on_error=None):
        self.fps = fps
        self.codec_args = codec_args
        self.output_path = output_path
        self.on_error = on_error
        self.is_recording = False
        self.paused = False
        self.size = None
        self._proc = None
        self._thread = None
        self._stop_event = threading.Event()
        self._start_time = None
        self._paused_elapsed = 0.0
        self._pause_started = None

    def start(self):
        probe = ImageGrab.grab(all_screens=True)
        w, h = probe.size
        w -= w % 2  # even dimensions required by yuv420p
        h -= h % 2
        self.size = (w, h)

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [ffmpeg_exe, "-y", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{w}x{h}", "-r", str(self.fps), "-i", "-",
               *self.codec_args, "-r", str(self.fps), self.output_path]
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                      stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL,
                                      creationflags=creationflags)
        self.is_recording = True
        self.paused = False
        self._start_time = time.perf_counter()
        self._paused_elapsed = 0.0
        self._pause_started = None
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        w, h = self.size
        interval = 1.0 / self.fps
        next_frame = time.perf_counter()
        try:
            while not self._stop_event.is_set():
                if self.paused:
                    time.sleep(0.05)
                    next_frame = time.perf_counter()
                    continue
                frame = ImageGrab.grab(all_screens=True)
                if frame.size != self.size:
                    frame = frame.crop((0, 0, w, h))
                self._proc.stdin.write(frame.convert("RGB").tobytes())
                next_frame += interval
                sleep_time = next_frame - time.perf_counter()
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    next_frame = time.perf_counter()
        except (BrokenPipeError, OSError) as exc:
            if self.on_error:
                self.on_error(str(exc))

    def pause(self):
        if not self.paused:
            self.paused = True
            self._pause_started = time.perf_counter()

    def resume(self):
        if self.paused:
            self.paused = False
            self._paused_elapsed += time.perf_counter() - self._pause_started
            self._pause_started = None

    def elapsed(self):
        if self._start_time is None:
            return 0.0
        now = time.perf_counter()
        paused = self._paused_elapsed
        if self.paused and self._pause_started:
            paused += now - self._pause_started
        return max(0.0, now - self._start_time - paused)

    def stop(self):
        self.is_recording = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        if self._proc:
            try:
                self._proc.stdin.close()
            except OSError:
                pass
            try:
                self._proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        return self.output_path


# Supersample factor for anti-aliased chrome: tk's native polygon/oval fills
# have no anti-aliasing on Windows, which shows up as jagged edges on round
# shapes (most visibly the traffic-light dots). Draw shapes bigger with PIL,
# which does anti-alias, then downsample - crisp edges at any DPI.
AA_SUPERSAMPLE = 4


def _round_rect_image(w, h, radius, fill, border=None, border_width=1):
    w, h = max(1, round(w)), max(1, round(h))
    ss = AA_SUPERSAMPLE
    r = max(1, min(radius, h // 2, w // 2)) * ss
    image = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([0, 0, w * ss - 1, h * ss - 1], radius=r,
                           fill=hex_rgb(fill) + (255,),
                           outline=hex_rgb(border or fill) + (255,),
                           width=max(1, border_width * ss))
    return image.resize((w, h), Image.Resampling.LANCZOS)


def _circle_image(diameter, fill, border=None, border_width=1):
    d = max(1, round(diameter))
    ss = AA_SUPERSAMPLE
    image = Image.new("RGBA", (d * ss, d * ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    inset = max(1, border_width * ss) / 2
    draw.ellipse([inset, inset, d * ss - 1 - inset, d * ss - 1 - inset],
                fill=hex_rgb(fill) + (255,) if fill else None,
                outline=hex_rgb(border) + (255,) if border else None,
                width=max(1, border_width * ss))
    return image.resize((d, d), Image.Resampling.LANCZOS)


def draw_panel(canvas, x1, y1, x2, y2, radius, fill, border=None, tags=""):
    """Anti-aliased rounded panel, rendered as a supersampled PIL image so
    corners stay smooth. Returns the PhotoImage - the caller must keep a
    reference (Tk drops images with no live Python reference) e.g.
    `self._panel_photo = draw_panel(...)`."""
    x1, y1 = round(x1), round(y1)
    image = _round_rect_image(x2 - x1, y2 - y1, radius, fill, border)
    photo = ImageTk.PhotoImage(image)
    canvas.create_image(x1, y1, image=photo, anchor="nw", tags=tags)
    return photo


# ---------------------------------------------------------------------------
# Fonts - prefer SF Pro on macOS and Segoe UI on Windows; fall back to
# whichever common Linux UI font is actually installed.
# ---------------------------------------------------------------------------
FONT = "Segoe UI"
FONT_SEMI = "Segoe UI Semibold"

FONT_CANDIDATES = ("Segoe UI", "SF Pro Display", "SF Pro Text",
                   "Helvetica Neue", "Ubuntu", "Noto Sans", "Cantarell",
                   "DejaVu Sans", "Liberation Sans")


def init_fonts(root):
    global FONT, FONT_SEMI
    families = set(tkfont.families())
    for family in FONT_CANDIDATES:
        if family in families:
            FONT = family
            semi = next((f"{family} {suffix}"
                        for suffix in ("Semibold", "SemiBold", "Bold")
                        if f"{family} {suffix}" in families), family)
            FONT_SEMI = semi
            break


def fnt(size):
    return (FONT, size)


def fnt_sb(size):
    if FONT_SEMI != FONT:
        return (FONT_SEMI, size)
    return (FONT, size, "bold")


# ---------------------------------------------------------------------------
# Glass widgets (canvas based, with animated hover states)
# ---------------------------------------------------------------------------
class GlassButton(tk.Canvas):
    """Capsule button in primary / glass / plain variants.

    `set_selected` turns a plain button into a lit toggle (used for tools)."""

    def __init__(self, parent, text, command=None, variant="glass",
                 width=120, height=44, radius=None, font=None):
        self._bg = parent.cget("bg")
        width, height = sc(width), sc(height)
        super().__init__(parent, width=width, height=height, bg=self._bg,
                         highlightthickness=0, cursor="hand2")
        self.command = command
        self.text = text
        self.variant = variant
        self.font = font or fnt_sb(10)
        self.radius = sc(radius) if radius is not None else int(height) // 2
        self._cw, self._ch = int(width), int(height)
        self._panel_photo = None
        self._glow = 0.0
        self._pressed = False
        self._selected = False
        self._anim = None
        self._draw()

        self.bind("<Enter>", lambda e: self._animate_glow(1.0))
        self.bind("<Leave>", lambda e: self._animate_glow(0.0))
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def set_selected(self, selected):
        self._selected = selected
        self._draw()

    def set_text(self, text):
        self.text = text
        self._draw()

    def _colors(self):
        """Returns (fill, border, fg); fill may be None for no backdrop."""
        g = self._glow
        if self._selected:
            fill = blend(self._bg, COL["accent"], 0.16 + 0.05 * g)
            return fill, blend(COL["accent"], self._bg, 0.35), \
                COL["accent_soft"]
        if self.variant == "primary":
            base = COL["accent"]
            if self._pressed:
                base = blend(base, "#000000", 0.18)
            elif g:
                base = blend(base, "#FFFFFF", 0.10 * g)
            return base, None, "#FFFFFF"
        if self.variant == "glass":
            t = 0.10 if self._pressed else 0.05 * g
            return (blend(COL["glass_high"], COL["text"], t),
                    COL["border_bright"], COL["text"])
        # plain: invisible at rest, faint tint on hover / press
        t = 0.12 if self._pressed else 0.07 * g
        fill = blend(self._bg, COL["text"], t) if t > 0.005 else None
        return fill, None, COL["accent_soft"]

    def _draw(self):
        self.delete("all")
        fill, border, fg = self._colors()
        w, h = self._cw, self._ch
        if fill:
            self._panel_photo = draw_panel(self, 1, 1, w - 1, h - 1,
                                           self.radius, fill, border=border)
        self.create_text(w // 2, h // 2, text=self.text, fill=fg,
                         font=self.font)

    def _animate_glow(self, target, steps=6):
        if self._anim:
            self.after_cancel(self._anim)
            self._anim = None
        start = self._glow

        def frame(i):
            if not self.winfo_exists():
                return
            self._glow = start + (target - start) * ease_out(i / steps)
            self._draw()
            if i < steps:
                self._anim = self.after(16, frame, i + 1)
            else:
                self._anim = None
        frame(1)

    def _on_press(self, _event):
        if self._anim:
            self.after_cancel(self._anim)
            self._anim = None
        self._pressed = True
        self._draw()

    def _on_release(self, event):
        self._pressed = False
        inside = (0 <= event.x <= self.winfo_width()
                  and 0 <= event.y <= self.winfo_height())
        self._glow = 1.0 if inside else 0.0
        self._draw()
        if inside and self.command:
            self.command()


class GlassSegmented(tk.Canvas):
    """Segmented control with a sliding thumb."""

    PAD = 3

    def __init__(self, parent, options, value, command=None,
                 seg_width=86, height=38):
        self._bg = parent.cget("bg")
        self.pad = sc(self.PAD)
        seg_width, height = sc(seg_width), sc(height)
        width = seg_width * len(options) + 2 * self.pad
        super().__init__(parent, width=width, height=height, bg=self._bg,
                         highlightthickness=0, cursor="hand2")
        self.options = list(options)
        self.value = value
        self.command = command
        self.seg_width = seg_width
        self._cw, self._ch = int(width), int(height)
        self._tx = float(self._target_x(self.options.index(value)))
        self._anim = None
        self._track_photo = None
        self._thumb_photo = None
        self._draw()
        self.bind("<Button-1>", self._on_click)

    def _target_x(self, index):
        return self.pad + index * self.seg_width

    def set_value(self, value):
        if value in self.options:
            self.value = value
            self._tx = float(self._target_x(self.options.index(value)))
            self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self._cw, self._ch
        self._track_photo = draw_panel(self, 1, 1, w - 1, h - 1, h // 2,
                                       COL["seg_track"], border=COL["border"])
        x1 = self._tx
        y1, y2 = self.pad + 1, h - self.pad - 1
        self._thumb_photo = draw_panel(
            self, x1, y1, x1 + self.seg_width, y2, (y2 - y1) // 2,
            COL["seg_thumb"], border=COL["border_bright"])
        for i, name in enumerate(self.options):
            cx = self.pad + i * self.seg_width + self.seg_width // 2
            selected = name == self.value
            self.create_text(cx, h // 2, text=name,
                             fill=COL["text"] if selected
                             else COL["text_secondary"],
                             font=fnt_sb(9) if selected else fnt(9))

    def _on_click(self, event):
        index = int((event.x - self.pad) // self.seg_width)
        index = max(0, min(len(self.options) - 1, index))
        name = self.options[index]
        if name == self.value:
            return
        self.value = name
        self._slide_to(self._target_x(index))
        if self.command:
            self.command(name)

    def _slide_to(self, target, steps=10):
        if self._anim:
            self.after_cancel(self._anim)
            self._anim = None
        start = self._tx

        def frame(i):
            if not self.winfo_exists():
                return
            self._tx = start + (target - start) * ease_out(i / steps)
            self._draw()
            if i < steps:
                self._anim = self.after(14, frame, i + 1)
            else:
                self._anim = None
        frame(1)


class GlassSwitch(tk.Canvas):
    """Toggle switch: grey track, accent when on, sliding white knob."""

    def __init__(self, parent, value=False, command=None, width=50, height=30):
        self._bg = parent.cget("bg")
        width, height = sc(width), sc(height)
        super().__init__(parent, width=width, height=height, bg=self._bg,
                         highlightthickness=0, cursor="hand2")
        self.value = bool(value)
        self.command = command
        self._cw, self._ch = int(width), int(height)
        self._pos = 1.0 if self.value else 0.0  # knob position 0..1
        self._anim = None
        self._track_photo = None
        self._knob_photo = None
        self._draw()
        self.bind("<Button-1>", lambda e: self.toggle())

    def toggle(self):
        self.value = not self.value
        self._animate(1.0 if self.value else 0.0)
        if self.command:
            self.command(self.value)

    def _draw(self):
        self.delete("all")
        w, h, r = self._cw, self._ch, self._ch // 2
        p = self._pos
        track = blend(COL["glass_dim"], COL["accent"], p)
        border = blend(COL["border"], COL["accent"], p)
        self._track_photo = draw_panel(self, 1, 1, w - 1, h - 1, r, track,
                                       border=border)
        kr = r - sc(4)
        kx = r + p * (w - 2 * r)
        cy = h // 2
        self._knob_photo = ImageTk.PhotoImage(
            _circle_image(2 * kr, "#FFFFFF", border=COL["border_bright"]))
        self.create_image(kx - kr, cy - kr, image=self._knob_photo,
                          anchor="nw")

    def _animate(self, target, steps=8):
        if self._anim:
            self.after_cancel(self._anim)
            self._anim = None
        start = self._pos

        def frame(i):
            if not self.winfo_exists():
                return
            self._pos = start + (target - start) * ease_out(i / steps)
            self._draw()
            if i < steps:
                self._anim = self.after(14, frame, i + 1)
            else:
                self._anim = None
        frame(1)


class GlassSlider(tk.Canvas):
    """Slider with a slim accent track and a white knob."""

    PAD = 14

    def __init__(self, parent, from_=40, to=100, value=90, command=None,
                 width=300, height=36):
        self._bg = parent.cget("bg")
        self.pad = sc(self.PAD)
        width, height = sc(width), sc(height)
        super().__init__(parent, width=width, height=height, bg=self._bg,
                         highlightthickness=0, cursor="hand2")
        self.from_, self.to = from_, to
        self.value = value
        self.command = command
        self._cw, self._ch = int(width), int(height)
        self._thumb_photo = None
        self._draw()
        self.bind("<Button-1>", self._on_drag)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        self._cw = event.width
        self._draw()

    def _thumb_x(self):
        span = self._cw - 2 * self.pad
        frac = (self.value - self.from_) / (self.to - self.from_)
        return self.pad + frac * span

    def _draw(self):
        self.delete("all")
        cy = self._ch // 2
        tx = self._thumb_x()
        lw = sc(4)
        self.create_line(self.pad, cy, self._cw - self.pad, cy,
                         fill=blend(self._bg, COL["text"], 0.14), width=lw,
                         capstyle="round")
        self.create_line(self.pad, cy, tx, cy,
                         fill=COL["accent"], width=lw, capstyle="round")
        tr = sc(9)
        self._thumb_photo = ImageTk.PhotoImage(
            _circle_image(2 * tr, "#FFFFFF", border=COL["border_bright"]))
        self.create_image(tx - tr, cy - tr, image=self._thumb_photo,
                          anchor="nw")

    def _on_drag(self, event):
        span = self._cw - 2 * self.pad
        frac = min(1.0, max(0.0, (event.x - self.pad) / span))
        new_value = round(self.from_ + frac * (self.to - self.from_))
        if new_value != self.value:
            self.value = new_value
            self._draw()
            if self.command:
                self.command(new_value)


class ColorDot(tk.Canvas):
    """Small color swatch; an accent ring marks the selected color."""

    def __init__(self, parent, color, command=None, size=26):
        self._bg = parent.cget("bg")
        size = sc(size)
        super().__init__(parent, width=size, height=size, bg=self._bg,
                         highlightthickness=0, cursor="hand2")
        self.color = color
        self.command = command
        self.size = size
        self.selected = False
        self._photo = None
        self._draw()
        self.bind("<Button-1>",
                  lambda e: self.command and self.command(self.color))

    def set_selected(self, selected):
        self.selected = selected
        self._draw()

    def _draw(self):
        self.delete("all")
        s = self.size
        d = 2 * (s // 2 - 5)
        canvas_img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        if self.selected:
            ring = _circle_image(d + 6, None, border=COL["accent"],
                                 border_width=2)
            canvas_img.paste(ring, (s // 2 - (d + 6) // 2,
                                    s // 2 - (d + 6) // 2), ring)
        dot = _circle_image(d, self.color, border=COL["border_bright"])
        canvas_img.paste(dot, (s // 2 - d // 2, s // 2 - d // 2), dot)
        self._photo = ImageTk.PhotoImage(canvas_img)
        self.create_image(0, 0, image=self._photo, anchor="nw")


class WidthDot(tk.Canvas):
    """Stroke width selector shown as a filled dot of that weight."""

    def __init__(self, parent, width_value, command=None, size=26):
        self._bg = parent.cget("bg")
        size = sc(size)
        super().__init__(parent, width=size, height=size, bg=self._bg,
                         highlightthickness=0, cursor="hand2")
        self.width_value = width_value
        self.command = command
        self.size = size
        self.selected = False
        self._photo = None
        self._draw()
        self.bind("<Button-1>",
                  lambda e: self.command and self.command(self.width_value))

    def set_selected(self, selected):
        self.selected = selected
        self._draw()

    def _draw(self):
        self.delete("all")
        s = self.size
        d = 2 * sc(2 + self.width_value)
        fill = COL["text"] if self.selected else COL["text_secondary"]
        canvas_img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        if self.selected:
            inset = sc(3)
            ring = _circle_image(s - 2 * inset, None, border=COL["accent"])
            canvas_img.paste(ring, (inset, inset), ring)
        dot = _circle_image(d, fill)
        canvas_img.paste(dot, (s // 2 - d // 2, s // 2 - d // 2), dot)
        self._photo = ImageTk.PhotoImage(canvas_img)
        self.create_image(0, 0, image=self._photo, anchor="nw")


class Tooltip:
    """Small hover tooltip shown under buttons, as a floating pill."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        self.job = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<Button-1>", self._hide, add="+")

    def _show(self):
        if self.tip:
            return
        font = tkfont.Font(family=FONT, size=9)
        w = font.measure(self.text) + sc(26)
        h = sc(28)
        self.tip = tk.Toplevel(self.widget)
        self.tip.overrideredirect(True)
        self.tip.attributes("-topmost", True)
        set_window_alpha(self.tip, 0.97)
        try:  # knock out the square corners around the pill
            self.tip.attributes("-transparentcolor", COL["bg"])
        except tk.TclError:
            pass
        canvas = tk.Canvas(self.tip, width=w, height=h, bg=COL["bg"],
                           highlightthickness=0)
        canvas.pack()
        self._tip_photo = draw_panel(canvas, 1, 1, w - 1, h - 1, h // 2,
                                     COL["glass_high"],
                                     border=COL["border_bright"])
        canvas.create_text(w // 2, h // 2, text=self.text, fill=COL["text"],
                           font=font)
        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + sc(6)
        self.tip.geometry(f"{w}x{h}+{x - w // 2}+{y}")

    def _schedule(self, _event):
        self.job = self.widget.after(600, self._show)

    def _hide(self, _event=None):
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None
        if self.tip:
            self.tip.destroy()
            self.tip = None


class TrafficLights(tk.Canvas):
    """macOS-style window controls: close, minimize, zoom. Glyphs appear
    inside the dots on hover."""

    D = 13   # dot diameter
    GAP = 7
    DOTS = (("#FF5F57", "#E0443E", "#7A1E16"),   # close
            ("#FEBC2E", "#D89E24", "#8F5E12"),   # minimize
            ("#28C840", "#1DAD2B", "#0B650D"))   # zoom

    def __init__(self, parent, commands):
        self._bg = parent.cget("bg")
        self.d = sc(self.D)
        self.gap = sc(self.GAP)
        self.pad = sc(2)
        w = 3 * self.d + 2 * self.gap + 2 * self.pad
        h = self.d + 2 * self.pad
        super().__init__(parent, width=w, height=h, bg=self._bg,
                         highlightthickness=0, cursor="hand2")
        self.commands = commands  # (close, minimize, zoom)
        self._hover = False
        self._photo = None
        self._draw()
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Button-1>", self._on_click)

    def _set_hover(self, hover):
        self._hover = hover
        self._draw()

    def _draw(self):
        """Rendered as one supersampled PIL image - tk's raw create_oval /
        create_line have no anti-aliasing on Windows, which is what made the
        dots (and their hover glyphs) look jagged at the edges."""
        self.delete("all")
        w, h = int(self["width"]), int(self["height"])
        ss = AA_SUPERSAMPLE
        d, gap, pad = self.d, self.gap, self.pad
        image = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        for i, (fill, edge, glyph) in enumerate(self.DOTS):
            x = pad + i * (d + gap)
            y = pad
            draw.ellipse([x * ss, y * ss, (x + d) * ss - 1, (y + d) * ss - 1],
                        fill=hex_rgb(fill) + (255,),
                        outline=hex_rgb(edge) + (255,), width=ss)
            if not self._hover:
                continue
            cx, cy = (x + d / 2) * ss, (y + d / 2) * ss
            r = (d / 2 - 3.2) * ss
            lw = max(1, round(1.4 * ss))
            g = hex_rgb(glyph) + (255,)
            if i == 0:    # x
                draw.line([cx - r, cy - r, cx + r, cy + r], fill=g, width=lw)
                draw.line([cx - r, cy + r, cx + r, cy - r], fill=g, width=lw)
            elif i == 1:  # minus
                draw.line([cx - r, cy, cx + r, cy], fill=g, width=lw)
            else:         # plus
                draw.line([cx - r, cy, cx + r, cy], fill=g, width=lw)
                draw.line([cx, cy - r, cx, cy + r], fill=g, width=lw)
        image = image.resize((w, h), Image.Resampling.LANCZOS)
        self._photo = ImageTk.PhotoImage(image)
        self.create_image(0, 0, image=self._photo, anchor="nw")

    def _on_click(self, event):
        index = int((event.x - self.pad) // (self.d + self.gap))
        index = max(0, min(2, index))
        self.commands[index]()


class GlassCard(tk.Canvas):
    """Rounded pane with a hairline edge, hosting an inner frame."""

    def __init__(self, parent, height, radius=20, pad=18):
        super().__init__(parent, height=sc(height), bg=parent.cget("bg"),
                         highlightthickness=0)
        self.radius = sc(radius)
        self.pad = sc(pad)
        self.inner = tk.Frame(self, bg=COL["glass"])
        self._win = None
        self._card_photo = None
        self.bind("<Configure>", self._redraw)

    def _redraw(self, _event=None):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2 * self.pad:
            return
        self.delete("card")
        self._card_photo = draw_panel(self, 1, 1, w - 1, h - 1, self.radius,
                                      COL["glass"], border=COL["border"],
                                      tags="card")
        self.tag_lower("card")
        if self._win is None:
            self._win = self.create_window(self.pad, self.pad, anchor="nw",
                                           window=self.inner)
        self.itemconfig(self._win, width=w - 2 * self.pad,
                        height=h - 2 * self.pad)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
TOOLS = (
    ("pen",       "✎", "Pen"),
    ("highlight", "▨", "Highlighter"),
    ("line",      "╱", "Line"),
    ("arrow",     "↗", "Arrow"),
    ("rect",      "▭", "Rectangle"),
    ("ellipse",   "◯", "Ellipse"),
    ("text",      "T",      "Text"),
    ("crop",      "⬚", "Crop"),
)

THEME_POLL_MS = 2500


class SnippyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Snippy")

        global SCALE
        SCALE = get_dpi_scale(_root_hwnd(root))
        self.dpi_scale = SCALE
        root.tk.call("tk", "scaling", SCALE * 96.0 / 72.0)

        width, height = sc(1100), sc(800)
        x = (root.winfo_screenwidth() - width) // 2
        y = (root.winfo_screenheight() - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(sc(960), sc(700))
        set_window_alpha(self.root, 0.0)  # faded in on launch

        self.dark = system_dark_mode()
        set_theme(self.dark)
        self.root.configure(bg=COL["bg"])

        self.settings = load_settings()
        self.icons = self._pick_icons()

        # capture state
        self.screenshot = None
        self.history = []          # newest first, screenshot is history[idx]
        self.history_index = -1
        self._undo = []
        self._preview_photo = None
        self._thumb_photos = []
        self._toast = None
        self._toast_job = None
        self._transitioning = False
        self._showing_settings = False

        # annotation state
        self.tool = None
        self.annot_color = ANNOT_COLORS[0]
        self.annot_width = ANNOT_WIDTHS[1]
        self._scale = None         # preview scale / offsets for coord mapping
        self._offset = (0, 0)
        self._drag_start = None
        self._pen_points = []

        # capture-overlay state
        self.overlay_window = None
        self.overlay_canvas = None
        self.selection_active = False
        self.start_x = self.start_y = self.end_x = self.end_y = 0

        # screen-recording state
        self.recorder = None
        self._record_bar = None
        self._record_bar_job = None
        self._pause_btn = None
        self._record_dot = None
        self._record_timer_text = None

        # frameless window with custom traffic-light controls
        self._frameless = strip_titlebar(self.root)
        if self._frameless:
            # re-strip if Windows restores the caption (e.g. after minimize)
            self.root.bind("<Map>", lambda e: strip_titlebar(self.root))

        self._build_ui()
        self._bind_shortcuts()
        self._fade_in()
        self.root.after(THEME_POLL_MS, self._watch_theme)
        self.root.after(THEME_POLL_MS, self._watch_dpi)

        self.hotkeys = GlobalHotkeys([
            (1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, RECORD_HOTKEY_VK,
             lambda: self.root.after(0, self.toggle_recording)),
            (2, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, PAUSE_HOTKEY_VK,
             lambda: self.root.after(0, self.toggle_pause_recording)),
        ])
        self.hotkeys.start()
        self.root.protocol("WM_DELETE_WINDOW", self._close_window)

    def _build_ui(self):
        if getattr(self, "titlebar", None):
            self.titlebar.destroy()
        self.titlebar = None
        if self._frameless:
            self._build_titlebar()
        self.container = tk.Frame(self.root, bg=COL["bg"])
        self.container.pack(fill="both", expand=True)
        self.main_view = tk.Frame(self.container, bg=COL["bg"])
        self.settings_view = tk.Frame(self.container, bg=COL["bg"])
        self._build_main_view()
        self._build_settings_view()
        shown = self.settings_view if self._showing_settings else self.main_view
        shown.place(relx=0, rely=0, relwidth=1, relheight=1)

    # -- custom titlebar ------------------------------------------------------
    def _build_titlebar(self):
        bar = tk.Frame(self.root, bg=COL["bg"], height=sc(34))
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)
        lights = TrafficLights(bar, (self._close_window, self._minimize,
                                     self._toggle_zoom))
        lights.pack(side="left", padx=(sc(14), 0), pady=sc(9))
        title = tk.Label(bar, text="Snippy", bg=COL["bg"],
                         fg=COL["text_tertiary"], font=fnt_sb(9))
        title.place(relx=0.5, rely=0.5, anchor="center")
        for widget in (bar, title):
            widget.bind("<Button-1>", self._titlebar_press)
            widget.bind("<B1-Motion>", self._titlebar_drag)
        self.titlebar = bar

    def _close_window(self):
        """Fade out then tear down - the single path all closes route through
        (traffic-light X, Alt+F4, taskbar close) so every one gets the fade."""
        alpha = get_window_alpha(self.root) - 0.09
        if alpha <= 0 or not set_window_alpha(self.root, alpha):
            self._on_close()
        else:
            self.root.after(16, self._close_window)

    def _on_close(self):
        if self.recorder:
            self.recorder.stop()
            self.recorder = None
        if getattr(self, "hotkeys", None):
            self.hotkeys.stop()
        self.root.destroy()

    def _minimize(self):
        self.root.iconify()

    def _toggle_zoom(self):
        zoomed = self.root.state() == "zoomed"
        self.root.state("normal" if zoomed else "zoomed")

    def _titlebar_press(self, event):
        if event.time - getattr(self, "_titlebar_click_time", -10**9) < 400:
            self._titlebar_click_time = -10**9  # double click: toggle zoom
            self._toggle_zoom()
            return
        self._titlebar_click_time = event.time
        self._drag_origin = None
        if sys.platform == "win32":
            try:  # native caption drag: use PostMessage to avoid re-entrancy
                # PostMessage is asynchronous and avoids processing window
                # messages synchronously inside the SendMessage call, which
                # can re-enter the Tcl event loop and trigger GIL issues.
                user32 = ctypes.windll.user32
                user32.ReleaseCapture()
                user32.PostMessageW(_root_hwnd(self.root), 0x00A1, 2, 0)
                return
            except Exception:
                pass
        self._drag_origin = (event.x_root - self.root.winfo_x(),
                             event.y_root - self.root.winfo_y())

    def _titlebar_drag(self, event):
        if getattr(self, "_drag_origin", None):
            dx, dy = self._drag_origin
            self.root.geometry(f"+{event.x_root - dx}+{event.y_root - dy}")

    # -- theme switching -----------------------------------------------------
    def _watch_theme(self):
        dark = system_dark_mode()
        if dark != self.dark:
            self._apply_theme(dark)
        self.root.after(THEME_POLL_MS, self._watch_theme)

    def _apply_theme(self, dark):
        """Re-skin live: recompute the palette and rebuild the themed views."""
        self.dark = dark
        set_theme(dark)
        self.root.configure(bg=COL["bg"])
        set_window_alpha(self.root, COL["alpha"])

        if self._toast_job:
            self.root.after_cancel(self._toast_job)
            self._toast_job = None
        if self._toast:
            self._toast.destroy()
            self._toast = None

        delay = self.delay_seg.value
        status = self.status_var.get()
        tool = self.tool
        self.tool = None
        self._drag_start = None
        self._transitioning = False
        self.container.destroy()
        self._build_ui()
        self.delay_seg.set_value(delay)
        self.status_var.set(status)
        if tool:
            self.set_tool(tool)

    # -- DPI switching (moving the window to a monitor with a different
    # scaling factor) -------------------------------------------------------
    def _watch_dpi(self):
        scale = get_dpi_scale(_root_hwnd(self.root))
        if abs(scale - self.dpi_scale) > 0.001:
            self._apply_dpi(scale)
        self.root.after(THEME_POLL_MS, self._watch_dpi)

    def _apply_dpi(self, scale):
        """Re-scale live: every widget size in this file is authored for a
        96 DPI screen and multiplied by the global SCALE at construction
        time, so picking up a new monitor's DPI just means rebuilding."""
        global SCALE
        SCALE = scale
        self.dpi_scale = scale
        self.root.tk.call("tk", "scaling", scale * 96.0 / 72.0)

        width, height = sc(1100), sc(800)
        self.root.minsize(sc(960), sc(700))
        self.root.geometry(f"{width}x{height}")

        if self._toast_job:
            self.root.after_cancel(self._toast_job)
            self._toast_job = None
        if self._toast:
            self._toast.destroy()
            self._toast = None

        delay = self.delay_seg.value
        status = self.status_var.get()
        tool = self.tool
        self.tool = None
        self._drag_start = None
        self._transitioning = False
        self.container.destroy()
        self._build_ui()
        self.delay_seg.set_value(delay)
        self.status_var.set(status)
        if tool:
            self.set_tool(tool)

    @staticmethod
    def _pick_icons():
        """Prefer Windows' Fluent/MDL2 icon fonts, fall back to symbols.

        Returns {name: (glyph, font)} so fluent and unicode glyphs can mix."""
        symbol = ("Segoe UI Symbol", 12)
        families = set(tkfont.families())
        for family in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
            if family in families:
                fluent = (family, 11)
                return {"settings":  ("\uE713", fluent),
                        "copy":      ("\uE8C8", fluent),
                        "save":      ("\uE74E", fluent),
                        "back":      ("\uE72B", fluent),
                        "quicksave": ("\uE896", fluent),   # Download
                        "clear":     ("\uE74D", fluent)}   # Delete
        return {"settings": ("⚙", symbol), "copy": ("⧉", symbol),
                "save": ("💾", symbol), "back": ("←", symbol),
                "quicksave": ("↓", symbol), "clear": ("×", symbol)}

    def _bind_shortcuts(self):
        self.root.bind("<Control-n>", lambda e: self.start_region_capture())
        self.root.bind("<Control-f>", lambda e: self.start_fullscreen_capture())
        self.root.bind("<Control-s>", lambda e: self.save_screenshot())
        self.root.bind("<Control-q>", lambda e: self.quick_save())
        self.root.bind("<Control-c>", lambda e: self.copy_to_clipboard())
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Delete>", lambda e: self.remove_current())
        self.root.bind("<Print>", lambda e: self.start_region_capture())

    # -- window / view transitions -----------------------------------------
    def _fade_in(self, alpha=0.0):
        alpha = min(alpha + 0.09, COL["alpha"])
        set_window_alpha(self.root, alpha)
        if alpha < COL["alpha"]:
            self.root.after(16, self._fade_in, alpha)

    def _slide_to(self, incoming, outgoing, direction, steps=16):
        """Slide `incoming` over `outgoing`; direction 1 = from right."""
        if self._transitioning:
            return
        self._transitioning = True
        incoming.place(relx=direction, rely=0, relwidth=1, relheight=1)
        incoming.lift()

        def frame(i):
            if not incoming.winfo_exists():
                return
            t = ease_out(i / steps)
            incoming.place_configure(relx=direction * (1 - t))
            outgoing.place_configure(relx=-direction * t)
            if i < steps:
                self.root.after(12, frame, i + 1)
            else:
                outgoing.place_forget()
                incoming.place_configure(relx=0)
                self._transitioning = False
        frame(1)

    def open_settings(self):
        self._showing_settings = True
        self._slide_to(self.settings_view, self.main_view, 1)

    def close_settings(self):
        self._showing_settings = False
        self._slide_to(self.main_view, self.settings_view, -1)

    # -- main view -----------------------------------------------------------
    def _build_main_view(self):
        view = self.main_view

        # header: title, capture actions, delay, icon actions
        top = tk.Frame(view, bg=COL["bg"])
        top.pack(fill="x", padx=28, pady=(20, 10))
        titles = tk.Frame(top, bg=COL["bg"])
        titles.pack(side="left")
        tk.Label(titles, text="Snippy", bg=COL["bg"], fg=COL["text"],
                 font=fnt_sb(20)).pack(anchor="w")
        tk.Label(titles, text="Screenshot studio", bg=COL["bg"],
                 fg=COL["text_secondary"], font=fnt(9)).pack(anchor="w")

        GlassButton(top, "＋  Snip region", command=self.start_region_capture,
                    variant="primary", width=160, height=44,
                    font=fnt_sb(11)).pack(side="left", padx=(26, 8))
        GlassButton(top, "Full screen", command=self.start_fullscreen_capture,
                    variant="glass", width=120, height=44,
                    font=fnt_sb(10)).pack(side="left", padx=(0, 8))
        record_btn = GlassButton(top, "⏺  Record", command=self.toggle_recording,
                                 variant="glass", width=120, height=44,
                                 font=fnt_sb(10))
        record_btn.pack(side="left", padx=(0, 12))
        Tooltip(record_btn, "Start screen recording (Ctrl+Alt+R)")
        delay_box = tk.Frame(top, bg=COL["bg"])
        delay_box.pack(side="left")
        tk.Label(delay_box, text="Delay", bg=COL["bg"],
                 fg=COL["text_tertiary"], font=fnt(8)).pack(anchor="w")
        self.delay_seg = GlassSegmented(delay_box, ["0s", "3s", "10s"],
                                        value="0s", seg_width=44, height=26)
        self.delay_seg.pack(anchor="w")

        # packed right-to-left: settings, quick save, save as, copy, remove
        for icon, tip, command in (
                ("settings", "Settings", self.open_settings),
                ("quicksave", "Quick save (Ctrl+Q)", self.quick_save),
                ("save", "Save as… (Ctrl+S)", self.save_screenshot),
                ("copy", "Copy (Ctrl+C)", self.copy_to_clipboard),
                ("clear", "Remove capture (Del)", self.remove_current)):
            glyph, font = self.icons[icon]
            btn = GlassButton(top, glyph, command=command, variant="plain",
                              width=44, height=44, radius=22, font=font)
            btn.pack(side="right", padx=3)
            Tooltip(btn, tip)

        # annotation toolbar
        bar = GlassCard(view, height=58, radius=18, pad=8)
        bar.pack(fill="x", padx=28)
        inner = bar.inner
        self.tool_buttons = {}
        for name, glyph, tip in TOOLS:
            font = fnt_sb(12) if name == "text" else ("Segoe UI Symbol", 12)
            btn = GlassButton(inner, glyph,
                              command=lambda n=name: self.set_tool(n),
                              variant="plain", width=40, height=40,
                              radius=20, font=font)
            btn.pack(side="left", padx=2)
            Tooltip(btn, tip)
            self.tool_buttons[name] = btn

        tk.Frame(inner, bg=COL["border"], width=1, height=sc(26)
                 ).pack(side="left", padx=sc(10), pady=sc(7))
        self.color_dots = {}
        for color in ANNOT_COLORS:
            dot = ColorDot(inner, color, command=self.set_color)
            dot.pack(side="left", padx=1, pady=7)
            self.color_dots[color] = dot
        self.color_dots[self.annot_color].set_selected(True)

        tk.Frame(inner, bg=COL["border"], width=1, height=sc(26)
                 ).pack(side="left", padx=sc(10), pady=sc(7))
        self.width_dots = {}
        for w in ANNOT_WIDTHS:
            dot = WidthDot(inner, w, command=self.set_width)
            dot.pack(side="left", padx=1, pady=7)
            self.width_dots[w] = dot
        self.width_dots[self.annot_width].set_selected(True)

        undo_btn = GlassButton(inner, "↺", command=self.undo,
                               variant="plain", width=40, height=40,
                               radius=20, font=("Segoe UI Symbol", 12))
        undo_btn.pack(side="right", padx=2)
        Tooltip(undo_btn, "Undo (Ctrl+Z)")

        # status row (packed before history so it sits at the very bottom)
        status = tk.Frame(view, bg=COL["bg"])
        status.pack(side="bottom", fill="x", padx=30, pady=(4, 12))
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(status, textvariable=self.status_var, bg=COL["bg"],
                 fg=COL["text_tertiary"], font=fnt(9)).pack(side="left")
        tk.Label(status,
                 text="Ctrl+N region · Ctrl+F full screen · Ctrl+Z undo",
                 bg=COL["bg"], fg=COL["text_tertiary"], font=fnt(8)
                 ).pack(side="right")

        # history rail
        self.history_strip = tk.Frame(view, bg=COL["bg"], height=sc(84))
        self.history_strip.pack(side="bottom", fill="x", padx=28, pady=(10, 0))
        self.history_strip.pack_propagate(False)
        self._render_history()

        # preview canvas
        self.preview_canvas = tk.Canvas(view, bg=COL["bg"],
                                        highlightthickness=0)
        self.preview_canvas.pack(fill="both", expand=True, padx=28,
                                 pady=(12, 0))
        self.preview_canvas.bind("<Configure>", lambda e: self._draw_preview())
        self.preview_canvas.bind("<Button-1>", self._on_preview_press)
        self.preview_canvas.bind("<B1-Motion>", self._on_preview_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", self._on_preview_release)

    # -- preview & coordinate mapping ------------------------------------------
    def _draw_preview(self):
        c = self.preview_canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 40 or h < 40:
            return
        self._preview_panel_photo = draw_panel(
            c, 1, 1, w - 1, h - 1, sc(24), COL["glass_dim"],
            border=COL["border"])
        if self.screenshot is None:
            self._scale = None
            c.create_text(w // 2, h // 2 - 14, text="\U0001F5BC",
                          font=("Segoe UI Emoji", 22),
                          fill=COL["text_tertiary"])
            c.create_text(w // 2, h // 2 + 20,
                          text="No capture yet · press Ctrl+N to snip",
                          font=fnt(10), fill=COL["text_secondary"])
            self._preview_photo = None
            return
        iw, ih = self.screenshot.size
        scale = min((w - 28) / iw, (h - 28) / ih, 1.0)
        tw, th = max(1, round(iw * scale)), max(1, round(ih * scale))
        thumb = self.screenshot.resize((tw, th), Image.Resampling.LANCZOS)
        self._preview_photo = ImageTk.PhotoImage(thumb)
        ox, oy = (w - tw) // 2, (h - th) // 2
        self._scale = scale
        self._offset = (ox, oy)
        c.create_image(ox, oy, image=self._preview_photo, anchor="nw")

    def _to_image(self, x, y):
        """Map preview-canvas coords to image pixel coords (clamped)."""
        if self._scale is None or self.screenshot is None:
            return None
        ox, oy = self._offset
        iw, ih = self.screenshot.size
        ix = (x - ox) / self._scale
        iy = (y - oy) / self._scale
        return (min(max(ix, 0), iw), min(max(iy, 0), ih))

    def _inside_image(self, x, y):
        if self._scale is None or self.screenshot is None:
            return False
        ox, oy = self._offset
        iw, ih = self.screenshot.size
        return (ox <= x <= ox + iw * self._scale
                and oy <= y <= oy + ih * self._scale)

    # -- annotation --------------------------------------------------------------
    def set_tool(self, name):
        self.tool = None if self.tool == name else name
        for tool_name, btn in self.tool_buttons.items():
            btn.set_selected(tool_name == self.tool)
        self.preview_canvas.configure(
            cursor="crosshair" if self.tool else "")
        if self.tool:
            tip = dict((n, t) for n, _, t in TOOLS)[self.tool]
            self._set_status(f"{tip} · drag on the preview"
                             if self.tool != "text"
                             else "Text · click on the preview")

    def set_color(self, color):
        self.annot_color = color
        for c, dot in self.color_dots.items():
            dot.set_selected(c == color)

    def set_width(self, width):
        self.annot_width = width
        for w, dot in self.width_dots.items():
            dot.set_selected(w == width)

    def _on_preview_press(self, event):
        if not self.tool or not self.screenshot:
            return
        if not self._inside_image(event.x, event.y):
            self._drag_start = None
            return
        self._drag_start = (event.x, event.y)
        if self.tool == "pen":
            self._pen_points = [self._to_image(event.x, event.y)]

    def _on_preview_drag(self, event):
        if not self._drag_start:
            return
        c = self.preview_canvas
        x0, y0 = self._drag_start
        x1, y1 = event.x, event.y
        if self.tool == "pen":
            c.create_line(self._last_pen_canvas() or (x0, y0), (x1, y1),
                          fill=self.annot_color, width=self.annot_width,
                          capstyle="round", tags="tmp")
            self._pen_points.append(self._to_image(x1, y1))
            return
        c.delete("tmp")
        if self.tool in ("line", "arrow"):
            c.create_line(x0, y0, x1, y1, fill=self.annot_color,
                          width=self.annot_width,
                          arrow="last" if self.tool == "arrow" else None,
                          capstyle="round", tags="tmp")
        elif self.tool == "rect":
            c.create_rectangle(x0, y0, x1, y1, outline=self.annot_color,
                               width=self.annot_width, tags="tmp")
        elif self.tool == "ellipse":
            c.create_oval(x0, y0, x1, y1, outline=self.annot_color,
                          width=self.annot_width, tags="tmp")
        elif self.tool == "highlight":
            c.create_rectangle(x0, y0, x1, y1, outline="",
                               fill=self.annot_color, stipple="gray25",
                               tags="tmp")
        elif self.tool == "crop":
            c.create_rectangle(x0, y0, x1, y1, outline=COL["accent"],
                               dash=(5, 3), tags="tmp")

    def _last_pen_canvas(self):
        if not self._pen_points or self._scale is None:
            return None
        ix, iy = self._pen_points[-1]
        ox, oy = self._offset
        return (ox + ix * self._scale, oy + iy * self._scale)

    def _on_preview_release(self, event):
        if not self._drag_start:
            return
        start = self._drag_start
        self._drag_start = None
        self.preview_canvas.delete("tmp")
        p0 = self._to_image(*start)
        p1 = self._to_image(event.x, event.y)
        if p0 is None or p1 is None:
            return
        scale = self._scale or 1.0
        eff_w = max(1, round(self.annot_width / scale))
        moved = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) > 3

        if self.tool == "text":
            self._annotate_text(p1)
            return
        if not moved and self.tool != "pen":
            return

        self._push_undo()
        img = self.screenshot
        if self.tool == "pen":
            if len(self._pen_points) > 1:
                ImageDraw.Draw(img).line(self._pen_points, fill=self.annot_color,
                                         width=eff_w, joint="curve")
            self._pen_points = []
        elif self.tool == "line":
            ImageDraw.Draw(img).line([p0, p1], fill=self.annot_color,
                                     width=eff_w)
        elif self.tool == "arrow":
            self._draw_arrow(img, p0, p1, eff_w)
        elif self.tool == "rect":
            box = self._sorted_box(p0, p1)
            ImageDraw.Draw(img).rectangle(box, outline=self.annot_color,
                                          width=eff_w)
        elif self.tool == "ellipse":
            box = self._sorted_box(p0, p1)
            ImageDraw.Draw(img).ellipse(box, outline=self.annot_color,
                                        width=eff_w)
        elif self.tool == "highlight":
            self.screenshot = self._draw_highlight(img, p0, p1)
        elif self.tool == "crop":
            box = self._sorted_box(p0, p1)
            if box[2] - box[0] < 5 or box[3] - box[1] < 5:
                self._undo.pop()
                return
            self.screenshot = img.crop(tuple(round(v) for v in box))
            self._set_status(f"Cropped to {self.screenshot.width} × "
                             f"{self.screenshot.height} px")
        self._commit()

    @staticmethod
    def _sorted_box(p0, p1):
        return (min(p0[0], p1[0]), min(p0[1], p1[1]),
                max(p0[0], p1[0]), max(p0[1], p1[1]))

    def _draw_arrow(self, img, p0, p1, width):
        draw = ImageDraw.Draw(img)
        draw.line([p0, p1], fill=self.annot_color, width=width)
        angle = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        head = max(12, width * 3.5)
        spread = 0.5
        left = (p1[0] - head * math.cos(angle - spread),
                p1[1] - head * math.sin(angle - spread))
        right = (p1[0] - head * math.cos(angle + spread),
                 p1[1] - head * math.sin(angle + spread))
        draw.polygon([p1, left, right], fill=self.annot_color)

    def _draw_highlight(self, img, p0, p1):
        base = img.convert("RGBA")
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        box = self._sorted_box(p0, p1)
        ImageDraw.Draw(overlay).rectangle(box,
                                          fill=hex_rgb(self.annot_color) + (80,))
        return Image.alpha_composite(base, overlay).convert("RGB")

    def _annotate_text(self, pos):
        text = simpledialog.askstring("Add text", "Annotation text:",
                                      parent=self.root)
        if not text:
            return
        self._push_undo()
        size = max(16, round(14 + 3 * self.annot_width / (self._scale or 1.0)))
        font = load_annotation_font(size)
        ImageDraw.Draw(self.screenshot).text(pos, text, fill=self.annot_color,
                                             font=font)
        self._commit()

    # -- undo / history -----------------------------------------------------------
    def _push_undo(self):
        self._undo.append(self.screenshot.copy())
        if len(self._undo) > UNDO_LIMIT:
            self._undo.pop(0)

    def undo(self):
        if not self._undo:
            self.show_toast("Nothing to undo")
            return
        self.screenshot = self._undo.pop()
        self._commit()
        self._set_status("Undid last edit")

    def _commit(self):
        """Sync the edited image into history and refresh the UI."""
        if 0 <= self.history_index < len(self.history):
            self.history[self.history_index] = self.screenshot
        self._draw_preview()
        self._render_history()

    def _add_capture(self, image):
        self.history.insert(0, image)
        del self.history[HISTORY_LIMIT:]
        self.history_index = 0
        self.screenshot = image
        self._undo.clear()
        self._draw_preview()
        self._render_history()
        if self.settings["auto_copy"]:
            try:
                self._set_clipboard_image(image)
                self.show_toast("Captured · copied to clipboard")
            except Exception:
                pass

    def select_capture(self, index):
        if not (0 <= index < len(self.history)):
            return
        self.history_index = index
        self.screenshot = self.history[index]
        self._undo.clear()
        self._draw_preview()
        self._render_history()
        self._set_status(f"Viewing capture {index + 1} of "
                         f"{len(self.history)}")

    def remove_current(self):
        if not self.history:
            return
        del self.history[self.history_index]
        if self.history:
            self.history_index = min(self.history_index,
                                     len(self.history) - 1)
            self.screenshot = self.history[self.history_index]
        else:
            self.history_index = -1
            self.screenshot = None
        self._undo.clear()
        self._draw_preview()
        self._render_history()
        self._set_status("Capture removed")

    def _render_history(self):
        for child in self.history_strip.winfo_children():
            child.destroy()
        self._thumb_photos = []
        if not self.history:
            tk.Label(self.history_strip, text="Recent captures appear here",
                     bg=COL["bg"], fg=COL["text_tertiary"],
                     font=fnt(9)).pack(side="left", pady=28)
            return
        for i, image in enumerate(self.history):
            item_w, item_h = sc(112), sc(70)
            item = tk.Canvas(self.history_strip, width=item_w, height=item_h,
                             bg=COL["bg"], highlightthickness=0,
                             cursor="hand2")
            item.pack(side="left", padx=(0, 10), pady=6)
            selected = i == self.history_index
            item._photo = draw_panel(
                item, 1, 1, item_w - 1, item_h - 1, sc(12), COL["glass"],
                border=COL["accent"] if selected else COL["border"])
            thumb = image.copy()
            thumb.thumbnail((item_w - 12, item_h - 12),
                            Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(thumb)
            self._thumb_photos.append(photo)
            item.create_image(item_w // 2, item_h // 2, image=photo)
            item.bind("<Button-1>", lambda e, idx=i: self.select_capture(idx))

    # -- settings view --------------------------------------------------------
    def _build_settings_view(self):
        view = self.settings_view

        top = tk.Frame(view, bg=COL["bg"])
        top.pack(fill="x", padx=28, pady=(22, 12))
        glyph, font = self.icons["back"]
        back = GlassButton(top, glyph, command=self.close_settings,
                           variant="plain", width=46, height=46, radius=23,
                           font=font)
        back.pack(side="left")
        Tooltip(back, "Back")
        tk.Label(top, text="Settings", bg=COL["bg"], fg=COL["text"],
                 font=fnt_sb(20)).pack(side="left", padx=12)

        tk.Label(view, text="EXPORT", bg=COL["bg"], fg=COL["text_tertiary"],
                 font=fnt_sb(9)).pack(anchor="w", padx=36, pady=(12, 8))

        export_card = GlassCard(view, height=212)
        export_card.pack(fill="x", padx=28)
        inner = export_card.inner
        tk.Label(inner, text="Image format", bg=COL["glass"],
                 fg=COL["text"], font=fnt_sb(11)).pack(anchor="w")
        self.format_seg = GlassSegmented(
            inner, list(FORMATS), value=self.settings["export_format"],
            command=self._set_format)
        self.format_seg.pack(anchor="w", pady=(10, 14))
        header = tk.Frame(inner, bg=COL["glass"])
        header.pack(fill="x")
        tk.Label(header, text="Quality", bg=COL["glass"], fg=COL["text"],
                 font=fnt_sb(11)).pack(side="left")
        self.quality_var = tk.StringVar(value=str(self.settings["quality"]))
        tk.Label(header, textvariable=self.quality_var, bg=COL["glass"],
                 fg=COL["accent_soft"], font=fnt_sb(11)).pack(side="right")
        GlassSlider(inner, value=self.settings["quality"],
                    command=self._set_quality, width=400).pack(fill="x",
                                                               pady=(4, 2))
        tk.Label(inner, text="Quality applies to JPEG and WEBP exports.",
                 bg=COL["glass"], fg=COL["text_secondary"],
                 font=fnt(9)).pack(anchor="w")

        tk.Label(view, text="GENERAL", bg=COL["bg"], fg=COL["text_tertiary"],
                 font=fnt_sb(9)).pack(anchor="w", padx=36, pady=(16, 8))

        row = tk.Frame(view, bg=COL["bg"])
        row.pack(fill="x", padx=28)

        copy_card = GlassCard(row, height=108)
        copy_card.pack(side="left", fill="x", expand=True, padx=(0, 8))
        inner = copy_card.inner
        header = tk.Frame(inner, bg=COL["glass"])
        header.pack(fill="x")
        tk.Label(header, text="Copy after capture", bg=COL["glass"],
                 fg=COL["text"], font=fnt_sb(11)).pack(side="left")
        GlassSwitch(header, value=self.settings["auto_copy"],
                    command=self._set_auto_copy).pack(side="right")
        tk.Label(inner, text="Puts every new capture on the clipboard\n"
                             "automatically.",
                 bg=COL["glass"], fg=COL["text_secondary"], font=fnt(9),
                 justify="left").pack(anchor="w", pady=(8, 0))

        dir_card = GlassCard(row, height=108)
        dir_card.pack(side="left", fill="x", expand=True, padx=(8, 0))
        inner = dir_card.inner
        header = tk.Frame(inner, bg=COL["glass"])
        header.pack(fill="x")
        tk.Label(header, text="Quick save folder", bg=COL["glass"],
                 fg=COL["text"], font=fnt_sb(11)).pack(side="left")
        GlassButton(header, "Change", command=self._choose_quick_save_dir,
                    variant="glass", width=76, height=30,
                    font=fnt_sb(9)).pack(side="right")
        self.dir_var = tk.StringVar(value=self.settings["quick_save_dir"])
        tk.Label(inner, textvariable=self.dir_var, bg=COL["glass"],
                 fg=COL["text_secondary"], font=fnt(9), anchor="w"
                 ).pack(fill="x", pady=(10, 0))

        tk.Label(view, text="SCREEN RECORDING", bg=COL["bg"],
                 fg=COL["text_tertiary"], font=fnt_sb(9)
                 ).pack(anchor="w", padx=36, pady=(16, 8))

        record_card = GlassCard(view, height=214)
        record_card.pack(fill="x", padx=28)
        inner = record_card.inner
        tk.Label(inner, text="Video format", bg=COL["glass"],
                 fg=COL["text"], font=fnt_sb(11)).pack(anchor="w")
        self.video_format_seg = GlassSegmented(
            inner, list(VIDEO_FORMATS), value=self.settings["video_format"],
            command=self._set_video_format, seg_width=64)
        self.video_format_seg.pack(anchor="w", pady=(8, 12))

        tk.Label(inner, text="Frame rate", bg=COL["glass"],
                 fg=COL["text"], font=fnt_sb(11)).pack(anchor="w")
        self.fps_seg = GlassSegmented(
            inner, [str(v) for v in RECORD_FPS_OPTIONS],
            value=str(self.settings["record_fps"]),
            command=self._set_record_fps, seg_width=52)
        self.fps_seg.pack(anchor="w", pady=(8, 8))
        tk.Label(inner, text="Match your display's refresh rate for the "
                            "smoothest capture (higher rates need more CPU "
                            "and disk space) · Ctrl+Alt+R starts/stops, "
                            "Ctrl+Alt+P pauses/resumes, from anywhere.",
                 bg=COL["glass"], fg=COL["text_secondary"], wraplength=460,
                 justify="left", font=fnt(9)).pack(anchor="w")

        tk.Label(view, text="Settings are saved automatically · "
                            "theme follows the Windows light/dark setting.",
                 bg=COL["bg"], fg=COL["text_tertiary"],
                 font=fnt(9)).pack(side="bottom", pady=14)

    def _set_format(self, name):
        self.settings["export_format"] = name
        save_settings(self.settings)

    def _set_quality(self, value):
        self.settings["quality"] = value
        self.quality_var.set(str(value))
        save_settings(self.settings)

    def _set_auto_copy(self, value):
        self.settings["auto_copy"] = value
        save_settings(self.settings)

    def _set_video_format(self, name):
        self.settings["video_format"] = name
        save_settings(self.settings)

    def _set_record_fps(self, value):
        self.settings["record_fps"] = int(value)
        save_settings(self.settings)

    def _choose_quick_save_dir(self):
        chosen = filedialog.askdirectory(
            initialdir=self.settings["quick_save_dir"], parent=self.root)
        if chosen:
            self.settings["quick_save_dir"] = chosen
            self.dir_var.set(chosen)
            save_settings(self.settings)

    # -- toast -------------------------------------------------------------
    def show_toast(self, message):
        if self._toast_job:
            self.root.after_cancel(self._toast_job)
            self._toast_job = None
        if self._toast:
            self._toast.destroy()

        font = tkfont.Font(family=FONT, size=10)
        w = min(font.measure(message) + sc(52), sc(440))
        h = sc(44)
        bar = tk.Canvas(self.root, width=w, height=h, bg=COL["bg"],
                        highlightthickness=0)
        bar._photo = draw_panel(bar, 1, 1, w - 1, h - 1, h // 2,
                                COL["glass_high"], border=COL["border_bright"])
        bar.create_text(w // 2, h // 2, text=message, fill=COL["text"],
                        font=font)
        self._toast = bar

        def slide(i, steps=10):
            if not bar.winfo_exists():
                return
            t = ease_out(i / steps)
            bar.place(relx=0.5, rely=1.06 - 0.09 * t, anchor="s")
            if i < steps:
                self.root.after(14, slide, i + 1)
            else:
                self._toast_job = self.root.after(2400, dismiss)

        def dismiss(i=1, steps=10):
            if not bar.winfo_exists():
                return
            t = ease_out(i / steps)
            bar.place(relx=0.5, rely=0.97 + 0.09 * t, anchor="s")
            if i < steps:
                self._toast_job = self.root.after(14, dismiss, i + 1)
            else:
                bar.destroy()
                if self._toast is bar:
                    self._toast = None
                self._toast_job = None

        slide(1)

    def _set_status(self, message):
        self.status_var.set(message)

    # -- capture ---------------------------------------------------------------
    def _delay_ms(self):
        return int(self.delay_seg.value.rstrip("s")) * 1000

    @staticmethod
    def _virtual_screen():
        """(x, y, w, h) of the full multi-monitor virtual screen."""
        try:
            user32 = ctypes.windll.user32
            return (user32.GetSystemMetrics(76), user32.GetSystemMetrics(77),
                    user32.GetSystemMetrics(78), user32.GetSystemMetrics(79))
        except Exception:
            return None

    def start_region_capture(self):
        delay = self._delay_ms()
        self._set_status("Click and drag to select an area · Esc to cancel")
        self.root.withdraw()
        self.root.after(200 + delay, self._create_overlay)

    def start_fullscreen_capture(self):
        delay = self._delay_ms()
        self._set_status("Capturing full screen…")
        self.root.withdraw()
        self.root.after(300 + delay, self._grab_fullscreen)

    def _grab_fullscreen(self):
        try:
            image = ImageGrab.grab(all_screens=True)
        except Exception as exc:
            self.root.deiconify()
            messagebox.showerror("Error", f"Failed to capture screen: {exc}")
            self._set_status("Capture failed")
            return
        self.root.deiconify()
        self._add_capture(image)
        self._set_status(f"Captured full screen · "
                         f"{image.width} × {image.height} px")

    def _create_overlay(self):
        self.overlay_window = tk.Toplevel(self.root)
        set_window_alpha(self.overlay_window, 0.35)
        self.overlay_window.attributes("-topmost", True)
        self.overlay_window.overrideredirect(True)

        virtual = self._virtual_screen()
        if virtual:
            vx, vy, vw, vh = virtual
        else:
            vx = vy = 0
            vw = self.overlay_window.winfo_screenwidth()
            vh = self.overlay_window.winfo_screenheight()
        self._overlay_origin = (vx, vy)
        self.overlay_window.geometry(f"{vw}x{vh}+{vx}+{vy}")

        self.overlay_canvas = tk.Canvas(self.overlay_window, bg="black",
                                        highlightthickness=0,
                                        cursor="crosshair")
        self.overlay_canvas.pack(fill="both", expand=True)

        self.overlay_canvas.bind("<Button-1>", self._on_mouse_down)
        self.overlay_canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.overlay_canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.overlay_window.bind("<Escape>", self.cancel_capture)
        self.overlay_window.focus_force()

    def _on_mouse_down(self, event):
        self.start_x, self.start_y = event.x, event.y
        self.selection_active = True

    def _on_mouse_drag(self, event):
        if not self.selection_active:
            return
        self.end_x, self.end_y = event.x, event.y
        c = self.overlay_canvas
        c.delete("selection")
        c.create_rectangle(self.start_x, self.start_y, self.end_x, self.end_y,
                           outline="#FFFFFF", width=1,
                           fill="#FFFFFF", stipple="gray12",
                           tags="selection")
        w = abs(self.end_x - self.start_x)
        h = abs(self.end_y - self.start_y)
        c.create_text(min(self.start_x, self.end_x) + 6,
                      min(self.start_y, self.end_y) - 12,
                      text=f"{w} × {h}", anchor="w",
                      fill="#FFFFFF", font=fnt_sb(10),
                      tags="selection")

    def _on_mouse_up(self, event):
        if not self.selection_active:
            return
        self.selection_active = False
        self.end_x, self.end_y = event.x, event.y
        self.overlay_window.destroy()
        self.overlay_window = None
        # let the overlay disappear before grabbing the screen
        self.root.after(150, self._capture_selection)

    def cancel_capture(self, _event=None):
        if self.overlay_window:
            self.overlay_window.destroy()
            self.overlay_window = None
        self.selection_active = False
        self.root.deiconify()
        self._set_status("Capture cancelled")

    def _capture_selection(self):
        x1, x2 = sorted((self.start_x, self.end_x))
        y1, y2 = sorted((self.start_y, self.end_y))

        if x2 - x1 < 5 or y2 - y1 < 5:
            self.root.deiconify()
            self._set_status("Selection too small")
            self.show_toast("Please select a larger area")
            return

        try:
            # overlay-local coords match the virtual-screen grab's origin
            full = ImageGrab.grab(all_screens=True)
            image = full.crop((x1, y1, x2, y2))
        except Exception as exc:
            self.root.deiconify()
            messagebox.showerror("Error", f"Failed to capture screenshot: {exc}")
            self._set_status("Capture failed")
            return
        self.root.deiconify()
        self._add_capture(image)
        self._set_status(
            f"Captured {x2 - x1} × {y2 - y1} px · ready to annotate or save")

    # -- screen recording ----------------------------------------------------
    def toggle_recording(self):
        if self.recorder and self.recorder.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if self.recorder and self.recorder.is_recording:
            return
        folder = self.settings["quick_save_dir"]
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Error", f"Cannot create folder: {exc}")
            return

        fmt = self.settings["video_format"]
        ext, codec_args = VIDEO_FORMATS[fmt]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(folder, f"recording_{timestamp}{ext}")

        recorder = ScreenRecorder(self.settings["record_fps"], codec_args,
                                  output_path, on_error=self._on_record_error)
        try:
            recorder.start()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to start recording: {exc}")
            return
        self.recorder = recorder
        self.root.withdraw()
        self._show_record_bar()
        self._set_status("Recording…")

    def stop_recording(self, discard=False):
        if not self.recorder:
            return
        recorder = self.recorder
        self.recorder = None
        path = recorder.stop()
        self._hide_record_bar()
        self.root.deiconify()
        if discard:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
            self._set_status("Recording discarded")
            return
        self._set_status(f"Recording saved · {os.path.basename(path)}")
        self.show_toast(f"Saved recording · {os.path.basename(path)}")

    def toggle_pause_recording(self):
        if not self.recorder or not self.recorder.is_recording:
            return
        if self.recorder.paused:
            self.recorder.resume()
        else:
            self.recorder.pause()
        self._update_record_bar_state()

    def _on_record_error(self, message):
        self.root.after(0, lambda: self._handle_record_error(message))

    def _handle_record_error(self, message):
        if not self.recorder:
            return
        self.stop_recording(discard=True)
        messagebox.showerror("Recording error", message)

    def _show_record_bar(self):
        w, h = sc(264), sc(56)
        bar = tk.Toplevel(self.root)
        bar.overrideredirect(True)
        bar.attributes("-topmost", True)
        set_window_alpha(bar, 0.96)
        x = (bar.winfo_screenwidth() - w) // 2
        bar.geometry(f"{w}x{h}+{x}+{sc(18)}")
        canvas = tk.Canvas(bar, width=w, height=h, bg=COL["bg"],
                           highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        self._record_bar_photo = draw_panel(
            canvas, 1, 1, w - 1, h - 1, h // 2, COL["glass_high"],
            border=COL["border_bright"])
        dr = sc(6)
        self._record_dot = canvas.create_oval(
            sc(20), h // 2 - dr, sc(20) + 2 * dr, h // 2 + dr,
            fill=COL["error"], outline="")
        self._record_timer_text = canvas.create_text(
            sc(42), h // 2, anchor="w", text="00:00", fill=COL["text"],
            font=fnt_sb(11))

        controls = tk.Frame(canvas, bg=COL["glass_high"])
        canvas.create_window(w - sc(8), h // 2, anchor="e", window=controls)
        self._pause_btn = GlassButton(controls, "⏸", command=self.toggle_pause_recording,
                                      variant="plain", width=36, height=36,
                                      radius=18, font=("Segoe UI Symbol", 12))
        self._pause_btn.pack(side="left", padx=2)
        Tooltip(self._pause_btn, "Pause / resume (Ctrl+Alt+P)")
        stop_btn = GlassButton(controls, "⏹", command=self.stop_recording,
                               variant="plain", width=36, height=36, radius=18,
                               font=("Segoe UI Symbol", 12))
        stop_btn.pack(side="left", padx=2)
        Tooltip(stop_btn, "Stop recording (Ctrl+Alt+R)")

        for widget in (bar, canvas):
            widget.bind("<Button-1>", self._record_bar_press)
            widget.bind("<B1-Motion>", self._record_bar_drag)
        exclude_from_capture(bar)

        self._record_bar = bar
        self._tick_record_bar()

    def _record_bar_press(self, event):
        self._record_bar_origin = (event.x_root - self._record_bar.winfo_x(),
                                   event.y_root - self._record_bar.winfo_y())

    def _record_bar_drag(self, event):
        dx, dy = self._record_bar_origin
        self._record_bar.geometry(
            f"+{event.x_root - dx}+{event.y_root - dy}")

    def _update_record_bar_state(self):
        if not self._pause_btn:
            return
        paused = bool(self.recorder and self.recorder.paused)
        self._pause_btn.set_text("▶" if paused else "⏸")

    def _tick_record_bar(self):
        if not self._record_bar or not self.recorder:
            return
        canvas = self._record_bar.winfo_children()[0]
        seconds = int(self.recorder.elapsed())
        canvas.itemconfig(self._record_timer_text,
                          text=f"{seconds // 60:02d}:{seconds % 60:02d}")
        if self.recorder.paused:
            dot_fill = COL["text_tertiary"]
        else:
            dot_fill = COL["error"] if seconds % 2 == 0 else COL["glass_high"]
        canvas.itemconfig(self._record_dot, fill=dot_fill)
        self._record_bar_job = self.root.after(500, self._tick_record_bar)

    def _hide_record_bar(self):
        if self._record_bar_job:
            self.root.after_cancel(self._record_bar_job)
            self._record_bar_job = None
        if self._record_bar:
            self._record_bar.destroy()
            self._record_bar = None
        self._pause_btn = None
        self._record_dot = None
        self._record_timer_text = None

    # -- actions -----------------------------------------------------------------
    def save_screenshot(self):
        if not self.screenshot:
            self.show_toast("Capture a screenshot first")
            return

        fmt = self.settings["export_format"]
        ext = FORMATS[fmt]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filetypes = [(f"{fmt} image", f"*{ext}")]
        filetypes += [(f"{name} image", f"*{fext}")
                      for name, fext in FORMATS.items() if name != fmt]
        filetypes.append(("All files", "*.*"))

        file_path = filedialog.asksaveasfilename(
            defaultextension=ext,
            initialfile=f"snippet_{timestamp}{ext}",
            filetypes=filetypes)
        if not file_path:
            return
        self._save_to(file_path)

    def quick_save(self):
        if not self.screenshot:
            self.show_toast("Capture a screenshot first")
            return
        folder = self.settings["quick_save_dir"]
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Error", f"Cannot create folder: {exc}")
            return
        ext = FORMATS[self.settings["export_format"]]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._save_to(os.path.join(folder, f"snippet_{timestamp}{ext}"))

    def _save_to(self, file_path):
        fmt = self.settings["export_format"]
        ext_map = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG",
                   ".webp": "WEBP", ".bmp": "BMP"}
        actual_fmt = ext_map.get(os.path.splitext(file_path)[1].lower(), fmt)

        try:
            img = self.screenshot
            if actual_fmt in ("JPEG", "BMP") and img.mode != "RGB":
                img = img.convert("RGB")
            kwargs = {}
            if actual_fmt in LOSSY_FORMATS:
                kwargs["quality"] = self.settings["quality"]
            img.save(file_path, actual_fmt, **kwargs)
            self._set_status(f"Saved to {os.path.basename(file_path)}")
            self.show_toast(f"Saved as {actual_fmt} · "
                            f"{os.path.basename(file_path)}")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to save: {exc}")
            self._set_status("Save failed")

    def copy_to_clipboard(self):
        if not self.screenshot:
            self.show_toast("Capture a screenshot first")
            return
        try:
            self._set_clipboard_image(self.screenshot)
            self._set_status("Copied to clipboard")
            self.show_toast("Copied to clipboard")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to copy: {exc}")
            self._set_status("Copy failed")

    @staticmethod
    def _set_clipboard_image(image):
        """Place the image on the system clipboard, picking the mechanism
        each OS actually supports (Windows/macOS have no shared API)."""
        if sys.platform == "win32":
            SnippyApp._set_clipboard_image_windows(image)
        elif sys.platform == "darwin":
            SnippyApp._set_clipboard_image_macos(image)
        else:
            SnippyApp._set_clipboard_image_linux(image)

    @staticmethod
    def _set_clipboard_image_windows(image):
        """Place the image on the Windows clipboard as a DIB."""
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, "BMP")
        data = buffer.getvalue()[14:]  # strip BITMAPFILEHEADER

        CF_DIB = 8
        GMEM_MOVEABLE = 0x0002
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]

        if not user32.OpenClipboard(0):
            raise RuntimeError("Could not open clipboard")
        try:
            user32.EmptyClipboard()
            handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
            pointer = kernel32.GlobalLock(handle)
            ctypes.memmove(pointer, data, len(data))
            kernel32.GlobalUnlock(handle)
            user32.SetClipboardData(CF_DIB, handle)
        finally:
            user32.CloseClipboard()

    @staticmethod
    def _set_clipboard_image_macos(image):
        """Set the clipboard via osascript, which needs the PNG on disk."""
        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            image.save(path, "PNG")
            script = (f'set the clipboard to (read (POSIX file "{path}") '
                      f'as «class PNGf»)')
            result = subprocess.run(["osascript", "-e", script],
                                    capture_output=True)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.decode(errors="replace")
                                   or "osascript failed")
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    @staticmethod
    def _set_clipboard_image_linux(image):
        """Pipe PNG bytes into whichever clipboard tool is installed."""
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, "PNG")
        data = buffer.getvalue()

        wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
        if wayland and shutil.which("wl-copy"):
            args = ["wl-copy", "--type", "image/png"]
        elif shutil.which("xclip"):
            args = ["xclip", "-selection", "clipboard", "-t", "image/png"]
        elif shutil.which("wl-copy"):
            args = ["wl-copy", "--type", "image/png"]
        else:
            raise RuntimeError(
                "Copying images requires 'xclip' (X11) or 'wl-clipboard' "
                "(Wayland) to be installed.")
        result = subprocess.run(args, input=data, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(
                result.stderr.decode(errors="replace") or f"{args[0]} failed")


def main():
    if sys.platform == "win32":
        try:  # align tkinter coordinates with physical pixels on scaled displays
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
    root = tk.Tk()
    init_fonts(root)
    SnippyApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
