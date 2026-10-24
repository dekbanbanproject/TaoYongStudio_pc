"""Publisher ("employee #2"): posts finished clips to YouTube, a Facebook Page and TikTok (draft).

Every post is recorded in the clip's meta.json under "posts" so a clip is never posted twice
to the same platform. Settings live in config.json -> "publish"; tokens in the "secrets" folder.
"""
import datetime as dt
import json
from pathlib import Path

from ..config import ROOT

PLATFORMS = ["youtube", "facebook_page", "tiktok"]
MAX_SECONDS = {"facebook_page": 90, "tiktok": 600, "youtube": 12 * 3600}  # Reels 3-90 s, TikTok draft 10 min
LABEL = {"youtube": "YouTube", "facebook_page": "Facebook Page", "tiktok": "TikTok (ส่งเข้าแบบร่าง)",
         "facebook_profile": "Facebook ส่วนตัว"}

DEFAULTS = {
    "mode": "off",  # off | approved | auto
    "max_per_day": 2,
    "post_times": ["12:00", "18:00"],
    "youtube": {"enabled": False, "format": "vertical", "privacy": "public", "category_id": "27"},
    "facebook_page": {"enabled": False, "format": "vertical", "graph_version": "v26.0"},
    "tiktok": {"enabled": False, "format": "vertical", "redirect_port": 3455},
}

SECRETS = ROOT / "secrets"


class PublishError(Exception):
    pass


def settings(cfg):
    out = json.loads(json.dumps(DEFAULTS))
    user = cfg.get("publish", {}) or {}
    for k, v in user.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def load_secret(name):
    p = SECRETS / ("%s.json" % name)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def save_secret(name, data):
    SECRETS.mkdir(exist_ok=True)
    (SECRETS / ("%s.json" % name)).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def delete_secret(name):
    p = SECRETS / ("%s.json" % name)
    if p.exists():
        p.unlink()


def module(platform):
    if platform == "youtube":
        from . import youtube as m
    elif platform == "facebook_page":
        from . import facebook as m
    elif platform == "tiktok":
        from . import tiktok as m
    else:
        raise PublishError("unknown platform %s" % platform)
    return m


def is_connected(platform):
    try:
        return module(platform).connected()
    except Exception:
        return False


def account_name(platform):
    try:
        return module(platform).account_name()
    except Exception:
        return ""


# ------------------------------------------------------------------ clips
def all_clips():
    base = ROOT / "output"
    out = []
    if not base.exists():
        return out
    for day in sorted([d for d in base.iterdir() if d.is_dir()]):
        for clip in sorted([c for c in day.iterdir() if c.is_dir()]):
            m = clip / "meta.json"
            if m.exists():
                try:
                    out.append((clip, json.loads(m.read_text(encoding="utf-8"))))
                except Exception:
                    pass
    return out


def write_meta(folder, meta):
    (Path(folder) / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def posted_today(platform):
    today = dt.date.today().isoformat()
    n = 0
    for _, meta in all_clips():
        p = (meta.get("posts") or {}).get(platform) or {}
        if p.get("status") in ("posted", "draft_sent") and str(p.get("at", "")).startswith(today):
            n += 1
    return n


def eligible(meta, mode):
    """Is this clip allowed to be posted automatically under the given mode?"""
    if meta.get("status") in ("rejected", "posted_manual"):
        return False
    if meta.get("needs_review"):
        return False  # fallback voice etc. - a person must look first
    if mode == "approved":
        return meta.get("status") == "approved"
    if mode == "auto":
        return meta.get("status") in ("ready_for_approval", "approved")
    return False


def caption(meta, platform):
    prepared = (meta.get("platform_captions") or {}).get(platform) or meta
    tags = prepared.get("tags") or []
    hashtags = " ".join("#" + str(t).replace(" ", "") for t in tags[:8])
    desc = (prepared.get("description") or "").strip()
    if platform == "youtube":
        return desc + ("\n\n" + hashtags if hashtags else "")
    return "%s\n\n%s\n\n%s" % (prepared.get("title", ""), desc, hashtags)


def post_clip(folder, platform, cfg, log=print, force=False):
    """Post one clip to one platform and record the result in meta.json."""
    folder = Path(folder)
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    posts = meta.setdefault("posts", {})
    prev = posts.get(platform) or {}
    if prev.get("status") in ("posted", "draft_sent") and not force:
        log("  %s: already posted (%s)" % (LABEL[platform], prev.get("url") or prev.get("id")))
        return prev
    st = settings(cfg)
    pcfg = st.get(platform, {})
    fmt = (meta.get("platform_formats") or {}).get(platform) or pcfg.get("format", "vertical")
    if platform == "youtube" and float(meta.get("duration_seconds", 0)) > 180:
        fmt = "horizontal"  # Shorts are limited to 3 minutes
    name = (meta.get("files") or {}).get(fmt)
    if not name or not (folder / name).exists():
        other = "horizontal" if fmt == "vertical" else "vertical"
        name = (meta.get("files") or {}).get(other)
        if not name or not (folder / name).exists():
            raise PublishError("no video file in %s" % folder)
    video = folder / name
    dur = float(meta.get("duration_seconds", 0))
    if dur > MAX_SECONDS.get(platform, 1e9):
        raise PublishError("%s: clip is %.0f s, longer than the %d s this platform accepts" % (
            LABEL[platform], dur, MAX_SECONDS[platform]))
    m = module(platform)
    if not m.connected():
        raise PublishError("%s is not connected" % LABEL[platform])
    log("  %s: uploading %s" % (LABEL[platform], video.name))
    try:
        effective = dict(meta)
        effective.update((meta.get("platform_captions") or {}).get(platform) or {})
        res = m.post(video, effective, caption(meta, platform), pcfg, log)
        rec = dict(res, at=dt.datetime.now().isoformat(timespec="seconds"))
    except Exception as e:
        rec = {"status": "failed", "error": str(e)[:500], "at": dt.datetime.now().isoformat(timespec="seconds")}
        posts[platform] = rec
        write_meta(folder, meta)
        raise
    posts[platform] = rec
    write_meta(folder, meta)
    log("  %s: %s %s" % (LABEL[platform], rec.get("status"), rec.get("url") or rec.get("id") or ""))
    return rec


def run_auto(cfg, log=print, per_run=1):
    """Called by the Windows scheduled task at each post time. Posts up to per_run clip per platform."""
    st = settings(cfg)
    mode = st.get("mode", "off")
    if mode == "off":
        log("auto post is OFF - nothing to do")
        return {"posted": 0}
    clips = all_clips()
    total = 0
    for platform in PLATFORMS:
        pcfg = st.get(platform, {})
        if not pcfg.get("enabled"):
            continue
        if not is_connected(platform):
            log("%s: enabled but not connected - skipped" % LABEL[platform])
            continue
        room = int(st.get("max_per_day", 2)) - posted_today(platform)
        if room <= 0:
            log("%s: daily limit reached" % LABEL[platform])
            continue
        todo = min(room, per_run)
        # oldest eligible clip first, skipping clips that failed on this platform twice
        for folder, meta in clips:
            if todo <= 0:
                break
            p = (meta.get("posts") or {}).get(platform) or {}
            if p.get("status") in ("posted", "draft_sent"):
                continue
            if p.get("status") == "failed" and p.get("fail_count", 1) >= 2:
                continue
            if not eligible(meta, mode):
                continue
            if float(meta.get("duration_seconds", 0)) > MAX_SECONDS.get(platform, 1e9):
                continue  # e.g. a 20-minute compilation is YouTube-only
            log("%s <- %s" % (LABEL[platform], meta.get("title")))
            try:
                post_clip(folder, platform, cfg, log)
                total += 1
                todo -= 1
            except Exception as e:
                log("  FAILED: %s" % e)
                meta2 = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
                rec = meta2.setdefault("posts", {}).setdefault(platform, {})
                rec["fail_count"] = int(p.get("fail_count", 0)) + 1
                write_meta(folder, meta2)
    log("auto post finished: %d post(s)" % total)
    return {"posted": total}
