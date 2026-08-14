// Screen recording orchestration - direct behavioral port of
// main_window.py's toggle_recording()/start_recording()/stop_recording()/
// toggle_pause_recording()/_handle_record_error()/_show_record_bar()/
// _hide_record_bar(). Runs entirely in the main window; the record-bar
// window only shows a HUD and emits button-click events back here (same
// split as the capture overlay).
import { PhysicalPosition } from "@tauri-apps/api/dpi";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { WebviewWindow } from "@tauri-apps/api/webviewWindow";
import {
  discardRecording,
  excludeWindowFromCapture,
  getCaptureBounds,
  getMonitors,
  getRecordingStatus,
  getVirtualScreen,
  getWindows,
  pauseRecording as ipcPauseRecording,
  resumeRecording as ipcResumeRecording,
  startRecording as ipcStartRecording,
  stopRecording as ipcStopRecording,
} from "./ipc";
import { VIDEO_EXTENSIONS } from "./constants";
import { timestampForFilename } from "./imageUtils";
import { useRecordingStore } from "../state/recordingStore";
import { useSettingsStore } from "../state/settingsStore";
import { useToastStore } from "../state/toastStore";
import { useWindowPickerStore } from "../state/windowPickerStore";
import type { RecordSourceArg } from "./types";

const RECORD_BAR_LABEL = "record-bar";
const RECORD_BAR_WIDTH = 208;
const RECORD_BAR_HEIGHT = 46;
const RECORD_BAR_TOP_MARGIN = 18;

let recordBarWindow: WebviewWindow | null = null;

function toast(message: string) {
  useToastStore.getState().show(message);
}

/** Resolves the configured `record_source` setting into the specific
 * capture target - opening the in-app window-picker modal for "window"
 * sources, exactly when a Record click/hotkey happens, matching
 * `_make_grab_fn()`'s synchronous `WindowPickerDialog.pick(self)` call. */
async function resolveSource(): Promise<RecordSourceArg | null> {
  const source = useSettingsStore.getState().settings?.record_source ?? "all";

  if (source === "window") {
    const windows = await getWindows();
    if (windows.length === 0) {
      toast("No windows available to record");
      return null;
    }
    const hwnd = await useWindowPickerStore.getState().show(windows);
    if (hwnd == null) return null;
    return { kind: "window", hwnd };
  }

  if (source.startsWith("monitor:")) {
    const index = Number(source.slice("monitor:".length));
    if (Number.isInteger(index) && index >= 0) {
      return { kind: "monitor", index };
    }
  }

  return { kind: "all" };
}

/** Where the bar would sit by default: horizontally centered, docked to
 * the top of the primary monitor - unchanged from before this existed. */
function defaultBarPosition(primary: { left: number; right: number; top: number }): {
  x: number;
  y: number;
} {
  return {
    x: primary.left + (primary.right - primary.left - RECORD_BAR_WIDTH) / 2,
    y: primary.top + RECORD_BAR_TOP_MARGIN,
  };
}

/** Nudges the default bar position out of `source`'s captured region when
 * it would otherwise overlap, for platforms with no
 * `exclude_window_from_capture` (see that command's Linux branch) - the
 * bar would otherwise get baked into its own recording. Only tries "just
 * above" or "just below" the captured region; if neither fits inside the
 * virtual desktop (e.g. a maximized window, or `source: "all"` has no
 * region to dodge at all), the bar keeps its default spot exactly like it
 * did before this existed. */
async function barPositionAvoidingCapture(
  source: RecordSourceArg,
  primary: { left: number; right: number; top: number },
): Promise<{ x: number; y: number }> {
  const fallback = defaultBarPosition(primary);
  try {
    const [bounds, virtualScreen] = await Promise.all([getCaptureBounds(source), getVirtualScreen()]);
    if (!bounds || !virtualScreen) return fallback;

    const [left, top, right, bottom] = bounds;
    const overlaps =
      fallback.x < right &&
      fallback.x + RECORD_BAR_WIDTH > left &&
      fallback.y < bottom &&
      fallback.y + RECORD_BAR_HEIGHT > top;
    if (!overlaps) return fallback;

    const x = left + (right - left - RECORD_BAR_WIDTH) / 2;
    const above = top - RECORD_BAR_TOP_MARGIN - RECORD_BAR_HEIGHT;
    if (above >= virtualScreen.y) {
      return { x, y: above };
    }
    const below = bottom + RECORD_BAR_TOP_MARGIN;
    if (below + RECORD_BAR_HEIGHT <= virtualScreen.y + virtualScreen.height) {
      return { x, y: below };
    }
    return fallback;
  } catch {
    return fallback;
  }
}

async function showRecordBar(source: RecordSourceArg) {
  const monitors = await getMonitors();
  const primary = monitors.find((m) => m.is_primary) ?? monitors[0];

  const bar = new WebviewWindow(RECORD_BAR_LABEL, {
    decorations: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    shadow: false,
    focus: false,
    width: RECORD_BAR_WIDTH,
    height: RECORD_BAR_HEIGHT,
  });
  recordBarWindow = bar;

  bar.once("tauri://created", async () => {
    if (primary) {
      const { x, y } = await barPositionAvoidingCapture(source, primary);
      await bar.setPosition(new PhysicalPosition(Math.round(x), Math.round(y)));
    }
    await bar.show();
    try {
      await excludeWindowFromCapture(RECORD_BAR_LABEL);
    } catch {
      // best-effort - unsupported on this Windows version/platform
    }
  });
}

async function hideRecordBar() {
  const bar = recordBarWindow;
  recordBarWindow = null;
  if (bar) {
    try {
      await bar.close();
    } catch {
      // already closed
    }
  }
}

export async function startRecording() {
  const state = useRecordingStore.getState();
  if (state.isRecording) return;

  const settings = useSettingsStore.getState().settings;
  if (!settings) return;

  const source = await resolveSource();
  if (!source) return;

  const win = getCurrentWindow();
  const ext = VIDEO_EXTENSIONS[settings.video_format] ?? "mp4";
  const separator = settings.quick_save_dir.includes("/") ? "/" : "\\";
  const outputPath = `${settings.quick_save_dir}${separator}recording_${timestampForFilename()}.${ext}`;

  await win.hide();
  try {
    await ipcStartRecording({
      fps: settings.record_fps,
      videoFormat: settings.video_format,
      extraFfmpegArgs: settings.record_extra_ffmpeg_args,
      scale: settings.record_scale,
      outputPath,
      source,
      cursor: settings.record_cursor,
    });
  } catch (err) {
    await win.show();
    toast(`Failed to start recording: ${err}`);
    return;
  }

  state.setRecording(true);
  state.setStatusMessage("Recording…");
  await showRecordBar(source);
}

export async function stopRecording(discard = false) {
  const state = useRecordingStore.getState();
  if (!state.isRecording) return;

  state.setRecording(false);
  let path: string | null = null;
  try {
    path = await ipcStopRecording(discard);
  } catch (err) {
    toast(`Failed to stop recording: ${err}`);
  }
  await hideRecordBar();

  const win = getCurrentWindow();
  await win.show();

  if (discard || !path) {
    state.setStatusMessage(discard ? "Recording discarded" : null);
    return;
  }
  const filename = path.split(/[\\/]/).pop() ?? path;
  state.setStatusMessage(`Recording saved · ${filename}`);
  toast(`Saved recording · ${filename}`);
}

export async function toggleRecording() {
  if (useRecordingStore.getState().isRecording) {
    await stopRecording();
  } else {
    await startRecording();
  }
}

export async function togglePauseRecording() {
  if (!useRecordingStore.getState().isRecording) return;
  // The record bar tracks paused/not-paused itself via polling
  // get_recording_status(), so this just needs to flip the Rust-side
  // state - matching `toggle_pause_recording()`'s split between
  // recorder.pause()/resume() and the bar's own `set_paused()` refresh.
  try {
    const status = await getRecordingStatus();
    if (status.paused) {
      await ipcResumeRecording();
    } else {
      await ipcPauseRecording();
    }
  } catch (err) {
    toast(`Failed to toggle pause: ${err}`);
  }
}

/** Called when the recording thread reports a mid-recording error (source
 * vanished, ffmpeg died) - direct port of `_handle_record_error`. */
export async function handleRecordingError(message: string) {
  const state = useRecordingStore.getState();
  if (!state.isRecording) return;
  state.setRecording(false);
  try {
    await discardRecording();
  } catch {
    // already gone
  }
  await hideRecordBar();
  const win = getCurrentWindow();
  await win.show();
  state.setStatusMessage(null);
  toast(`Recording error: ${message}`);
}
