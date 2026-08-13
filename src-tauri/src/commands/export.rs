//! Image export - a direct port of main_window.py's `_write_image()`. The
//! frontend sends raw RGBA pixels (straight off the canvas via
//! `getImageData`) rather than a pre-encoded blob, so every format is
//! encoded uniformly here - canvas's own `toBlob()` can't produce BMP, and
//! its WebP encoder can't be quality-controlled, so PNG/JPEG/WEBP/BMP all
//! go through the same Rust path for consistency rather than mixing.

use image::codecs::jpeg::JpegEncoder;
use image::{DynamicImage, ImageBuffer, Rgba};
use std::fs::File;
use std::io::BufWriter;

fn to_dynamic_image(width: u32, height: u32, rgba: Vec<u8>) -> Result<DynamicImage, String> {
    let buffer: ImageBuffer<Rgba<u8>, Vec<u8>> =
        ImageBuffer::from_raw(width, height, rgba).ok_or("Pixel buffer size doesn't match width/height")?;
    Ok(DynamicImage::ImageRgba8(buffer))
}

/// Encodes `image` as `format` ("PNG"/"JPEG"/"WEBP"/"BMP") and writes it to
/// `path`. `quality` (40-100) applies to JPEG/WEBP only, matching
/// settings.py's LOSSY_FORMATS.
fn encode_and_write(image: &DynamicImage, format: &str, quality: u8, path: &str) -> Result<(), String> {
    match format {
        "PNG" => image.save_with_format(path, image::ImageFormat::Png).map_err(|e| e.to_string()),
        "BMP" => image.save_with_format(path, image::ImageFormat::Bmp).map_err(|e| e.to_string()),
        "JPEG" => {
            let rgb = image.to_rgb8();
            let file = File::create(path).map_err(|e| e.to_string())?;
            let mut encoder = JpegEncoder::new_with_quality(BufWriter::new(file), quality);
            encoder.encode_image(&rgb).map_err(|e| e.to_string())
        }
        "WEBP" => {
            let rgba = image.to_rgba8();
            let encoder = webp::Encoder::from_rgba(rgba.as_raw(), rgba.width(), rgba.height());
            let encoded = encoder.encode(quality as f32);
            std::fs::write(path, &*encoded).map_err(|e| e.to_string())
        }
        other => Err(format!("Unsupported export format: {other}")),
    }
}

#[tauri::command]
pub fn save_image(
    width: u32,
    height: u32,
    rgba: Vec<u8>,
    format: String,
    quality: u8,
    path: String,
) -> Result<(), String> {
    if let Some(parent) = std::path::Path::new(&path).parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let image = to_dynamic_image(width, height, rgba)?;
    encode_and_write(&image, &format, quality, &path)
}
