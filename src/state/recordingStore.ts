import { create } from "zustand";

// The main window only needs a coarse "is something recording" flag plus a
// one-line status message - the live elapsed timer lives entirely in the
// separate RecordControlBar window (the only UI actually visible while
// recording, since the main window hides itself, same as Python's
// `self.hide()` in `start_recording()`), which polls its own status
// independently in its own JS context.
interface RecordingState {
  isRecording: boolean;
  statusMessage: string | null;
  setRecording: (value: boolean) => void;
  setStatusMessage: (message: string | null) => void;
}

export const useRecordingStore = create<RecordingState>((set) => ({
  isRecording: false,
  statusMessage: null,
  setRecording: (value) => set({ isRecording: value }),
  setStatusMessage: (message) => set({ statusMessage: message }),
}));
