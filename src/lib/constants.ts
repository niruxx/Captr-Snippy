// Direct port of snippy/settings.py's app-wide constants.
export const EXPORT_FORMATS = ["PNG", "JPEG", "WEBP", "BMP"] as const;
export const LOSSY_FORMATS = ["JPEG", "WEBP"] as const;
export const VIDEO_FORMATS = ["MP4", "MKV", "FLV", "WEBM"] as const;
export const RECORD_FPS_PRESETS = [15, 30, 60, 120, 144, 165, 240] as const;
export const ANNOT_COLORS = [
  "#FF453A",
  "#FF9F0A",
  "#FFD60A",
  "#32D74B",
  "#0A84FF",
  "#FFFFFF",
  "#000000",
] as const;
export const ANNOT_WIDTHS = [2, 4, 8] as const;
export const HISTORY_LIMIT = 8;
export const HISTORY_LIMIT_PRESETS = [4, 8, 16, 24] as const;
export const UNDO_LIMIT = 8;

export const EXPORT_EXTENSIONS: Record<string, string> = {
  PNG: "png",
  JPEG: "jpg",
  WEBP: "webp",
  BMP: "bmp",
};

export const VIDEO_EXTENSIONS: Record<string, string> = {
  MP4: "mp4",
  MKV: "mkv",
  FLV: "flv",
  WEBM: "webm",
};
