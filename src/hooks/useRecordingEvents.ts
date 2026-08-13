import { useEffect } from "react";
import { listen } from "@tauri-apps/api/event";
import {
  handleRecordingError,
  stopRecording,
  togglePauseRecording,
  toggleRecording,
} from "../lib/recordingActions";
import { useToastStore } from "../state/toastStore";

/** Wires the main window up to everything that can trigger a recording
 * action from outside a button click: the Rust-registered global hotkeys
 * (Ctrl+Alt+R/P, direct port of hotkeys.py - work even while unfocused),
 * the record-bar window's Stop button (a separate Tauri window/JS context,
 * so it hands control back via an event), and the recording thread's own
 * error channel (`_handle_record_error`'s port). Mount once at the app
 * root, same as useTheme(). */
export function useRecordingEvents() {
  useEffect(() => {
    const unlistens = [
      listen("hotkey:record-toggle", () => toggleRecording()),
      listen("hotkey:pause-toggle", () => togglePauseRecording()),
      listen<string>("hotkey:register-failed", (e) =>
        useToastStore.getState().show(`Couldn't register hotkey ${e.payload}`),
      ),
      listen("recordbar:stop-clicked", () => stopRecording()),
      listen<string>("recording:error", (e) => handleRecordingError(e.payload)),
    ];

    return () => {
      unlistens.forEach((p) => p.then((fn) => fn()));
    };
  }, []);
}
