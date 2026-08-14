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

/// HDR detection via the `color-management-v1` Wayland protocol - the
/// emerging cross-desktop standard for querying an output's color state,
/// supported by recent KDE (KWin) and GNOME (Mutter). Each `wl_output`'s
/// current image description is fetched and its transfer function checked
/// against the two named HDR curves (`st2084_pq` = HDR10/PQ, `hlg` = Hybrid
/// Log-Gamma); anything else (`srgb`, `bt1886`, etc.) means that output is
/// in SDR mode. `supported: false` only means the compositor answered but
/// its image description had no queryable info - not "no HDR".
///
/// This has no X11 equivalent (X11 predates HDR and has no color-state
/// protocol at all), and it's a no-op on any compositor that doesn't
/// advertise the protocol yet - both cases just return `[]`, same
/// "unknown, not no-HDR" contract as the Windows pre-1903 fallback.
#[cfg(target_os = "linux")]
mod linux_impl {
    use super::DisplayColorStatus;
    use std::collections::HashMap;
    use wayland_client::{
        delegate_noop,
        protocol::{wl_output::WlOutput, wl_registry},
        Connection, Dispatch, EventQueue, Proxy, QueueHandle,
    };
    use wayland_protocols::wp::color_management::v1::client::{
        wp_color_management_output_v1::WpColorManagementOutputV1,
        wp_color_manager_v1::{self, WpColorManagerV1},
        wp_image_description_info_v1::{self, WpImageDescriptionInfoV1},
        wp_image_description_v1::{self, WpImageDescriptionV1},
    };

    struct State {
        color_manager: Option<WpColorManagerV1>,
        outputs: Vec<(u32, WlOutput)>,
        results: Vec<DisplayColorStatus>,
        /// Whether an in-flight image description's `tf_named` event
        /// reported an HDR transfer function, keyed by the
        /// `wp_image_description_info_v1` object id.
        hdr_seen: HashMap<u32, bool>,
    }

    impl Dispatch<wl_registry::WlRegistry, ()> for State {
        fn event(
            state: &mut Self,
            registry: &wl_registry::WlRegistry,
            event: wl_registry::Event,
            _data: &(),
            _conn: &Connection,
            qh: &QueueHandle<Self>,
        ) {
            let wl_registry::Event::Global { name, interface, version } = event else {
                return;
            };
            match interface.as_str() {
                "wp_color_manager_v1" => {
                    state.color_manager =
                        Some(registry.bind::<WpColorManagerV1, _, _>(name, version.min(1), qh, ()));
                }
                "wl_output" => {
                    let output = registry.bind::<WlOutput, _, _>(name, version.min(4), qh, ());
                    state.outputs.push((name, output));
                }
                _ => {}
            }
        }
    }

    delegate_noop!(State: ignore WlOutput);
    delegate_noop!(State: ignore WpColorManagerV1);
    delegate_noop!(State: ignore WpColorManagementOutputV1);

    /// User data is the owning output's registry name, threaded through so
    /// the final result can be attributed to the right `target_id`.
    impl Dispatch<WpImageDescriptionV1, u32> for State {
        fn event(
            state: &mut Self,
            image_description: &WpImageDescriptionV1,
            event: wp_image_description_v1::Event,
            output_name: &u32,
            _conn: &Connection,
            qh: &QueueHandle<Self>,
        ) {
            match event {
                wp_image_description_v1::Event::Ready { .. } => {
                    image_description.get_information(qh, *output_name);
                }
                wp_image_description_v1::Event::Failed { .. } => {
                    state.results.push(DisplayColorStatus {
                        target_id: *output_name,
                        supported: false,
                        enabled: false,
                    });
                }
                _ => {}
            }
        }
    }

    impl Dispatch<WpImageDescriptionInfoV1, u32> for State {
        fn event(
            state: &mut Self,
            info: &WpImageDescriptionInfoV1,
            event: wp_image_description_info_v1::Event,
            output_name: &u32,
            _conn: &Connection,
            _qh: &QueueHandle<Self>,
        ) {
            match event {
                wp_image_description_info_v1::Event::TfNamed { tf } => {
                    let is_hdr = matches!(
                        tf.into_result(),
                        Ok(wp_color_manager_v1::TransferFunction::St2084Pq)
                            | Ok(wp_color_manager_v1::TransferFunction::Hlg)
                    );
                    if is_hdr {
                        state.hdr_seen.insert(info.id().protocol_id(), true);
                    }
                }
                wp_image_description_info_v1::Event::Done => {
                    let enabled = state.hdr_seen.remove(&info.id().protocol_id()).unwrap_or(false);
                    state.results.push(DisplayColorStatus {
                        target_id: *output_name,
                        supported: true,
                        enabled,
                    });
                }
                _ => {}
            }
        }
    }

    pub fn displays_hdr_status() -> Vec<DisplayColorStatus> {
        let Ok(conn) = Connection::connect_to_env() else {
            return Vec::new();
        };
        let mut event_queue: EventQueue<State> = conn.new_event_queue();
        let qh = event_queue.handle();
        conn.display().get_registry(&qh, ());

        let mut state = State {
            color_manager: None,
            outputs: Vec::new(),
            results: Vec::new(),
            hdr_seen: HashMap::new(),
        };

        // One round-trip is enough for every `global` advertisement
        // (color manager + outputs) to arrive.
        if event_queue.roundtrip(&mut state).is_err() {
            return Vec::new();
        }

        let (Some(color_manager), false) = (state.color_manager.clone(), state.outputs.is_empty())
        else {
            return Vec::new();
        };

        let expected = state.outputs.len();
        for (name, output) in state.outputs.clone() {
            let cmo = color_manager.get_output(&output, &qh, ());
            cmo.get_image_description(&qh, name);
        }

        // Each output's chain (get_image_description -> ready ->
        // get_information -> tf_named* -> done) needs its own round-trip
        // to fully resolve; this loop just bounds how long we wait.
        for _ in 0..expected + 4 {
            if state.results.len() >= expected {
                break;
            }
            if event_queue.roundtrip(&mut state).is_err() {
                break;
            }
        }

        state.results
    }
}

#[cfg(target_os = "linux")]
pub use linux_impl::displays_hdr_status;

/// Left as "unknown" (empty) on every other non-Windows platform: there's
/// no cross-desktop-environment equivalent of `DisplayConfigGetDeviceInfo`,
/// and macOS/other targets aren't covered by the Wayland protocol path
/// above.
#[cfg(not(any(windows, target_os = "linux")))]
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
