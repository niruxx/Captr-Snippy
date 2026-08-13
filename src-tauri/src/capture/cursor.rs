//! Live mouse cursor capture, for compositing onto recording frames -
//! xcap's `Monitor::capture_image()` never includes the cursor, so this
//! grabs it separately via the same `GetCursorInfo`/`GetIconInfo`/
//! `DrawIconEx` sequence most Windows screen recorders use, and returns a
//! small RGBA bitmap already positioned (hotspot-adjusted) in screen
//! coordinates for the caller to `image::imageops::overlay` onto a frame.

use image::RgbaImage;

pub struct CursorSnapshot {
    /// Top-left corner to draw `image` at, in the same virtual-desktop
    /// coordinate space `capture_virtual_desktop()`'s origin uses - already
    /// adjusted for the cursor's hotspot, so callers just subtract the
    /// frame's own capture origin and overlay.
    pub x: i32,
    pub y: i32,
    pub image: RgbaImage,
}

#[cfg(windows)]
mod windows_impl {
    use super::CursorSnapshot;
    use image::RgbaImage;
    use windows::Win32::Graphics::Gdi::{
        CreateCompatibleDC, CreateDIBSection, DeleteDC, DeleteObject, GetDC, GetObjectW,
        ReleaseDC, SelectObject, BITMAP, BITMAPINFO, BITMAPINFOHEADER, BI_RGB, DIB_RGB_COLORS,
        HGDIOBJ,
    };
    use windows::Win32::UI::WindowsAndMessaging::{
        DrawIconEx, GetCursorInfo, GetIconInfo, CURSORINFO, CURSOR_SHOWING, DI_NORMAL, ICONINFO,
    };

    pub fn capture_cursor() -> Option<CursorSnapshot> {
        unsafe {
            let mut info = CURSORINFO {
                cbSize: std::mem::size_of::<CURSORINFO>() as u32,
                ..Default::default()
            };
            if GetCursorInfo(&mut info).is_err() || info.flags != CURSOR_SHOWING {
                return None;
            }

            let mut icon_info = ICONINFO::default();
            if GetIconInfo(info.hCursor.into(), &mut icon_info).is_err() {
                return None;
            }
            // Always owned by us now regardless of what happens below - make
            // sure both get freed on every exit path.
            let cleanup_bitmaps = |ii: &ICONINFO| {
                if !ii.hbmColor.is_invalid() {
                    let _ = DeleteObject(ii.hbmColor.into());
                }
                if !ii.hbmMask.is_invalid() {
                    let _ = DeleteObject(ii.hbmMask.into());
                }
            };

            let measure_from = if !icon_info.hbmColor.is_invalid() {
                icon_info.hbmColor
            } else {
                icon_info.hbmMask
            };
            let mut bmp = BITMAP::default();
            let written = GetObjectW(
                HGDIOBJ(measure_from.0),
                std::mem::size_of::<BITMAP>() as i32,
                Some(&mut bmp as *mut _ as *mut _),
            );
            if written == 0 {
                cleanup_bitmaps(&icon_info);
                return None;
            }
            // A monochrome cursor (no color bitmap) packs AND+XOR masks
            // stacked in one bitmap, so its real height is half of what
            // GetObject reports.
            let height = if icon_info.hbmColor.is_invalid() {
                bmp.bmHeight / 2
            } else {
                bmp.bmHeight
            };
            let (w, h) = (bmp.bmWidth, height);
            if w <= 0 || h <= 0 {
                cleanup_bitmaps(&icon_info);
                return None;
            }

            let screen_dc = GetDC(None);
            let mem_dc = CreateCompatibleDC(Some(screen_dc));

            let mut bmi = BITMAPINFO::default();
            bmi.bmiHeader.biSize = std::mem::size_of::<BITMAPINFOHEADER>() as u32;
            bmi.bmiHeader.biWidth = w;
            bmi.bmiHeader.biHeight = -h; // negative = top-down DIB
            bmi.bmiHeader.biPlanes = 1;
            bmi.bmiHeader.biBitCount = 32;
            bmi.bmiHeader.biCompression = BI_RGB.0 as u32;

            let mut bits_ptr: *mut core::ffi::c_void = std::ptr::null_mut();
            let Ok(dib) = CreateDIBSection(Some(mem_dc), &bmi, DIB_RGB_COLORS, &mut bits_ptr, None, 0)
            else {
                let _ = DeleteDC(mem_dc);
                ReleaseDC(None, screen_dc);
                cleanup_bitmaps(&icon_info);
                return None;
            };
            let old = SelectObject(mem_dc, dib.into());

            // DrawIconEx paints straight onto the (zero-initialized, fully
            // transparent) DIB - real ARGB cursors keep their alpha
            // channel; legacy mask-only cursors come out fully opaque
            // wherever their AND mask says "draw", which is good enough
            // (no worse than what every other lightweight screen recorder
            // does for the rare non-alpha cursor).
            let _ = DrawIconEx(mem_dc, 0, 0, info.hCursor.into(), w, h, 0, None, DI_NORMAL);

            let pixel_count = (w * h) as usize;
            let mut rgba = vec![0u8; pixel_count * 4];
            if !bits_ptr.is_null() {
                let src = std::slice::from_raw_parts(bits_ptr as *const u8, pixel_count * 4);
                for i in 0..pixel_count {
                    let (b, g, r, a) = (src[i * 4], src[i * 4 + 1], src[i * 4 + 2], src[i * 4 + 3]);
                    rgba[i * 4] = r;
                    rgba[i * 4 + 1] = g;
                    rgba[i * 4 + 2] = b;
                    rgba[i * 4 + 3] = a;
                }
            }

            SelectObject(mem_dc, old);
            let _ = DeleteObject(dib.into());
            let _ = DeleteDC(mem_dc);
            ReleaseDC(None, screen_dc);
            cleanup_bitmaps(&icon_info);

            let image = RgbaImage::from_raw(w as u32, h as u32, rgba)?;
            Some(CursorSnapshot {
                x: info.ptScreenPos.x - icon_info.xHotspot as i32,
                y: info.ptScreenPos.y - icon_info.yHotspot as i32,
                image,
            })
        }
    }
}

#[cfg(windows)]
pub use windows_impl::capture_cursor;

#[cfg(not(windows))]
pub fn capture_cursor() -> Option<CursorSnapshot> {
    None
}

/// Draws `cursor` onto `frame`, where `frame`'s top-left pixel corresponds
/// to `(origin_x, origin_y)` in the same screen-coordinate space the cursor
/// snapshot uses - `image::imageops::overlay` clips automatically if the
/// cursor is partially or fully outside `frame`'s bounds (e.g. near the
/// edge of a cropped monitor/window recording).
pub fn composite_cursor(frame: &mut RgbaImage, cursor: &CursorSnapshot, origin_x: i32, origin_y: i32) {
    image::imageops::overlay(
        frame,
        &cursor.image,
        (cursor.x - origin_x) as i64,
        (cursor.y - origin_y) as i64,
    );
}
