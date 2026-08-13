//! Per-frame pixel grabbing for the three recording sources. All three
//! route through the same full-virtual-desktop capture + optional bbox
//! crop the Python build's `DesktopGrabber.grab(bbox=...)` used, so
//! `record_source`'s "all"/"monitor:N"/"window" cases share one code path
//! here too - "monitor" and "window" just supply a bbox, "window"'s bbox is
//! re-queried every frame so the capture follows the window if it moves or
//! resizes.

use crate::capture::grabber::{capture_region, capture_virtual_desktop};
use crate::capture::win_enum::window_rect_if_capturable;
use image::RgbaImage;

#[derive(Debug, Clone, Copy)]
pub struct Bbox {
    pub left: i32,
    pub top: i32,
    pub right: i32,
    pub bottom: i32,
}

#[derive(Debug, Clone, Copy)]
pub enum GrabSource {
    All,
    /// Bbox resolved once at recording start (matches the Python build,
    /// which reads `self._monitors` at start_recording() time rather than
    /// re-enumerating monitors every frame).
    Monitor(Bbox),
    /// Re-queries `GetWindowRect` every frame via `hwnd`.
    Window(i64),
}

/// `Ok(None)` means the source is gone (window closed/minimized) - the
/// caller treats that exactly like Python's `if frame is None: on_error(...)`.
/// Returns the frame's own top-left corner in virtual-desktop coordinates
/// alongside it, so a live cursor snapshot (also in that same coordinate
/// space) can be composited at the right offset regardless of which source
/// mode cropped the frame.
pub fn grab_frame(source: &GrabSource) -> Result<Option<(RgbaImage, i32, i32)>, String> {
    match source {
        GrabSource::All => capture_virtual_desktop().map(|(image, x, y)| Some((image, x, y))),
        GrabSource::Monitor(bbox) => {
            capture_region(bbox.left, bbox.top, bbox.right, bbox.bottom)
                .map(|image| Some((image, bbox.left, bbox.top)))
        }
        GrabSource::Window(hwnd) => match window_rect_if_capturable(*hwnd) {
            None => Ok(None),
            Some((left, top, right, bottom)) => {
                capture_region(left, top, right, bottom).map(|image| Some((image, left, top)))
            }
        },
    }
}
