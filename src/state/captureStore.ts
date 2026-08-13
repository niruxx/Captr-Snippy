import { create } from "zustand";
import type { CapturedImage } from "../lib/types";
import type { ToolName } from "../lib/annotation";
import { ANNOT_COLORS, ANNOT_WIDTHS, HISTORY_LIMIT, UNDO_LIMIT } from "../lib/constants";

// The direct equivalent of models.py's CaptureState: a capture history
// (newest first, capped at HISTORY_LIMIT) plus a per-capture edit-undo
// stack that resets whenever the active capture changes.
interface CaptureState {
  screenshot: CapturedImage | null;
  history: CapturedImage[];
  historyIndex: number;
  /** Bumped only when the *active capture itself* changes (a new capture
   * arrives, or a different history thumbnail is selected) - not on every
   * in-place edit/undo of the same capture. The preview canvas keys its
   * entrance animation off this so annotating doesn't replay a "new
   * photo" pop-in on every stroke. */
  captureSeq: number;
  tool: ToolName | null;
  color: string;
  width: number;
  undoStack: CapturedImage[];

  /** A brand-new capture (Snip region / Full screen) - inserted at the
   * front of history, mirroring CaptureState.add_capture(). `limit`
   * defaults to HISTORY_LIMIT but callers pass the user's configured
   * `history_limit` setting when available. */
  addCapture: (image: CapturedImage, limit?: number) => void;
  /** Switches to an earlier capture from the history rail. */
  selectCapture: (index: number) => void;
  /** Drops the current capture from history (Delete key / overflow menu). */
  removeCurrent: () => void;
  /** An edit to the *current* capture - updates both `screenshot` and its
   * slot in `history`, mirroring CaptureState.commit(). */
  setScreenshot: (image: CapturedImage) => void;
  setTool: (tool: ToolName | null) => void;
  setColor: (color: string) => void;
  setWidth: (width: number) => void;
  /** Snapshots the current screenshot onto the undo stack before an edit -
   * call before mutating the canvas, mirroring CaptureState.push_undo(). */
  pushUndo: () => void;
  /** Rolls back a pushUndo() when the edit that prompted it didn't
   * actually happen (e.g. a crop box that turned out too small). */
  popUndo: () => void;
  /** Pops the undo stack and restores that snapshot as the current
   * screenshot; returns it so the canvas can redraw, or null if empty. */
  undo: () => CapturedImage | null;
}

export const useCaptureStore = create<CaptureState>((set, get) => ({
  screenshot: null,
  history: [],
  historyIndex: -1,
  captureSeq: 0,
  tool: null,
  color: ANNOT_COLORS[0],
  width: ANNOT_WIDTHS[1],
  undoStack: [],

  addCapture: (image, limit = HISTORY_LIMIT) => {
    const history = [image, ...get().history].slice(0, limit);
    set((s) => ({ history, historyIndex: 0, screenshot: image, undoStack: [], captureSeq: s.captureSeq + 1 }));
  },

  selectCapture: (index) => {
    const { history } = get();
    if (index < 0 || index >= history.length) return;
    set((s) => ({ historyIndex: index, screenshot: history[index], undoStack: [], captureSeq: s.captureSeq + 1 }));
  },

  removeCurrent: () => {
    const { history, historyIndex } = get();
    if (history.length === 0) return;
    const next = history.filter((_, i) => i !== historyIndex);
    if (next.length === 0) {
      set((s) => ({ history: [], historyIndex: -1, screenshot: null, undoStack: [], captureSeq: s.captureSeq + 1 }));
      return;
    }
    const newIndex = Math.min(historyIndex, next.length - 1);
    set((s) => ({ history: next, historyIndex: newIndex, screenshot: next[newIndex], undoStack: [], captureSeq: s.captureSeq + 1 }));
  },

  setScreenshot: (image) => {
    const { history, historyIndex } = get();
    if (historyIndex >= 0 && historyIndex < history.length) {
      const nextHistory = history.slice();
      nextHistory[historyIndex] = image;
      set({ screenshot: image, history: nextHistory });
    } else {
      set({ screenshot: image });
    }
  },

  setTool: (tool) => set((s) => ({ tool: s.tool === tool ? null : tool })),
  setColor: (color) => set({ color }),
  setWidth: (width) => set({ width }),

  pushUndo: () => {
    const { screenshot, undoStack } = get();
    if (!screenshot) return;
    const next = [...undoStack, screenshot].slice(-UNDO_LIMIT);
    set({ undoStack: next });
  },

  popUndo: () => {
    set((s) => ({ undoStack: s.undoStack.slice(0, -1) }));
  },

  undo: () => {
    const { undoStack, history, historyIndex } = get();
    if (undoStack.length === 0) return null;
    const previous = undoStack[undoStack.length - 1];
    const nextHistory =
      historyIndex >= 0 && historyIndex < history.length
        ? history.map((h, i) => (i === historyIndex ? previous : h))
        : history;
    set({ undoStack: undoStack.slice(0, -1), screenshot: previous, history: nextHistory });
    return previous;
  },
}));
