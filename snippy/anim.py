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
    the QPropertyAnimation so the caller can keep a reference if needed
    (Qt does not require this for a running animation, but holding one
    avoids relying on GC timing across event-loop turns)."""
    anim = QPropertyAnimation(obj, prop_name, parent or obj)
    anim.setDuration(duration)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(easing)
    if on_finished:
        anim.finished.connect(on_finished)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim
