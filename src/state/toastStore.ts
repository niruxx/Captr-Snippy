import { create } from "zustand";

interface ToastState {
  message: string | null;
  show: (message: string) => void;
  dismiss: () => void;
}

let dismissTimer: ReturnType<typeof setTimeout> | undefined;
const DISMISS_DELAY_MS = 2400;

/** A brief floating notification pill - direct port of widgets/toast.py's
 * show_message(), minus the slide animation (a CSS transition on mount/
 * unmount below covers that instead of a manual pos-tween). */
export const useToastStore = create<ToastState>((set) => ({
  message: null,
  show: (message) => {
    clearTimeout(dismissTimer);
    set({ message });
    dismissTimer = setTimeout(() => set({ message: null }), DISMISS_DELAY_MS);
  },
  dismiss: () => {
    clearTimeout(dismissTimer);
    set({ message: null });
  },
}));
