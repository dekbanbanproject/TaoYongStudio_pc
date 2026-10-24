"""TikTok via the official Content Posting API, "upload to inbox" mode (scope video.upload).

The clip arrives in the TikTok app as a draft notification; the owner opens it, adds the caption
(TaoYongStudio copies it for you) and taps Post. TikTok's rules require the creator to review each
post, so fully automatic public posting is not offered.

Desktop login uses PKCE with a hex SHA256 code challenge and a localhost redirect URI that must be
registered in the TikTok developer portal, e.g. http://127.0.0.1:3455/callback/
"""
import hashlib
import http.server
import os
import secrets
import threading
import time
import urllib.parse
import webbrowser

import requests

from . import PublishError, delete_secret, load_secret, save_secret

AUTH = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN = "https://open.tiktokapis.com/v2/oauth/token/"
INIT = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
STATUS = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
USER = "https://open.tiktokapis.com/v2/user/info/"
CREATOR_INFO = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
DIRECT_INIT = "https://open.tiktokapis.com/v2/post/publish/video/init/"
SCOPES = "user.info.basic,video.upload,video.publish"

# privacy_level values TikTok returns -> label shown to the owner (no default is ever pre-selected)
PRIVACY_LABELS = {"PUBLIC_TO_EVERYONE": "ทุกคน (สาธารณะ)", "MUTUAL_FOLLOW_FRIENDS": "เพื่อน (ติดตามกันและกัน)",
                  "FOLLOWER_OF_CREATOR": "ผู้ติดตามของฉัน", "SELF_ONLY": "เฉพาะฉัน (ส่วนตัว)"}


# error codes TikTok returns that need an action from the owner, explained in Thai
ERROR_HELP = {
    "unaudited_client_can_only_post_to_private_accounts":
        "แอปยังไม่ผ่าน audit จึงโพสต์ตรงได้เฉพาะบัญชี TikTok ที่ตั้งเป็น \"บัญชีส่วนตัว\" และเลือก \"เฉพาะฉัน\"",
    "privacy_level_option_mismatch": "ตัวเลือก \"ใครดูได้\" ไม่ตรงกับที่บัญชีนี้อนุญาต",
    "spam_risk_too_many_posts": "วันนี้โพสต์ถึงจำนวนที่ TikTok จำกัดแล้ว",
    "spam_risk_user_banned_from_posting": "บัญชีนี้ถูก TikTok ระงับการโพสต์ชั่วคราว",
    "scope_not_authorized": "ยังไม่ได้สิทธิ์นี้ ให้กดยกเลิกการเชื่อมแล้วเชื่อม TikTok ใหม่",
}


def _err(e):
    code = e.get("code", "") if isinstance(e, dict) else ""
    msg = e.get("message", e) if isinstance(e, dict) else e
    return "TikTok [%s]: %s" % (code, ERROR_HELP.get(code, msg))


def redirect_uri(port):
    return "http://127.0.0.1:%d/callback/" % int(port)


def save_app(client_key, client_secret):
    save_secret("tiktok_app", {"client_key": client_key.strip(), "client_secret": client_secret.strip()})


def connect(port=3455, timeout=300):
    """Open TikTok login in the browser and wait for the localhost callback (blocking)."""
    app = load_secret("tiktok_app")
    if not app:
        raise PublishError("ใส่ Client key และ Client secret ก่อน")
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = hashlib.sha256(verifier.encode()).hexdigest()
    state = secrets.token_hex(8)
    got = {}

    done = threading.Event()

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).items()}
            # Only the callback for THIS attempt counts. Old tabs from an earlier attempt (other state),
            # favicon requests and prefetches are answered but ignored, so they can't end the wait early.
            mine = q.get("state") == state and ("code" in q or "error" in q)
            if mine:
                got.update(q)
                msg = "เชื่อม TikTok สำเร็จ ปิดหน้านี้แล้วกลับไปที่ TaoYongStudio ได้เลย" if "code" in q else                     "เชื่อม TikTok ไม่สำเร็จ: %s" % q.get("error_description", q.get("error", ""))
            else:
                msg = "หน้านี้มาจากการเชื่อมครั้งก่อน กรุณาใช้หน้าที่เพิ่งเปิดล่าสุด"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(("<h2 style='font-family:sans-serif'>%s</h2>" % msg).encode("utf-8"))
            if mine:
                done.set()

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", int(port)), H)
    srv.timeout = 1
    deadline = time.time() + timeout

    def serve():
        while not done.is_set() and time.time() < deadline:
            srv.handle_request()

    th = threading.Thread(target=serve, daemon=True)
    th.start()
    url = AUTH + "?" + urllib.parse.urlencode({
        "client_key": app["client_key"], "response_type": "code", "scope": SCOPES,
        "redirect_uri": redirect_uri(port), "state": state, "code_challenge": challenge,
        "code_challenge_method": "S256"})
    webbrowser.open(url)
    th.join(timeout + 2)
    srv.server_close()
    if "code" not in got:
        raise PublishError("ไม่ได้รับการอนุญาตจาก TikTok (%s)" % (got.get("error_description") or "หมดเวลา"))
    if got.get("state") != state:
        raise PublishError("state ไม่ตรงกัน ลองใหม่อีกครั้ง")
    r = requests.post(TOKEN, data={
        "client_key": app["client_key"], "client_secret": app["client_secret"], "code": got["code"],
        "grant_type": "authorization_code", "redirect_uri": redirect_uri(port), "code_verifier": verifier},
        headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
    tok = r.json()
    if "access_token" not in tok:
        raise PublishError("TikTok token: %s" % tok)
    tok["obtained"] = int(time.time())
    save_secret("tiktok_token", tok)
    name = _user_name(tok["access_token"])
    tok["display_name"] = name
    save_secret("tiktok_token", tok)
    return name


def _user_name(access):
    try:
        r = requests.get(USER, params={"fields": "display_name"},
                         headers={"Authorization": "Bearer %s" % access}, timeout=30)
        return r.json().get("data", {}).get("user", {}).get("display_name", "")
    except Exception:
        return ""


def _access():
    tok = load_secret("tiktok_token")
    app = load_secret("tiktok_app")
    if not tok or not app:
        raise PublishError("TikTok ยังไม่ได้เชื่อม")
    if time.time() > tok.get("obtained", 0) + int(tok.get("expires_in", 0)) - 600:
        r = requests.post(TOKEN, data={
            "client_key": app["client_key"], "client_secret": app["client_secret"],
            "grant_type": "refresh_token", "refresh_token": tok["refresh_token"]},
            headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
        new = r.json()
        if "access_token" not in new:
            raise PublishError("TikTok ต้องเชื่อมใหม่ (%s)" % new.get("error_description", new))
        new["obtained"] = int(time.time())
        new["display_name"] = tok.get("display_name", "")
        save_secret("tiktok_token", new)
        tok = new
    return tok["access_token"]


def disconnect():
    delete_secret("tiktok_token")


def connected():
    return bool(load_secret("tiktok_token")) and bool(load_secret("tiktok_app"))


def account_name():
    return (load_secret("tiktok_token") or {}).get("display_name", "")


def post(video, meta, caption, pcfg, log):
    access = _access()
    size = os.path.getsize(video)
    r = requests.post(INIT, json={"source_info": {"source": "FILE_UPLOAD", "video_size": size,
                                                  "chunk_size": size, "total_chunk_count": 1}},
                      headers={"Authorization": "Bearer %s" % access,
                               "Content-Type": "application/json; charset=UTF-8"}, timeout=60)
    data = r.json()
    if data.get("error", {}).get("code", "ok") != "ok":
        raise PublishError(_err(data["error"]))
    up = data["data"]["upload_url"]
    pid = data["data"].get("publish_id", "")
    with open(video, "rb") as f:
        r = requests.put(up, data=f, headers={"Content-Type": "video/mp4", "Content-Length": str(size),
                                              "Content-Range": "bytes 0-%d/%d" % (size - 1, size)}, timeout=600)
    if r.status_code >= 300:
        raise PublishError("TikTok upload HTTP %s: %s" % (r.status_code, r.text[:200]))
    log("    tiktok draft sent - open the TikTok app inbox to finish posting")
    return {"status": "draft_sent", "id": pid, "url": "",
            "note": "เปิดแอป TikTok > กล่องข้อความ (Inbox) แล้วกดแจ้งเตือนเพื่อโพสต์ต่อ"}


def has_direct_post():
    """True when the saved token was granted video.publish (older tokens only have video.upload)."""
    tok = load_secret("tiktok_token") or {}
    return "video.publish" in str(tok.get("scope", ""))


def creator_info():
    """Ask TikTok who is posting and which options they may use. Must be shown to the owner before posting."""
    r = requests.post(CREATOR_INFO, headers={"Authorization": "Bearer %s" % _access(),
                                             "Content-Type": "application/json; charset=UTF-8"}, timeout=30)
    data = r.json()
    if data.get("error", {}).get("code", "ok") != "ok":
        raise PublishError(_err(data["error"]))
    return data.get("data", {})


def direct_post(video, title, privacy, disable_comment=True, disable_duet=True, disable_stitch=True,
                ai_generated=True, brand_organic=False, brand_content=False, log=print, wait=180):
    """Direct Post: publish the clip to the owner's profile with the options chosen on screen."""
    access = _access()
    size = os.path.getsize(video)
    post_info = {"title": title[:2200], "privacy_level": privacy, "disable_comment": bool(disable_comment),
                 "disable_duet": bool(disable_duet), "disable_stitch": bool(disable_stitch),
                 "video_cover_timestamp_ms": 1000, "is_aigc": bool(ai_generated),
                 "brand_organic_toggle": bool(brand_organic), "brand_content_toggle": bool(brand_content)}
    headers = {"Authorization": "Bearer %s" % access, "Content-Type": "application/json; charset=UTF-8"}
    r = requests.post(DIRECT_INIT, json={"post_info": post_info, "source_info": {
        "source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1}},
        headers=headers, timeout=60)
    data = r.json()
    if data.get("error", {}).get("code", "ok") != "ok":
        raise PublishError(_err(data["error"]))
    up = data["data"]["upload_url"]
    pid = data["data"].get("publish_id", "")
    with open(video, "rb") as f:
        r = requests.put(up, data=f, headers={"Content-Type": "video/mp4", "Content-Length": str(size),
                                              "Content-Range": "bytes 0-%d/%d" % (size - 1, size)}, timeout=600)
    if r.status_code >= 300:
        raise PublishError("TikTok upload HTTP %s: %s" % (r.status_code, r.text[:200]))
    log("    tiktok direct post uploaded, waiting for TikTok to process")
    end = time.time() + wait
    state = "PROCESSING_UPLOAD"
    while time.time() < end:
        time.sleep(4)
        s = requests.post(STATUS, json={"publish_id": pid}, headers=headers, timeout=30).json()
        state = (s.get("data") or {}).get("status", state)
        if state == "PUBLISH_COMPLETE":
            return {"status": "posted", "id": pid, "url": "", "privacy": privacy,
                    "note": "โพสต์ลงโปรไฟล์ TikTok แล้ว"}
        if state == "FAILED":
            raise PublishError("TikTok ปฏิเสธคลิป: %s" % (s.get("data") or {}).get("fail_reason", "unknown"))
    return {"status": "posted", "id": pid, "url": "", "privacy": privacy,
            "note": "ส่งขึ้นแล้ว TikTok ยังประมวลผล (%s) ดูในโปรไฟล์ภายในไม่กี่นาที" % state}
