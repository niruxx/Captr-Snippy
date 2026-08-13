// Typed wrappers around invoke() calls to the Rust backend - one function
// per #[tauri::command], so call sites never hand-spell command names.
import { invoke } from "@tauri-apps/api/core";
import type {
  CapturedImage,
  DisplayColorStatus,
  MonitorRect,
  RecordingStatus,
  RecordSourceArg,
  Settings,
  VirtualScreen,
  WindowEntry,
} from "./types";

export function getSettings(): Promise<Settings> {
  return invoke("get_settings");
}

export function saveSettings(settings: Settings): Promise<void> {
  return invoke("save_settings", { settings });
}

export function captureFullscreen(): Promise<CapturedImage> {
  return invoke("capture_fullscreen");
}

export function captureRegion(x1: number, y1: number, x2: number, y2: number): Promise<CapturedImage> {
  return invoke("capture_region", { x1, y1, x2, y2 });
}

export function getVirtualScreen(): Promise<VirtualScreen | null> {
  return invoke("get_virtual_screen");
}

export function getMonitors(): Promise<MonitorRect[]> {
  return invoke("get_monitors");
}

export function getWindows(): Promise<WindowEntry[]> {
  return invoke("get_windows");
}

export function saveImage(
  width: number,
  height: number,
  rgba: Uint8ClampedArray,
  format: string,
  quality: number,
  path: string,
): Promise<void> {
  // Pass the typed array directly (not Array.from()) - Tauri's IPC bridge
  // transfers Uint8Array-backed args as raw bytes to Rust's Vec<u8>, which
  // matters for a multi-megabyte 4K screenshot's worth of pixels.
  return invoke("save_image", {
    width,
    height,
    rgba: new Uint8Array(rgba.buffer, rgba.byteOffset, rgba.byteLength),
    format,
    quality,
    path,
  });
}

export function startRecording(args: {
  fps: number;
  videoFormat: string;
  extraFfmpegArgs: string[];
  scale: number;
  outputPath: string;
  source: RecordSourceArg;
  cursor: boolean;
}): Promise<void> {
  return invoke("start_recording", {
    fps: args.fps,
    videoFormat: args.videoFormat,
    extraFfmpegArgs: args.extraFfmpegArgs,
    scale: args.scale,
    outputPath: args.outputPath,
    source: args.source,
    cursor: args.cursor,
  });
}

export function stopRecording(discard: boolean): Promise<string | null> {
  return invoke("stop_recording", { discard });
}

export function pauseRecording(): Promise<void> {
  return invoke("pause_recording");
}

export function resumeRecording(): Promise<void> {
  return invoke("resume_recording");
}

export function getRecordingStatus(): Promise<RecordingStatus> {
  return invoke("get_recording_status");
}

export function discardRecording(): Promise<void> {
  return invoke("discard_recording");
}

export function excludeWindowFromCapture(label: string): Promise<void> {
  return invoke("exclude_window_from_capture", { label });
}

export function getHdrStatus(): Promise<DisplayColorStatus[]> {
  return invoke("get_hdr_status");
}
