"""Snippy - a Material You styled snipping tool."""

import ctypes
import io
import json
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import font as tkfont
from datetime import datetime

from PIL import Image, ImageGrab, ImageTk


# ---------------------------------------------------------------------------
# Material 3 dark tonal palette (baseline purple scheme)
# ---------------------------------------------------------------------------
COL = {
    "surface":                 "#141218",
    "surface_container":       "#211F26",
    "surface_container_high":  "#2B2930",
    "surface_variant":         "#49454F",
    "on_surface":              "#E6E0E9",
    "on_surface_variant":      "#CAC4D0",
    "outline":                 "#938F99",
    "primary":                 "#D0BCFF",
    "on_primary":              "#381E72",
    "primary_container":       "#4F378B",
    "on_primary_container":    "#EADDFF",
    "secondary_container":     "#4A4458",
    "on_secondary_container":  "#E8DEF8",
    "inverse_surface":         "#E6E0E9",
    "inverse_on_surface":      "#322F35",
    "error":                   "#F2B8B5",
}

WINDOW_ALPHA = 0.965

FORMATS = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp", "BMP": ".bmp"}
LOSSY_FORMATS = ("JPEG", "WEBP")

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "settings.json")
DEFAULT_SETTINGS = {"export_format": "PNG", "quality": 90}


def load_settings():
    settings = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as fh:
            saved = json.load(fh)
        if saved.get("export_format") in FORMATS:
            settings["export_format"] = saved["export_format"]
        if isinstance(saved.get("quality"), int):
            settings["quality"] = max(40, min(100, saved["quality"]))
    except (OSError, ValueError):
        pass
    return settings


def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(settings, fh, indent=2)
    except OSError:
        pass


def blend(hex1, hex2, t):
    """Linear blend between two hex colors, t in [0, 1]."""
    c1 = [int(hex1[i:i + 2], 16) for i in (1, 3, 5)]
    c2 = [int(hex2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(
        round(a + (b - a) * t) for a, b in zip(c1, c2))


def round_points(x1, y1, x2, y2, r):
    """Vertex list for a smooth-polygon rounded rectangle."""
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]


def ease_out(t):
    return 1 - (1 - t) ** 3


# ---------------------------------------------------------------------------
# HiDPI scaling
# ---------------------------------------------------------------------------
SCALE = 1.0


def init_scale(root):
    """Derive the UI scale from the monitor DPI (requires DPI awareness)."""
    global SCALE
    try:
        SCALE = max(1.0, root.winfo_fpixels("1i") / 96.0)
    except tk.TclError:
        SCALE = 1.0
    # keep point-sized fonts in step with the pixel scale
    root.tk.call("tk", "scaling", SCALE * 96 / 72)


def dp(value):
    """Scale a 96-dpi design pixel value to physical pixels."""
    return round(value * SCALE)


# ---------------------------------------------------------------------------
# Material widgets (canvas based, with animated state layers)
# ---------------------------------------------------------------------------
class MDButton(tk.Canvas):
    """Pill button in filled / tonal / text variants with hover transitions."""

    def __init__(self, parent, text, command=None, variant="filled",
                 width=120, height=44, radius=None, font=None):
        bg = parent.cget("bg")
        super().__init__(parent, width=width, height=height, bg=bg,
                         highlightthickness=0, cursor="hand2")
        self.command = command
        self.radius = radius if radius is not None else height // 2

        if variant == "filled":
            self.base, on = COL["primary"], COL["on_primary"]
        elif variant == "tonal":
            self.base, on = COL["secondary_container"], COL["on_secondary_container"]
        else:  # text
            self.base, on = bg, COL["primary"]
        self.hover = blend(self.base, on, 0.10)
        self.pressed = blend(self.base, on, 0.16)
        self._fill = self.base
        self._anim = None

        w, h = int(width), int(height)
        self._shape = self.create_polygon(
            round_points(1, 1, w - 1, h - 1, self.radius),
            smooth=True, fill=self.base)
        self.create_text(w // 2, h // 2, text=text, fill=on,
                         font=font or ("Segoe UI Semibold", 10))

        self.bind("<Enter>", lambda e: self._animate_to(self.hover))
        self.bind("<Leave>", lambda e: self._animate_to(self.base))
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _set_fill(self, color):
        self._fill = color
        self.itemconfig(self._shape, fill=color)

    def _animate_to(self, target, steps=6):
        if self._anim:
            self.after_cancel(self._anim)
            self._anim = None
        start = self._fill

        def frame(i):
            self._set_fill(blend(start, target, ease_out(i / steps)))
            if i < steps:
                self._anim = self.after(16, frame, i + 1)
            else:
                self._anim = None
        frame(1)

    def _on_press(self, _event):
        if self._anim:
            self.after_cancel(self._anim)
            self._anim = None
        self._set_fill(self.pressed)

    def _on_release(self, event):
        inside = (0 <= event.x <= self.winfo_width()
                  and 0 <= event.y <= self.winfo_height())
        self._animate_to(self.hover if inside else self.base)
        if inside and self.command:
            self.command()


class MDChip(tk.Canvas):
    """Material choice chip used for the export-format selector."""

    def __init__(self, parent, text, command=None, width=94, height=36):
        bg = parent.cget("bg")
        super().__init__(parent, width=width, height=height, bg=bg,
                         highlightthickness=0, cursor="hand2")
        self.text = text
        self.command = command
        self.selected = False
        self._bg = bg
        self._cw, self._ch = int(width), int(height)
        self._draw()
        self.bind("<Button-1>", lambda e: self.command and self.command(self.text))
        self.bind("<Enter>", lambda e: self._draw(hover=True))
        self.bind("<Leave>", lambda e: self._draw())

    def set_selected(self, selected):
        self.selected = selected
        self._draw()

    def _draw(self, hover=False):
        self.delete("all")
        if self.selected:
            fill = COL["secondary_container"]
            fg = COL["on_secondary_container"]
            outline = fill
            label = "✓  " + self.text
        else:
            fill = self._bg
            fg = COL["on_surface_variant"]
            outline = COL["outline"]
            label = self.text
        if hover:
            fill = blend(fill, fg, 0.08)
        self.create_polygon(round_points(1, 1, self._cw - 1, self._ch - 1, 10),
                            smooth=True, fill=fill, outline=outline)
        self.create_text(self._cw // 2, self._ch // 2, text=label, fill=fg,
                         font=("Segoe UI", 9))


class MDSlider(tk.Canvas):
    """Material slider with a primary active track and round thumb."""

    PAD = 14

    def __init__(self, parent, from_=40, to=100, value=90, command=None,
                 width=300, height=36):
        super().__init__(parent, width=width, height=height,
                         bg=parent.cget("bg"), highlightthickness=0,
                         cursor="hand2")
        self.from_, self.to = from_, to
        self.value = value
        self.command = command
        self._cw, self._ch = int(width), int(height)
        self._draw()
        self.bind("<Button-1>", self._on_drag)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        self._cw = event.width
        self._draw()

    def _thumb_x(self):
        span = self._cw - 2 * self.PAD
        frac = (self.value - self.from_) / (self.to - self.from_)
        return self.PAD + frac * span

    def _draw(self):
        self.delete("all")
        cy = self._ch // 2
        tx = self._thumb_x()
        self.create_line(self.PAD, cy, self._cw - self.PAD, cy,
                         fill=COL["surface_variant"], width=4,
                         capstyle="round")
        self.create_line(self.PAD, cy, tx, cy,
                         fill=COL["primary"], width=4, capstyle="round")
        self.create_oval(tx - 9, cy - 9, tx + 9, cy + 9,
                         fill=COL["primary"], outline="")

    def _on_drag(self, event):
        span = self._cw - 2 * self.PAD
        frac = min(1.0, max(0.0, (event.x - self.PAD) / span))
        new_value = round(self.from_ + frac * (self.to - self.from_))
        if new_value != self.value:
            self.value = new_value
            self._draw()
            if self.command:
                self.command(new_value)


class Tooltip:
    """Small hover tooltip shown under icon buttons."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        self.job = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<Button-1>", self._hide, add="+")

    def _schedule(self, _event):
        self.job = self.widget.after(600, self._show)

    def _show(self):
        if self.tip:
            return
        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.overrideredirect(True)
        self.tip.attributes("-topmost", True)
        self.tip.attributes("-alpha", 0.95)
        tk.Label(self.tip, text=self.text, bg=COL["inverse_surface"],
                 fg=COL["inverse_on_surface"], font=("Segoe UI", 9),
                 padx=10, pady=4).pack()
        self.tip.update_idletasks()
        self.tip.geometry(f"+{x - self.tip.winfo_width() // 2}+{y}")

    def _hide(self, _event=None):
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None
        if self.tip:
            self.tip.destroy()
            self.tip = None


class Card(tk.Canvas):
    """Rounded surface-container card hosting an inner frame."""

    def __init__(self, parent, height, radius=16, pad=16):
        super().__init__(parent, height=height, bg=parent.cget("bg"),
                         highlightthickness=0)
        self.radius = radius
        self.pad = pad
        self.inner = tk.Frame(self, bg=COL["surface_container"])
        self._win = None
        self.bind("<Configure>", self._redraw)

    def _redraw(self, _event=None):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2 * self.pad:
            return
        self.delete("card")
        self.create_polygon(round_points(1, 1, w - 1, h - 1, self.radius),
                            smooth=True, fill=COL["surface_container"],
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
class SnippyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Snippy")
        width, height = 920, 580
        x = (root.winfo_screenwidth() - width) // 2
        y = (root.winfo_screenheight() - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(780, 500)
        self.root.configure(bg=COL["surface"])
        self.root.attributes("-alpha", 0.0)  # faded in on launch

        self.settings = load_settings()
        self.icon_font, self.icons = self._pick_icons()

        self.screenshot = None
        self._preview_photo = None
        self._snackbar = None
        self._snackbar_job = None
        self._transitioning = False

        # capture-overlay state
        self.overlay_window = None
        self.overlay_canvas = None
        self.selection_active = False
        self.start_x = self.start_y = self.end_x = self.end_y = 0

        self.container = tk.Frame(root, bg=COL["surface"])
        self.container.pack(fill="both", expand=True)

        self.main_view = tk.Frame(self.container, bg=COL["surface"])
        self.settings_view = tk.Frame(self.container, bg=COL["surface"])
        self._build_main_view()
        self._build_settings_view()
        self.main_view.place(relx=0, rely=0, relwidth=1, relheight=1)

        self._fade_in()

    @staticmethod
    def _pick_icons():
        """Prefer Windows' Fluent/MDL2 icon fonts, fall back to symbols."""
        families = set(tkfont.families())
        for family in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
            if family in families:
                return (family, 12), {"settings": "", "copy": "",
                                      "save": "", "back": ""}
        return ("Segoe UI Symbol", 12), {"settings": "⚙", "copy": "⧉",
                                         "save": "💾", "back": "←"}

    # -- window / view transitions -----------------------------------------
    def _fade_in(self, alpha=0.0):
        alpha = min(alpha + 0.09, WINDOW_ALPHA)
        self.root.attributes("-alpha", alpha)
        if alpha < WINDOW_ALPHA:
            self.root.after(16, self._fade_in, alpha)

    def _slide_to(self, incoming, outgoing, direction, steps=16):
        """Slide `incoming` over `outgoing`; direction 1 = from right."""
        if self._transitioning:
            return
        self._transitioning = True
        incoming.place(relx=direction, rely=0, relwidth=1, relheight=1)
        incoming.lift()

        def frame(i):
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
        self._slide_to(self.settings_view, self.main_view, 1)

    def close_settings(self):
        self._slide_to(self.main_view, self.settings_view, -1)

    # -- main view -----------------------------------------------------------
    def _build_main_view(self):
        view = self.main_view

        top = tk.Frame(view, bg=COL["surface"])
        top.pack(fill="x", padx=28, pady=(22, 12))
        titles = tk.Frame(top, bg=COL["surface"])
        titles.pack(side="left")
        tk.Label(titles, text="Snippy", bg=COL["surface"],
                 fg=COL["on_surface"], font=("Segoe UI Semibold", 20)
                 ).pack(anchor="w")
        tk.Label(titles, text="Screenshot tool", bg=COL["surface"],
                 fg=COL["on_surface_variant"], font=("Segoe UI", 9)
                 ).pack(anchor="w")

        # packed right-to-left, so on screen this reads: settings, copy, save
        for icon, tip, command in (
                ("save", "Save", self.save_screenshot),
                ("copy", "Copy to clipboard", self.copy_to_clipboard),
                ("settings", "Settings", self.open_settings)):
            btn = MDButton(top, self.icons[icon], command=command,
                           variant="text", width=46, height=46, radius=23,
                           font=self.icon_font)
            btn.pack(side="right", padx=4)
            Tooltip(btn, tip)

        bottom = tk.Frame(view, bg=COL["surface"])
        bottom.pack(side="bottom", fill="x", padx=28, pady=(20, 24))
        MDButton(bottom, "＋  New capture", command=self.start_capture,
                 variant="filled", width=210, height=52, radius=26,
                 font=("Segoe UI Semibold", 12)).pack(side="left")
        MDButton(bottom, "Clear", command=self.clear_screenshot,
                 variant="text", width=100, height=44
                 ).pack(side="left", padx=(14, 0), pady=4)
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(bottom, textvariable=self.status_var, bg=COL["surface"],
                 fg=COL["on_surface_variant"], font=("Segoe UI", 9)
                 ).pack(side="right")

        self.preview_canvas = tk.Canvas(view, bg=COL["surface"],
                                        highlightthickness=0)
        self.preview_canvas.pack(fill="both", expand=True, padx=28,
                                 pady=(6, 0))
        self.preview_canvas.bind("<Configure>", lambda e: self._draw_preview())

    def _draw_preview(self):
        c = self.preview_canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 40 or h < 40:
            return
        c.create_polygon(round_points(1, 1, w - 1, h - 1, 20), smooth=True,
                         fill=COL["surface_container_high"])
        if self.screenshot is None:
            c.create_text(w // 2, h // 2 - 14, text="\U0001F5BC",
                          font=("Segoe UI Emoji", 22),
                          fill=COL["on_surface_variant"])
            c.create_text(w // 2, h // 2 + 20, text="No capture yet",
                          font=("Segoe UI", 10),
                          fill=COL["on_surface_variant"])
            self._preview_photo = None
            return
        thumb = self.screenshot.copy()
        thumb.thumbnail((w - 28, h - 28), Image.Resampling.LANCZOS)
        self._preview_photo = ImageTk.PhotoImage(thumb)
        c.create_image(w // 2, h // 2, image=self._preview_photo)

    # -- settings view --------------------------------------------------------
    def _build_settings_view(self):
        view = self.settings_view

        top = tk.Frame(view, bg=COL["surface"])
        top.pack(fill="x", padx=28, pady=(22, 12))
        back = MDButton(top, self.icons["back"], command=self.close_settings,
                        variant="text", width=46, height=46, radius=23,
                        font=self.icon_font)
        back.pack(side="left")
        Tooltip(back, "Back")
        tk.Label(top, text="Settings", bg=COL["surface"],
                 fg=COL["on_surface"], font=("Segoe UI Semibold", 20)
                 ).pack(side="left", padx=12)

        tk.Label(view, text="EXPORT", bg=COL["surface"], fg=COL["primary"],
                 font=("Segoe UI Semibold", 9)).pack(anchor="w",
                                                     padx=36, pady=(12, 8))

        fmt_card = Card(view, height=132)
        fmt_card.pack(fill="x", padx=28)
        inner = fmt_card.inner
        tk.Label(inner, text="Image format", bg=COL["surface_container"],
                 fg=COL["on_surface"], font=("Segoe UI Semibold", 11)
                 ).pack(anchor="w")
        chip_row = tk.Frame(inner, bg=COL["surface_container"])
        chip_row.pack(anchor="w", pady=(10, 6))
        self.format_chips = {}
        for name in FORMATS:
            chip = MDChip(chip_row, name, command=self._set_format)
            chip.pack(side="left", padx=(0, 8))
            self.format_chips[name] = chip
        self.format_chips[self.settings["export_format"]].set_selected(True)
        tk.Label(inner, text="Format used when saving captures.",
                 bg=COL["surface_container"], fg=COL["on_surface_variant"],
                 font=("Segoe UI", 9)).pack(anchor="w")

        quality_card = Card(view, height=124)
        quality_card.pack(fill="x", padx=28, pady=(16, 0))
        inner = quality_card.inner
        header = tk.Frame(inner, bg=COL["surface_container"])
        header.pack(fill="x")
        tk.Label(header, text="Quality", bg=COL["surface_container"],
                 fg=COL["on_surface"], font=("Segoe UI Semibold", 11)
                 ).pack(side="left")
        self.quality_var = tk.StringVar(value=str(self.settings["quality"]))
        tk.Label(header, textvariable=self.quality_var,
                 bg=COL["surface_container"], fg=COL["primary"],
                 font=("Segoe UI Semibold", 11)).pack(side="right")
        MDSlider(inner, value=self.settings["quality"],
                 command=self._set_quality, width=400).pack(fill="x",
                                                            pady=(6, 2))
        tk.Label(inner, text="Applies to JPEG and WEBP exports.",
                 bg=COL["surface_container"], fg=COL["on_surface_variant"],
                 font=("Segoe UI", 9)).pack(anchor="w")

        tk.Label(view, text="Settings are saved automatically.",
                 bg=COL["surface"], fg=COL["on_surface_variant"],
                 font=("Segoe UI", 9)).pack(side="bottom", pady=14)

    def _set_format(self, name):
        for chip_name, chip in self.format_chips.items():
            chip.set_selected(chip_name == name)
        self.settings["export_format"] = name
        save_settings(self.settings)

    def _set_quality(self, value):
        self.settings["quality"] = value
        self.quality_var.set(str(value))
        save_settings(self.settings)

    # -- snackbar --------------------------------------------------------------
    def show_snackbar(self, message):
        if self._snackbar_job:
            self.root.after_cancel(self._snackbar_job)
            self._snackbar_job = None
        if self._snackbar:
            self._snackbar.destroy()

        font = tkfont.Font(family="Segoe UI", size=10)
        w = min(font.measure(message) + 48, 440)
        h = 44
        bar = tk.Canvas(self.root, width=w, height=h, bg=COL["surface"],
                        highlightthickness=0)
        bar.create_polygon(round_points(1, 1, w - 1, h - 1, 12), smooth=True,
                           fill=COL["inverse_surface"])
        bar.create_text(w // 2, h // 2, text=message,
                        fill=COL["inverse_on_surface"], font=font)
        self._snackbar = bar

        def slide(i, steps=10):
            t = ease_out(i / steps)
            bar.place(relx=0.5, rely=1.06 - 0.09 * t, anchor="s")
            if i < steps:
                self.root.after(14, slide, i + 1)
            else:
                self._snackbar_job = self.root.after(2400, dismiss)

        def dismiss(i=1, steps=10):
            t = ease_out(i / steps)
            bar.place(relx=0.5, rely=0.97 + 0.09 * t, anchor="s")
            if i < steps:
                self._snackbar_job = self.root.after(14, dismiss, i + 1)
            else:
                bar.destroy()
                if self._snackbar is bar:
                    self._snackbar = None
                self._snackbar_job = None

        slide(1)

    def _set_status(self, message):
        self.status_var.set(message)

    # -- capture ---------------------------------------------------------------
    def start_capture(self):
        self._set_status("Click and drag to select an area · Esc to cancel")
        self.root.withdraw()
        self.root.after(200, self._create_overlay)

    def _create_overlay(self):
        self.overlay_window = tk.Toplevel(self.root)
        self.overlay_window.attributes("-alpha", 0.35)
        self.overlay_window.attributes("-topmost", True)
        self.overlay_window.overrideredirect(True)

        sw = self.overlay_window.winfo_screenwidth()
        sh = self.overlay_window.winfo_screenheight()
        self.overlay_window.geometry(f"{sw}x{sh}+0+0")

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
                           outline=COL["primary"], width=2,
                           fill=COL["primary"], stipple="gray12",
                           tags="selection")
        w = abs(self.end_x - self.start_x)
        h = abs(self.end_y - self.start_y)
        c.create_text(min(self.start_x, self.end_x) + 6,
                      min(self.start_y, self.end_y) - 12,
                      text=f"{w} × {h}", anchor="w",
                      fill=COL["primary"], font=("Segoe UI Semibold", 10),
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
            self.show_snackbar("Please select a larger area")
            return

        try:
            self.screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
            self._draw_preview()
            self._set_status(
                f"Captured {x2 - x1} × {y2 - y1} px · ready to save or copy")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to capture screenshot: {exc}")
            self._set_status("Capture failed")
        finally:
            self.root.deiconify()

    # -- actions -----------------------------------------------------------------
    def save_screenshot(self):
        if not self.screenshot:
            self.show_snackbar("Capture a screenshot first")
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
            self.show_snackbar(f"Saved as {actual_fmt} · "
                               f"{os.path.basename(file_path)}")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to save: {exc}")
            self._set_status("Save failed")

    def copy_to_clipboard(self):
        if not self.screenshot:
            self.show_snackbar("Capture a screenshot first")
            return
        try:
            self._set_clipboard_image(self.screenshot)
            self._set_status("Copied to clipboard")
            self.show_snackbar("Copied to clipboard")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to copy: {exc}")
            self._set_status("Copy failed")

    @staticmethod
    def _set_clipboard_image(image):
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

    def clear_screenshot(self):
        self.screenshot = None
        self._draw_preview()
        self._set_status("Ready")


def main():
    if sys.platform == "win32":
        try:  # align tkinter coordinates with physical pixels on scaled displays
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
    root = tk.Tk()
    SnippyApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
