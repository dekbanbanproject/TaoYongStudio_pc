//! Manages the local Python engine process and proxies JSON calls to it.
//!
//! The Python side runs a loopback-only HTTP service (see `engine/taoyong/service.py`).
//! It binds 127.0.0.1 only and requires a per-session bearer token that is
//! generated here and never leaves the machine.

use once_cell::sync::Lazy;
use serde_json::{json, Value};
use std::collections::hash_map::RandomState;
use std::hash::{BuildHasher, Hasher};
use std::io::{BufRead, BufReader};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;

pub struct PythonService {
    child: Mutex<Option<Child>>,
    base_url: String,
    token: String,
    root: String,
    engine_dir: String,
    python_exe: String,
}

static SERVICE: Lazy<Mutex<Option<PythonService>>> = Lazy::new(|| Mutex::new(None));

fn random_token() -> String {
    let mut out = String::new();
    for _ in 0..4 {
        let mut h = RandomState::new().build_hasher();
        h.write_u64(std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos() as u64)
            .unwrap_or(0));
        out.push_str(&format!("{:016x}", h.finish()));
    }
    out
}

fn app_root() -> String {
    if let Ok(v) = std::env::var("TAOYONG_ROOT") {
        if !v.trim().is_empty() {
            return v;
        }
    }
    // dev: <repo>/desktop/src-tauri  ->  <repo>
    if let Ok(exe) = std::env::current_exe() {
        let mut p = exe.as_path();
        while let Some(parent) = p.parent() {
            if parent.join("engine").is_dir() && parent.join("scripts").is_dir() {
                return parent.to_string_lossy().to_string();
            }
            p = parent;
        }
    }
    std::env::current_dir()
        .map(|d| d.to_string_lossy().to_string())
        .unwrap_or_else(|_| ".".to_string())
}

fn engine_dir(root: &str) -> String {
    if let Ok(v) = std::env::var("TAOYONG_ENGINE_DIR") {
        if !v.trim().is_empty() {
            return v;
        }
    }
    format!("{}\\engine", root)
}

fn python_exe(root: &str) -> String {
    if let Ok(v) = std::env::var("TAOYONG_PYTHON") {
        if !v.trim().is_empty() {
            return v;
        }
    }
    // Prefer the project virtualenv when it exists (it has the real deps).
    let venv = format!("{}\\engine\\.venv\\Scripts\\python.exe", root);
    if Path::new(&venv).exists() {
        return venv;
    }
    "python".to_string()
}

impl PythonService {
    fn spawn(root: String, engine_dir: String, python_exe: String) -> Result<Self, String> {
        let token = random_token();
        let mut child = Command::new(&python_exe)
            .args([
                "-m",
                "taoyong.service",
                "--host",
                "127.0.0.1",
                "--port",
                "0",
                "--token",
                &token,
            ])
            .current_dir(&engine_dir)
            .env("TAOYONG_ROOT", &root)
            .env("PYTHONUNBUFFERED", "1")
            .env("PYTHONIOENCODING", "utf-8")
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| {
                format!(
                    "เริ่ม Python Engine ไม่ได้ ({}): {} — ตรวจสอบว่ามี Python และติดตั้ง requirements",
                    python_exe, e
                )
            })?;

        // READY line: {"port": <int>, "token": "<token>"}
        let stdout = child.stdout.take().ok_or("ไม่พบ stdout ของ Python Engine")?;
        let mut reader = BufReader::new(stdout);
        let mut line = String::new();
        let mut port: Option<u16> = None;
        let mut announced = String::new();

        for _ in 0..40 {
            line.clear();
            let n = reader
                .read_line(&mut line)
                .map_err(|e| format!("อ่าน stdout ของ Python Engine ไม่ได้: {}", e))?;
            if n == 0 {
                break;
            }
            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }
            if let Ok(v) = serde_json::from_str::<Value>(trimmed) {
                if let Some(p) = v.get("port").and_then(|p| p.as_u64()) {
                    port = Some(p as u16);
                    if let Some(t) = v.get("token").and_then(|t| t.as_str()) {
                        announced = t.to_string();
                    }
                    break;
                }
            }
            if trimmed.starts_with("READY") {
                // READY <port>
                if let Some(p) = trimmed.split_whitespace().nth(1).and_then(|p| p.parse::<u16>().ok()) {
                    port = Some(p);
                    break;
                }
            }
        }

        let port = port.ok_or_else(|| {
            "Python Engine เริ่มทำงานแต่ไม่ส่งพอร์ตกลับมา (ดู log ของ Python Engine)".to_string()
        })?;

        // Drain stderr in the background so the engine's traceback is never lost.
        if let Some(stderr) = child.stderr.take() {
            std::thread::spawn(move || {
                let reader = BufReader::new(stderr);
                for line in reader.lines().map_while(Result::ok) {
                    eprintln!("[python-engine] {}", line);
                }
            });
        }

        // Keep draining stdout so the pipe never blocks the engine.
        std::thread::spawn(move || {
            let mut reader = BufReader::new(stdout);
            for line in reader.lines().map_while(Result::ok) {
                let t = line.trim();
                if !t.is_empty() && !t.starts_with('{') && !t.starts_with("READY") {
                    eprintln!("[python-engine] {}", t);
                }
            }
        });

        let token = if announced.is_empty() { token } else { announced };
        Ok(PythonService {
            child: Mutex::new(Some(child)),
            base_url: format!("http://127.0.0.1:{}", port),
            token,
            root,
            engine_dir,
            python_exe,
        })
    }

    fn request_raw(&self, method: &str, path: &str, body: Option<Value>) -> Result<Value, String> {
        let url = format!("{}{}", self.base_url, path);
        let result = match method.to_ascii_uppercase().as_str() {
            "GET" => ureq::get(&url)
                .set("X-TAOYONG-TOKEN", &self.token)
                .call(),
            "DELETE" => ureq::delete(&url)
                .set("X-TAOYONG-TOKEN", &self.token)
                .call(),
            "POST" => {
                let payload = body.unwrap_or(Value::Object(Default::default()));
                ureq::post(&url)
                    .set("X-TAOYONG-TOKEN", &self.token)
                    .send_json(&payload)
            }
            "PUT" => {
                let payload = body.unwrap_or(Value::Object(Default::default()));
                ureq::put(&url)
                    .set("X-TAOYONG-TOKEN", &self.token)
                    .send_json(&payload)
            }
            other => return Err(format!("วิธีเรียก API ไม่รองรับ: {}", other)),
        };

        match result {
            Ok(resp) => resp
                .body_mut()
                .read_json::<Value>()
                .map_err(|e| format!("อ่านคำตอบจาก Python Engine ไม่ได้: {}", e)),
            Err(ureq::Error::Status(code, resp)) => {
                let payload: Value = resp
                    .body_mut()
                    .read_json()
                    .unwrap_or_else(|_| json!({ "error": format!("HTTP {}", code) }));
                let msg = payload
                    .get("error")
                    .and_then(|e| e.as_str())
                    .unwrap_or("ไม่ทราบสาเหตุ")
                    .to_string();
                Err(format!("{} (HTTP {})", msg, code))
            }
            Err(e) => Err(format!("เชื่อมต่อ Python Engine ไม่สำเร็จ: {}", e)),
        }
    }

    fn status(&self) -> Value {
        json!({
            "running": true,
            "baseUrl": self.base_url,
            "root": self.root,
            "engineDir": self.engine_dir,
            "python": self.python_exe,
        })
    }
}

fn ensure_started() -> Result<(), String> {
    let mut guard = SERVICE.lock().map_err(|_| "service lock poisoned".to_string())?;
    if guard.is_some() {
        return Ok(());
    }
    let root = app_root();
    let edir = engine_dir(&root);
    let py = python_exe(&root);
    let svc = PythonService::spawn(root, edir, py)?;
    *guard = Some(svc);
    Ok(())
}

fn with_service<T>(f: impl FnOnce(&PythonService) -> T) -> Result<T, String> {
    ensure_started()?;
    let guard = SERVICE.lock().map_err(|_| "service lock poisoned".to_string())?;
    match guard.as_ref() {
        Some(svc) => Ok(f(svc)),
        None => Err("Python Engine ไม่ได้ทำงาน".to_string()),
    }
}

/// Public JSON API used by the React layer.
pub fn api_request(method: String, path: String, body: Option<Value>) -> Result<Value, String> {
    with_service(|svc| svc.request_raw(&method, &path, body))
}

pub fn engine_status() -> Value {
    match with_service(|svc| svc.status()) {
        Ok(mut v) => v,
        Err(e) => json!({ "running": false, "error": e }),
    }
}

pub fn engine_restart() -> Result<Value, String> {
    {
        let mut guard = SERVICE.lock().map_err(|_| "service lock poisoned".to_string())?;
        if let Some(svc) = guard.as_mut() {
            if let Some(child) = svc.child.lock().ok().and_then(|mut c| c.take()) {
                let _ = child.kill();
            }
        }
        *guard = None;
    }
    std::thread::sleep(Duration::from_millis(300));
    ensure_started()?;
    engine_status()
}

pub fn shutdown() {
    if let Ok(mut guard) = SERVICE.lock() {
        if let Some(svc) = guard.as_mut() {
            if let Some(child) = svc.child.lock().ok().and_then(|mut c| c.take()) {
                let _ = child.kill();
            }
        }
        *guard = None;
    }
}
