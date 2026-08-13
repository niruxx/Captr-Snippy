use crate::capture::{grabber, win_enum};
use crate::hdr;
use image::RgbaImage;
use serde::Serialize;
use tauri::AppHandle;

#[derive(Serialize)]
pub struct CapturedImage {
    pub width: u32,
    pub height: u32,
    /// A `data:image/png;base64,...` URL - directly usable as an `<img>`
    /// src, which the annotation canvas draws from (see the annotation-
    /// engine milestone).
    pub data_url: String,
}

/// Applies the HDR tone-map heuristic to a freshly-taken capture when the
/// setting is on and a display is currently in HDR mode - direct port of
/// `CaptureState.add_capture()`'s `if settings.get("hdr_tone_map") and
/// any_display_hdr_enabled():` gate.
fn maybe_tone_map(app: &AppHandle, image: RgbaImage) -> RgbaImage {
    let settings = crate::commands::settings::load_settings(app);
    if settings.hdr_tone_map && hdr::any_display_hdr_enabled() {
        hdr::apply_hdr_tone_map(&image)
    } else {
        image
    }
}

#[tauri::command]
pub fn capture_fullscreen(app: AppHandle) -> Result<CapturedImage, String> {
    let (image, _origin_x, _origin_y) = grabber::capture_virtual_desktop()?;
    let image = maybe_tone_map(&app, image);
    let data_url = grabber::image_to_png_data_url(&image)?;
    Ok(CapturedImage { width: image.width(), height: image.height(), data_url })
}

#[tauri::command]
pub fn capture_region(app: AppHandle, x1: i32, y1: i32, x2: i32, y2: i32) -> Result<CapturedImage, String> {
    let image = grabber::capture_region(x1, y1, x2, y2)?;
    let image = maybe_tone_map(&app, image);
    let data_url = grabber::image_to_png_data_url(&image)?;
    Ok(CapturedImage { width: image.width(), height: image.height(), data_url })
}

#[tauri::command]
pub fn get_hdr_status() -> Vec<hdr::DisplayColorStatus> {
    hdr::displays_hdr_status()
}

#[tauri::command]
pub fn get_virtual_screen() -> Option<win_enum::VirtualScreen> {
    win_enum::virtual_screen()
}

#[tauri::command]
pub fn get_monitors() -> Vec<win_enum::MonitorRect> {
    win_enum::list_monitors()
}

#[tauri::command]
pub fn get_windows() -> Vec<win_enum::WindowEntry> {
    win_enum::list_windows()
}
