"""Central cross-thread signal hub.

Background workers (the global-hotkey message-loop thread, the recording
thread's error callback) call `.emit()` on these from their own thread;
Qt's queued cross-thread connection marshals the call onto the GUI thread
automatically, replacing the old `root.after(0, ...)` dance.
"""

from PySide6.QtCore import QObject, Signal


class AppSignals(QObject):
    record_error = Signal(str)
    hotkey_record = Signal()
    hotkey_pause = Signal()
