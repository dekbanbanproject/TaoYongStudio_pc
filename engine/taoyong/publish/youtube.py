"""YouTube upload via the official YouTube Data API v3 (OAuth, your own Google Cloud project)."""
import json
import shutil
from pathlib import Path

from . import SECRETS, PublishError, delete_secret, load_secret, save_secret

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly"]
CLIENT = SECRETS / "youtube_client.json"


def set_client_file(path):
    SECRETS.mkdir(exist_ok=True)
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "installed" not in data:
        raise PublishError("ไฟล์นี้ไม่ใช่ OAuth client แบบ Desktop app (ต้องมีหัวข้อ \"installed\")")
    shutil.copy(path, CLIENT)


def _creds():
    tok = load_secret("youtube_token")
    if not tok:
        return None
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    creds = Credentials.from_authorized_user_info(tok, SCOPES)
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
        save_secret("youtube_token", json.loads(creds.to_json()) | {"channel": tok.get("channel", "")})
    return creds


def connect():
    """Opens the browser for Google sign-in (blocking). Returns the channel name."""
    if not CLIENT.exists():
        raise PublishError("เลือกไฟล์ client_secret.json ก่อน")
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", open_browser=True,
                                  success_message="เชื่อม YouTube สำเร็จ ปิดหน้านี้แล้วกลับไปที่ TaoYongStudio ได้เลย")
    data = json.loads(creds.to_json())
    save_secret("youtube_token", data)
    name = _channel_name(creds)
    data["channel"] = name
    save_secret("youtube_token", data)
    return name


def _channel_name(creds):
    from googleapiclient.discovery import build
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    r = yt.channels().list(part="snippet", mine=True).execute()
    items = r.get("items") or []
    return items[0]["snippet"]["title"] if items else "(ไม่พบช่อง)"


def disconnect():
    delete_secret("youtube_token")


def connected():
    return bool(load_secret("youtube_token"))


def account_name():
    t = load_secret("youtube_token") or {}
    return t.get("channel", "")


def post(video, meta, caption, pcfg, log):
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    creds = _creds()
    if not creds:
        raise PublishError("YouTube ยังไม่ได้เชื่อม")
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    title = meta.get("title", "")[:100]
    tags = [str(t)[:30] for t in (meta.get("tags") or [])][:15]
    body = {
        "snippet": {"title": title, "description": caption[:4900], "tags": tags,
                    "categoryId": str(pcfg.get("category_id", "27")), "defaultLanguage": "th",
                    "defaultAudioLanguage": "th"},
        "status": {"privacyStatus": pcfg.get("privacy", "public"),
                   "selfDeclaredMadeForKids": bool(meta.get("made_for_kids", True)),
                   "containsSyntheticMedia": bool(meta.get("ai_generated", True)),
                   "embeddable": True},
    }
    media = MediaFileUpload(str(video), mimetype="video/mp4", chunksize=4 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            log("    youtube %d%%" % int(status.progress() * 100))
    vid = resp["id"]
    # thumbnails only apply to regular videos; Shorts pick a frame automatically
    thumb = Path(video).parent / "thumb_horizontal.jpg"
    if pcfg.get("format") == "horizontal" and thumb.exists():
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumb))).execute()
        except Exception as e:  # needs a verified channel; not fatal
            log("    thumbnail not set: %s" % str(e)[:120])
    return {"status": "posted", "id": vid, "url": "https://youtu.be/%s" % vid,
            "privacy": body["status"]["privacyStatus"]}
