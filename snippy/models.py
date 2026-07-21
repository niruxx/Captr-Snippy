"""Capture/annotation state, split out of the old monolithic SnippyApp so
it carries no widget references. Callers (MainWindow) mutate this then
explicitly refresh whichever views need it - no observer framework, since
this is a small solo project and that would be ceremony.
"""

from dataclasses import dataclass, field

from .hdr import any_display_hdr_enabled, apply_hdr_tone_map
from .settings import ANNOT_COLORS, ANNOT_WIDTHS, HISTORY_LIMIT, UNDO_LIMIT


@dataclass
class CaptureState:
    screenshot: object = None          # PIL.Image.Image | None
    history: list = field(default_factory=list)   # newest first
    history_index: int = -1
    undo_stack: list = field(default_factory=list)
    tool: str = None
    annot_color: str = ANNOT_COLORS[0]
    annot_width: int = ANNOT_WIDTHS[1]

    def push_undo(self):
        self.undo_stack.append(self.screenshot.copy())
        if len(self.undo_stack) > UNDO_LIMIT:
            self.undo_stack.pop(0)

    def pop_undo(self):
        """Rolls back a push_undo() when the caller decides the edit that
        prompted it didn't actually happen (e.g. a crop box that turned out
        too small to commit)."""
        if self.undo_stack:
            self.undo_stack.pop()

    def undo(self):
        """Returns True if an edit was undone, False if the stack was empty."""
        if not self.undo_stack:
            return False
        self.screenshot = self.undo_stack.pop()
        self.commit()
        return True

    def commit(self):
        """Sync the (already-edited) `screenshot` back into history."""
        if 0 <= self.history_index < len(self.history):
            self.history[self.history_index] = self.screenshot

    def add_capture(self, image, settings=None):
        if settings and settings.get("hdr_tone_map") and any_display_hdr_enabled():
            try:
                image = apply_hdr_tone_map(image)
            except Exception:
                pass
        self.history.insert(0, image)
        del self.history[HISTORY_LIMIT:]
        self.history_index = 0
        self.screenshot = image
        self.undo_stack.clear()

    def select(self, index):
        if not (0 <= index < len(self.history)):
            return False
        self.history_index = index
        self.screenshot = self.history[index]
        self.undo_stack.clear()
        return True

    def remove_current(self):
        if not self.history:
            return
        del self.history[self.history_index]
        if self.history:
            self.history_index = min(self.history_index, len(self.history) - 1)
            self.screenshot = self.history[self.history_index]
        else:
            self.history_index = -1
            self.screenshot = None
        self.undo_stack.clear()
