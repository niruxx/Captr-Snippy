"""App constants and settings.json persistence.

Ported from the Tkinter build with the OCR / cloud-upload / NAS-Samba keys
removed (those features were cut from the PySide6 rewrite). Old settings
files that still contain those keys are simply ignored on load - no
migration/deletion needed.
"""

import json
import os

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

SETTINGS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "settings.json")

DEFAULT_SETTINGS = {
    "export_format": "PNG",
    "quality": 90,
    "auto_copy": False,
    "quick_save_dir": os.path.join(os.path.expanduser("~"),
                                   "Pictures", "Snippy"),
    "video_format": "MP4",
    "record_fps": 30,
    "record_source": "all",   # "all" | "monitor:<index>" | "window"
    # JSON-only power-user knobs - not exposed in the GUI, but honored if
    # set by hand in settings.json:
    "record_scale": 1.0,          # downscale captured frames (0.1-1.0);
                                  # smaller frames capture/encode faster
    "record_extra_ffmpeg_args": [],  # extra args appended to the ffmpeg
                                     # encode command, e.g. a custom bitrate
    "hdr_tone_map": False,
}

# fps the GUI's segmented control offers by default; settings.json may set
# record_fps to any other positive value and it'll still be honored (the
# control just grows an extra pill for it so the display stays accurate)
RECORD_FPS_RANGE = (1, 1000)


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
        record_fps = saved.get("record_fps")
        if isinstance(record_fps, int) and not isinstance(record_fps, bool) \
                and RECORD_FPS_RANGE[0] <= record_fps <= RECORD_FPS_RANGE[1]:
            settings["record_fps"] = record_fps
        source = saved.get("record_source")
        if source == "all" or source == "window" or (
                isinstance(source, str) and source.startswith("monitor:")
                and source[8:].isdigit()):
            settings["record_source"] = source
        scale = saved.get("record_scale")
        if isinstance(scale, (int, float)) and not isinstance(scale, bool) \
                and 0.1 <= scale <= 1.0:
            settings["record_scale"] = float(scale)
        extra_args = saved.get("record_extra_ffmpeg_args")
        if isinstance(extra_args, list) and \
                all(isinstance(a, str) for a in extra_args):
            settings["record_extra_ffmpeg_args"] = extra_args
        if isinstance(saved.get("hdr_tone_map"), bool):
            settings["hdr_tone_map"] = saved["hdr_tone_map"]
    except (OSError, ValueError):
        pass
    return settings


def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(settings, fh, indent=2)
    except OSError:
        pass
