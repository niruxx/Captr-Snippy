//! Monitor/window enumeration and virtual-desktop bounds, ported near-
//! verbatim from capture.py's ctypes calls (same predicate, so the "record
//! a window" picker and multi-monitor math behave identically to the
//! Python build) - windows-rs just gives typed bindings instead of
//! hand-defined `ctypes.Structure`s. On Linux this is backed by `xcap`
//! (already a dependency for pixel capture), which talks to X11/XWayland
//! directly - so native-Wayland-only windows (no XWayland surface) won't
//! be listed, a protocol-level limitation Wayland imposes on every app,
//! not something fixable in userspace. Elsewhere (e.g. macOS) these still
//! return empty/None.

use serde::Serialize;

#[derive(Debug, Clone, Copy, Serialize)]
pub struct MonitorRect {
    pub left: i32,
    pub top: i32,
    pub right: i32,
    pub bottom: i32,
    pub is_primary: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct WindowEntry {
    /// The HWND, widened to i64 so it round-trips through JSON/JS numbers
    /// without precision loss (HWNDs are pointer-sized).
    pub hwnd: i64,
    pub title: String,
}

#[derive(Debug, Clone, Copy, Serialize)]
pub struct VirtualScreen {
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
}

#[cfg(windows)]
mod windows_impl {
    use super::{MonitorRect, VirtualScreen, WindowEntry};
    use windows::Win32::Foundation::{HWND, LPARAM, RECT, TRUE};
    use windows::Win32::Graphics::Gdi::{EnumDisplayMonitors, GetMonitorInfoW, HDC, HMONITOR, MONITORINFO};
    use windows::Win32::UI::WindowsAndMessaging::{
        EnumWindows, GetSystemMetrics, GetWindowRect, GetWindowTextLengthW, GetWindowTextW,
        IsIconic, IsWindow, IsWindowVisible, MONITORINFOF_PRIMARY, SM_CXVIRTUALSCREEN,
        SM_CYVIRTUALSCREEN, SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN,
    };
    use windows::core::BOOL;

    pub fn virtual_screen() -> Option<VirtualScreen> {
        unsafe {
            Some(VirtualScreen {
                x: GetSystemMetrics(SM_XVIRTUALSCREEN),
                y: GetSystemMetrics(SM_YVIRTUALSCREEN),
                width: GetSystemMetrics(SM_CXVIRTUALSCREEN),
                height: GetSystemMetrics(SM_CYVIRTUALSCREEN),
            })
        }
    }

    pub fn list_monitors() -> Vec<MonitorRect> {
        let mut monitors: Vec<MonitorRect> = Vec::new();

        unsafe extern "system" fn callback(
            hmonitor: HMONITOR,
            _hdc: HDC,
            _rect: *mut RECT,
            data: LPARAM,
        ) -> BOOL {
            let monitors = unsafe { &mut *(data.0 as *mut Vec<MonitorRect>) };
            let mut info = MONITORINFO {
                cbSize: std::mem::size_of::<MONITORINFO>() as u32,
                ..Default::default()
            };
            if unsafe { GetMonitorInfoW(hmonitor, &mut info) }.as_bool() {
                let r = info.rcMonitor;
                monitors.push(MonitorRect {
                    left: r.left,
                    top: r.top,
                    right: r.right,
                    bottom: r.bottom,
                    is_primary: (info.dwFlags & MONITORINFOF_PRIMARY) != 0,
                });
            }
            TRUE
        }

        unsafe {
            let _ = EnumDisplayMonitors(
                None,
                None,
                Some(callback),
                LPARAM(&mut monitors as *mut _ as isize),
            );
        }
        monitors
    }

    pub fn list_windows() -> Vec<WindowEntry> {
        let mut windows: Vec<WindowEntry> = Vec::new();

        unsafe extern "system" fn callback(hwnd: HWND, data: LPARAM) -> BOOL {
            let windows = unsafe { &mut *(data.0 as *mut Vec<WindowEntry>) };
            unsafe {
                if !IsWindowVisible(hwnd).as_bool() || IsIconic(hwnd).as_bool() {
                    return TRUE;
                }
                let length = GetWindowTextLengthW(hwnd);
                if length == 0 {
                    return TRUE;
                }
                let mut buf = vec![0u16; (length + 1) as usize];
                let copied = GetWindowTextW(hwnd, &mut buf);
                if copied == 0 {
                    return TRUE;
                }
                let title = String::from_utf16_lossy(&buf[..copied as usize]);
                if !title.is_empty() && title != "Snippy" {
                    windows.push(WindowEntry {
                        hwnd: hwnd.0 as i64,
                        title,
                    });
                }
            }
            TRUE
        }

        unsafe {
            let _ = EnumWindows(Some(callback), LPARAM(&mut windows as *mut _ as isize));
        }
        windows
    }

    /// Live bounding box of a still-capturable window, re-queried every
    /// recording frame so the "record a window" source follows it if it
    /// moves/resizes - mirrors recording's per-frame `GetWindowRect` +
    /// `IsWindow`/`IsIconic` validity check in the Python build. `None`
    /// means the window closed or got minimized (the caller treats that as
    /// "recording source no longer available").
    pub fn window_rect_if_capturable(hwnd: i64) -> Option<(i32, i32, i32, i32)> {
        unsafe {
            let hwnd = HWND(hwnd as *mut core::ffi::c_void);
            if !IsWindow(Some(hwnd)).as_bool() || IsIconic(hwnd).as_bool() {
                return None;
            }
            let mut rect = RECT::default();
            if GetWindowRect(hwnd, &mut rect).is_err() {
                return None;
            }
            if rect.right <= rect.left || rect.bottom <= rect.top {
                return None;
            }
            Some((rect.left, rect.top, rect.right, rect.bottom))
        }
    }
}

#[cfg(windows)]
pub use windows_impl::{list_monitors, list_windows, virtual_screen, window_rect_if_capturable};

#[cfg(target_os = "linux")]
mod linux_impl {
    use super::{MonitorRect, VirtualScreen, WindowEntry};
    use xcap::{Monitor, Window};

    pub fn virtual_screen() -> Option<VirtualScreen> {
        let monitors = list_monitors();
        if monitors.is_empty() {
            return None;
        }
        let left = monitors.iter().map(|m| m.left).min()?;
        let top = monitors.iter().map(|m| m.top).min()?;
        let right = monitors.iter().map(|m| m.right).max()?;
        let bottom = monitors.iter().map(|m| m.bottom).max()?;
        Some(VirtualScreen {
            x: left,
            y: top,
            width: (right - left).max(0),
            height: (bottom - top).max(0),
        })
    }

    pub fn list_monitors() -> Vec<MonitorRect> {
        let Ok(monitors) = Monitor::all() else {
            return Vec::new();
        };
        monitors
            .iter()
            .filter_map(|monitor| {
                let x = monitor.x().ok()?;
                let y = monitor.y().ok()?;
                let width = monitor.width().ok()? as i32;
                let height = monitor.height().ok()? as i32;
                let is_primary = monitor.is_primary().unwrap_or(false);
                Some(MonitorRect {
                    left: x,
                    top: y,
                    right: x + width,
                    bottom: y + height,
                    is_primary,
                })
            })
            .collect()
    }

    /// `xcap::Window::all()` enumerates X11/XWayland clients, so windows
    /// belonging to a native-Wayland toolkit backend (no XWayland surface)
    /// won't appear here - Wayland deliberately gives no app permission to
    /// list other clients' windows, so there's no userspace fix for that
    /// gap short of a compositor-mediated portal picker.
    pub fn list_windows() -> Vec<WindowEntry> {
        let Ok(windows) = Window::all() else {
            return Vec::new();
        };
        windows
            .iter()
            .filter_map(|window| {
                if window.is_minimized().unwrap_or(false) {
                    return None;
                }
                let title = window.title().ok()?;
                if title.is_empty() || title == "Snippy" {
                    return None;
                }
                let id = window.id().ok()?;
                Some(WindowEntry {
                    hwnd: id as i64,
                    title,
                })
            })
            .collect()
    }

    /// Re-enumerates every frame (xcap has no cheaper single-window
    /// lookup-by-id), mirroring the Windows build's per-frame
    /// `GetWindowRect`/`IsWindow` validity check.
    pub fn window_rect_if_capturable(hwnd: i64) -> Option<(i32, i32, i32, i32)> {
        let windows = Window::all().ok()?;
        let window = windows
            .iter()
            .find(|window| window.id().ok().map(|id| id as i64) == Some(hwnd))?;
        if window.is_minimized().unwrap_or(false) {
            return None;
        }
        let x = window.x().ok()?;
        let y = window.y().ok()?;
        let width = window.width().ok()? as i32;
        let height = window.height().ok()? as i32;
        if width <= 0 || height <= 0 {
            return None;
        }
        Some((x, y, x + width, y + height))
    }
}

#[cfg(target_os = "linux")]
pub use linux_impl::{list_monitors, list_windows, virtual_screen, window_rect_if_capturable};

#[cfg(not(any(windows, target_os = "linux")))]
pub fn virtual_screen() -> Option<VirtualScreen> {
    None
}

#[cfg(not(any(windows, target_os = "linux")))]
pub fn list_monitors() -> Vec<MonitorRect> {
    Vec::new()
}

#[cfg(not(any(windows, target_os = "linux")))]
pub fn list_windows() -> Vec<WindowEntry> {
    Vec::new()
}

#[cfg(not(any(windows, target_os = "linux")))]
pub fn window_rect_if_capturable(_hwnd: i64) -> Option<(i32, i32, i32, i32)> {
    None
}
