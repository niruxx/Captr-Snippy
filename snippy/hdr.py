"""HDR display detection - best-effort via the Windows 10 1903+ DisplayConfig
API. Neither GDI capture nor DXGI's 8-bit path ever hands back real HDR pixel
data (Windows always tone-maps the desktop down to an SDR-referenced blend
for both capture paths), so this can't recover true HDR values - it's only
used to know *whether* a capture was taken while a display was in HDR mode,
so a corrective heuristic can be applied.

Framework-agnostic: pure ctypes + Pillow, no UI toolkit dependency, ported
unchanged from the Tkinter build.
"""

import ctypes
import sys
from ctypes import wintypes

from PIL import ImageEnhance


class _LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class _DISPLAYCONFIG_RATIONAL(ctypes.Structure):
    _fields_ = [("Numerator", wintypes.UINT), ("Denominator", wintypes.UINT)]


class _DISPLAYCONFIG_PATH_SOURCE_INFO(ctypes.Structure):
    _fields_ = [("adapterId", _LUID), ("id", wintypes.UINT),
                ("modeInfoIdx", wintypes.UINT), ("statusFlags", wintypes.UINT)]


class _DISPLAYCONFIG_PATH_TARGET_INFO(ctypes.Structure):
    _fields_ = [("adapterId", _LUID), ("id", wintypes.UINT),
                ("modeInfoIdx", wintypes.UINT),
                ("outputTechnology", wintypes.UINT),
                ("rotation", wintypes.UINT), ("scaling", wintypes.UINT),
                ("refreshRate", _DISPLAYCONFIG_RATIONAL),
                ("scanLineOrdering", wintypes.UINT),
                ("targetAvailable", wintypes.BOOL),
                ("statusFlags", wintypes.UINT)]


class _DISPLAYCONFIG_PATH_INFO(ctypes.Structure):
    _fields_ = [("sourceInfo", _DISPLAYCONFIG_PATH_SOURCE_INFO),
                ("targetInfo", _DISPLAYCONFIG_PATH_TARGET_INFO),
                ("flags", wintypes.UINT)]


class _DISPLAYCONFIG_MODE_INFO(ctypes.Structure):
    # The real struct is a tagged union of source/target/desktop-image mode
    # info; contents are never read here; only its size (fixed at 64 bytes
    # on all supported Windows versions) is used to satisfy
    # QueryDisplayConfig's mode-array buffer requirement.
    _fields_ = [("raw", ctypes.c_byte * 64)]


class _DISPLAYCONFIG_DEVICE_INFO_HEADER(ctypes.Structure):
    _fields_ = [("type", wintypes.UINT), ("size", wintypes.UINT),
                ("adapterId", _LUID), ("id", wintypes.UINT)]


class _DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO(ctypes.Structure):
    _fields_ = [("header", _DISPLAYCONFIG_DEVICE_INFO_HEADER),
                ("value", wintypes.UINT),
                ("colorEncoding", wintypes.UINT),
                ("bitsPerColorChannel", wintypes.UINT)]


QDC_ONLY_ACTIVE_PATHS = 0x00000002
DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO = 9


def displays_hdr_status():
    """{target_id: (advanced_color_supported, advanced_color_enabled)} for
    each active display path. Returns {} (meaning "unknown", not "no HDR")
    on non-Windows, pre-1903 Windows, or any API failure."""
    if sys.platform != "win32":
        return {}
    try:
        user32 = ctypes.windll.user32
        n_paths = wintypes.UINT()
        n_modes = wintypes.UINT()
        if user32.GetDisplayConfigBufferSizes(
                QDC_ONLY_ACTIVE_PATHS, ctypes.byref(n_paths),
                ctypes.byref(n_modes)) != 0:
            return {}
        paths = (_DISPLAYCONFIG_PATH_INFO * n_paths.value)()
        modes = (_DISPLAYCONFIG_MODE_INFO * n_modes.value)()
        if user32.QueryDisplayConfig(
                QDC_ONLY_ACTIVE_PATHS, ctypes.byref(n_paths), paths,
                ctypes.byref(n_modes), modes, None) != 0:
            return {}
        result = {}
        for path in paths[:n_paths.value]:
            info = _DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO()
            info.header.type = DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO
            info.header.size = ctypes.sizeof(info)
            info.header.adapterId = path.targetInfo.adapterId
            info.header.id = path.targetInfo.id
            if user32.DisplayConfigGetDeviceInfo(ctypes.byref(info)) == 0:
                supported = bool(info.value & 0x1)
                enabled = bool(info.value & 0x2)
                result[path.targetInfo.id] = (supported, enabled)
        return result
    except Exception:
        return {}


def any_display_hdr_enabled():
    return any(enabled for _supported, enabled in displays_hdr_status().values())


def apply_hdr_tone_map(image):
    """Heuristic brightness/contrast/saturation lift for screenshots taken
    while a display is in HDR mode. Both capture paths this app uses (GDI
    ImageGrab and bettercam's DXGI duplication) only ever return an 8-bit
    SDR-referenced blend of the real HDR frame, which is why HDR captures
    look dim and desaturated next to what's actually on screen - there is
    no real HDR pixel data available to tone-map from correctly, so this is
    an approximation, not a physically accurate PQ/HLG conversion."""
    corrected = ImageEnhance.Brightness(image).enhance(1.18)
    corrected = ImageEnhance.Contrast(corrected).enhance(1.08)
    corrected = ImageEnhance.Color(corrected).enhance(1.06)
    return corrected
