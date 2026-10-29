use serde_json::Value;

use crate::python;

/// Generic JSON proxy to the local Python engine service.
/// The React layer never talks to Python directly; everything goes through here.
#[tauri::command]
pub async fn api_request(
    method: String,
    path: String,
    body: Option<Value>,
) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || python::api_request(method, path, body))
        .await
        .map_err(|e| format!("task join failed: {}", e))?
}

/// Honest status of the Python engine (running / error / not started).
#[tauri::command]
pub async fn engine_status() -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(python::engine_status)
        .await
        .map_err(|e| format!("task join failed: {}", e))
}

/// Restart the Python engine process.
#[tauri::command]
pub async fn engine_restart() -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(python::engine_restart)
        .await
        .map_err(|e| format!("task join failed: {}", e))?
}

/// Open a file or folder with the default OS application (Explorer, media player, ...).
#[tauri::command]
pub async fn open_path(app: tauri::AppHandle, path: String) -> Result<(), String> {
    use tauri_plugin_opener::OpenerExt;
    app.opener()
        .open_path(path, None::<&str>)
        .map_err(|e| format!("เปิดไฟล์ไม่สำเร็จ: {}", e))
}

/// Reveal a file inside its parent folder in Explorer.
#[tauri::command]
pub async fn reveal_path(app: tauri::AppHandle, path: String) -> Result<(), String> {
    use tauri_plugin_opener::OpenerExt;
    app.opener()
        .reveal_item_in_dir(path)
        .map_err(|e| format!("แสดงโฟลเดอร์ไม่สำเร็จ: {}", e))
}
