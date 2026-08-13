import { create } from "zustand";
import type { WindowEntry } from "../lib/types";

// Backs the in-app "Choose a window to record" modal - direct port of
// views/window_picker.py's WindowPickerDialog, minus the separate native
// dialog (it doesn't need overlay/always-on-top/capture-exclusion, so it's
// just a modal in the main window). `show()` resolves once the user picks
// a window or cancels, mirroring `WindowPickerDialog.pick()`'s blocking
// `exec()` call.
interface WindowPickerState {
  open: boolean;
  windows: WindowEntry[];
  _resolve: ((hwnd: number | null) => void) | null;
  show: (windows: WindowEntry[]) => Promise<number | null>;
  choose: (hwnd: number) => void;
  cancel: () => void;
}

export const useWindowPickerStore = create<WindowPickerState>((set, get) => ({
  open: false,
  windows: [],
  _resolve: null,
  show: (windows) =>
    new Promise((resolve) => {
      set({ open: true, windows, _resolve: resolve });
    }),
  choose: (hwnd) => {
    get()._resolve?.(hwnd);
    set({ open: false, windows: [], _resolve: null });
  },
  cancel: () => {
    get()._resolve?.(null);
    set({ open: false, windows: [], _resolve: null });
  },
}));
