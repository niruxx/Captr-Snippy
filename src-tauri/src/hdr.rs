//! HDR display detection - windows-rs port of hdr.py's DisplayConfig API
//! usage (`QueryDisplayConfig`/`DisplayConfigGetDeviceInfo`, Windows 10
//! 1903+). Neither GDI capture nor DXGI's 8-bit path ever hands back real
//! HDR pixel data (Windows always tone-maps the desktop down to an
//! SDR-referenced blend for both capture paths), so this can't recover
//! true HDR values - it only knows *whether* a capture was taken while a
//! display was in HDR mode, so a corrective heuristic can be applied.

use image::RgbaImage;
use serde::Serialize;

#[derive(Debug, Clone, Copy, Serialize)]
pub struct DisplayColorStatus {
    pub target_id: u32,
    pub supported: bool,
    pub enabled: bool,
}

#[cfg(windows)]
mod windows_impl {
    use super::DisplayColorStatus;
    use windows::Win32::Devices::Display::{
        DisplayConfigGetDeviceInfo, GetDisplayConfigBufferSizes, QueryDisplayConfig,
        DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO, DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO,
        DISPLAYCONFIG_MODE_INFO, DISPLAYCONFIG_PATH_INFO, QDC_ONLY_ACTIVE_PATHS,
    };

    /// Returns `[]` (meaning "unknown", not "no HDR") on pre-1903 Windows
    /// or any API failure - same "best-effort, fail quiet" contract as the
    /// Python version.
    pub fn displays_hdr_status() -> Vec<DisplayColorStatus> {
        unsafe {
            let mut n_paths: u32 = 0;
            let mut n_modes: u32 = 0;
            if GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS, &mut n_paths, &mut n_modes)
                .is_err()
            {
                return Vec::new();
            }
            let mut paths: Vec<DISPLAYCONFIG_PATH_INFO> =
                vec![DISPLAYCONFIG_PATH_INFO::default(); n_paths as usize];
            let mut modes: Vec<DISPLAYCONFIG_MODE_INFO> =
                vec![DISPLAYCONFIG_MODE_INFO::default(); n_modes as usize];
            if QueryDisplayConfig(
                QDC_ONLY_ACTIVE_PATHS,
                &mut n_paths,
                paths.as_mut_ptr(),
                &mut n_modes,
                modes.as_mut_ptr(),
                None,
            )
            .is_err()
            {
                return Vec::new();
            }

            let mut results = Vec::new();
            for path in &paths[..n_paths as usize] {
                let mut info = DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO::default();
                info.header.r#type = DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO;
                info.header.size =
                    std::mem::size_of::<DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO>() as u32;
                info.header.adapterId = path.targetInfo.adapterId;
                info.header.id = path.targetInfo.id;
                if DisplayConfigGetDeviceInfo(&mut info.header as *mut _ as *mut _) == 0 {
                    let flags = info.Anonymous.value;
                    results.push(DisplayColorStatus {
                        target_id: path.targetInfo.id,
                        supported: (flags & 0x1) != 0,
                        enabled: (flags & 0x2) != 0,
                    });
                }
            }
            results
        }
    }
}

#[cfg(windows)]
pub use windows_impl::displays_hdr_status;

/// Left as "unknown" (empty) on every non-Windows platform, Linux
/// included: there's no cross-desktop-environment equivalent of
/// `DisplayConfigGetDeviceInfo` - HDR/color-management state lives behind
/// compositor-specific, still-unstable protocols (e.g. Wayland's
/// `color-management-v1`, GNOME- and KDE-specific D-Bus interfaces) with no
/// shared query surface, so there's nothing generic to port here.
#[cfg(not(windows))]
pub fn displays_hdr_status() -> Vec<DisplayColorStatus> {
    Vec::new()
}

pub fn any_display_hdr_enabled() -> bool {
    displays_hdr_status().iter().any(|s| s.enabled)
}

/// Heuristic brightness/contrast/saturation lift for screenshots taken
/// while a display is in HDR mode - a faithful port of PIL's
/// `ImageEnhance.Brightness/Contrast/Color(...).enhance(factor)` chain
/// (each is a blend between the original and a reference image: black for
/// brightness, the whole image's mean gray level for contrast, each
/// pixel's own luma for saturation), since the `image` crate has no
/// built-in equivalent. Not a physically accurate PQ/HLG tone-map - there's
/// no real HDR pixel data available to tone-map from correctly, since both
/// capture paths this app uses only ever return an 8-bit SDR-referenced
/// blend of the real HDR frame.
pub fn apply_hdr_tone_map(image: &RgbaImage) -> RgbaImage {
    let brightened = enhance(image, 1.18, |_, _, _| 0.0);
    let mean = mean_luma(&brightened);
    let contrasted = enhance(&brightened, 1.08, move |_, _, _| mean);
    enhance(&contrasted, 1.06, luma)
}

fn luma(r: f32, g: f32, b: f32) -> f32 {
    0.299 * r + 0.587 * g + 0.114 * b
}

fn mean_luma(image: &RgbaImage) -> f32 {
    let mut sum = 0f64;
    let mut count = 0f64;
    for p in image.pixels() {
        sum += luma(p[0] as f32, p[1] as f32, p[2] as f32) as f64;
        count += 1.0;
    }
    if count == 0.0 {
        0.0
    } else {
        (sum / count).round() as f32
    }
}

/// `Image.blend(reference, image, factor)` = `reference + factor * (image - reference)`,
/// applied per RGB channel; `reference_fn` computes each channel's blend
/// target from the pixel's own (r, g, b).
fn enhance(image: &RgbaImage, factor: f32, reference_fn: impl Fn(f32, f32, f32) -> f32) -> RgbaImage {
    let mut out = image.clone();
    for p in out.pixels_mut() {
        let (r, g, b) = (p[0] as f32, p[1] as f32, p[2] as f32);
        let reference = reference_fn(r, g, b);
        p[0] = (reference + (r - reference) * factor).round().clamp(0.0, 255.0) as u8;
        p[1] = (reference + (g - reference) * factor).round().clamp(0.0, 255.0) as u8;
        p[2] = (reference + (b - reference) * factor).round().clamp(0.0, 255.0) as u8;
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tone_map_matches_pil_blend_math_on_a_uniform_image() {
        // A perfectly uniform gray image has zero contrast/saturation
        // headroom (every reference value equals the pixel itself), so
        // only the brightness pass should move it: 128 * 1.18 = 151.04 ->
        // rounds to 151. This pins the blend formula and rounding/clamping
        // behavior against hand-computed PIL semantics without needing
        // real HDR display hardware to exercise the full pipeline.
        let image = RgbaImage::from_pixel(4, 4, image::Rgba([128, 128, 128, 255]));
        let result = apply_hdr_tone_map(&image);
        for p in result.pixels() {
            assert_eq!([p[0], p[1], p[2]], [151, 151, 151]);
        }
    }

    #[test]
    fn tone_map_clamps_instead_of_wrapping() {
        // 240 * 1.18 = 283.2, which would wrap to 27 if cast to u8 without
        // the explicit clamp - this pins that the intermediate f32 math is
        // clamped to 255 before narrowing, not truncated/wrapped.
        let image = RgbaImage::from_pixel(2, 2, image::Rgba([240, 240, 240, 255]));
        let result = apply_hdr_tone_map(&image);
        for p in result.pixels() {
            assert_eq!([p[0], p[1], p[2]], [255, 255, 255]);
        }
    }
}
