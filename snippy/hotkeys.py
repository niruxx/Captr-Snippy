"""Global hotkeys - registered on a dedicated thread with its own Win32
message loop, since RegisterHotKey delivers WM_HOTKEY to the *thread* that
registered it. Framework-agnostic: callbacks are plain zero-arg callables;
the Qt integration point just points them at `AppSignals.emit`.
"""

import ctypes
import sys
import threading
from ctypes import wintypes

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000


class GlobalHotkeys:
    """Registers a fixed set of system-wide hotkeys. `bindings` is a list of
    (id, modifiers, vk, callback) tuples; callbacks fire on the hotkey
    thread, so they should hand off via a thread-safe mechanism (a Qt
    signal's `.emit()`, which Qt marshals onto the GUI thread for us)."""

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
