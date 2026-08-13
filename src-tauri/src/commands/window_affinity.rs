//! `SetWindowDisplayAffinity` - the one Win32 integration Tauri's window
//! APIs don't cover, ported from `win_integration.py::exclude_from_capture`.
//! Hides a top-level window from screen-capture APIs (Windows 10 2004+) so
//! the floating recording-control bar never ends up baked into the
//! recording it controls.

use tauri::{AppHandle, Manager};

#[tauri::command]
pub fn exclude_window_from_capture(app: AppHandle, label: String) -> Result<(), String> {
    let window = app
        .get_webview_window(&label)
        .ok_or_else(|| format!("No window with label {label}"))?;

    #[cfg(windows)]
    {
        use windows::Win32::UI::WindowsAndMessaging::{
            SetWindowDisplayAffinity, WDA_EXCLUDEFROMCAPTURE,
        };
        let hwnd = window.hwnd().map_err(|e| e.to_string())?;
        unsafe {
            SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE).map_err(|e| e.to_string())?;
        }
    }
    #[cfg(not(windows))]
    {
        let _ = window;
    }

    Ok(())
}
