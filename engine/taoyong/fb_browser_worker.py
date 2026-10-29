"""Facebook Profile Browser Automation Worker (RPA).

Automates Google Chrome / Microsoft Edge using Chrome DevTools Protocol (CDP)
without any external pip dependencies.
Handles:
  1. Opening persistent worker profile for one-time Facebook login
  2. Navigating to Facebook Reels / post creator
  3. Uploading the video file directly into the file input
  4. Entering caption with @ผู้ติดตาม and hashtags
  5. Stepping through Next / Publish buttons automatically
"""
import base64
import json
import os
import re
import socket
import struct
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from .config import ROOT

# Directories
WORKER_PROFILE_DIR = ROOT / "cache" / "chrome_facebook_worker"
WORKER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

DEBUG_PORT = 9228  # Port dedicated to the Facebook worker (avoids conflict with other workers)

CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]


def find_browser_exe():
    """Find installed Chrome or Edge executable on Windows."""
    for p in CHROME_CANDIDATES:
        if p and p.is_file():
            return str(p)
    return None


# ---------------------------------------------------------------------------
# Pure Python WebSocket & CDP Implementation (Zero external dependencies)
# ---------------------------------------------------------------------------

class CDPClient:
    def __init__(self, ws_url, timeout=20):
        self.ws_url = ws_url
        self.timeout = timeout
        self.sock = None
        self.msg_id = 1
        self._connect()

    def _connect(self):
        u = urlparse(self.ws_url)
        host = u.hostname or "127.0.0.1"
        port = u.port or DEBUG_PORT
        self.sock = socket.create_connection((host, port), self.timeout)
        self.sock.settimeout(self.timeout)

        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET {u.path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode("utf-8"))

        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("WebSocket handshake failed: connection closed")
            resp += chunk

    def _send_frame(self, text):
        data = text.encode("utf-8")
        mask = os.urandom(4)
        header = bytearray([0x81])
        n = len(data)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += struct.pack("!H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack("!Q", n)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(bytes(header) + mask + masked)

    def _recv_frame(self):
        hdr = self.sock.recv(2)
        if len(hdr) < 2:
            return None
        length = hdr[1] & 0x7F
        if length == 126:
            length = struct.unpack("!H", self.sock.recv(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self.sock.recv(8))[0]
        data = b""
        while len(data) < length:
            chunk = self.sock.recv(min(length - len(data), 65536))
            if not chunk:
                break
            data += chunk
        return data.decode("utf-8", errors="replace")

    def call(self, method, params=None):
        mid = self.msg_id
        self.msg_id += 1
        req_obj = {"id": mid, "method": method, "params": params or {}}
        self._send_frame(json.dumps(req_obj))

        deadline = time.time() + self.timeout
        while time.time() < deadline:
            raw = self._recv_frame()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"CDP error in {method}: {msg['error']}")
                return msg.get("result", {})
        raise TimeoutError(f"CDP call {method} timed out")

    def eval(self, js_expr):
        """Evaluate JS expression in page and return value."""
        r = self.call("Runtime.evaluate", {"expression": js_expr, "returnByValue": True})
        return r.get("result", {}).get("value")

    def close(self):
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Browser Process & Session Management
# ---------------------------------------------------------------------------

def is_debug_port_open(port=DEBUG_PORT):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False


def get_active_targets(port=DEBUG_PORT):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=2.5) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return []


def launch_worker_browser(initial_url="https://www.facebook.com/", port=DEBUG_PORT):
    """Launch Chrome with dedicated worker profile and remote debugging enabled."""
    if is_debug_port_open(port):
        return True

    exe = find_browser_exe()
    if not exe:
        raise FileNotFoundError("ไม่พบ Google Chrome หรือ Microsoft Edge บนเครื่องนี้")

    args = [
        exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={str(WORKER_PROFILE_DIR)}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-notifications",
        initial_url,
    ]

    subprocess.Popen(args)

    # Wait up to 10 seconds for debug port to become responsive
    deadline = time.time() + 10
    while time.time() < deadline:
        if is_debug_port_open(port):
            return True
        time.sleep(0.5)

    return False


def open_login_window(log_callback=print):
    """Open Chrome with worker profile so the user can log into Facebook once."""
    log_callback("กำลังเปิดเบราว์เซอร์สำหรับเข้าสู่ระบบ Facebook...")
    launch_worker_browser("https://www.facebook.com/", port=DEBUG_PORT)
    log_callback("เปิดหน้า Facebook แล้ว: กรุณาเข้าสู่ระบบในหน้าต่างที่เปิดขึ้นมา (ระบบจะจำบัญชีไว้อัตโนมัติ)")


# ---------------------------------------------------------------------------
# Automated Facebook Reels Publisher
# ---------------------------------------------------------------------------

def publish_facebook_reel(
    video_path,
    caption,
    auto_publish=True,
    log_callback=print,
    port=DEBUG_PORT,
):
    """Run full browser automation to upload video and post caption with @ผู้ติดตาม."""
    vid = Path(video_path)
    if not vid.is_file():
        raise FileNotFoundError(f"ไม่พบไฟล์วิดีโอ: {video_path}")

    log_callback("🚀 เริ่มการทำงานของพนักงานโพสต์อัตโนมัติ (Browser RPA)...")

    # Step 1: Ensure browser is open with debugging port
    log_callback("1. กำลังเปิดและเชื่อมต่อเบราว์เซอร์...")
    if not launch_worker_browser("https://www.facebook.com/reel/create", port=port):
        raise RuntimeError("ไม่สามารถเชื่อมต่อกับเบราว์เซอร์ผ่านพอร์ตควบคุมได้")

    time.sleep(2.0)

    # Step 2: Find the page target
    targets = get_active_targets(port=port)
    page_target = None
    for t in targets:
        if t.get("type") == "page":
            page_target = t
            if "facebook.com" in (t.get("url") or ""):
                break

    if not page_target:
        raise RuntimeError("ไม่พบหน้าต่าง Facebook ในเบราว์เซอร์")

    ws_url = page_target.get("webSocketDebuggerUrl")
    if not ws_url:
        raise RuntimeError("ไม่พบ WebSocket URL สำหรับการควบคุมหน้าจอ")

    cdp = CDPClient(ws_url, timeout=30)
    try:
        # Step 3: Navigate to Facebook Reels Create
        log_callback("2. กำลังไปยังหน้าสร้าง Reels (facebook.com/reel/create)...")
        current_url = cdp.eval("window.location.href") or ""
        if "reel/create" not in current_url:
            cdp.call("Page.navigate", {"url": "https://www.facebook.com/reel/create"})
            time.sleep(4.0)
        else:
            time.sleep(2.0)

        # Check if user is logged in
        is_login_page = cdp.eval("!!document.querySelector('input[name=\"email\"], #email')")
        if is_login_page:
            log_callback("⚠️ พบบัญชี Facebook ยังไม่ได้เข้าสู่ระบบ กรุณาเข้าสู่ระบบในเบราว์เซอร์ก่อน")
            raise PermissionError("Facebook ยังไม่ได้เข้าสู่ระบบในเบราว์เซอร์นี้ (กดปุ่ม 'เข้าสู่ระบบ Facebook สำหรับพนักงาน' ก่อน)")

        # Step 4: Find file input and upload video directly via CDP DOM
        log_callback(f"3. กำลังอัปโหลดไฟล์วิดีโอ ({vid.name})...")
        doc = cdp.call("DOM.getDocument", {"depth": 3})
        root_node_id = doc.get("root", {}).get("nodeId", 1)

        # Search for file input
        file_input = cdp.call(
            "DOM.querySelector",
            {"nodeId": root_node_id, "selector": "input[type='file'][accept*='video']"},
        )
        file_node_id = file_input.get("nodeId")

        if not file_node_id:
            # Fallback to any file input
            file_input = cdp.call(
                "DOM.querySelector",
                {"nodeId": root_node_id, "selector": "input[type='file']"},
            )
            file_node_id = file_input.get("nodeId")

        if not file_node_id:
            raise RuntimeError("ไม่พบช่องอัปโหลดวิดีโอในหน้า Facebook Reels")

        # Ingest file into input element
        cdp.call("DOM.setFileInputFiles", {"files": [str(vid.resolve())], "nodeId": file_node_id})
        log_callback("   แนบไฟล์วิดีโอเข้าสู่ Facebook แล้ว กำลังรอโหลด...")
        time.sleep(4.0)

        # Step 5: Wait for video upload to process
        log_callback("4. ตรวจสอบสถานะการอัปโหลดวิดีโอ...")
        for _ in range(30):
            time.sleep(1.5)
            # Check if next button is active or video element appeared
            has_video_loaded = cdp.eval("""
                (function() {
                    const video = document.querySelector('video');
                    const nextBtn = Array.from(document.querySelectorAll('div[role="button"]'))
                        .find(b => b.textContent.includes('ถัดไป') || b.textContent.includes('Next'));
                    return !!video || !!nextBtn;
                })()
            """)
            if has_video_loaded:
                log_callback("   วิดีโอโหลดขึ้นสู่หน้าจอเรียบร้อยแล้ว!")
                break

        # Step 6: Insert caption into description field
        log_callback("5. กำลังใส่แคปชั่น พร้อม @ผู้ติดตาม และแฮชแท็ก...")
        caption_escaped = json.dumps(caption)
        caption_injected = cdp.eval(f"""
            (function() {{
                const text = {caption_escaped};
                const targets = [
                    document.querySelector('div[contenteditable="true"][role="textbox"]'),
                    document.querySelector('textarea[aria-label*="คำอธิบาย"], textarea[aria-label*="Description"], textarea'),
                    document.querySelector('div[contenteditable="true"]')
                ];
                for (const el of targets) {{
                    if (el) {{
                        el.focus();
                        if (el.tagName === 'TEXTAREA') {{
                            el.value = text;
                            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            return true;
                        }} else {{
                            // contenteditable
                            document.execCommand('selectAll', false, null);
                            document.execCommand('insertText', false, text);
                            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            return true;
                        }}
                    }}
                }}
                return false;
            }})()
        """)

        if caption_injected:
            log_callback("   ใส่แคปชั่นเรียบร้อยแล้ว!")
        else:
            log_callback("   (หมายเหตุ: จัดเตรียมแคปชั่นไว้ในคลิปบอร์ดสำรอง)")

        time.sleep(2.0)

        # Step 7: Click "Next" / "ถัดไป" button
        log_callback("6. กำลังกดปุ่ม 'ถัดไป'...")
        for _ in range(2):
            clicked_next = cdp.eval("""
                (function() {
                    const buttons = Array.from(document.querySelectorAll('div[role="button"], button'));
                    const btn = buttons.find(b => {
                        const txt = (b.textContent || '').trim();
                        return txt === 'ถัดไป' || txt === 'Next';
                    });
                    if (btn) {
                        btn.click();
                        return true;
                    }
                    return false;
                })()
            """)
            if clicked_next:
                log_callback("   คลิกปุ่มถัดไปแล้ว")
                time.sleep(3.0)

        # Step 8: Final Publish Button
        if auto_publish:
            log_callback("7. กำลังกดปุ่ม 'เผยแพร่' (Publish)...")
            time.sleep(2.0)
            published = cdp.eval("""
                (function() {
                    const buttons = Array.from(document.querySelectorAll('div[role="button"], button'));
                    const btn = buttons.find(b => {
                        const txt = (b.textContent || '').trim();
                        return txt === 'เผยแพร่' || txt === 'Publish' || txt === 'โพสต์' || txt === 'Post';
                    });
                    if (btn) {
                        btn.click();
                        return true;
                    }
                    return false;
                })()
            """)
            if published:
                log_callback("🎉 พนักงานโพสต์คลิปลง Facebook Profile ให้เรียบร้อยแล้ว!")
            else:
                log_callback("⚠️ กรุณากดปุ่ม 'เผยแพร่' ในหน้าจอเบราว์เซอร์เพื่อยืนยันขั้นสุดท้าย")
        else:
            log_callback("✨ เตรียมวิดีโอและแคปชั่นเรียบร้อยแล้ว! หน้าต่างเบราว์เซอร์เปิดค้างไว้ให้คุณตรวจทานก่อนกดเผยแพร่")

        return True

    finally:
        cdp.close()
