"""AI Automation Worker Scheduler.

Manages scheduled execution of the AI Worker across multiple platforms
(Facebook Profile via Browser RPA, Facebook Page, TikTok, YouTube, Batch Render).
Supports multi-time scheduling (5, 7, 10, 15 slots or custom times) with:
  1. Windows Task Scheduler (schtasks) for system-level triggers
  2. In-App live heartbeat daemon for immediate execution while the studio is running
"""
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

from .config import ROOT

CACHE_DIR = ROOT / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
SCHEDULE_FILE = CACHE_DIR / "ai_worker_schedule.json"
BAT_FILE = ROOT / "run_worker_auto.bat"
LOG_FILE = ROOT / "logs" / "worker_auto.log"

TASK_PREFIX = "KidsStudio AI Worker "
MAX_WINDOWS_TASKS = 25

NOWIN = {"creationflags": 0x08000000} if sys.platform == "win32" else {}

# Time Presets for high-converting posting schedules
PRESETS = {
    5: ["08:00", "11:00", "14:00", "17:00", "20:00"],
    7: ["08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00"],
    10: ["07:30", "09:00", "10:30", "12:00", "13:30", "15:00", "16:30", "18:00", "19:30", "21:00"],
    15: [
        "07:00", "08:00", "09:00", "10:00", "11:00",
        "12:00", "13:00", "14:00", "15:00", "16:00",
        "17:00", "18:00", "19:00", "20:00", "21:00"
    ],
}

DEFAULT_SCHEDULE = {
    "enabled": False,
    "platforms": {
        "facebook_profile": True,
        "facebook_page": False,
        "tiktok": False,
        "youtube": False,
        "batch_render": False,
    },
    "times": ["08:00", "11:00", "14:00", "17:00", "20:00"],
    "last_run": None,
    "last_run_minute": None,
    "history": [],
}


def load_schedule():
    """Load schedule configuration from cache file, creating default if missing."""
    if not SCHEDULE_FILE.is_file():
        save_schedule(DEFAULT_SCHEDULE)
        return dict(DEFAULT_SCHEDULE)
    try:
        data = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
        merged = dict(DEFAULT_SCHEDULE)
        merged.update(data)
        if "platforms" in data and isinstance(data["platforms"], dict):
            p = dict(DEFAULT_SCHEDULE["platforms"])
            p.update(data["platforms"])
            merged["platforms"] = p
        return merged
    except Exception:
        return dict(DEFAULT_SCHEDULE)


def save_schedule(data):
    """Save schedule configuration to JSON file."""
    SCHEDULE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_preset_times(count):
    """Return preset list of times for 5, 7, 10, or 15 slots."""
    return list(PRESETS.get(count, PRESETS[5]))


def normalize_times(times):
    """Validate, deduplicate, and sort HH:MM times chronologically."""
    valid = set()
    for t in times:
        t = str(t).strip()
        parts = t.split(":")
        if len(parts) == 2:
            try:
                h = int(parts[0])
                m = int(parts[1])
                if 0 <= h <= 23 and 0 <= m <= 59:
                    valid.add(f"{h:02d}:{m:02d}")
            except ValueError:
                pass
    return sorted(valid)


def get_next_run(times):
    """Calculate the next upcoming scheduled time and minutes remaining.
    
    Returns:
        (next_time_str, countdown_str) or (None, "ไม่มีเวลาที่ตั้งไว้")
    """
    times = normalize_times(times)
    if not times:
        return None, "ยังไม่ได้กำหนดเวลา"

    now = dt.datetime.now()
    today_date = now.date()
    candidates = []

    for t_str in times:
        h, m = map(int, t_str.split(":"))
        run_dt = dt.datetime(today_date.year, today_date.month, today_date.day, h, m, 0)
        if run_dt <= now:
            # Tomorrow
            run_dt += dt.timedelta(days=1)
        candidates.append((run_dt, t_str))

    candidates.sort(key=lambda x: x[0])
    next_dt, next_hhmm = candidates[0]
    diff = next_dt - now
    total_mins = int(diff.total_seconds() // 60)
    hours = total_mins // 60
    mins = total_mins % 60

    if hours > 0:
        cd_str = f"อีก {hours} ชม. {mins} นาที"
    else:
        cd_str = f"อีก {mins} นาที"

    is_tomorrow = next_dt.date() > today_date
    day_prefix = "พรุ่งนี้ " if is_tomorrow else "วันนี้ "
    return next_hhmm, f"{day_prefix}{next_hhmm} น. ({cd_str})"


def ensure_worker_bat():
    """Ensure run_worker_auto.bat exists and is correctly configured."""
    content = (
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        "cd /d \"%~dp0\"\r\n"
        "if not exist logs mkdir logs\r\n"
        ".venv\\Scripts\\python -m studio worker-run >> logs\\worker_auto.log 2>&1\r\n"
    )
    try:
        BAT_FILE.write_text(content, encoding="utf-8")
    except Exception:
        pass
    return BAT_FILE


def apply_windows_scheduled_tasks(times):
    """Create Windows scheduled tasks for each time in the list.
    
    Returns:
        (success_count, message)
    """
    if sys.platform != "win32":
        return 0, "ระบบตั้งเวลา Windows รองรับเฉพาะระบบปฏิบัติการ Windows"

    times = normalize_times(times)
    ensure_worker_bat()

    # Step 1: Remove all existing KidsStudio AI Worker tasks
    for i in range(1, MAX_WINDOWS_TASKS + 1):
        tn = f"{TASK_PREFIX}{i}"
        subprocess.run(["schtasks", "/Delete", "/F", "/TN", tn],
                       capture_output=True, text=True, **NOWIN)

    if not times:
        return 0, "ปิดระบบตั้งเวลา Windows เรียบร้อยแล้ว (ไม่มีเวลาที่เปิดใช้งาน)"

    # Step 2: Register each scheduled time
    ok_count = 0
    bat_path = str(BAT_FILE.resolve())

    for idx, hhmm in enumerate(times, 1):
        if idx > MAX_WINDOWS_TASKS:
            break
        tn = f"{TASK_PREFIX}{idx}"
        cmd = [
            "schtasks", "/Create", "/F",
            "/TN", tn,
            "/SC", "DAILY",
            "/ST", hhmm,
            "/TR", f'"{bat_path}"',
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, **NOWIN)
        if res.returncode == 0:
            ok_count += 1

    msg = f"ตั้งเวลาระบบ Windows เรียบร้อย {ok_count} จาก {len(times)} ช่วงเวลา"
    return ok_count, msg


def remove_windows_scheduled_tasks():
    """Delete all KidsStudio AI Worker tasks from Windows Task Scheduler."""
    if sys.platform != "win32":
        return 0
    count = 0
    for i in range(1, MAX_WINDOWS_TASKS + 1):
        tn = f"{TASK_PREFIX}{i}"
        res = subprocess.run(["schtasks", "/Delete", "/F", "/TN", tn],
                             capture_output=True, text=True, **NOWIN)
        if res.returncode == 0:
            count += 1
    return count


# ---------------------------------------------------------------------------
# Core Execution Engine (Called when time arrives or on manual test run)
# ---------------------------------------------------------------------------

def execute_worker_job(platforms=None, log=print):
    """Execute AI Worker for enabled platforms.
    
    Can be called directly from Python, from Windows Task Scheduler via CLI,
    or from GUI test button.
    """
    cfg = load_schedule()
    active_platforms = platforms or [k for k, v in cfg.get("platforms", {}).items() if v]

    now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log(f"[{now_str}] 🤖 พนักงาน AI เริ่มต้นทำงานอัตโนมัติ...")
    log(f"   แพลตฟอร์มเป้าหมาย: {', '.join(active_platforms) if active_platforms else 'ไม่มี'}")

    results = {}
    success_count = 0

    # 1. Facebook Profile (Browser RPA Worker)
    if "facebook_profile" in active_platforms:
        log("🔹 [1/4] ทำงานบน Facebook Profile (Browser Worker)...")
        try:
            from . import facebook_profile_flow as fb_flow
            from . import fb_browser_worker

            # Find candidates: 1) recent videos from Flow/Downloads, or 2) ready clips in output
            video_cand = None
            vids = fb_flow.find_recent_videos(limit=5)
            posted_records = fb_flow.load_facebook_posts_history(limit=100)
            posted_paths = {r.get("video_path") for r in posted_records if r.get("video_path")}

            for v in vids:
                if str(v["path"]) not in posted_paths and Path(v["path"]).is_file():
                    video_cand = Path(v["path"])
                    break

            # Fallback to output/ clips
            if not video_cand:
                from . import publish
                for folder, meta in publish.all_clips():
                    fmt = (meta.get("platform_formats") or {}).get("facebook_profile", "vertical")
                    fname = (meta.get("files") or {}).get(fmt) or (meta.get("files") or {}).get("vertical")
                    if fname and (folder / fname).is_file():
                        p_meta = (meta.get("posts") or {}).get("facebook_profile") or {}
                        if p_meta.get("status") not in ("posted", "draft_sent"):
                            video_cand = folder / fname
                            break

            # Load Shopee product for caption
            prods = fb_flow.load_shopee_products()
            sel_prod = prods[0] if prods else {
                "name": "สินค้าแนะนำ Shopee",
                "effective_price": 199,
                "affiliate_url": "https://shopee.co.th/",
                "rating": 4.9,
                "sold_count": 1200,
            }

            caption = fb_flow.generate_facebook_caption(sel_prod)

            if video_cand and video_cand.is_file():
                log(f"   พบวิดีโอพร้อมโพสต์: {video_cand.name}")
                fb_browser_worker.publish_facebook_reel(
                    video_path=video_cand,
                    caption=caption,
                    auto_publish=True,
                    log_callback=log,
                )
                fb_flow.record_facebook_post(sel_prod, str(video_cand), caption, "https://www.facebook.com/")
                results["facebook_profile"] = "โพสต์สำเร็จ"
                success_count += 1
            else:
                log("   ⚠️ ยังไม่มีไฟล์วิดีโอ .mp4 ใหม่ใน Downloads หรือ output/ (กรุณาสร้างวิดีโอด้วย Flow ก่อน)")
                results["facebook_profile"] = "รอไฟล์วิดีโอ"

        except Exception as e:
            err = f"Facebook Profile ล้มเหลว: {e}"
            log(f"   ❌ {err}")
            results["facebook_profile"] = f"ผิดพลาด: {str(e)[:100]}"

    # 2. Facebook Page, TikTok, YouTube (Publisher Engine)
    pub_platforms = [p for p in active_platforms if p in ("facebook_page", "tiktok", "youtube")]
    if pub_platforms:
        log(f"🔹 ทำงานบน {', '.join(pub_platforms)} ผ่านระบบสตูดิโอ...")
        try:
            from . import config as configmod
            from . import publish

            app_cfg = configmod.load()
            pub_res = publish.run_auto(app_cfg, log=log, per_run=1)
            for p in pub_platforms:
                results[p] = f"เผยแพร่ {pub_res.get('posted', 0)} คลิป"
                if pub_res.get("posted", 0) > 0:
                    success_count += 1
        except Exception as e:
            err = f"Publisher engine ผิดพลาด: {e}"
            log(f"   ❌ {err}")
            for p in pub_platforms:
                results[p] = f"ผิดพลาด: {str(e)[:80]}"

    # 3. Batch Render (Auto create clips from inbox)
    if "batch_render" in active_platforms:
        log("🔹 ทำงานเรนเดอร์คลิปอัตโนมัติ (Batch Render)...")
        try:
            from . import config as configmod
            from . import cli

            app_cfg = configmod.load()
            inbox_dir = ROOT / "scripts" / "inbox"
            if inbox_dir.is_dir() and list(inbox_dir.glob("*.json")):
                class DummyArgs:
                    limit = 2
                    format = "config"
                    out = None
                    skip_existing = True
                cli.cmd_batch(DummyArgs(), app_cfg)
                results["batch_render"] = "เรนเดอร์สำเร็จ"
                success_count += 1
            else:
                log("   ไม่มีบทใหม่ใน scripts/inbox")
                results["batch_render"] = "ไม่มีบทใหม่"
        except Exception as e:
            log(f"   ❌ Batch render ผิดพลาด: {e}")
            results["batch_render"] = f"ผิดพลาด: {str(e)[:80]}"

    # Record history
    history_item = {
        "time": now_str,
        "platforms": active_platforms,
        "results": results,
        "success_count": success_count,
    }
    history = cfg.get("history", [])
    history.insert(0, history_item)
    cfg["history"] = history[:100]
    cfg["last_run"] = now_str
    cfg["last_run_status"] = f"สำเร็จ {success_count} งาน"
    save_schedule(cfg)

    log(f"[{now_str}] ✨ พนักงาน AI ทำงานเสร็จสิ้น (สำเร็จ {success_count} งาน)")
    return history_item
