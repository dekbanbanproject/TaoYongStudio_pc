"""JSON API for the TaoYongStudio desktop shell.

Every handler returns a plain dict that is serialised to JSON. Handlers read and
write the real engine data (scripts/, plans/, output/, config.json, secrets/).
Nothing here fabricates content: when an external integration is not connected
the payload says so explicitly.

Handler signature:  fn(query: dict, body: dict) -> dict
"""
import datetime as dt
import json
import os
import re
import shutil
import threading
import time
import traceback
from pathlib import Path

from .config import ROOT, load as load_cfg

ROUTES = {}

# --------------------------------------------------------------------- jobs
_JOBS = {}
_JOBS_LOCK = threading.Lock()


def route(method, path):
    def deco(fn):
        ROUTES[(method.upper(), path)] = fn
        return fn
    return deco


def _job_new(kind, label):
    jid = "job-%d-%d" % (int(time.time() * 1000) % 100000000, len(_JOBS))
    with _JOBS_LOCK:
        _JOBS[jid] = {
            "id": jid,
            "kind": kind,
            "label": label,
            "status": "running",
            "progress": 0,
            "log": [],
            "result": None,
            "error": None,
            "startedAt": dt.datetime.now().isoformat(timespec="seconds"),
            "finishedAt": None,
            "_cancel": False,
        }
    return jid


def _job_log(jid, line):
    with _JOBS_LOCK:
        j = _JOBS.get(jid)
        if not j:
            return
        j["log"].append(str(line))
        if len(j["log"]) > 800:
            del j["log"][:200]
        m = re.search(r"(\d{1,3})%", str(line))
        if m:
            try:
                j["progress"] = max(j["progress"], min(100, int(m.group(1))))
            except Exception:
                pass


def _job_done(jid, result=None, error=None):
    with _JOBS_LOCK:
        j = _JOBS.get(jid)
        if not j:
            return
        j["status"] = "failed" if error else "done"
        j["result"] = result
        j["error"] = error
        j["progress"] = 100 if not error else j["progress"]
        j["finishedAt"] = dt.datetime.now().isoformat(timespec="seconds")


def _job_public(j):
    return {k: v for k, v in j.items() if not k.startswith("_")}


# ------------------------------------------------------------------ helpers
def _read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _rel(path):
    """Absolute path as a string (the Rust layer turns it into an asset URL)."""
    try:
        return str(Path(path).resolve())
    except Exception:
        return str(path)


def _safe_rel(root: Path, candidate: str) -> Path:
    """Resolve a client supplied path and refuse anything outside the workspace."""
    p = Path(candidate)
    if not p.is_absolute():
        p = root / p
    p = p.resolve()
    try:
        p.relative_to(root.resolve())
    except ValueError:
        raise ValueError("เส้นทางอยู่นอกโฟลเดอร์ของโปรแกรม")
    return p


def _script_summary(path: Path, sc: dict, group: str):
    scenes = sc.get("scenes") or []
    beats = sum(len(s.get("beats") or []) for s in scenes)
    return {
        "id": sc.get("id") or path.stem,
        "title": sc.get("title") or path.stem,
        "description": sc.get("description") or "",
        "genre": sc.get("genre") or "",
        "tags": sc.get("tags") or [],
        "characters": sc.get("characters") or [],
        "sceneCount": len(scenes),
        "beatCount": beats,
        "backgrounds": sorted({s.get("background", "") for s in scenes if s.get("background")}),
        "group": group,
        "path": _rel(path),
        "fileName": path.name,
        "modifiedAt": dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
        "requestId": sc.get("request_id") or "",
        "review": "pending",
        "formats": sc.get("formats") or [],
        "thumb": _rel(path.parent.parent / "samples" / "thumb.png") if False else "",
    }


def _script_folder(root: Path, group: str):
    return {
        "inbox": root / "scripts" / "inbox",
        "done": root / "scripts" / "done",
        "samples": root / "scripts" / "samples",
        "removed": root / "scripts" / "removed",
        "compilations": root / "scripts" / "compilations",
    }.get(group, root / "scripts" / "inbox")


def _list_scripts(root: Path, group: str):
    out = []
    folder = _script_folder(root, group)
    if not folder.exists():
        return out
    for p in sorted(folder.rglob("*.json")):
        sc = _read_json(p)
        if not isinstance(sc, dict):
            continue
        out.append(_script_summary(p, sc, group))
    return out


def _clip_entries(root: Path):
    out = []
    base = root / "output"
    if not base.exists():
        return out
    for day in sorted([d for d in base.iterdir() if d.is_dir()], reverse=True):
        if day.name in ("removed", "trash", ".trash"):
            continue
        for clip in sorted([c for c in day.iterdir() if c.is_dir()]):
            meta = _read_json(clip / "meta.json")
            if not isinstance(meta, dict):
                continue
            files = meta.get("files") or {}
            thumbs = []
            for v in files.values():
                if isinstance(v, str) and v.lower().endswith((".jpg", ".jpeg", ".png")):
                    thumbs.append(_rel(clip / v))
            out.append({
                "folder": _rel(clip),
                "folderName": clip.name,
                "day": day.name,
                "id": meta.get("id") or clip.name,
                "title": meta.get("title") or clip.name,
                "description": meta.get("description") or "",
                "tags": meta.get("tags") or [],
                "characters": meta.get("characters") or [],
                "genre": meta.get("genre") or "",
                "durationSeconds": meta.get("duration_seconds") or 0,
                "status": meta.get("status") or "",
                "needsReview": meta.get("needs_review") or [],
                "files": {k: _rel(clip / v) if isinstance(v, str) else v for k, v in files.items()},
                "thumb": thumbs[0] if thumbs else "",
                "resolution": meta.get("resolution") or "",
                "fps": meta.get("fps") or 0,
                "engineType": meta.get("engine_type") or "",
                "voiceEngines": meta.get("voice_engines") or [],
                "createdAt": dt.datetime.fromtimestamp(clip.stat().st_mtime).isoformat(timespec="seconds"),
                "renderSeconds": meta.get("render_seconds") or 0,
                "posts": meta.get("posts") or {},
                "platformCaptions": meta.get("platform_captions") or {},
                "madeForKids": meta.get("made_for_kids", True),
            })
    return out


# =========================================================== health / system
@route("GET", "/api/health")
def health(query, body):
    return {
        "ok": True,
        "root": str(ROOT),
        "python": os.path.basename(os.sys.executable),
        "version": "2.0.0",
        "time": dt.datetime.now().isoformat(timespec="seconds"),
    }


@route("GET", "/api/hardware")
def hardware(query, body):
    from . import hardware as hw
    try:
        info = hw.detect_hardware()
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "hardware": info}


def _system_states(root: Path):
    """Real capability probes — never faked."""
    states = {}

    # AI providers
    try:
        from . import credential_store
        has_gemini = bool(credential_store.has_key())
    except Exception:
        has_gemini = False
    states["ai"] = {
        "ready": has_gemini,
        "label": "พร้อมใช้งาน" if has_gemini else "ยังไม่ได้ตั้งค่า Gemini API Key",
        "detail": "Gemini API" if has_gemini else "ต้องตั้งค่า Gemini API Key ในหน้าตั้งค่า",
    }

    # Python engine
    states["python"] = {
        "ready": True,
        "label": "ทำงานอยู่",
        "detail": "Python %s" % os.sys.version.split()[0],
    }

    # TTS
    cfg = load_cfg()
    engines = (cfg.get("tts") or {}).get("engines") or []
    azure_key = (cfg.get("tts") or {}).get("azure_key") or ""
    tts_ready = bool(azure_key) or "edge" in engines or "sapi" in engines
    states["tts"] = {
        "ready": bool(tts_ready),
        "label": "พร้อมใช้งาน" if tts_ready else "ยังไม่มีเสียงที่ใช้ได้",
        "detail": ", ".join(engines) if engines else "ไม่ได้ตั้งค่าเสียง",
    }

    # Renderer
    try:
        from . import hardware as hw
        info = hw.detect_hardware()
        encoders = info.get("encoders") or {}
        ok_enc = [k for k, v in encoders.items() if (v or {}).get("ok")]
        states["renderer"] = {
            "ready": bool(ok_enc),
            "label": "พร้อมเรนเดอร์" if ok_enc else "ไม่พบตัวเข้ารหัสวิดีโอ",
            "detail": ", ".join(ok_enc) if ok_enc else "ตรวจไม่พบ encoder ที่ใช้ได้",
        }
        states["gpu"] = {
            "ready": bool(info.get("gpus")),
            "label": "พบ %d การ์ดกราฟิกส์" % len(info.get("gpus") or []),
            "detail": ", ".join(g.get("name", "") for g in (info.get("gpus") or [])[:2]) or "ไม่พบ GPU",
        }
    except Exception as e:
        states["renderer"] = {"ready": False, "label": "ตรวจสอบไม่สำเร็จ", "detail": str(e)}
        states["gpu"] = {"ready": False, "label": "ตรวจสอบไม่สำเร็จ", "detail": str(e)}

    # Facebook account
    try:
        from .publish import facebook as fb
        fb_ok = bool(fb.connected())
        fb_name = fb.account_name() if fb_ok else ""
    except Exception:
        fb_ok, fb_name = False, ""
    states["facebook"] = {
        "ready": fb_ok,
        "label": "เชื่อมต่อแล้ว" if fb_ok else "ยังไม่ได้เชื่อมต่อ",
        "detail": fb_name or "เชื่อมต่อบัญชีในหน้าตั้งค่าโพสต์",
    }

    return states


@route("GET", "/api/dashboard")
def dashboard(query, body):
    root = ROOT
    cfg = load_cfg()

    inbox = _list_scripts(root, "inbox")
    done = _list_scripts(root, "done")
    clips = _clip_entries(root)

    today = dt.date.today().isoformat()
    clips_today = [c for c in clips if c["day"] == today]
    needs_review = [c for c in clips if c.get("needsReview")]

    # next scheduled post
    next_post = None
    try:
        from . import ai_worker_scheduler as sched
        data = sched.load_schedule()
        times = sched.normalize_times((data or {}).get("times") or [])
        hhmm, countdown = sched.get_next_run(times)
        if hhmm:
            next_post = {"at": hhmm, "label": hhmm, "countdown": countdown}
    except Exception:
        next_post = None

    # recent activity from real files
    activity = []
    for p in sorted(root.glob("plans/requests/*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:4]:
        d = _read_json(p) or {}
        activity.append({
            "title": "คำขอไอเดีย %s" % (d.get("provider") or "AI"),
            "detail": d.get("topic") or d.get("title") or p.stem,
            "at": dt.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
            "kind": "planner",
        })
    for c in clips[:4]:
        activity.append({
            "title": "คลิป %s" % c["title"][:40],
            "detail": "สร้างเมื่อ %s" % c["day"],
            "at": c["createdAt"],
            "kind": "clip",
        })
    activity.sort(key=lambda a: a["at"], reverse=True)

    return {
        "ok": True,
        "stats": {
            "scriptsPending": len(inbox),
            "scriptsDone": len(done),
            "clipsToday": len(clips_today),
            "clipsTotal": len(clips),
            "clipsNeedsReview": len(needs_review),
        },
        "nextPost": next_post,
        "systems": _system_states(root),
        "activity": activity[:8],
        "channelName": cfg.get("channel_name") or "",
    }


# ================================================================== scripts
@route("GET", "/api/scripts")
def scripts_list(query, body):
    root = ROOT
    return {
        "ok": True,
        "inbox": _list_scripts(root, "inbox"),
        "done": _list_scripts(root, "done"),
        "samples": _list_scripts(root, "samples"),
    }


@route("GET", "/api/scripts/detail")
def scripts_detail(query, body):
    root = ROOT
    path = _safe_rel(root, query.get("path", ""))
    sc = _read_json(path)
    if not isinstance(sc, dict):
        raise ValueError("อ่านไฟล์บทไม่สำเร็จ")
    return {"ok": True, "script": sc, "path": _rel(path)}


@route("POST", "/api/scripts/import")
def scripts_import(query, body):
    root = ROOT
    text = (body.get("text") or "").strip()
    if not text:
        raise ValueError("ไม่พบข้อความ JSON ที่นำเข้า")
    try:
        sc = json.loads(text)
    except Exception as e:
        raise ValueError("JSON ไม่ถูกต้อง: %s" % e)
    if not isinstance(sc, dict) or "title" not in sc:
        raise ValueError("ไฟล์บทต้องมีฟิลด์ title")

    from . import script as scriptmod
    err, warn = scriptmod.validate(sc)
    sid = (sc.get("id") or scriptmod.slugify(sc.get("title", "clip"))).strip()
    sc.setdefault("id", sid)
    sc["id"] = sid
    dest = root / "scripts" / "inbox" / ("%s.json" % sid)
    _write_json(dest, sc)
    return {"ok": True, "path": _rel(dest), "warnings": warn, "errors": err, "id": sid}


@route("POST", "/api/scripts/add-sample")
def scripts_add_sample(query, body):
    root = ROOT
    src = root / "scripts" / "samples"
    dst = root / "scripts" / "inbox"
    if not src.exists():
        raise ValueError("ไม่พบโฟลเดอร์ตัวอย่างบท")
    dst.mkdir(parents=True, exist_ok=True)
    added = []
    for p in sorted(src.glob("*.json")):
        target = dst / p.name
        shutil.copy2(p, target)
        added.append(target.name)
    return {"ok": True, "added": added, "count": len(added)}


@route("POST", "/api/scripts/delete")
def scripts_delete(query, body):
    root = ROOT
    paths = body.get("paths") or []
    removed = []
    trash = root / "scripts" / "removed"
    trash.mkdir(parents=True, exist_ok=True)
    for p in paths:
        try:
            src = _safe_rel(root, p)
        except ValueError:
            continue
        if not src.exists():
            continue
        dest = trash / src.name
        i = 1
        while dest.exists():
            dest = trash / ("%s.%d.json" % (src.stem, i))
            i += 1
        shutil.move(str(src), str(dest))
        removed.append(dest.name)
    return {"ok": True, "removed": removed, "count": len(removed)}


@route("POST", "/api/scripts/send-to-flow")
def scripts_send_to_flow(query, body):
    """Build the Google Flow prompt for a script and open flow.google.com."""
    root = ROOT
    path = _safe_rel(root, body.get("path", ""))
    sc = _read_json(path)
    if not isinstance(sc, dict):
        raise ValueError("อ่านไฟล์บทไม่สำเร็จ")
    from . import platform_workspace as pw
    prompts = pw.flow_prompts_from_script(sc, fmt=body.get("format") or "vertical")
    return {"ok": True, "prompts": prompts, "title": sc.get("title", ""),
            "flowUrl": "https://flow.google.com/"}


# =================================================================== clips
@route("GET", "/api/clips")
def clips_list(query, body):
    return {"ok": True, "clips": _clip_entries(ROOT)}


@route("GET", "/api/clips/detail")
def clips_detail(query, body):
    root = ROOT
    folder = _safe_rel(root, query.get("folder", ""))
    meta = _read_json(folder / "meta.json")
    if not isinstance(meta, dict):
        raise ValueError("ไม่พบไฟล์ meta.json ของคลิป")
    files = meta.get("files") or {}
    return {
        "ok": True,
        "meta": meta,
        "folder": _rel(folder),
        "files": {k: _rel(folder / v) if isinstance(v, str) else v for k, v in files.items()},
    }


@route("POST", "/api/clips/delete")
def clips_delete(query, body):
    root = ROOT
    folders = body.get("folders") or []
    trash = root / "output" / "removed"
    trash.mkdir(parents=True, exist_ok=True)
    removed = []
    for f in folders:
        try:
            src = _safe_rel(root, f)
        except ValueError:
            continue
        if not src.is_dir():
            continue
        dest = trash / src.name
        i = 1
        while dest.exists():
            dest = trash / ("%s.%d" % (src.name, i))
            i += 1
        shutil.move(str(src), str(dest))
        removed.append(dest.name)
    return {"ok": True, "removed": removed, "count": len(removed)}


@route("POST", "/api/clips/status")
def clips_status(query, body):
    root = ROOT
    folder = _safe_rel(root, body.get("folder", ""))
    meta = _read_json(folder / "meta.json")
    if not isinstance(meta, dict):
        raise ValueError("ไม่พบไฟล์ meta.json ของคลิป")
    meta["status"] = body.get("status") or meta.get("status")
    _write_json(folder / "meta.json", meta)
    return {"ok": True, "status": meta["status"]}


# ================================================================= planner
@route("GET", "/api/planner/ideas")
def planner_ideas(query, body):
    root = ROOT
    ideas_doc = _read_json(root / "plans" / "ideas.json", {}) or {}
    product_doc = _read_json(root / "plans" / "product_ideas.json", {}) or {}
    return {
        "ok": True,
        "ideas": ideas_doc.get("ideas") or [],
        "genres": ideas_doc.get("genres") or [],
        "note": ideas_doc.get("note") or "",
        "updated": ideas_doc.get("updated") or "",
        "productIdeas": product_doc.get("ideas") or product_doc if isinstance(product_doc, list) else [],
    }


@route("GET", "/api/planner/requests")
def planner_requests(query, body):
    root = ROOT
    req_dir = root / "plans" / "requests"
    res_dir = root / "plans" / "results"
    out = []
    if req_dir.exists():
        for p in sorted(req_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            d = _read_json(p) or {}
            res = _read_json(res_dir / p.name)
            out.append({
                "id": p.stem,
                "provider": d.get("provider") or "",
                "when": d.get("when") or "",
                "scheduledAt": d.get("scheduled_at") or "",
                "topic": d.get("topic") or d.get("detail") or "",
                "details": d.get("details") or "",
                "status": d.get("status") or ("done" if res else "pending"),
                "ideaCount": len(d.get("idea_ids") or []) or d.get("idea_count") or 0,
                "createdAt": dt.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
                "hasResult": bool(res),
                "requestPath": _rel(p),
                "resultPath": _rel(res_dir / p.name) if res else "",
            })
    return {"ok": True, "requests": out}


@route("GET", "/api/planner/result")
def planner_result(query, body):
    root = ROOT
    p = _safe_rel(root, query.get("path", ""))
    data = _read_json(p)
    if data is None:
        raise ValueError("ไม่พบผลลัพธ์ของคำขอนี้")
    return {"ok": True, "result": data, "path": _rel(p)}


@route("POST", "/api/planner/request")
def planner_request(query, body):
    """Create a real planner request file and, when Gemini is configured, run it."""
    root = ROOT
    provider = (body.get("provider") or "gemini").lower()
    when = body.get("when") or "now"
    now = dt.datetime.now()
    stamp = now.strftime("%Y%m%d-%H%M%S")
    rid = "REQ-%s" % stamp
    details = (body.get("details") or "").strip()
    idea_ids = body.get("ideaIds") or []

    req = {
        "id": rid,
        "provider": provider,
        "when": when,
        "scheduled_at": body.get("scheduledAt") or "",
        "custom_time": body.get("customTime") or "",
        "topic": (body.get("topic") or details or "ไอเดียใหม่")[:120],
        "details": details,
        "idea_ids": idea_ids,
        "status": "pending",
        "created_at": now.isoformat(timespec="seconds"),
    }
    req_path = root / "plans" / "requests" / ("%s.json" % rid)
    _write_json(req_path, req)

    if provider == "gemini" and when == "now":
        try:
            from . import planner_generate
            planner_generate.generate_request(str(req_path), root=root)
            req["status"] = "done"
            _write_json(req_path, req)
            return {"ok": True, "requestId": rid, "status": "done",
                    "resultPath": _rel(root / "plans" / "results" / ("%s.json" % rid)),
                    "note": "สร้างไอเดียด้วย Gemini API สำเร็จ"}
        except Exception as e:
            req["status"] = "failed"
            req["error"] = str(e)
            _write_json(req_path, req)
            return {"ok": False, "requestId": rid, "status": "failed", "error": str(e)}

    return {"ok": True, "requestId": rid, "status": "pending",
            "note": "สร้างคำขอแล้ว — เปิด AI ที่เลือกแล้วนำคำสั่งไปวางเพื่อรับผลลัพธ์"}


@route("POST", "/api/planner/import-response")
def planner_import(query, body):
    root = ROOT
    rid = (body.get("requestId") or "").strip()
    text = body.get("text") or ""
    if not rid:
        raise ValueError("ไม่พบรหัสคำขอ")
    req_path = root / "plans" / "requests" / ("%s.json" % rid)
    req = _read_json(req_path)
    if not isinstance(req, dict):
        raise ValueError("ไม่พบคำขอ %s" % rid)
    from . import planner_handoff
    try:
        out = planner_handoff.import_response(text, req, root=root)
    except Exception as e:
        raise ValueError("นำเข้าผลลัพธ์ไม่สำเร็จ: %s" % e)
    req["status"] = "done"
    _write_json(req_path, req)
    return {"ok": True, "resultPath": _rel(out) if isinstance(out, (str, Path)) else "",
            "imported": True}


@route("POST", "/api/planner/cancel")
def planner_cancel(query, body):
    root = ROOT
    rid = (body.get("requestId") or "").strip()
    req_path = root / "plans" / "requests" / ("%s.json" % rid)
    req = _read_json(req_path)
    if not isinstance(req, dict):
        raise ValueError("ไม่พบคำขอ %s" % rid)
    if req.get("status") == "done":
        raise ValueError("คำขอนี้ทำงานเสร็จแล้ว ยกเลิกไม่ได้")
    req["status"] = "cancelled"
    _write_json(req_path, req)
    return {"ok": True, "status": "cancelled"}


@route("POST", "/api/planner/product-ideas")
def planner_product_ideas(query, body):
    root = ROOT
    count = int(body.get("count") or 10)
    try:
        from . import product_clips
        ideas = product_clips.build_ideas(count=count)
    except Exception as e:
        raise ValueError("สร้างไอเดียสินค้าไม่สำเร็จ: %s" % e)
    doc = _read_json(root / "plans" / "product_ideas.json", {}) or {}
    doc["ideas"] = ideas
    doc["updated"] = dt.date.today().isoformat()
    _write_json(root / "plans" / "product_ideas.json", doc)
    return {"ok": True, "count": len(ideas), "ideas": ideas}


# =============================================================== platforms
PLATFORM_LABEL = {
    "tiktok": "TikTok",
    "youtube": "YouTube",
    "shopee": "Shopee",
    "facebook_profile": "Facebook Profile",
    "facebook_page": "Facebook Page",
}


@route("GET", "/api/platform/scripts")
def platform_scripts(query, body):
    root = ROOT
    return {"ok": True, "scripts": _list_scripts(root, "inbox") + _list_scripts(root, "done")}


@route("GET", "/api/platform/clips")
def platform_clips(query, body):
    return {"ok": True, "clips": _clip_entries(ROOT)}


@route("POST", "/api/platform/import-video")
def platform_import_video(query, body):
    root = ROOT
    platform = body.get("platform") or "tiktok"
    src = _safe_rel(root, body.get("path", ""))
    if not src.exists():
        raise ValueError("ไม่พบไฟล์วิดีโอที่เลือก")
    cfg = load_cfg()
    from . import platform_workspace as pw
    try:
        meta = pw.import_video(
            str(src), platform,
            title=body.get("title") or src.stem,
            description=body.get("description") or "",
            tags=body.get("tags") or [],
            fmt=body.get("format") or "vertical",
            cfg=cfg, root=root,
        )
    except TypeError:
        meta = pw.import_video(str(src), platform, body.get("title") or src.stem,
                               body.get("description") or "", body.get("tags") or [],
                               body.get("format") or "vertical", cfg=cfg, root=root)
    except Exception as e:
        raise ValueError("นำเข้าคลิปไม่สำเร็จ: %s" % e)
    return {"ok": True, "meta": meta, "folder": _rel(meta.get("folder", ""))}


@route("POST", "/api/platform/google-video")
def platform_google_video(query, body):
    root = ROOT
    platform = body.get("platform") or "tiktok"
    cfg = load_cfg()
    from . import platform_workspace as pw
    try:
        meta = pw.generate_google_video(
            body.get("prompt") or "", platform,
            title=body.get("title") or "", description=body.get("description") or "",
            tags=body.get("tags") or [], fmt=body.get("format") or "vertical",
            cfg=cfg, root=root,
        )
    except Exception as e:
        raise ValueError("สร้างวิดีโอด้วย Google API ไม่สำเร็จ: %s" % e)
    return {"ok": True, "meta": meta}


@route("POST", "/api/platform/analyze-prompt")
def platform_analyze_prompt(query, body):
    from . import prompt_analysis
    try:
        res = prompt_analysis.analyze_prompt(
            body.get("prompt") or "",
            context=body.get("context") or "video",
            duration=body.get("duration"),
        )
    except Exception as e:
        raise ValueError("AI วิเคราะห์พรอมต์ไม่สำเร็จ: %s" % e)
    return {"ok": True, "analysis": res}


# ================================================================= posting
@route("GET", "/api/posting/status")
def posting_status(query, body):
    root = ROOT
    cfg = load_cfg()
    from .publish import settings as pub_settings, is_connected, account_name, posted_today
    st = pub_settings(cfg)
    out = {"mode": st.get("mode"), "maxPerDay": st.get("max_per_day"),
           "postTimes": st.get("post_times"), "platforms": {}}
    for p in ("tiktok", "youtube", "facebook_page", "facebook_profile"):
        try:
            connected = bool(is_connected(p))
            name = account_name(p) if connected else ""
        except Exception:
            connected, name = False, ""
        out["platforms"][p] = {
            "label": PLATFORM_LABEL.get(p, p),
            "connected": connected,
            "accountName": name,
            "postedToday": posted_today(p) if p != "facebook_profile" else 0,
            "settings": st.get(p) or {},
        }
    return {"ok": True, "posting": out}


@route("POST", "/api/posting/save")
def posting_save(query, body):
    root = ROOT
    cfg = load_cfg()
    cfg.setdefault("publish", {})
    upd = body.get("settings") or {}
    for k, v in upd.items():
        if isinstance(v, dict) and isinstance(cfg["publish"].get(k), dict):
            cfg["publish"][k].update(v)
        else:
            cfg["publish"][k] = v
    _write_json(root / "config.json", cfg)
    return {"ok": True, "settings": upd}


@route("POST", "/api/posting/connect")
def posting_connect(query, body):
    platform = body.get("platform") or ""
    from .publish import module, PublishError
    try:
        m = module(platform)
    except PublishError:
        raise ValueError("แพลตฟอร์มไม่รองรับการเชื่อมต่อแบบอัตโนมัติ: %s" % platform)
    try:
        if platform == "youtube":
            m.set_client_file(str(ROOT / "secrets" / "youtube_client.json"))
        m.connect()
    except Exception as e:
        raise ValueError("เชื่อมต่อ %s ไม่สำเร็จ: %s" % (PLATFORM_LABEL.get(platform, platform), e))
    return {"ok": True, "connected": True, "accountName": m.account_name()}


@route("POST", "/api/posting/disconnect")
def posting_disconnect(query, body):
    platform = body.get("platform") or ""
    from .publish import module, PublishError
    try:
        m = module(platform)
    except PublishError:
        raise ValueError("แพลตฟอร์มนี้ไม่รองรับ")
    try:
        m.disconnect()
    except Exception as e:
        raise ValueError("ยกเลิกการเชื่อมต่อไม่สำเร็จ: %s" % e)
    return {"ok": True, "connected": False}


# =============================================================== scheduler
@route("GET", "/api/scheduler")
def scheduler_get(query, body):
    root = ROOT
    from . import ai_worker_scheduler as sched
    try:
        data = sched.load_schedule()
    except Exception:
        data = {}
    data = data or {}
    times = sched.normalize_times(data.get("times") or [])
    next_run, countdown = sched.get_next_run(times) if times else (None, "")
    return {
        "ok": True,
        "schedule": {
            "enabled": bool(data.get("enabled")),
            "times": times,
            "platforms": data.get("platforms") or [],
            "perDay": data.get("per_day") or data.get("max_per_day") or 2,
            "mode": data.get("mode") or "manual",
            "lastRun": data.get("last_run") or "",
            "nextRun": next_run or "",
            "nextRunLabel": next_run or "",
            "countdown": countdown or "",
        },
        "presetTimes": ["08:00", "12:00", "20:00"],
    }


@route("POST", "/api/scheduler/save")
def scheduler_save(query, body):
    root = ROOT
    from . import ai_worker_scheduler as sched
    data = sched.load_schedule() or {}
    data.update(body.get("schedule") or {})
    data["times"] = sched.normalize_times(data.get("times") or [])
    sched.save_schedule(data)
    try:
        if data.get("enabled"):
            sched.apply_windows_scheduled_tasks(data["times"])
        else:
            sched.remove_windows_scheduled_tasks()
    except Exception:
        pass
    return {"ok": True, "schedule": data}


@route("POST", "/api/scheduler/test")
def scheduler_test(query, body):
    root = ROOT
    jid = _job_new("worker_test", "ทดสอบการทำงานของพนักงาน AI")
    platforms = (body.get("schedule") or {}).get("platforms") or []

    def run():
        try:
            from . import ai_worker_scheduler as sched
            res = sched.execute_worker_job(platforms or None, log=lambda m: _job_log(jid, m))
            _job_done(jid, result=res)
        except Exception as e:
            _job_done(jid, error="%s\n%s" % (e, traceback.format_exc(limit=3)))

    threading.Thread(target=run, daemon=True).start()
    return {"ok": True, "jobId": jid}


@route("POST", "/api/scheduler/stop")
def scheduler_stop(query, body):
    try:
        from . import ai_worker_scheduler as sched
        sched.remove_windows_scheduled_tasks()
    except Exception:
        pass
    data = {}
    try:
        from . import ai_worker_scheduler as sched
        data = sched.load_schedule() or {}
        data["enabled"] = False
        sched.save_schedule(data)
    except Exception:
        pass
    return {"ok": True, "enabled": False}


# ================================================================ settings
@route("GET", "/api/settings")
def settings_get(query, body):
    root = ROOT
    cfg = load_cfg()
    try:
        from . import credential_store
        has_gemini = bool(credential_store.has_key())
    except Exception:
        has_gemini = False
    try:
        from .publish import facebook as fb
        fb_connected = bool(fb.connected())
    except Exception:
        fb_connected = False
    azure_key = (cfg.get("tts") or {}).get("azure_key") or ""
    return {
        "ok": True,
        "settings": {
            "channelName": cfg.get("channel_name") or "",
            "outroText": cfg.get("outro_text") or "",
            "readTitle": bool(cfg.get("read_title", True)),
            "readOutro": bool(cfg.get("read_outro", True)),
            "formats": (cfg.get("video") or {}).get("formats") or [],
            "musicVolume": (cfg.get("audio") or {}).get("music_volume", 0.16),
            "voiceVolume": (cfg.get("audio") or {}).get("voice_volume", 1.0),
            "sfxVolume": (cfg.get("audio") or {}).get("sfx_volume", 0.5),
            "fps": (cfg.get("video") or {}).get("fps", 30),
            "voices": cfg.get("voices") or {},
            "ttsEngines": (cfg.get("tts") or {}).get("engines") or [],
            "azureRegion": (cfg.get("tts") or {}).get("azure_region") or "southeastasia",
            "allowTestVoice": bool(cfg.get("allow_test_voice", False)),
        },
        "providers": {
            "gemini": {"connected": has_gemini, "label": "Google Gemini"},
            "azure": {"connected": bool(azure_key), "label": "Azure Speech",
                      "region": (cfg.get("tts") or {}).get("azure_region") or ""},
            "facebookPage": {"connected": fb_connected, "label": "Facebook Page"},
        },
        "characters": ["narrator", "bunny", "bear", "chick", "cat"],
        "voiceOptions": ["th-TH-PremwadeeNeural", "th-TH-NiwatNeural"],
    }


@route("POST", "/api/settings/save")
def settings_save(query, body):
    root = ROOT
    cfg = load_cfg()
    s = body.get("settings") or {}
    if "channelName" in s:
        cfg["channel_name"] = s["channelName"]
    if "outroText" in s:
        cfg["outro_text"] = s["outroText"]
    if "readTitle" in s:
        cfg["read_title"] = bool(s["readTitle"])
    if "readOutro" in s:
        cfg["read_outro"] = bool(s["readOutro"])
    if "formats" in s:
        cfg.setdefault("video", {})["formats"] = s["formats"]
    if "fps" in s:
        cfg.setdefault("video", {})["fps"] = int(s["fps"])
    if "musicVolume" in s:
        cfg.setdefault("audio", {})["music_volume"] = float(s["musicVolume"])
    if "voiceVolume" in s:
        cfg.setdefault("audio", {})["voice_volume"] = float(s["voiceVolume"])
    if "sfxVolume" in s:
        cfg.setdefault("audio", {})["sfx_volume"] = float(s["sfxVolume"])
    if "ttsEngines" in s:
        cfg.setdefault("tts", {})["engines"] = s["ttsEngines"]
    if "azureRegion" in s:
        cfg.setdefault("tts", {})["azure_region"] = s["azureRegion"]
    if "allowTestVoice" in s:
        cfg["allow_test_voice"] = bool(s["allowTestVoice"])
    if "voices" in s and isinstance(s["voices"], dict):
        cfg.setdefault("voices", {})
        for who, v in s["voices"].items():
            if isinstance(v, dict):
                cfg["voices"].setdefault(who, {}).update(v)
    _write_json(root / "config.json", cfg)
    return {"ok": True, "settings": s}


@route("POST", "/api/settings/key")
def settings_key_save(query, body):
    root = ROOT
    key = (body.get("key") or "").strip()
    if not key:
        raise ValueError("ไม่พบค่า key")
    try:
        from . import credential_store
        credential_store.save_key(key)
    except Exception as e:
        raise ValueError("บันทึก key ไม่สำเร็จ: %s" % e)
    return {"ok": True, "connected": True}


@route("POST", "/api/settings/key/delete")
def settings_key_delete(query, body):
    try:
        from . import credential_store
        credential_store.delete_key()
    except Exception as e:
        raise ValueError("ลบ key ไม่สำเร็จ: %s" % e)
    return {"ok": True, "connected": False}


@route("POST", "/api/settings/test-voice")
def settings_test_voice(query, body):
    root = ROOT
    who = body.get("who") or "narrator"
    cfg = load_cfg()
    vcfg = (cfg.get("voices") or {}).get(who)
    if not vcfg:
        raise ValueError("ไม่พบการตั้งค่าเสียงของ %s" % who)
    from . import tts
    jid = _job_new("voice_test", "ทดสอบเสียง %s" % who)

    def run():
        try:
            engines = (cfg.get("tts") or {}).get("engines") or []
            text = body.get("text") or "สวัสดีครับ นี่คือเสียงทดสอบของโปรแกรม"
            cache = root / "cache" / "tts"
            path = tts.synth_with_fallback(text, vcfg, engines, cache,
                                            lambda m: _job_log(jid, m),
                                            allow_test=bool(cfg.get("allow_test_voice")))
            _job_done(jid, result={"path": _rel(path) if path else ""})
        except Exception as e:
            _job_done(jid, error="%s\n%s" % (e, traceback.format_exc(limit=3)))

    threading.Thread(target=run, daemon=True).start()
    return {"ok": True, "jobId": jid}


@route("POST", "/api/settings/test-azure")
def settings_test_azure(query, body):
    cfg = load_cfg()
    tts_cfg = cfg.get("tts") or {}
    key = tts_cfg.get("azure_key") or ""
    region = tts_cfg.get("azure_region") or ""
    if not key:
        raise ValueError("ยังไม่ได้บันทึก Speech Key")
    try:
        import urllib.request
        url = "https://%s.api.cognitiveservices.com/sts/v1.0/makestt/token" % region
        req = urllib.request.Request(url, headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/ssml+xml",
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            token = r.read().decode("utf-8", "ignore")
        return {"ok": True, "connected": True, "detail": "เชื่อมต่อ Azure Speech สำเร็จ (region %s)" % region}
    except Exception as e:
        return {"ok": False, "connected": False, "error": str(e)}


# ========================================================== shopee / fb page
@route("GET", "/api/shopee/products")
def shopee_products(query, body):
    try:
        from . import facebook_profile_flow as fpf
        prods = fpf.load_shopee_products(
            min_price=float(query.get("minPrice") or 0),
            search=query.get("search") or "",
            category=query.get("category") or "",
        )
    except Exception as e:
        raise ValueError("โหลดข้อมูลสินค้าไม่สำเร็จ: %s" % e)
    sort = query.get("sort") or "default"
    if sort == "price_asc":
        prods.sort(key=lambda p: float(p.get("sale_price") or p.get("price") or 0))
    elif sort == "price_desc":
        prods.sort(key=lambda p: -(float(p.get("sale_price") or p.get("price") or 0)))
    elif sort == "sold":
        prods.sort(key=lambda p: -(float(p.get("sold_count") or 0)))
    elif sort == "rating":
        prods.sort(key=lambda p: -(float(p.get("rating") or 0)))
    limit = int(query.get("limit") or 200)
    total = len(prods)
    page = int(query.get("page") or 1)
    per = int(query.get("perPage") or 20)
    start = (page - 1) * per
    return {"ok": True, "products": prods[start:start + per], "total": total,
            "page": page, "perPage": per}


@route("GET", "/api/shopee/categories")
def shopee_categories(query, body):
    try:
        from . import facebook_profile_flow as fpf
        return {"ok": True, "categories": fpf.get_categories()}
    except Exception as e:
        return {"ok": False, "categories": [], "error": str(e)}


@route("POST", "/api/facebook/prompt")
def facebook_prompt(query, body):
    try:
        from . import facebook_profile_flow as fpf
        p = body.get("product") or {}
        prompt = fpf.generate_flow_prompt(p, duration_sec=int(body.get("duration") or 8),
                                          style_key=body.get("style") or "presenter")
    except Exception as e:
        raise ValueError("สร้างพรอมต์ไม่สำเร็จ: %s" % e)
    return {"ok": True, "prompt": prompt}


@route("POST", "/api/facebook/caption")
def facebook_caption(query, body):
    try:
        from . import facebook_profile_flow as fpf
        p = body.get("product") or {}
        caption = fpf.generate_facebook_caption(p, style=body.get("style") or "reels")
    except Exception as e:
        raise ValueError("สร้างแคปชันไม่สำเร็จ: %s" % e)
    return {"ok": True, "caption": caption}


@route("GET", "/api/facebook/posts")
def facebook_posts(query, body):
    try:
        from . import facebook_profile_flow as fpf
        return {"ok": True, "posts": fpf.load_facebook_posts_history()}
    except Exception as e:
        return {"ok": False, "posts": [], "error": str(e)}


# ==================================================================== jobs
@route("GET", "/api/job")
def job_get(query, body):
    with _JOBS_LOCK:
        j = _JOBS.get(query.get("id") or "")
    if not j:
        raise ValueError("ไม่พบงานที่ระบุ")
    return {"ok": True, "job": _job_public(j)}


@route("POST", "/api/job/cancel")
def job_cancel(query, body):
    with _JOBS_LOCK:
        j = _JOBS.get(body.get("id") or "")
        if j:
            j["_cancel"] = True
            j["status"] = "cancelled"
            j["finishedAt"] = dt.datetime.now().isoformat(timespec="seconds")
    return {"ok": True, "cancelled": True}


@route("POST", "/api/render")
def render(query, body):
    """Render a script into a clip. Runs in the background with live progress."""
    root = ROOT
    path = _safe_rel(root, body.get("path", ""))
    if not path.exists():
        raise ValueError("ไม่พบไฟล์บท")
    fmt = body.get("format") or "vertical"
    jid = _job_new("render", "เรนเดอร์ %s" % path.stem)

    def run():
        try:
            cfg = load_cfg()
            from . import cli
            out_root = root / "output" / dt.date.today().isoformat()
            formats = [fmt] if fmt != "both" else list((cfg.get("video") or {}).get("formats") or ["vertical", "horizontal"])
            meta = cli._render_one(
                str(path), cfg, out_root, formats,
                resolution=body.get("resolution") or "1080p",
                fps=body.get("fps"),
                encoder=body.get("encoder") or "auto",
                engine_type=body.get("engineType") or "2d_cartoon",
                device_id=body.get("deviceId"),
                chibi_options=body.get("chibiOptions") or {},
            )
            _job_done(jid, result=meta)
        except Exception as e:
            _job_done(jid, error="%s\n%s" % (e, traceback.format_exc(limit=5)))

    threading.Thread(target=run, daemon=True).start()
    return {"ok": True, "jobId": jid}
