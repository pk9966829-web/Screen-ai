use tauri::{Manager, WebviewWindow};

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![greet, show_companion, hide_companion])
        .setup(|app| {
            // Companion starts hidden (see tauri.conf.json).
            // It will be shown when the user clicks "Start observing".
            if let Some(window) = app.get_webview_window("companion") {
                let _ = window.hide();
                let _ = window.set_always_on_top(true);
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
