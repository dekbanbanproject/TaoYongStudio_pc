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
use std::path::Path;
use std::process::{Child, Command, Stdio};
use std::sync::mpsc::{channel, RecvTimeoutError};
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
        h.write_u64(
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_nanos() as u64)
                .unwrap_or(0),
        );
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

    let has = |p: &Path, rel: &str| p.join(rel).exists();

    // A workspace root holds the engine package and the script store.
    let is_root = |p: &Path| p.join("engine").is_dir() && p.join("scripts").is_dir();

    // A development workspace also holds the React/Tauri project, which is what
    // distinguishes it from a Cargo build directory (Tauri copies the bundle
    // resources next to the binary, so the build folder looks like a root too).
    let is_dev_workspace =
        |p: &Path| is_root(p) && p.join("desktop").join("src").is_dir();

    let mut exe_ancestors: Vec<std::path::PathBuf> = Vec::new();
    if let Some(dir) = exe_dir() {
        exe_ancestors.push(dir.clone());
    }
    if let Ok(exe) = std::env::current_exe() {
        let mut p = exe.as_path();
        while let Some(parent) = p.parent() {
            exe_ancestors.push(parent.to_path_buf());
            p = parent;
        }
    }

    let mut cwd_ancestors: Vec<std::path::PathBuf> = Vec::new();
    if let Ok(cwd) = std::env::current_dir() {
        let mut p = cwd.as_path();
        cwd_ancestors.push(cwd.clone());
        while let Some(parent) = p.parent() {
            cwd_ancestors.push(parent.to_path_buf());
            p = parent;
        }
    }

    // 1) A development workspace above the executable wins: it holds the live
    //    engine source and its virtualenv.
    for c in &exe_ancestors {
        if is_dev_workspace(c) {
            return c.to_string_lossy().to_string();
        }
    }

    // 2) A packaged app: its own folder holds the engine and the data.
    if let Some(dir) = exe_dir() {
        if is_root(&dir) {
            return dir.to_string_lossy().to_string();
        }
        let res = dir.join("resources");
        if is_root(&res) {
            return res.to_string_lossy().to_string();
        }
    }

    // 3) Fall back to the working directory, but only when nothing above the
    //    executable matched.
    for c in &cwd_ancestors {
        if is_dev_workspace(c) {
            return c.to_string_lossy().to_string();
        }
    }
    for c in &cwd_ancestors {
        if is_root(c) {
            return c.to_string_lossy().to_string();
        }
    }

    let _ = has;
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

/// How the engine process is started.
enum Launcher {
    /// `python -m taoyong.service ...`
    Python { exe: String, cwd: String, root: String },
    /// `taoyong-engine.exe --host ... --port ... --token ...` (packaged sidecar)
    Sidecar { exe: String, cwd: String, root: String },
}

impl Launcher {
    fn command(&self, token: &str) -> Command {
        let mut cmd = match self {
            Launcher::Python { exe, cwd, .. } => {
                let mut c = Command::new(exe);
                c.args(["-m", "taoyong.service"]);
                c.current_dir(cwd);
                c
            }
            Launcher::Sidecar { exe, cwd, .. } => {
                let mut c = Command::new(exe);
                c.current_dir(cwd);
                c
            }
        };
        cmd.args([
            "--host",
            "127.0.0.1",
            "--port",
            "0",
            "--token",
            token,
        ])
        .env("TAOYONG_ROOT", &self.root())
        .env("PYTHONUNBUFFERED", "1")
        .env("PYTHONIOENCODING", "utf-8")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
        cmd
    }

    fn root(&self) -> &str {
        match self {
            Launcher::Python { root, .. } => root,
            Launcher::Sidecar { root, .. } => root,
        }
    }
}

fn exe_dir() -> Option<std::path::PathBuf> {
    std::env::current_exe()
        .ok()
        .and_then(|e| e.parent().map(|p| p.to_path_buf()))
}

/// Tauri lays resources out differently per platform and per bundle config, so
/// look in every place the sidecar may have been placed.
fn find_sidecar(root: &str) -> Option<(String, String)> {
    let mut candidates: Vec<std::path::PathBuf> = Vec::new();

    if let Ok(v) = std::env::var("TAOYONG_ENGINE_SIDECAR") {
        if !v.trim().is_empty() {
            candidates.push(std::path::PathBuf::from(v));
        }
    }
    if let Some(dir) = exe_dir() {
        candidates.push(dir.join("engine").join("taoyong-engine.exe"));
        candidates.push(dir.join("engine").join("taoyong-engine").join("taoyong-engine.exe"));
        candidates.push(dir.join("resources").join("engine").join("taoyong-engine.exe"));
        candidates.push(
            dir.join("resources")
                .join("engine")
                .join("taoyong-engine")
                .join("taoyong-engine.exe"),
        );
        candidates.push(dir.join("resources").join("taoyong-engine").join("taoyong-engine.exe"));
        candidates.push(dir.join("taoyong-engine").join("taoyong-engine.exe"));
    }
    let rp = Path::new(root);
    candidates.push(
        rp.join("engine")
            .join("dist")
            .join("taoyong-engine")
            .join("taoyong-engine.exe"),
    );

    for c in candidates {
        if c.exists() {
            let cwd = c
                .parent()
                .map(|p| p.to_string_lossy().to_string())
                .unwrap_or_else(|| root.to_string());
            return Some((c.to_string_lossy().to_string(), cwd));
        }
    }
    None
}

fn resolve_launcher(root: &str) -> Launcher {
    let root_path = Path::new(root);

    // 1) project virtualenv (development — always uses the live engine source)
    let venv = root_path
        .join("engine")
        .join(".venv")
        .join("Scripts")
        .join("python.exe");
    if venv.exists() {
        return Launcher::Python {
            exe: venv.to_string_lossy().to_string(),
            cwd: format!("{}\\engine", root),
            root: root.to_string(),
        };
    }

    // 2) packaged / locally built sidecar
    if let Some((exe, cwd)) = find_sidecar(root) {
        return Launcher::Sidecar {
            exe,
            cwd,
            root: root.to_string(),
        };
    }

    // 3) system Python
    Launcher::Python {
        exe: "python".to_string(),
        cwd: format!("{}\\engine", root),
        root: root.to_string(),
    }
}

impl PythonService {
    fn spawn(root: String, engine_dir: String, python_exe: String) -> Result<Self, String> {
        let token = random_token();

        let launcher = resolve_launcher(&root);
        let mut child = launcher
            .command(&token)
            .spawn()
            .map_err(|e| {
                format!(
                    "เริ่ม Python Engine ไม่ได้ ({}): {} — ตรวจสอบว่ามี Python และติดตั้ง requirements",
                    python_exe, e
                )
            })?;

        let stdout = child.stdout.take().ok_or("ไม่พบ stdout ของ Python Engine")?;
        let (tx, rx) = channel::<u16>();

        // One thread owns stdout: it reports the port and then keeps draining.
        std::thread::spawn(move || {
            let reader = BufReader::new(stdout);
            let mut reported = false;
            for line in reader.lines().map_while(Result::ok) {
                let t = line.trim();
                if t.is_empty() {
                    continue;
                }
                if !reported {
                    let mut port: Option<u16> = None;
                    if let Ok(v) = serde_json::from_str::<Value>(t) {
                        if let Some(p) = v.get("port").and_then(|p| p.as_u64()) {
                            port = Some(p as u16);
                        }
                    } else if t.starts_with("READY") {
                        port = t
                            .split_whitespace()
                            .nth(1)
                            .and_then(|p| p.parse::<u16>().ok());
                    }
                    if let Some(p) = port {
                        reported = true;
                        let _ = tx.send(p);
                        continue;
                    }
                }
                eprintln!("[python-engine] {}", t);
            }
        });

        let stderr = child.stderr.take();
        if let Some(stderr) = stderr {
            std::thread::spawn(move || {
                let reader = BufReader::new(stderr);
                for line in reader.lines().map_while(Result::ok) {
                    eprintln!("[python-engine] {}", line);
                }
            });
        }

        let port = match rx.recv_timeout(Duration::from_secs(30)) {
            Ok(p) => p,
            Err(RecvTimeoutError::Timeout) => {
                let _ = child.kill();
                return Err(
                    "Python Engine เริ่มทำงานแต่ไม่ตอบกลับภายใน 30 วินาที (ดู log ของ Python Engine)"
                        .to_string(),
                );
            }
            Err(_) => {
                let _ = child.kill();
                return Err("Python Engine หยุดทำงานก่อนจะเริ่มให้บริการได้".to_string());
            }
        };

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
        let payload = body.unwrap_or(Value::Object(Default::default()));

        let result = match method.to_ascii_uppercase().as_str() {
            "GET" => ureq::get(&url)
                .set("X-TAOYONG-TOKEN", &self.token)
                .call(),
            "DELETE" => ureq::delete(&url)
                .set("X-TAOYONG-TOKEN", &self.token)
                .call(),
            "POST" => ureq::post(&url)
                .set("X-TAOYONG-TOKEN", &self.token)
                .send_json(&payload),
            "PUT" => ureq::put(&url)
                .set("X-TAOYONG-TOKEN", &self.token)
                .send_json(&payload),
            other => return Err(format!("วิธีเรียก API ไม่รองรับ: {}", other)),
        };

        match result {
            Ok(resp) => resp
                .into_json::<Value>()
                .map_err(|e| format!("อ่านคำตอบจาก Python Engine ไม่ได้: {}", e)),
            Err(ureq::Error::Status(code, resp)) => {
                let raw = resp.into_string().unwrap_or_default();
                let msg = serde_json::from_str::<Value>(&raw)
                    .ok()
                    .and_then(|v| {
                        v.get("error")
                            .and_then(|e| e.as_str())
                            .map(|s| s.to_string())
                    })
                    .unwrap_or_else(|| format!("HTTP {}", code));
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
    with_service(|svc| svc.request_raw(&method, &path, body))?
}

pub fn engine_status() -> Value {
    match with_service(|svc| svc.status()) {
        Ok(v) => v,
        Err(e) => json!({ "running": false, "error": e }),
    }
}

pub fn engine_restart() -> Result<Value, String> {
    {
        let mut guard = SERVICE.lock().map_err(|_| "service lock poisoned".to_string())?;
        if let Some(svc) = guard.as_mut() {
            if let Ok(mut slot) = svc.child.lock() {
                if let Some(mut child) = slot.take() {
                    let _ = child.kill();
                }
            }
        }
        *guard = None;
    }
    std::thread::sleep(Duration::from_millis(300));
    ensure_started()?;
    Ok(engine_status())
}

pub fn shutdown() {
    if let Ok(mut guard) = SERVICE.lock() {
        if let Some(svc) = guard.as_mut() {
            if let Ok(mut slot) = svc.child.lock() {
                if let Some(mut child) = slot.take() {
                    let _ = child.kill();
                }
            }
        }
        *guard = None;
    }
}
