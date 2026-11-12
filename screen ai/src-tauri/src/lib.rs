use tauri::{Manager, PhysicalPosition, PhysicalSize, WebviewWindow};
use tauri_plugin_opener::OpenerExt;
use std::process::Command;

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
        "google" => "https://www.google.com/",
        "gmail" => "https://mail.google.com/",
        "github" => "https://github.com/",
        "outlook" => "https://outlook.office.com/",
        "calendar" => "https://calendar.google.com/",
        "google-sign-in" => "https://accounts.google.com/",
        "microsoft-sign-in" => "https://login.microsoftonline.com/",
        "github-sign-in" => "https://github.com/login",
        "windows-settings" => "ms-settings:",
        "wifi-settings" => "ms-settings:network-wifi",
        "network-settings" => "ms-settings:network",
        "sound-settings" => "ms-settings:sound",
        "display-settings" => "ms-settings:display",
        "bluetooth-settings" => "ms-settings:bluetooth",
        "privacy-settings" => "ms-settings:privacy",
        "microphone-settings" => "ms-settings:privacy-microphone",
        "camera-settings" => "ms-settings:privacy-webcam",
        "notifications-settings" => "ms-settings:notifications",
        "accessibility-settings" => "ms-settings:easeofaccess",
        "apps-settings" => "ms-settings:appsfeatures",
        "accounts-settings" => "ms-settings:yourinfo",
        "personalization-settings" => "ms-settings:personalization",
        "storage-settings" => "ms-settings:storagesense",
        "time-settings" => "ms-settings:dateandtime",
        "keyboard-settings" => "ms-settings:typing",
        "mouse-settings" => "ms-settings:mousetouchpad",
        "power-settings" => "ms-settings:powersleep",
        "update-settings" => "ms-settings:windowsupdate",
        "screenshot" => "ms-screenclip:",
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

/// Search a fixed, trusted provider. The query is treated only as encoded URL data.
#[tauri::command]
fn search_device_web(app: tauri::AppHandle, provider: String, query: String) -> Result<(), String> {
    let query = query.trim();
    if query.is_empty() || query.chars().count() > 200 {
        return Err("Please use a search phrase between 1 and 200 characters.".into());
    }
    let base = match provider.as_str() {
        "google" => "https://www.google.com/search?q=",
        "youtube" => "https://www.youtube.com/results?search_query=",
        "bing" => "https://www.bing.com/search?q=",
        _ => return Err("That search provider is not supported.".into()),
    };
    let encoded: String = query
        .bytes()
        .map(|byte| match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                (byte as char).to_string()
            }
            _ => format!("%{byte:02X}"),
        })
        .collect();
    app.opener()
        .open_url(format!("{base}{encoded}"), None::<&str>)
        .map_err(|error| format!("Could not open search results: {error}"))
}

/// Open a public YouTube watch page for a validated video ID returned by backend search.
#[tauri::command]
fn play_youtube_video(app: tauri::AppHandle, video_id: String) -> Result<(), String> {
    if video_id.len() != 11 || !video_id.chars().all(|ch| ch.is_ascii_alphanumeric() || ch == '_' || ch == '-') {
        return Err("YouTube returned an invalid video ID.".into());
    }
    app.opener()
        .open_url(format!("https://www.youtube.com/watch?v={video_id}&autoplay=1"), None::<&str>)
        .map_err(|error| format!("Could not open the YouTube video: {error}"))
}

/// Launch a small allow-list of built-in Windows apps without invoking a shell.
#[tauri::command]
fn launch_device_app(target: String) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        let executable = match target.as_str() {
            "calculator" => "calc.exe",
            "notepad" => "notepad.exe",
            "file-explorer" => "explorer.exe",
            "task-manager" => "taskmgr.exe",
            "paint" => "mspaint.exe",
            "edge" => "msedge.exe",
            "chrome" => "chrome.exe",
            "word" => "winword.exe",
            "excel" => "excel.exe",
            "powerpoint" => "powerpnt.exe",
            "outlook-app" => "outlook.exe",
            _ => return Err("That app is not supported yet.".into()),
        };
        Command::new(executable)
            .spawn()
            .map(|_| ())
            .map_err(|error| format!("Could not launch the requested app: {error}"))
    }

    #[cfg(not(target_os = "windows"))]
    {
        let _ = target;
        Err("Built-in app shortcuts are available in the Windows VOSI app.".into())
    }
}

/// Adjust Windows master volume or toggle mute using the standard media keys.
#[tauri::command]
fn control_volume(action: String) -> Result<String,String> {
    #[cfg(target_os = "windows")]
    {
        let key = match action.as_str() { "up" => 0xAFu16, "down" => 0xAEu16, "mute" => 0xADu16, "unmute" => 0xAFu16, _ => return Err("Choose volume up, down, mute, or unmute.".into()) };
        let script = if action == "mute" || action == "unmute" {
            format!("$w=New-Object -ComObject WScript.Shell; $w.SendKeys([char]{key})")
        } else {
            format!("$w=New-Object -ComObject WScript.Shell; 1..5 | ForEach-Object {{ $w.SendKeys([char]{key}); Start-Sleep -Milliseconds 80 }}")
        };
        let output = Command::new("powershell.exe")
            .args(["-NoProfile", "-WindowStyle", "Hidden", "-Command", &script])
            .output()
            .map_err(|error| format!("Could not adjust volume: {error}"))?;
        if !output.status.success() {
            return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
        }
        return Ok(match action.as_str() {
            "up" => "Windows volume-up key action completed.",
            "down" => "Windows volume-down key action completed.",
            "mute" => "Windows mute key action completed.",
            _ => "Windows unmute key action completed.",
        }.into());
    }
    #[cfg(not(target_os = "windows"))] { let _=action; Err("Volume controls are supported in the Windows VOSI app.".into()) }
}

/// Schedule a one-time Windows alarm through Task Scheduler.
#[tauri::command]
fn set_alarm(hour: u32, minute: u32) -> Result<String, String> {
    #[cfg(target_os = "windows")]
    {
        use chrono::{Local, Duration};
        if hour > 23 || minute > 59 { return Err("Please provide a valid time.".into()); }
        let now = Local::now();
        let mut alarm = now.date_naive().and_hms_opt(hour, minute, 0).ok_or("Invalid alarm time")?;
        if alarm <= now.naive_local() { alarm += Duration::days(1); }
        let date=alarm.format("%m/%d/%Y").to_string(); let time=alarm.format("%H:%M").to_string();
        let task_name=format!("VOSI_Alarm_{}",alarm.format("%Y%m%d_%H%M"));
        let script="Add-Type -AssemblyName System.Windows.Forms; 1..8 | ForEach-Object { [System.Media.SystemSounds]::Exclamation.Play(); Start-Sleep -Milliseconds 700 }; [System.Windows.Forms.MessageBox]::Show('Your VOSI alarm is ringing.','VOSI Alarm') | Out-Null";
        use base64::Engine;
        let encoded=base64::engine::general_purpose::STANDARD.encode(script.encode_utf16().flat_map(|c|c.to_le_bytes()).collect::<Vec<u8>>());
        let action=format!("powershell.exe -NoProfile -WindowStyle Hidden -EncodedCommand {encoded}");
        let output=Command::new("schtasks.exe").args(["/Create","/F","/SC","ONCE","/SD",&date,"/ST",&time,"/TN",&task_name,"/TR",&action,"/IT"]).output().map_err(|e|format!("Could not create alarm: {e}"))?;
        if !output.status.success(){return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());}
        return Ok(format!("Alarm set for {}. Windows will trigger it while your account is signed in and the computer is awake.",alarm.format("%-I:%M %p")));
    }
    #[cfg(not(target_os = "windows"))] { let _=(hour,minute); Err("VOSI alarms are supported on Windows.".into()) }
}
#[tauri::command]
fn set_timer(seconds: u64) -> Result<String,String> {
    if seconds == 0 || seconds > 86400 {
        return Err("Choose a timer between 1 second and 24 hours.".into());
    }
    #[cfg(target_os = "windows")]
    {
        use chrono::{Duration, Local, Timelike};
        let target = Local::now() + Duration::seconds(seconds as i64);
        // schtasks accepts minute precision; round upward so a timer never fires early.
        let due = target + Duration::seconds((60 - target.second() as i64) % 60);
        let date = due.format("%m/%d/%Y").to_string();
        let time = due.format("%H:%M").to_string();
        let task_name = format!("VOSI_Timer_{}", due.format("%Y%m%d_%H%M%S"));
        let script = "Add-Type -AssemblyName System.Windows.Forms; 1..5 | ForEach-Object { [System.Media.SystemSounds]::Asterisk.Play(); Start-Sleep -Milliseconds 600 }; [System.Windows.Forms.MessageBox]::Show('Your VOSI timer is complete.','VOSI Timer') | Out-Null";
        use base64::Engine;
        let encoded = base64::engine::general_purpose::STANDARD.encode(
            script.encode_utf16().flat_map(|c| c.to_le_bytes()).collect::<Vec<u8>>()
        );
        let action = format!("powershell.exe -NoProfile -WindowStyle Hidden -EncodedCommand {encoded}");
        let output = Command::new("schtasks.exe")
            .args(["/Create", "/F", "/SC", "ONCE", "/SD", &date, "/ST", &time, "/TN", &task_name, "/TR", &action, "/IT"])
            .output()
            .map_err(|error| format!("Could not schedule timer: {error}"))?;
        if !output.status.success() {
            return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
        }
        return Ok(format!(
            "Timer scheduled for {}. Windows will trigger it while your account is signed in and the computer is awake.",
            due.format("%-I:%M %p")
        ));
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = seconds;
        Err("VOSI timers are supported in the Windows VOSI app.".into())
    }
}
#[tauri::command]
fn lock_pc()->Result<String,String>{#[cfg(target_os="windows")]{Command::new("rundll32.exe").args(["user32.dll,LockWorkStation"]).spawn().map_err(|e|e.to_string())?;return Ok("Locking your Windows device.".into());}#[cfg(not(target_os="windows"))]{Err("Locking is supported in the Windows VOSI app.".into())}}
#[tauri::command]
fn shutdown_pc()->Result<String,String>{#[cfg(target_os="windows")]{Command::new("shutdown.exe").args(["/s","/t","10"]).spawn().map_err(|e|e.to_string())?;return Ok("Windows will shut down in 10 seconds. Run shutdown /a to cancel.".into());}#[cfg(not(target_os="windows"))]{Err("Shutdown is supported in Windows.".into())}}
#[tauri::command]
fn restart_pc()->Result<String,String>{#[cfg(target_os="windows")]{Command::new("shutdown.exe").args(["/r","/t","10"]).spawn().map_err(|e|e.to_string())?;return Ok("Windows will restart in 10 seconds. Run shutdown /a to cancel.".into());}#[cfg(not(target_os="windows"))]{Err("Restart is supported in Windows.".into())}}

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


/// Store the paired desktop device credential in Windows Credential Manager.
#[cfg(target_os = "windows")]
#[tauri::command]
fn save_agent_device_credential(credential: String) -> Result<(), String> {
    if credential.is_empty() || credential.len() > 2048 {
        return Err("Invalid desktop device credential.".into());
    }
    let entry = keyring::Entry::new("com.pb7.vosi", "agent-device-credential")
        .map_err(|error| format!("Windows Credential Manager is unavailable: {error}"))?;
    entry.set_password(&credential)
        .map_err(|error| format!("Could not save the VOSI credential securely: {error}"))
}

#[cfg(not(target_os = "windows"))]
#[tauri::command]
fn save_agent_device_credential(_credential: String) -> Result<(), String> {
    Err("Secure desktop pairing is currently supported in the Windows VOSI app.".into())
}

/// Read the paired credential from Windows Credential Manager; never from web storage.
#[cfg(target_os = "windows")]
#[tauri::command]
fn load_agent_device_credential() -> Result<Option<String>, String> {
    let entry = keyring::Entry::new("com.pb7.vosi", "agent-device-credential")
        .map_err(|error| format!("Windows Credential Manager is unavailable: {error}"))?;
    match entry.get_password() {
        Ok(value) => Ok(Some(value)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(error) => Err(format!("Could not read the VOSI credential securely: {error}")),
    }
}

#[cfg(not(target_os = "windows"))]
#[tauri::command]
fn load_agent_device_credential() -> Result<Option<String>, String> {
    Err("Secure desktop pairing is currently supported in the Windows VOSI app.".into())
}

#[cfg(target_os = "windows")]
#[tauri::command]
fn clear_agent_device_credential() -> Result<(), String> {
    let entry = keyring::Entry::new("com.pb7.vosi", "agent-device-credential")
        .map_err(|error| format!("Windows Credential Manager is unavailable: {error}"))?;
    match entry.delete_credential() {
        Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(error) => Err(format!("Could not clear the VOSI credential: {error}")),
    }
}

#[cfg(not(target_os = "windows"))]
#[tauri::command]
fn clear_agent_device_credential() -> Result<(), String> {
    Err("Secure desktop pairing is currently supported in the Windows VOSI app.".into())
}


/// Open the dedicated Windows voice companion panel.
#[tauri::command]
async fn show_voice_companion(app: tauri::AppHandle) -> Result<(), String> {
    let window = app.get_webview_window("voice").ok_or("Voice companion window not found")?;
    window.show().map_err(|e| e.to_string())?;
    window.set_always_on_top(true).map_err(|e| e.to_string())?;
    window.set_focus().map_err(|e| e.to_string())?;
    Ok(())
}

/// Hide the dedicated Windows voice companion panel.
#[tauri::command]
async fn hide_voice_companion(app: tauri::AppHandle) -> Result<(), String> {
    let window = app.get_webview_window("voice").ok_or("Voice companion window not found")?;
    window.hide().map_err(|e| e.to_string())?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![greet, open_device_target, search_device_web, play_youtube_video, launch_device_app, control_volume, set_alarm, set_timer, lock_pc, shutdown_pc, restart_pc, show_companion, hide_companion, show_guide, hide_guide, show_voice_companion, hide_voice_companion, save_agent_device_credential, load_agent_device_credential, clear_agent_device_credential])
        .setup(|app| {
            #[cfg(desktop)]
            {
                let _ = app.handle().plugin(tauri_plugin_autostart::init(
                    tauri_plugin_autostart::MacosLauncher::LaunchAgent,
                    None,
                ));
            }
            if let Some(window) = app.get_webview_window("voice") {
                let _ = window.hide();
                let _ = window.set_always_on_top(true);
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
