//! Settings persistence - a direct port of snippy/settings.py's
//! DEFAULT_SETTINGS + load_settings()/save_settings(). Each key is
//! independently validated on load (type/range/membership checked exactly
//! like the Python build), so a single unknown or malformed key never
//! invalidates the rest of the file - unlike a plain `#[derive(Deserialize)]`
//! on `Settings`, which would reject the whole file on one bad field.

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fs;
use std::path::PathBuf;
use tauri::{AppHandle, Manager};

pub const FORMATS: [&str; 4] = ["PNG", "JPEG", "WEBP", "BMP"];
pub const VIDEO_FORMATS: [&str; 4] = ["MP4", "MKV", "FLV", "WEBM"];
pub const THEMES: [&str; 4] = ["classic", "aurora", "snowfall", "sunset"];
const RECORD_FPS_RANGE: (i64, i64) = (1, 1000);
const HISTORY_LIMIT_RANGE: (i64, i64) = (1, 50);

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Settings {
    pub export_format: String,
    pub quality: i64,
    pub auto_copy: bool,
    pub quick_save_dir: String,
    pub video_format: String,
    pub record_fps: i64,
    pub record_source: String,
    pub record_scale: f64,
    pub record_extra_ffmpeg_args: Vec<String>,
    pub hdr_tone_map: bool,
    /// Accent-color + animated-background flavor, applied via CSS custom
    /// properties on the frontend (see src/lib/themes.ts) - one of [`THEMES`].
    pub theme: String,
    /// Gates the first-run onboarding flow; set true once it's completed
    /// (or skipped) so it never shows again for this user.
    pub onboarding_complete: bool,
    /// When true, closing the main window hides it to the tray icon instead
    /// of quitting the app - lets global hotkeys (Ctrl+Alt+R/P) and a
    /// pending recording keep working with no window open. Handled entirely
    /// in the frontend (`WindowFrame.tsx`'s close handler); this field is
    /// just the persisted user choice.
    pub close_to_tray: bool,
    /// Plays a short shutter-click sound (Web Audio, no asset file) on every
    /// new capture.
    pub capture_sound: bool,
    /// Max thumbnails kept in the capture history rail - one of
    /// [`HISTORY_LIMIT_RANGE`]'s clamped range, default 8.
    pub history_limit: i64,
    /// Draws the live mouse cursor into screen recordings (not stills) -
    /// composited per-frame in `recording::run()` since xcap's own capture
    /// never includes it.
    pub record_cursor: bool,
}

impl Settings {
    fn default_with(quick_save_dir: String) -> Self {
        Settings {
            export_format: "PNG".into(),
            quality: 90,
            auto_copy: false,
            quick_save_dir,
            video_format: "MP4".into(),
            record_fps: 30,
            record_source: "all".into(),
            record_scale: 1.0,
            record_extra_ffmpeg_args: Vec::new(),
            hdr_tone_map: false,
            theme: "classic".into(),
            onboarding_complete: false,
            close_to_tray: false,
            capture_sound: true,
            history_limit: 8,
            record_cursor: false,
        }
    }
}

fn default_quick_save_dir(app: &AppHandle) -> String {
    app.path()
        .picture_dir()
        .map(|d| d.join("Captr"))
        .unwrap_or_else(|_| PathBuf::from("Captr"))
        .to_string_lossy()
        .into_owned()
}

/// The settings file's permanent home: the OS-standard per-user config
/// directory, e.g. `%APPDATA%/com.captr.desktop/settings.json` on Windows.
fn settings_path(app: &AppHandle) -> PathBuf {
    let dir = app
        .path()
        .app_config_dir()
        .expect("app_config_dir should always resolve on desktop");
    dir.join("settings.json")
}

/// The Python/PySide6 build's settings.json lived next to `main.py` at the
/// repo root - `CARGO_MANIFEST_DIR` is `<repo>/src-tauri`, so its parent is
/// that same repo root. Only used as a one-time migration source when the
/// real (app_config_dir) settings file doesn't exist yet; harmless once
/// this app is actually installed/run outside the dev checkout, since the
/// path simply won't exist there.
fn legacy_settings_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("src-tauri always has a parent directory")
        .join("settings.json")
}

fn is_valid_record_source(source: &str) -> bool {
    if source == "all" || source == "window" {
        return true;
    }
    match source.strip_prefix("monitor:") {
        Some(rest) => !rest.is_empty() && rest.chars().all(|c| c.is_ascii_digit()),
        None => false,
    }
}

/// Validates one field at a time against `saved`, falling back to
/// `defaults`' value for anything missing/wrong-typed/out-of-range - the
/// same per-key contract as settings.py's load_settings().
fn merge_validated(defaults: Settings, saved: &Value) -> Settings {
    let mut settings = defaults;

    if let Some(v) = saved.get("export_format").and_then(Value::as_str) {
        if FORMATS.contains(&v) {
            settings.export_format = v.to_string();
        }
    }
    if let Some(v) = saved.get("quality").and_then(Value::as_i64) {
        settings.quality = v.clamp(40, 100);
    }
    if let Some(v) = saved.get("auto_copy").and_then(Value::as_bool) {
        settings.auto_copy = v;
    }
    if let Some(v) = saved.get("quick_save_dir").and_then(Value::as_str) {
        if !v.is_empty() {
            settings.quick_save_dir = v.to_string();
        }
    }
    if let Some(v) = saved.get("video_format").and_then(Value::as_str) {
        if VIDEO_FORMATS.contains(&v) {
            settings.video_format = v.to_string();
        }
    }
    if let Some(v) = saved.get("record_fps").and_then(Value::as_i64) {
        if v >= RECORD_FPS_RANGE.0 && v <= RECORD_FPS_RANGE.1 {
            settings.record_fps = v;
        }
    }
    if let Some(v) = saved.get("record_source").and_then(Value::as_str) {
        if is_valid_record_source(v) {
            settings.record_source = v.to_string();
        }
    }
    if let Some(v) = saved.get("record_scale").and_then(Value::as_f64) {
        if (0.1..=1.0).contains(&v) {
            settings.record_scale = v;
        }
    }
    if let Some(v) = saved.get("record_extra_ffmpeg_args").and_then(Value::as_array) {
        if let Some(args) = v
            .iter()
            .map(|a| a.as_str().map(str::to_string))
            .collect::<Option<Vec<String>>>()
        {
            settings.record_extra_ffmpeg_args = args;
        }
    }
    if let Some(v) = saved.get("hdr_tone_map").and_then(Value::as_bool) {
        settings.hdr_tone_map = v;
    }
    if let Some(v) = saved.get("theme").and_then(Value::as_str) {
        if THEMES.contains(&v) {
            settings.theme = v.to_string();
        }
    }
    if let Some(v) = saved.get("onboarding_complete").and_then(Value::as_bool) {
        settings.onboarding_complete = v;
    }
    if let Some(v) = saved.get("close_to_tray").and_then(Value::as_bool) {
        settings.close_to_tray = v;
    }
    if let Some(v) = saved.get("capture_sound").and_then(Value::as_bool) {
        settings.capture_sound = v;
    }
    if let Some(v) = saved.get("history_limit").and_then(Value::as_i64) {
        settings.history_limit = v.clamp(HISTORY_LIMIT_RANGE.0, HISTORY_LIMIT_RANGE.1);
    }
    if let Some(v) = saved.get("record_cursor").and_then(Value::as_bool) {
        settings.record_cursor = v;
    }

    settings
}

pub fn load_settings(app: &AppHandle) -> Settings {
    let defaults = Settings::default_with(default_quick_save_dir(app));
    let primary = settings_path(app);

    let source_path = if primary.exists() {
        Some(primary.clone())
    } else {
        let legacy = legacy_settings_path();
        legacy.exists().then_some(legacy)
    };

    let Some(path) = source_path else {
        return defaults;
    };
    let Ok(text) = fs::read_to_string(&path) else {
        return defaults;
    };
    let Ok(value) = serde_json::from_str::<Value>(&text) else {
        return defaults;
    };

    let settings = merge_validated(defaults, &value);
    if path != primary {
        // migrate: copy the legacy file's (validated) contents into the
        // real per-user location so future runs no longer need it
        let _ = save_settings_to_disk(app, &settings);
    }
    settings
}

fn save_settings_to_disk(app: &AppHandle, settings: &Settings) -> Result<(), String> {
    let path = settings_path(app);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let text = serde_json::to_string_pretty(settings).map_err(|e| e.to_string())?;
    fs::write(&path, text).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn get_settings(app: AppHandle) -> Settings {
    load_settings(&app)
}

#[tauri::command]
pub fn save_settings(app: AppHandle, settings: Settings) -> Result<(), String> {
    // re-validate on the way in too, so a buggy/future frontend can't write
    // a corrupt file - round-trip through the same merge logic as load.
    let defaults = Settings::default_with(default_quick_save_dir(&app));
    let value = serde_json::to_value(&settings).map_err(|e| e.to_string())?;
    let validated = merge_validated(defaults, &value);
    save_settings_to_disk(&app, &validated)
}
