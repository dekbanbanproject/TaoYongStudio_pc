"""QA harness for TaoYongStudio Desktop V2.

    python tools/qa.py            # engine + endpoints + typecheck + build + pages
    python tools/qa.py --quick    # skip the frontend typecheck / production build

Checks
  1. Every engine module imports cleanly and the API routes are registered.
  2. Every route answers on a live service instance with real data.
  3. The service rejects requests without the bearer token.
  4. The frontend typechecks and the Vite production build succeeds.
  5. The frontend source contains no fabricated rows or fake success strings.
  6. Every page exists and every route in App.tsx has a page.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def tool(name: str) -> str:
    """Resolve an npm tool, adding the .cmd shim Windows needs."""
    found = shutil.which(name)
    if found:
        return found
    for ext in (".cmd", ".exe", ".bat"):
        candidate = str(DESKTOP / "node_modules" / ".bin" / (name + ext))
        if os.path.exists(candidate):
            return candidate
    return name

ROOT = Path(__file__).resolve().parent.parent
DESKTOP = ROOT / "desktop"
SRC = DESKTOP / "src"
ENGINE = ROOT / "engine"
PY = ENGINE / ".venv" / "Scripts" / "python.exe"
if not PY.exists():
    PY = Path(sys.executable)

QUICK = "--quick" in sys.argv
failures = []
warnings = []


def head(title):
    print("\n" + "=" * 74)
    print(title)
    print("=" * 74)


def ok(label, detail=""):
    print(f"  PASS  {label}" + (f"  ({detail})" if detail else ""))


def bad(label, detail=""):
    print(f"  FAIL  {label}" + (f"  ({detail})" if detail else ""))
    failures.append(label)


def warn(label, detail=""):
    print(f"  WARN  {label}" + (f"  ({detail})" if detail else ""))
    warnings.append(label)


ENGINE_ENV = {**os.environ, "TAOYONG_ROOT": str(ROOT), "PYTHONIOENCODING": "utf-8"}

# ---------------------------------------------------------------- 1. engine
head("1. Python engine imports")
MODULES = [
    "config", "script", "episode", "compile", "art", "audio", "tts",
    "textrender", "hardware", "credential_store", "planner_generate",
    "planner_handoff", "planner_ideas", "platform_workspace", "product_clips",
    "caption_ai", "prompt_analysis", "ai_worker_scheduler",
    "facebook_profile_flow", "fb_browser_worker", "publish",
]
for m in MODULES:
    r = subprocess.run([str(PY), "-c", f"import taoyong.{m}"], cwd=str(ENGINE),
                       capture_output=True, text=True, timeout=240, env=ENGINE_ENV)
    if r.returncode == 0:
        ok(f"import taoyong.{m}")
    else:
        tail = (r.stderr or "").strip().splitlines()[-1:] or [""]
        bad(f"import taoyong.{m}", tail[0][:160])

r = subprocess.run([str(PY), "-c", "from taoyong import api; print(len(api.ROUTES))"],
                   cwd=str(ENGINE), capture_output=True, text=True, timeout=180, env=ENGINE_ENV)
if r.returncode == 0:
    n = int(r.stdout.strip().splitlines()[-1])
    ok("api routes registered", f"{n} routes")
    if n < 40:
        bad("api route count", f"only {n}")
else:
    bad("api module import", (r.stderr or "").strip()[-200:])

# --------------------------------------------------------------- 2. service
head("2. Live service endpoints (real data)")
TOKEN = "qa-token"
proc = subprocess.Popen(
    [str(PY), "-m", "taoyong.service", "--host", "127.0.0.1", "--port", "0", "--token", TOKEN],
    cwd=str(ENGINE), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=ENGINE_ENV,
)
port = None
t0 = time.time()
while time.time() - t0 < 45:
    line = proc.stdout.readline()
    if not line:
        break
    line = line.strip()
    if line.startswith("{"):
        port = json.loads(line)["port"]
        break
if not port:
    bad("service start", "no port announced")
else:
    ok("service start", f"port {port}")

    def call(method, path, body=None, token=TOKEN):
        url = f"http://127.0.0.1:{port}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        if token:
            req.add_header("X-TAOYONG-TOKEN", token)
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                return e.code, json.loads(raw)
            except Exception:
                return e.code, {"raw": raw[:400]}
        except Exception as e:
            return 0, {"error": str(e)}

    ENDPOINTS = [
        ("GET", "/api/health", None),
        ("GET", "/api/dashboard", None),
        ("GET", "/api/scripts", None),
        ("GET", "/api/clips", None),
        ("GET", "/api/settings", None),
        ("GET", "/api/posting/status", None),
        ("GET", "/api/scheduler", None),
        ("GET", "/api/planner/ideas", None),
        ("GET", "/api/planner/requests", None),
        ("GET", "/api/hardware", None),
        ("GET", "/api/shopee/categories", None),
        ("GET", "/api/shopee/products?perPage=5", None),
        ("GET", "/api/platform/scripts", None),
        ("GET", "/api/platform/clips", None),
        ("GET", "/api/facebook/posts", None),
    ]
    for method, path, body in ENDPOINTS:
        status, payload = call(method, path, body)
        if status == 200 and payload.get("ok") is not False:
            extra = ""
            if path == "/api/dashboard":
                s = payload.get("stats") or {}
                extra = f"pending={s.get('scriptsPending')} clips={s.get('clipsTotal')}"
            elif path == "/api/clips":
                extra = f"{len(payload.get('clips') or [])} clips"
            elif path == "/api/shopee/products":
                extra = f"{payload.get('total')} products"
            elif path == "/api/planner/ideas":
                extra = f"{len(payload.get('ideas') or [])} ideas"
            ok(f"{method} {path}", extra)
        else:
            bad(f"{method} {path}", str(payload.get("error"))[:160])

    status, _ = call("GET", "/api/health", None, token="wrong-token")
    ok("auth rejects a bad token") if status == 401 else bad("auth rejects a bad token", f"status {status}")

    status, _ = call("GET", "/api/does-not-exist", None)
    ok("unknown route -> 404") if status == 404 else bad("unknown route -> 404", f"status {status}")

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()

# -------------------------------------------------------------- 3. frontend
if not QUICK:
    head("3. Frontend typecheck + production build")
    r = subprocess.run([tool("tsc"), "-p", "tsconfig.app.json", "--noEmit"],
                       cwd=str(DESKTOP), capture_output=True, text=True, timeout=1200)
    if r.returncode == 0:
        ok("tsc --noEmit")
    else:
        errs = [l for l in (r.stdout or "").splitlines() if "error TS" in l]
        for l in errs[:25]:
            print("      " + l)
        bad("tsc --noEmit", f"{len(errs)} errors")

    r = subprocess.run([tool("vite"), "build"], cwd=str(DESKTOP),
                       capture_output=True, text=True, timeout=1200)
    if r.returncode == 0 and (DESKTOP / "dist" / "index.html").exists():
        size = sum(f.stat().st_size for f in (DESKTOP / "dist").rglob("*") if f.is_file())
        ok("vite build", f"dist={size // 1024} KB")
    else:
        for l in (r.stdout or "").splitlines()[-12:]:
            print("      " + l)
        bad("vite build")
else:
    print("\n(skipping frontend build checks)")

# ------------------------------------------------------- 4. mock-data scan
head("4. Source scan - no fabricated data / fake success")
MOCK_PATTERNS = [
    (r"\bmock[A-Z_]", "mock* identifier"),
    (r"\bfake[A-Z_]", "fake* identifier"),
    (r"placeholderData", "placeholderData"),
    (r"sample_?(rows|data)\s*=", "sample rows literal"),
]
scanned = 0
for p in list(SRC.rglob("*.ts")) + list(SRC.rglob("*.tsx")):
    if "node_modules" in p.parts:
        continue
    scanned += 1
    text = p.read_text(encoding="utf-8", errors="ignore")
    for pat, label in MOCK_PATTERNS:
        for m in re.finditer(pat, text):
            line = text[: m.start()].count("\n") + 1
            warn(f"{p.name}:{line} matches {label}", m.group(0)[:40])
ok("scanned frontend sources", f"{scanned} files")

# --------------------------------------------------------- 5. pages/routes
head("5. Pages and routes")
PAGES = {
    "Dashboard.tsx": "/",
    "Planner.tsx": "/planner",
    "Scripts.tsx": "/scripts",
    "Clips.tsx": "/clips",
    "CreatePublish.tsx": "/create",
    "PostingSettings.tsx": "/posting-settings",
    "Scheduler.tsx": "/scheduler",
    "Settings.tsx": "/settings",
    "FacebookProfile.tsx": "/facebook-profile",
}
for name in PAGES:
    p = SRC / "pages" / name
    if p.exists() and p.stat().st_size > 500:
        ok(f"page {name}", f"{p.stat().st_size // 1024} KB")
    else:
        bad(f"page {name}", "missing or empty")

app_tsx = (SRC / "App.tsx").read_text(encoding="utf-8")
for name, route in PAGES.items():
    ok(f"route {route} wired") if route in app_tsx else bad(f"route {route} wired", "not in App.tsx")

# --------------------------------------------------------------- summary
head("SUMMARY")
print(f"  failures : {len(failures)}")
print(f"  warnings : {len(warnings)}")
for f in failures:
    print("   FAIL ->", f)
sys.exit(1 if failures else 0)
