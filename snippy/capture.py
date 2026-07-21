"""Desktop/monitor/window enumeration and GPU-accelerated capture.

Framework-agnostic: ctypes + Pillow (+ optional bettercam/numpy), no UI
toolkit dependency, ported unchanged from the Tkinter build.
"""

import ctypes
import sys
import time
from ctypes import wintypes

from PIL import Image, ImageGrab

try:  # optional GPU-accelerated capture (Windows only); recording falls
    # back to plain ImageGrab everywhere else, or if this fails to load
    # (older GPU/driver, virtual display, Remote Desktop, non-Windows OS).
    import bettercam
    import numpy as np
    HAVE_BETTERCAM = sys.platform == "win32"
except ImportError:
    bettercam = None
    np = None
    HAVE_BETTERCAM = False


def virtual_screen():
    """(x, y, w, h) of the full multi-monitor virtual screen."""
    if sys.platform != "win32":
        return None
    try:
        user32 = ctypes.windll.user32
        return (user32.GetSystemMetrics(76), user32.GetSystemMetrics(77),
                user32.GetSystemMetrics(78), user32.GetSystemMetrics(79))
    except Exception:
        return None


MONITORINFOF_PRIMARY = 0x00000001


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", ctypes.c_ulong)]


def list_monitors():
    """[(left, top, right, bottom, is_primary), ...] for each connected
    monitor, in the same virtual-desktop coordinate space ImageGrab uses."""
    if sys.platform != "win32":
        return []
    monitors = []
    MonitorEnumProc = ctypes.WINFUNCTYPE(
        ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
        ctypes.POINTER(wintypes.RECT), ctypes.c_double)

    def callback(hmonitor, _hdc, _rect, _data):
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if ctypes.windll.user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            r = info.rcMonitor
            primary = bool(info.dwFlags & MONITORINFOF_PRIMARY)
            monitors.append((r.left, r.top, r.right, r.bottom, primary))
        return 1

    try:
        ctypes.windll.user32.EnumDisplayMonitors(
            None, None, MonitorEnumProc(callback), 0)
    except Exception:
        return []
    return monitors


def list_windows():
    """[(hwnd, title), ...] for visible, titled top-level windows other than
    Snippy's own - candidates for the "record a window" source picker."""
    if sys.platform != "win32":
        return []
    user32 = ctypes.windll.user32
    windows = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        if title and title != "Snippy":
            windows.append((hwnd, title))
        return True

    try:
        user32.EnumWindows(WNDENUMPROC(callback), 0)
    except Exception:
        return []
    return windows


# ---------------------------------------------------------------------------
# Desktop capture - GPU-accelerated (DXGI Desktop Duplication, via
# bettercam) when available, since plain BitBlt (what ImageGrab uses) is
# often too slow to sustain a smooth frame rate on a large or multi-monitor
# desktop. Falls back to ImageGrab transparently: on non-Windows platforms,
# when bettercam isn't installed, or if DXGI duplication itself fails (older
# GPU/driver, virtual display, Remote Desktop all commonly reject it).
# ---------------------------------------------------------------------------
class DesktopGrabber:
    """Grabs the whole virtual desktop (optionally cropped to `bbox`, in the
    same coordinate space `list_monitors()` reports) as fast as possible."""

    def __init__(self):
        self._monitors = list_monitors() if HAVE_BETTERCAM else []
        self._cams = []
        self._last_frames = {}
        self._canvas = None  # reused across frames - see _grab_gpu()
        self.using_gpu = False
        if self._monitors:
            lefts = [m[0] for m in self._monitors]
            tops = [m[1] for m in self._monitors]
            rights = [m[2] for m in self._monitors]
            bottoms = [m[3] for m in self._monitors]
            self._origin = (min(lefts), min(tops))
            self._size = (max(rights) - min(lefts), max(bottoms) - min(tops))
            self._try_start_gpu()
        else:
            self._origin = (0, 0)
            self._size = (0, 0)

    def _try_start_gpu(self):
        try:
            cams = [bettercam.create(output_idx=i, output_color="RGB")
                    for i in range(len(self._monitors))]
            # smoke-test the whole pipeline now (surfaces a missing codec
            # DLL, an unsupported adapter, or a Remote Desktop session
            # immediately, rather than partway through a recording)
            for cam in cams:
                for _ in range(50):
                    if cam.grab() is not None:
                        break
                    time.sleep(0.01)
            self._cams = cams
            self.using_gpu = True
        except Exception:
            self._stop_gpu()

    def _stop_gpu(self):
        for cam in self._cams:
            try:
                cam.release()
            except Exception:
                pass
        self._cams = []
        self.using_gpu = False

    def grab(self, bbox=None):
        """Returns a PIL Image for the requested region. When GPU capture
        is active the image may share memory with an internal buffer that
        the *next* grab() call overwrites in place - callers must finish
        with one frame (e.g. `.convert("RGB").tobytes()`, which copies)
        before requesting the next."""
        if self.using_gpu:
            try:
                image = self._grab_gpu(bbox)
                if image is not None:
                    return image
            except Exception:
                self._stop_gpu()
        image = ImageGrab.grab(all_screens=True)
        if bbox is not None:
            ox, oy = self._origin if self._monitors else \
                self._virtual_origin()
            image = image.crop((bbox[0] - ox, bbox[1] - oy,
                                bbox[2] - ox, bbox[3] - oy))
        return image

    def _monitor_index_for_bbox(self, bbox):
        """Index of the one monitor bbox lies fully within, else None."""
        left, top, right, bottom = bbox
        for i, (ml, mt, mr, mb, _primary) in enumerate(self._monitors):
            if left >= ml and top >= mt and right <= mr and bottom <= mb:
                return i
        return None

    def _grab_monitor(self, index):
        frame = self._cams[index].grab()
        if frame is not None:
            self._last_frames[index] = frame
        return self._last_frames.get(index)

    def _grab_gpu(self, bbox):
        # The common case (recording just one monitor, or a window that
        # lives on one monitor) only needs that camera's own frame, sliced
        # directly - compositing the whole virtual desktop for it would
        # waste a full-size buffer allocation and copy on every frame.
        if bbox is not None:
            index = self._monitor_index_for_bbox(bbox)
            if index is not None:
                frame = self._grab_monitor(index)
                if frame is None:
                    return None
                ml, mt, _, _, _ = self._monitors[index]
                left, top, right, bottom = bbox
                x0, y0 = left - ml, top - mt
                x1, y1 = right - ml, bottom - mt
                return Image.fromarray(
                    np.ascontiguousarray(frame[y0:y1, x0:x1]))

        w, h = self._size
        if self._canvas is None:
            # Allocated once and overwritten in place on every subsequent
            # call - a fresh np.zeros() per frame meant a 4K+ desktop was
            # re-allocating and re-zeroing tens of MB every single frame.
            # Any gap no monitor covers just stays black forever either way.
            self._canvas = np.zeros((h, w, 3), dtype=np.uint8)
        canvas = self._canvas
        ox, oy = self._origin
        for i, (left, top, _right, _bottom, _primary) in \
                enumerate(self._monitors):
            frame = self._grab_monitor(i)
            if frame is None:
                continue
            x0, y0 = left - ox, top - oy
            fh = min(frame.shape[0], h - y0)
            fw = min(frame.shape[1], w - x0)
            canvas[y0:y0 + fh, x0:x0 + fw] = frame[:fh, :fw]
        image = Image.fromarray(canvas)
        if bbox is not None:  # bbox spanning multiple monitors (rare)
            ox, oy = self._origin
            image = image.crop((bbox[0] - ox, bbox[1] - oy,
                                bbox[2] - ox, bbox[3] - oy))
        return image

    @staticmethod
    def _virtual_origin():
        if sys.platform != "win32":
            return (0, 0)
        try:
            user32 = ctypes.windll.user32
            return (user32.GetSystemMetrics(76), user32.GetSystemMetrics(77))
        except Exception:
            return (0, 0)

    def close(self):
        self._stop_gpu()
