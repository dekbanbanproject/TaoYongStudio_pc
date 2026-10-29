mod commands;
mod python;

use tauri_plugin_opener::OpenerExt;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            // Warm up the Python engine in the background so the first page load is fast.
            let handle = app.handle().clone();
            std::thread::spawn(move || {
                std::thread::sleep(std::time::Duration::from_millis(150));
                let _ = python::api_request(
                    "GET".into(),
                    "/api/health".into(),
                    None,
                );
                let _ = handle;
            });
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                python::shutdown();
            }
        })
        .invoke_handler(tauri::generate_handler![
            commands::api_request,
            commands::engine_status,
            commands::engine_restart,
            commands::open_path,
            commands::reveal_path,
        ])
        .run(tauri::generate_context!())
        .expect("error while running TaoYongStudio");
}
