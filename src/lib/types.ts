// Mirrors src-tauri/src/commands/settings.rs's `Settings` struct field for
// field (same JSON shape as the legacy Python settings.json, snake_case
// keys and all, for a seamless read on first run).
export interface Settings {
  export_format: string;
  quality: number;
  auto_copy: boolean;
  quick_save_dir: string;
  video_format: string;
  record_fps: number;
  record_source: string;
  record_scale: number;
  record_extra_ffmpeg_args: string[];
  hdr_tone_map: boolean;
  onboarding_complete: boolean;
  close_to_tray: boolean;
  capture_sound: boolean;
  history_limit: number;
  record_cursor: boolean;
}

export interface CapturedImage {
  width: number;
  height: number;
  /** A `data:image/png;base64,...` URL - directly usable as an <img> src. */
  data_url: string;
}

export interface VirtualScreen {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface MonitorRect {
  left: number;
  top: number;
  right: number;
  bottom: number;
  is_primary: boolean;
}

export interface WindowEntry {
  hwnd: number;
  title: string;
}

export type RecordSourceArg =
  | { kind: "all" }
  | { kind: "monitor"; index: number }
  | { kind: "window"; hwnd: number };

export interface RecordingStatus {
  is_recording: boolean;
  paused: boolean;
  elapsed_secs: number;
}

export interface DisplayColorStatus {
  target_id: number;
  supported: boolean;
  enabled: boolean;
}
