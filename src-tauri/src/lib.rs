mod capture;
mod commands;
mod hdr;
mod recording;
mod state;

use commands::{
    capture as capture_cmds, export, recording as recording_cmds, settings, window_affinity,
};
use state::AppState;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{Emitter, Manager};
use tauri_plugin_global_shortcut::{Code, Modifiers, Shortcut, ShortcutState};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Ctrl+Alt+R starts/stops recording, Ctrl+Alt+P pauses/resumes - same
    // bindings as settings.py's RECORD_HOTKEY_VK/PAUSE_HOTKEY_VK, registered
    // as real OS-level global shortcuts (work while the app isn't focused)
    // instead of hotkeys.py's dedicated Win32-message-loop thread.
    let record_shortcut = Shortcut::new(Some(Modifiers::CONTROL | Modifiers::ALT), Code::KeyR);
    let pause_shortcut = Shortcut::new(Some(Modifiers::CONTROL | Modifiers::ALT), Code::KeyP);
    let handler_record_shortcut = record_shortcut;
    let handler_pause_shortcut = pause_shortcut;

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            None,
        ))
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(move |app, shortcut, event| {
                    if event.state != ShortcutState::Pressed {
                        return;
                    }
                    // Starting a recording needs current settings + (for
                    // the "window" source) the in-app window-picker modal,
                    // both of which live in the frontend - so, like the
                    // UI's own Record/Pause buttons, the hotkey just tells
                    // the frontend to run the same toggle logic rather than
                    // duplicating it here.
                    if shortcut == &handler_record_shortcut {
                        let _ = app.emit("hotkey:record-toggle", ());
                    } else if shortcut == &handler_pause_shortcut {
                        let _ = app.emit("hotkey:pause-toggle", ());
                    }
                })
                .build(),
        )
        .manage(AppState::default())
        .setup(move |app| {
            use tauri_plugin_global_shortcut::GlobalShortcutExt;
            // Registration failure (hotkey already owned by another app) is
            // surfaced to the frontend as a toast rather than failing setup.
            let shortcuts = app.global_shortcut();
            if let Err(e) = shortcuts.register(record_shortcut) {
                let _ = app.emit("hotkey:register-failed", format!("Ctrl+Alt+R: {e}"));
            }
            if let Err(e) = shortcuts.register(pause_shortcut) {
                let _ = app.emit("hotkey:register-failed", format!("Ctrl+Alt+P: {e}"));
            }

            // Lets "minimize to tray instead of closing" (a Settings →
            // General toggle) keep the app - and its global hotkeys - alive
            // with no window open; WindowFrame.tsx's close handler hides
            // rather than closes when that setting is on, and this is what
            // gets the window back (or exits for real via "Quit").
            let show_item = MenuItem::with_id(app, "show", "Show Captr", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let tray_menu = Menu::with_items(app, &[&show_item, &quit_item])?;

            let show_main = |app: &tauri::AppHandle| {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            };

            TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .tooltip("Captr")
                .menu(&tray_menu)
                .show_menu_on_left_click(false)
                .on_menu_event(move |app, event| match event.id.as_ref() {
                    "show" => show_main(app),
                    "quit" => app.exit(0),
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                })
                .build(app)?;

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            settings::get_settings,
            settings::save_settings,
            capture_cmds::capture_fullscreen,
            capture_cmds::capture_region,
            capture_cmds::get_virtual_screen,
            capture_cmds::get_monitors,
            capture_cmds::get_windows,
            capture_cmds::get_hdr_status,
            export::save_image,
            recording_cmds::start_recording,
            recording_cmds::stop_recording,
            recording_cmds::pause_recording,
            recording_cmds::resume_recording,
            recording_cmds::get_recording_status,
            recording_cmds::discard_recording,
            recording_cmds::get_capture_bounds,
            window_affinity::exclude_window_from_capture,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
