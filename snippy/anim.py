"""One reusable animation helper backing every animated widget (button
hover-glow, segmented-control thumb, switch knob, view slide, toast,
window fade), replacing the five duplicated `after()`-loop implementations
from the Tkinter build with a single `QPropertyAnimation` wrapper.
"""

from PySide6.QtCore import QEasingCurve, QPropertyAnimation


def animate(obj, prop_name, start, end, duration=180,
            easing=QEasingCurve.Type.OutCubic, on_finished=None, parent=None):
    """Animate a Qt property (declared via @Property on `obj`, or a native
    property like b"windowOpacity"/b"pos") from `start` to `end`. Returns
    the QPropertyAnimation so the caller can keep a reference if needed.

    Deliberately does NOT use QPropertyAnimation.DeleteWhenStopped: the
    animation is already parented to `obj` (or `parent`), so Qt's normal
    parent/child ownership cleans it up - auto-deleting it on top of that
    is what breaks any caller that keeps the returned reference and later
    calls a method on it (e.g. `.stop()` to cancel a still-running
    animation before starting a new one), since the C++ object may already
    be gone by then."""
    anim = QPropertyAnimation(obj, prop_name, parent or obj)
    anim.setDuration(duration)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(easing)
    if on_finished:
        anim.finished.connect(on_finished)
    anim.start()
    return anim
