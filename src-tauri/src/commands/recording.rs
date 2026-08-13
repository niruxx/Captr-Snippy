//! Screen recording commands - thin Tauri wrappers around `recording::Recorder`,
//! holding the single active recorder (if any) in `AppState`.

use crate::capture::win_enum::list_monitors;
use crate::recording::{Bbox, GrabSource, Recorder};
use crate::state::AppState;
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, State};

#[derive(Debug, Deserialize)]
#[serde(tag = "kind", rename_all = "lowercase")]
pub enum RecordSourceArg {
    All,
    Monitor { index: usize },
    Window { hwnd: i64 },
}

fn resolve_source(arg: RecordSourceArg) -> Result<GrabSource, String> {
    match arg {
        RecordSourceArg::All => Ok(GrabSource::All),
        RecordSourceArg::Window { hwnd } => Ok(GrabSource::Window(hwnd)),
        RecordSourceArg::Monitor { index } => {
            let monitors = list_monitors();
            let rect = monitors
                .get(index)
                .ok_or_else(|| format!("Monitor index {index} out of range"))?;
            Ok(GrabSource::Monitor(Bbox {
                left: rect.left,
                top: rect.top,
                right: rect.right,
                bottom: rect.bottom,
            }))
        }
    }
}

#[tauri::command]
#[allow(clippy::too_many_arguments)]
pub fn start_recording(
    app: AppHandle,
    state: State<AppState>,
    fps: u32,
    video_format: String,
    extra_ffmpeg_args: Vec<String>,
    scale: f64,
    output_path: String,
    source: RecordSourceArg,
    cursor: bool,
) -> Result<(), String> {
    let mut guard = state.recorder.lock().unwrap();
    if guard.is_some() {
        return Err("A recording is already in progress".into());
    }
    let source = resolve_source(source)?;
    let recorder = Recorder::start(
        app,
        fps,
        &video_format,
        &extra_ffmpeg_args,
        scale,
        output_path,
        source,
        cursor,
    )?;
    *guard = Some(recorder);
    Ok(())
}

/// Returns the finished file's path, or `None` if there was nothing
/// recording (already stopped, e.g. by an error) or `discard` removed it.
#[tauri::command]
pub fn stop_recording(state: State<AppState>, discard: bool) -> Result<Option<String>, String> {
    let recorder = state.recorder.lock().unwrap().take();
    let Some(recorder) = recorder else {
        return Ok(None);
    };
    let path = recorder.stop();
    if discard {
        if path.exists() {
            let _ = std::fs::remove_file(&path);
        }
        return Ok(None);
    }
    Ok(Some(path.to_string_lossy().into_owned()))
}

#[tauri::command]
pub fn pause_recording(state: State<AppState>) -> Result<(), String> {
    let guard = state.recorder.lock().unwrap();
    match guard.as_ref() {
        Some(r) => {
            r.pause();
            Ok(())
        }
        None => Err("No recording in progress".into()),
    }
}

#[tauri::command]
pub fn resume_recording(state: State<AppState>) -> Result<(), String> {
    let guard = state.recorder.lock().unwrap();
    match guard.as_ref() {
        Some(r) => {
            r.resume();
            Ok(())
        }
        None => Err("No recording in progress".into()),
    }
}

#[derive(Debug, Serialize)]
pub struct RecordingStatus {
    pub is_recording: bool,
    pub paused: bool,
    pub elapsed_secs: u64,
}

#[tauri::command]
pub fn get_recording_status(state: State<AppState>) -> RecordingStatus {
    let guard = state.recorder.lock().unwrap();
    match guard.as_ref() {
        Some(r) => RecordingStatus {
            is_recording: true,
            paused: r.is_paused(),
            elapsed_secs: r.elapsed_secs(),
        },
        None => RecordingStatus {
            is_recording: false,
            paused: false,
            elapsed_secs: 0,
        },
    }
}

/// Discards whatever is currently recording without a graceful stop - used
/// when the frame thread reports a mid-recording error (source vanished,
/// ffmpeg died), matching `_handle_record_error`'s `stop_recording(discard=True)`.
#[tauri::command]
pub fn discard_recording(state: State<AppState>) -> Result<(), String> {
    let recorder = state.recorder.lock().unwrap().take();
    if let Some(recorder) = recorder {
        let path = recorder.stop();
        if path.exists() {
            let _ = std::fs::remove_file(&path);
        }
    }
    Ok(())
}
