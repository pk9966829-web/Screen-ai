use tauri::{Manager, PhysicalPosition, PhysicalSize, WebviewWindow};
use tauri_plugin_opener::OpenerExt;

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

/// Open one of VOSI's explicitly supported sites or Windows settings pages.
/// The target is a fixed allow-list so voice input cannot pass arbitrary URLs or commands.
#[tauri::command]
fn open_device_target(app: tauri::AppHandle, target: String) -> Result<(), String> {
    let url = match target.as_str() {
        "youtube" => "https://www.youtube.com/",
        "google-sign-in" => "https://accounts.google.com/",
        "microsoft-sign-in" => "https://login.microsoftonline.com/",
        "github-sign-in" => "https://github.com/login",
        "windows-settings" => "ms-settings:",
        "wifi-settings" => "ms-settings:network-wifi",
        "network-settings" => "ms-settings:network",
        "sound-settings" => "ms-settings:sound",
        "display-settings" => "ms-settings:display",
        "bluetooth-settings" => "ms-settings:bluetooth",
        _ => return Err("That device action is not supported yet.".into()),
    };

    #[cfg(not(target_os = "windows"))]
    if target.ends_with("-settings") {
        return Err("These Windows settings shortcuts are available in the Windows app.".into());
    }

    app.opener()
        .open_url(url, None::<&str>)
        .map_err(|error| format!("Could not open the requested page: {error}"))
}

/// Force the floating companion character to appear on top of everything
#[tauri::command]
async fn show_companion(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("companion") {
        window.show().map_err(|e| e.to_string())?;
        window.set_always_on_top(true).map_err(|e| e.to_string())?;
        let _ = window.set_focus();
        // Bring to front
        let _ = window.set_ignore_cursor_events(false);
        Ok(())
    } else {
        Err("Companion window not found".into())
    }
}

/// Hide the floating companion
#[tauri::command]
async fn hide_companion(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("companion") {
        window.hide().map_err(|e| e.to_string())?;
        Ok(())
    } else {
        Err("Companion window not found".into())
    }
}

/// Show a transparent, click-through overlay aligned to the primary display.
#[tauri::command]
async fn show_guide(app: tauri::AppHandle) -> Result<(), String> {
    let window = app.get_webview_window("guide").ok_or("Guide window not found")?;
    if let Some(monitor) = app
        .get_webview_window("main")
        .and_then(|main| main.primary_monitor().ok().flatten())
    {
        let position = monitor.position();
        let size = monitor.size();
        window
            .set_position(PhysicalPosition::new(position.x, position.y))
            .map_err(|e| e.to_string())?;
        window
            .set_size(PhysicalSize::new(size.width, size.height))
            .map_err(|e| e.to_string())?;
    }
    window.set_always_on_top(true).map_err(|e| e.to_string())?;
    window.set_ignore_cursor_events(true).map_err(|e| e.to_string())?;
    window.show().map_err(|e| e.to_string())?;
    Ok(())
}

/// Hide the click guide overlay.
#[tauri::command]
async fn hide_guide(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("guide") {
        window.hide().map_err(|e| e.to_string())?;
        Ok(())
    } else {
        Err("Guide window not found".into())
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![greet, open_device_target, show_companion, hide_companion, show_guide, hide_guide])
        .setup(|app| {
            #[cfg(desktop)]
            {
                let _ = app.handle().plugin(tauri_plugin_autostart::init(
                    tauri_plugin_autostart::MacosLauncher::LaunchAgent,
                    None,
                ));
            }
            // Companion starts hidden (see tauri.conf.json).
            // It will be shown when the user clicks "Start observing".
            if let Some(window) = app.get_webview_window("companion") {
                let _ = window.hide();
                let _ = window.set_always_on_top(true);
            }
            if let Some(window) = app.get_webview_window("guide") {
                // Keep the transparent overlay loaded so its event listener is ready
                // before VOSI emits the first click-guidance event.
                let _ = window.set_always_on_top(true);
                let _ = window.set_ignore_cursor_events(true);
                let _ = window.show();
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
