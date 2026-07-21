"""Small Win32 integrations that have no Qt equivalent.

Window dragging and DPI awareness are handled by Qt itself in the PySide6
build (`startSystemMove()`, native high-DPI scaling) - this module only
keeps the one piece Qt doesn't provide: hiding a widget from screen-capture
APIs, via `SetWindowDisplayAffinity`.
"""

import ctypes
import sys

WDA_EXCLUDEFROMCAPTURE = 0x00000011


def exclude_from_capture(widget):
    """Hide a top-level widget from screen-capture APIs (Windows 10 2004+),
    so the floating recording-control bar never ends up baked into the
    recording. `widget` must already have a native window handle realized
    (i.e. shown at least once) - Qt's `winId()` forces creation of one."""
    if sys.platform != "win32":
        return
    try:
        hwnd = int(widget.winId())
        ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
    except Exception:
        pass
