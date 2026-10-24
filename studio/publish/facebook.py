"""Facebook Page Reels via the official Graph API (Reels Publishing API).

Connect flow (no website needed):
  1. Create an app at developers.facebook.com (type Business), note App ID + App Secret.
  2. In Graph API Explorer pick that app, add permissions pages_show_list, pages_read_engagement,
     pages_manage_posts, click "Generate Access Token", copy the token.
  3. Paste App ID, App Secret and the token into TaoYongStudio -> it exchanges it for a
     long-lived Page token (does not expire) and lets you choose the Page.
"""
import os

import requests

from . import PublishError, delete_secret, load_secret, save_secret

GRAPH = "https://graph.facebook.com"
EXPLORER = "https://developers.facebook.com/tools/explorer/"


def _v(pcfg=None):
    return (pcfg or {}).get("graph_version") or "v26.0"


def _check(r):
    try:
        data = r.json()
    except Exception:
        raise PublishError("Facebook HTTP %s: %s" % (r.status_code, r.text[:300]))
    if r.status_code >= 400 or "error" in data:
        err = data.get("error", {})
        raise PublishError("Facebook: %s" % (err.get("message") or data))
    return data


def list_pages(app_id, app_secret, short_token, version="v26.0"):
    """Exchange a short user token for a long-lived one and return the Pages it manages."""
    r = requests.get("%s/%s/oauth/access_token" % (GRAPH, version), params={
        "grant_type": "fb_exchange_token", "client_id": app_id, "client_secret": app_secret,
        "fb_exchange_token": short_token}, timeout=30)
    long_user = _check(r)["access_token"]
    r = requests.get("%s/%s/me/accounts" % (GRAPH, version),
                     params={"access_token": long_user, "fields": "id,name,access_token,tasks", "limit": 100},
                     timeout=30)
    pages = _check(r).get("data", [])
    return [p for p in pages if "CREATE_CONTENT" in (p.get("tasks") or ["CREATE_CONTENT"])]


def save_page(page):
    save_secret("facebook_page", {"page_id": page["id"], "page_name": page["name"],
                                  "page_token": page["access_token"]})


def disconnect():
    delete_secret("facebook_page")


def connected():
    return bool(load_secret("facebook_page"))


def account_name():
    s = load_secret("facebook_page") or {}
    return s.get("page_name", "")


def post(video, meta, caption, pcfg, log):
    s = load_secret("facebook_page")
    if not s:
        raise PublishError("Facebook Page ยังไม่ได้เชื่อม")
    v = _v(pcfg)
    page, token = s["page_id"], s["page_token"]
    size = os.path.getsize(video)
    # 1) start
    r = requests.post("%s/%s/%s/video_reels" % (GRAPH, v, page),
                      json={"upload_phase": "start", "access_token": token}, timeout=60)
    vid = _check(r)["video_id"]
    # 2) upload bytes
    with open(video, "rb") as f:
        r = requests.post("https://rupload.facebook.com/video-upload/%s/%s" % (v, vid),
                          headers={"Authorization": "OAuth %s" % token, "offset": "0", "file_size": str(size),
                                   "Content-Type": "application/octet-stream"}, data=f, timeout=600)
    if not _check(r).get("success"):
        raise PublishError("Facebook upload failed: %s" % r.text[:300])
    log("    facebook uploaded %.1f MB" % (size / 1e6))
    # 3) publish
    r = requests.post("%s/%s/%s/video_reels" % (GRAPH, v, page), params={
        "access_token": token, "video_id": vid, "upload_phase": "finish", "video_state": "PUBLISHED",
        "description": caption[:2200], "title": meta.get("title", "")[:255],
        "is_ai_generated": "true" if meta.get("ai_generated", True) else "false"},
        timeout=120)
    if not _check(r).get("success"):
        raise PublishError("Facebook publish failed: %s" % r.text[:300])
    return {"status": "posted", "id": vid, "url": "https://www.facebook.com/reel/%s" % vid}
