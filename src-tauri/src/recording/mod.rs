//! Screen recording - frames are grabbed on a background thread and piped
//! into a bundled ffmpeg sidecar via a genuinely blocking stdin write,
//! which is what gives the pause/resume/backpressure algorithm below its
//! timing guarantees (a full pipe blocks the writer, naturally throttling
//! frame production to what ffmpeg can actually keep up with). This is a
//! near-verbatim port of `recording.py`'s `ScreenRecorder` - spawned with
//! raw `std::process::Command` rather than a plugin's async `Command` API
//! specifically to keep that blocking-write semantics intact.

mod grab;
pub use grab::{Bbox, GrabSource};

use image::{DynamicImage, RgbaImage};
use std::io::Write;
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};
use tauri::{AppHandle, Emitter};

pub const RECORDING_ERROR_EVENT: &str = "recording:error";

/// Codec args per container - mirrors `settings.py`'s `VIDEO_FORMATS` dict
/// (libx264 for the MPEG-4/Matroska/FLV muxers, libvpx for WebM). The
/// frontend owns the file extension (same pattern as image export), so
/// this only returns encoder args.
pub fn video_codec_args(format: &str) -> Option<Vec<String>> {
    let strs = |v: &[&str]| v.iter().map(|s| s.to_string()).collect::<Vec<_>>();
    match format {
        "MP4" | "MKV" | "FLV" => Some(strs(&[
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p",
        ])),
        "WEBM" => Some(strs(&[
            "-c:v", "libvpx", "-deadline", "realtime", "-cpu-used", "8", "-b:v", "6M",
        ])),
        _ => None,
    }
}

/// Resolves the bundled ffmpeg sidecar's path. `tauri-build`'s build.rs
/// integration copies `bundle.externalBin` next to the compiled app binary
/// (stripped of its target-triple suffix) for both `cargo build`/`tauri
/// dev` and the final packaged app, so that's checked first; the raw
/// `src-tauri/binaries/ffmpeg-<target-triple>` path is a dev-only fallback
/// for `cargo run` invoked directly, before that copy step has run.
fn resolve_ffmpeg_path() -> Result<PathBuf, String> {
    let name = format!("ffmpeg{}", std::env::consts::EXE_SUFFIX);
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            let candidate = dir.join(&name);
            if candidate.exists() {
                return Ok(candidate);
            }
        }
    }
    let triple = option_env!("TAURI_ENV_TARGET_TRIPLE").unwrap_or("x86_64-pc-windows-msvc");
    let candidate = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("binaries")
        .join(format!("ffmpeg-{triple}{}", std::env::consts::EXE_SUFFIX));
    if candidate.exists() {
        return Ok(candidate);
    }
    Err("ffmpeg binary not found (expected next to the app executable or in src-tauri/binaries/)"
        .into())
}

/// Pause/resume/elapsed bookkeeping shared between the recording thread and
/// the Tauri command handlers that control it - direct port of
/// `ScreenRecorder`'s `_start_time`/`_paused_elapsed`/`_pause_started`
/// fields and `elapsed()`/`pause()`/`resume()` methods.
struct SharedState {
    paused: AtomicBool,
    stop: AtomicBool,
    start_time: Instant,
    paused_elapsed: Mutex<Duration>,
    pause_started: Mutex<Option<Instant>>,
}

impl SharedState {
    fn new() -> Self {
        SharedState {
            paused: AtomicBool::new(false),
            stop: AtomicBool::new(false),
            start_time: Instant::now(),
            paused_elapsed: Mutex::new(Duration::ZERO),
            pause_started: Mutex::new(None),
        }
    }

    fn elapsed(&self) -> Duration {
        let now = Instant::now();
        let mut paused = *self.paused_elapsed.lock().unwrap();
        if self.paused.load(Ordering::SeqCst) {
            if let Some(started) = *self.pause_started.lock().unwrap() {
                paused += now.saturating_duration_since(started);
            }
        }
        now.saturating_duration_since(self.start_time)
            .saturating_sub(paused)
    }

    fn pause(&self) {
        if !self.paused.swap(true, Ordering::SeqCst) {
            *self.pause_started.lock().unwrap() = Some(Instant::now());
        }
    }

    fn resume(&self) {
        if self.paused.swap(false, Ordering::SeqCst) {
            if let Some(started) = self.pause_started.lock().unwrap().take() {
                *self.paused_elapsed.lock().unwrap() +=
                    Instant::now().saturating_duration_since(started);
            }
        }
    }
}

pub struct Recorder {
    shared: Arc<SharedState>,
    child: Child,
    thread: Option<JoinHandle<()>>,
    pub output_path: PathBuf,
}

impl Recorder {
    #[allow(clippy::too_many_arguments)]
    pub fn start(
        app: AppHandle,
        fps: u32,
        video_format: &str,
        extra_ffmpeg_args: &[String],
        scale: f64,
        output_path: String,
        source: GrabSource,
        cursor: bool,
    ) -> Result<Recorder, String> {
        let (probe, _, _) = grab::grab_frame(&source)?.ok_or("Recording source is not available.")?;

        let scale = if scale > 0.0 && scale < 1.0 { scale } else { 1.0 };
        let (mut w, mut h) = (probe.width(), probe.height());
        if scale != 1.0 {
            w = ((w as f64 * scale).round() as u32).max(2);
            h = ((h as f64 * scale).round() as u32).max(2);
        }
        w -= w % 2; // even dimensions required by yuv420p
        h -= h % 2;
        let size = (w.max(2), h.max(2));

        let mut codec_args = video_codec_args(video_format)
            .ok_or_else(|| format!("Unsupported video format: {video_format}"))?;
        codec_args.extend(extra_ffmpeg_args.iter().cloned());

        if let Some(parent) = std::path::Path::new(&output_path).parent() {
            std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }

        let ffmpeg_path = resolve_ffmpeg_path()?;
        let mut cmd = Command::new(&ffmpeg_path);
        cmd.args([
            "-y",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            &format!("{}x{}", size.0, size.1),
            "-r",
            &fps.to_string(),
            "-i",
            "-",
        ])
        .args(&codec_args)
        .args(["-r", &fps.to_string()])
        .arg(&output_path)
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::null());

        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            cmd.creation_flags(CREATE_NO_WINDOW);
        }

        let mut child = cmd
            .spawn()
            .map_err(|e| format!("Failed to start ffmpeg: {e}"))?;
        let stdin = child
            .stdin
            .take()
            .ok_or("Failed to open ffmpeg's stdin pipe")?;

        let shared = Arc::new(SharedState::new());
        let thread_shared = shared.clone();
        let thread_app = app.clone();
        let thread = thread::spawn(move || {
            run(thread_shared, stdin, source, fps, size, scale, cursor, thread_app);
        });

        Ok(Recorder {
            shared,
            child,
            thread: Some(thread),
            output_path: PathBuf::from(output_path),
        })
    }

    pub fn pause(&self) {
        self.shared.pause();
    }

    pub fn resume(&self) {
        self.shared.resume();
    }

    pub fn is_paused(&self) -> bool {
        self.shared.paused.load(Ordering::SeqCst)
    }

    pub fn elapsed_secs(&self) -> u64 {
        self.shared.elapsed().as_secs()
    }

    /// Consumes the recorder: signals the frame thread to stop, waits for
    /// it to exit (which drops its stdin handle, closing ffmpeg's input
    /// pipe so it can finalize the container), then waits for ffmpeg to
    /// exit - killing it if it hangs, matching `ScreenRecorder.stop()`'s
    /// 20s `_proc.wait(timeout=20)` / `_proc.kill()` fallback.
    pub fn stop(mut self) -> PathBuf {
        self.shared.stop.store(true, Ordering::SeqCst);
        if let Some(handle) = self.thread.take() {
            let _ = handle.join();
        }
        wait_for_exit(&mut self.child, Duration::from_secs(20));
        self.output_path
    }
}

fn wait_for_exit(child: &mut Child, timeout: Duration) {
    let start = Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(_)) => return,
            Ok(None) => {
                if start.elapsed() > timeout {
                    let _ = child.kill();
                    let _ = child.wait();
                    return;
                }
                thread::sleep(Duration::from_millis(50));
            }
            Err(_) => return,
        }
    }
}

/// The frame-production loop, run on a dedicated thread - direct port of
/// `ScreenRecorder._run()`. `target_frames` is recomputed against the
/// *active* (unpaused) elapsed time both before and after the (possibly
/// slow) grab, and every fps-slot up to that target gets a copy of the
/// frame just captured; that's what keeps the encoded timeline's duration
/// tracking real wall-clock recording time even when capture can't keep up
/// with the requested fps, instead of ffmpeg silently compressing a
/// dropped-frame recording into a shorter, sped-up clip.
#[allow(clippy::too_many_arguments)]
fn run(
    shared: Arc<SharedState>,
    mut stdin: ChildStdin,
    source: GrabSource,
    fps: u32,
    size: (u32, u32),
    scale: f64,
    cursor: bool,
    app: AppHandle,
) {
    let interval = 1.0 / fps as f64;
    let mut frames_written: u64 = 0;

    loop {
        if shared.stop.load(Ordering::SeqCst) {
            return;
        }
        if shared.paused.load(Ordering::SeqCst) {
            thread::sleep(Duration::from_millis(20));
            continue;
        }

        let mut target_frames = (shared.elapsed().as_secs_f64() / interval) as u64 + 1;
        if target_frames <= frames_written {
            thread::sleep(Duration::from_secs_f64(interval / 4.0));
            continue;
        }

        let (mut frame, origin_x, origin_y) = match grab::grab_frame(&source) {
            Ok(Some(f)) => f,
            Ok(None) => {
                let _ = app.emit(
                    RECORDING_ERROR_EVENT,
                    "Recording source is no longer available (window closed?).".to_string(),
                );
                return;
            }
            Err(e) => {
                let _ = app.emit(RECORDING_ERROR_EVENT, e);
                return;
            }
        };
        if cursor {
            if let Some(snapshot) = crate::capture::cursor::capture_cursor() {
                crate::capture::cursor::composite_cursor(&mut frame, &snapshot, origin_x, origin_y);
            }
        }
        let fitted = fit_frame(frame, size, scale);
        let rgb_bytes = to_rgb_bytes(&fitted);

        target_frames =
            target_frames.max((shared.elapsed().as_secs_f64() / interval) as u64 + 1);
        while frames_written < target_frames && !shared.stop.load(Ordering::SeqCst) {
            if let Err(e) = stdin.write_all(&rgb_bytes) {
                let _ = app.emit(RECORDING_ERROR_EVENT, e.to_string());
                return;
            }
            frames_written += 1;
        }
    }
}

/// `record_scale` downsamples every frame to a fixed target size regardless
/// of small native-size wobble (absorbing e.g. a resized recorded window
/// for free); without scaling, a source whose size drifted from the
/// recording's fixed frame size (a resized window) is padded onto a
/// black canvas instead, so the raw-frame pipe's fixed-size contract with
/// ffmpeg never breaks.
fn fit_frame(frame: RgbaImage, size: (u32, u32), scale: f64) -> RgbaImage {
    if scale != 1.0 {
        image::imageops::resize(&frame, size.0, size.1, image::imageops::FilterType::Triangle)
    } else if frame.width() != size.0 || frame.height() != size.1 {
        let mut canvas = RgbaImage::from_pixel(size.0, size.1, image::Rgba([0, 0, 0, 255]));
        image::imageops::overlay(&mut canvas, &frame, 0, 0);
        canvas
    } else {
        frame
    }
}

fn to_rgb_bytes(frame: &RgbaImage) -> Vec<u8> {
    DynamicImage::ImageRgba8(frame.clone()).to_rgb8().into_raw()
}
