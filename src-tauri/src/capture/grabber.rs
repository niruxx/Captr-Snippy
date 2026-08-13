//! Pixel capture via `xcap` - the direct equivalent of `ImageGrab.grab
//! (all_screens=True)` (BitBlt-class capture, same speed tier as the
//! Python build's non-GPU fallback path; GPU-accelerated Desktop
//! Duplication is deferred fast-follow work, not part of this port).

use base64::Engine;
use image::RgbaImage;
use xcap::Monitor;

/// Captures every monitor and composites them into one image in the same
/// virtual-desktop coordinate space `win_enum::virtual_screen()` uses.
/// Returns `(image, origin_x, origin_y)` - the origin is needed to map
/// global screen coordinates (e.g. a drag-selected region) onto pixels in
/// the returned image.
pub fn capture_virtual_desktop() -> Result<(RgbaImage, i32, i32), String> {
    let monitors = Monitor::all().map_err(|e| e.to_string())?;
    if monitors.is_empty() {
        return Err("No monitors found".into());
    }

    let mut frames = Vec::with_capacity(monitors.len());
    let (mut min_x, mut min_y) = (i32::MAX, i32::MAX);
    let (mut max_x, mut max_y) = (i32::MIN, i32::MIN);
    for monitor in &monitors {
        let x = monitor.x().map_err(|e| e.to_string())?;
        let y = monitor.y().map_err(|e| e.to_string())?;
        let image = monitor.capture_image().map_err(|e| e.to_string())?;
        min_x = min_x.min(x);
        min_y = min_y.min(y);
        max_x = max_x.max(x + image.width() as i32);
        max_y = max_y.max(y + image.height() as i32);
        frames.push((x, y, image));
    }

    let width = (max_x - min_x).max(1) as u32;
    let height = (max_y - min_y).max(1) as u32;
    let mut canvas = RgbaImage::new(width, height);
    for (x, y, image) in frames {
        image::imageops::overlay(&mut canvas, &image, (x - min_x) as i64, (y - min_y) as i64);
    }

    Ok((canvas, min_x, min_y))
}

/// Crops a full virtual-desktop capture to the (global-coordinate) region
/// between the two points, in either drag direction - mirrors
/// `annotation.sorted_box()` + `PIL.Image.crop()` in the Python build.
pub fn capture_region(x1: i32, y1: i32, x2: i32, y2: i32) -> Result<RgbaImage, String> {
    let (desktop, origin_x, origin_y) = capture_virtual_desktop()?;
    let left = x1.min(x2);
    let top = y1.min(y2);
    let right = x1.max(x2);
    let bottom = y1.max(y2);

    let crop_x = (left - origin_x).clamp(0, desktop.width() as i32) as u32;
    let crop_y = (top - origin_y).clamp(0, desktop.height() as i32) as u32;
    let crop_right = (right - origin_x).clamp(0, desktop.width() as i32) as u32;
    let crop_bottom = (bottom - origin_y).clamp(0, desktop.height() as i32) as u32;

    let crop_w = crop_right.saturating_sub(crop_x).max(1);
    let crop_h = crop_bottom.saturating_sub(crop_y).max(1);

    Ok(image::imageops::crop_imm(&desktop, crop_x, crop_y, crop_w, crop_h).to_image())
}

pub fn image_to_png_data_url(image: &RgbaImage) -> Result<String, String> {
    let mut bytes: Vec<u8> = Vec::new();
    image::DynamicImage::ImageRgba8(image.clone())
        .write_to(&mut std::io::Cursor::new(&mut bytes), image::ImageFormat::Png)
        .map_err(|e| e.to_string())?;
    let encoded = base64::engine::general_purpose::STANDARD.encode(&bytes);
    Ok(format!("data:image/png;base64,{encoded}"))
}
