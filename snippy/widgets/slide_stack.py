"""SlideStack - a small container that holds exactly the views added to it,
always keeping non-current views hidden (so nothing can ever visually
overlap, even if a transition is interrupted), and animates between them
with a horizontal slide. Replaces main_window's old QStackedLayout(StackAll)
+ manual position bookkeeping, which could leave both views visible on top
of each other if a slide was interrupted mid-flight.
"""

from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPoint, QPropertyAnimation
from PySide6.QtWidgets import QWidget


class SlideStack(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._views = []
        self.current = None
        self._group = None

    def add_view(self, widget):
        widget.setParent(self)
        if self.current is None:
            self.current = widget
            widget.setGeometry(self.rect())
            widget.show()
        else:
            widget.hide()
        self._views.append(widget)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Only the current, settled view tracks live resizes; a view mid-
        # transition keeps its animated geometry (resizing almost never
        # happens mid-slide in practice, and this avoids fighting the
        # in-flight animation over widget geometry).
        if self._group is None and self.current is not None:
            self.current.setGeometry(self.rect())

    def slide_to(self, target, direction=1, duration=220):
        """direction=1 slides `target` in from the right (used for
        "forward"/into-settings navigation), -1 from the left (back)."""
        if target not in self._views or target is self.current:
            return
        outgoing = self.current
        incoming = target
        w, h = self.width(), self.height()

        if self._group is not None:
            self._group.stop()
            self._group = None
            # snap any in-flight views to a sane resting state before
            # starting a new transition, so nothing is left stranded
            # mid-slide (this is exactly what caused the overlap bug).
            outgoing.move(0, 0)

        incoming.setGeometry(direction * w, 0, w, h)
        incoming.show()
        incoming.raise_()

        move_in = QPropertyAnimation(incoming, b"pos", self)
        move_in.setDuration(duration)
        move_in.setStartValue(QPoint(direction * w, 0))
        move_in.setEndValue(QPoint(0, 0))
        move_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        move_out = QPropertyAnimation(outgoing, b"pos", self)
        move_out.setDuration(duration)
        move_out.setStartValue(QPoint(0, 0))
        move_out.setEndValue(QPoint(-direction * w, 0))
        move_out.setEasingCurve(QEasingCurve.Type.OutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(move_in)
        group.addAnimation(move_out)
        group.finished.connect(lambda: self._finish_slide(incoming, outgoing, group))
        self._group = group
        self.current = incoming
        group.start()

    def _finish_slide(self, incoming, outgoing, group):
        outgoing.hide()
        outgoing.move(0, 0)
        incoming.move(0, 0)
        incoming.setGeometry(self.rect())
        if self._group is group:
            self._group = None
