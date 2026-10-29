"""Long videos (5-20+ min) made by joining finished episodes with chapter cards.

A compilation spec lives in scripts/compilations/<id>.json :
{
  "id": "comp001-numbers-10min",
  "title": "รวมนับเลขสนุก 10 นาที",
  "description": "...", "tags": [...],
  "target_minutes": 10,
  "format": "horizontal",
  "episodes": ["ep004-...", "ep009-..."],      # wanted first, in this order
  "fill_genre": ["นับเลข"],                    # then any finished episode of these genres
  "request_id": "REQ-..."                      # optional, links back to the planner
}
It is built once enough finished episodes exist (at least 85% of the target length).
"""
import json
import math
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image

from . import art, audio
from .config import ROOT
from .textrender import load_font, text_block

SIZE = {"horizontal": (1920, 1080), "vertical": (1080, 1920)}


def _episodes_index(fmt):
    """id -> (folder, meta) for every finished episode that has the wanted format (newest wins)."""
    idx = {}
    base = ROOT / "output"
    if not base.exists():
        return idx
    for day in sorted(d for d in base.iterdir() if d.is_dir()):
        if day.name in ("removed", "trash", ".trash"):
            continue
        for clip in sorted(c for c in day.iterdir() if c.is_dir()):
            m = clip / "meta.json"
            if not m.exists():
                continue
            try:
                meta = json.loads(m.read_text(encoding="utf-8"))
            except Exception:
                continue
            if meta.get("kind") == "compilation" or meta.get("status") == "rejected":
                continue
            f = (meta.get("files") or {}).get(fmt)
            if f and (clip / f).exists():
                idx[meta.get("id", clip.name)] = (clip, meta)
    return idx


def pick(spec, fmt):
    idx = _episodes_index(fmt)
    target = float(spec.get("target_minutes", 10)) * 60
    chosen, total = [], 0.0
    for eid in spec.get("episodes", []):
        if eid in idx and eid not in [c[0] for c in chosen]:
            chosen.append((eid,) + idx[eid])
            total += idx[eid][1].get("duration_seconds", 0) + 2.5
    genres = spec.get("fill_genre") or []
    if isinstance(genres, str):
        genres = [genres]
    if total < target and genres:
        for eid, (folder, meta) in idx.items():
            if total >= target:
                break
            if eid in [c[0] for c in chosen] or meta.get("genre") not in genres:
                continue
            chosen.append((eid, folder, meta))
            total += meta.get("duration_seconds", 0) + 2.5
    return chosen, total, target


def _card(fmt, title, sub, seed):
    W, H = SIZE[fmt]
    ground = int(H * (0.83 if fmt == "horizontal" else 0.72))
    bg = art.draw_background(["meadow", "beach", "classroom", "bedroom", "night"][seed % 5], W, H, ground, seed=seed)
    img = bg.convert("RGBA")
    font = load_font(str(ROOT / "fonts" / "Kanit-Bold.ttf"))
    # characters along the bottom
    ch_h = int(H * (0.42 if fmt == "horizontal" else 0.26))
    xs = [0.14, 0.38, 0.62, 0.86]
    for i, sp in enumerate(["bunny", "bear", "chick", "cat"]):
        c = art.draw_character(sp, mouth=1 if i % 2 else 0, arm_l=150 if i == 0 else 18,
                               arm_r=150 if i == 3 else 18, scale=ch_h / art.CHAR_H)
        img.alpha_composite(c, (int(W * xs[i] - c.width / 2), ground - c.height + 6))
    tb = text_block(font, title, int(H * (0.085 if fmt == "horizontal" else 0.05)), int(W * 0.78), fill=art.INK,
                    max_lines=3, min_size=40)
    pw, ph = tb.width + 120, tb.height + 110
    if sub:
        sb = text_block(font, sub, int(H * (0.045 if fmt == "horizontal" else 0.03)), int(W * 0.7), fill="#5B3FE0",
                        max_lines=1, min_size=24)
        ph += sb.height + 20
    panel = art.draw_panel(pw, ph, fill="#FFD93D", radius=60)
    y = (panel.height - (tb.height + (sb.height + 20 if sub else 0))) // 2
    if sub:
        panel.alpha_composite(sb, ((panel.width - sb.width) // 2, y))
        y += sb.height + 20
    panel.alpha_composite(tb, ((panel.width - tb.width) // 2, y))
    py = int(H * (0.12 if fmt == "horizontal" else 0.2))
    img.alpha_composite(panel, ((W - panel.width) // 2, py))
    return img.convert("RGB")


def _encode_card(img, seconds, out, cfg):
    tmp = Path(tempfile.mkdtemp())
    try:
        png = tmp / "card.png"
        img.save(png)
        n = int(seconds * audio.SR)
        snd = np.zeros(n, dtype=np.float32)
        audio._add(snd, 0.15, audio.sfx_chime(), 0.45)
        wav = tmp / "card.wav"
        audio.write_wav(wav, snd)
        v = cfg["video"]
        cmd = [audio.ffmpeg_exe(), "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(v.get("fps", 30)),
               "-i", str(png), "-i", str(wav), "-t", "%.3f" % seconds,
               "-c:v", "libx264", "-preset", v.get("preset", "veryfast"), "-crf", str(v.get("crf", 21)),
               "-pix_fmt", "yuv420p", "-r", str(v.get("fps", 30)),
               "-ar", "48000", "-ac", "2", "-c:a", "aac", "-b:a", "160k", "-shortest",
               "-movflags", "+faststart", str(out)]
        subprocess.run(cmd, check=True, **audio._no_window())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _concat(parts, out, reencode=False, cfg=None):
    lst = Path(out).with_suffix(".txt")
    lst.write_text("".join("file '%s'\n" % str(p).replace("'", "'\\''") for p in parts), encoding="utf-8")
    try:
        if reencode:
            v = cfg["video"]
            cmd = [audio.ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                   "-c:v", "libx264", "-preset", v.get("preset", "veryfast"), "-crf", str(v.get("crf", 21)),
                   "-pix_fmt", "yuv420p", "-r", str(v.get("fps", 30)), "-ar", "48000", "-ac", "2",
                   "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)]
        else:
            cmd = [audio.ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                   "-c", "copy", "-movflags", "+faststart", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True, **audio._no_window())
        return r.returncode == 0, r.stderr
    finally:
        lst.unlink(missing_ok=True)


def _duration(path):
    r = subprocess.run([audio.ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True, text=True,
                       **audio._no_window())
    import re
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def _audio_rate(path):
    import re
    r = subprocess.run([audio.ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True, text=True,
                       **audio._no_window())
    m = re.search(r"Audio:.*?(\d+) Hz", r.stderr)
    return int(m.group(1)) if m else 0


def _ts(sec):
    sec = int(sec)
    return "%d:%02d:%02d" % (sec // 3600, sec // 60 % 60, sec % 60) if sec >= 3600 else "%02d:%02d" % (sec // 60, sec % 60)


def build(spec, cfg, out_root, log=print, force=False):
    """Returns meta dict when built, or None when there are not enough episodes yet."""
    fmt = spec.get("format", "horizontal")
    chosen, total, target = pick(spec, fmt)
    if not chosen or (total < 0.85 * target and not force):
        log("  %s: waiting - %.1f of %.0f minutes available (%d episodes)" % (
            spec["id"], total / 60, target / 60, len(chosen)))
        return None
    t0 = time.time()
    out = Path(out_root) / spec["id"]
    out.mkdir(parents=True, exist_ok=True)
    work = out / "_parts"
    work.mkdir(exist_ok=True)
    parts, chapters, t = [], [], 0.0
    opening = _card(fmt, spec["title"], "รวม %d ตอน" % len(chosen), seed=0)  # bright meadow for the thumbnail
    _encode_card(opening, 4.0, work / "c000.mp4", cfg)
    parts.append(work / "c000.mp4")
    chapters.append((0.0, "เริ่ม"))
    t += 4.0
    needs = []
    for i, (eid, folder, meta) in enumerate(chosen, 1):
        card = work / ("c%03d.mp4" % i)
        _encode_card(_card(fmt, meta.get("title", eid), "ตอนที่ %d" % i, seed=i), 2.5, card, cfg)
        parts.append(card)
        chapters.append((t, meta.get("title", eid)))
        clip = folder / meta["files"][fmt]
        parts.append(clip)
        t += 2.5 + float(meta.get("duration_seconds", 0))
        needs += ["%s: %s" % (eid, n) for n in meta.get("needs_review", [])]
        log("  + %s" % meta.get("title", eid))
    mp4 = out / ("%s_%s.mp4" % (spec["id"], fmt))
    same = all(_audio_rate(p) == 48000 for p in parts[2::2])  # older clips may be 44.1 kHz
    ok, err = _concat(parts, mp4) if same else (False, "mixed audio formats")
    if not ok or abs(_duration(mp4) - t) > 5:
        log("  fast join failed, re-encoding (slower)")
        ok, err = _concat(parts, mp4, reencode=True, cfg=cfg)
        if not ok:
            raise RuntimeError("ffmpeg concat failed: %s" % err[-400:])
    shutil.rmtree(work, ignore_errors=True)
    dur = _duration(mp4) or t
    thumb = opening.resize((1280, 720) if fmt == "horizontal" else (720, 1280), Image.LANCZOS)
    thumb.save(out / ("thumb_%s.jpg" % fmt), quality=90)
    chap_txt = "\n".join("%s %s" % (_ts(s), name) for s, name in chapters)
    desc = (spec.get("description") or "").strip()
    tags = spec.get("tags") or []
    full_desc = "%s\n\nสารบัญ\n%s" % (desc, chap_txt) if desc else "สารบัญ\n%s" % chap_txt
    hashtags = " ".join("#" + str(x).replace(" ", "") for x in tags[:8])
    (out / "upload.txt").write_text("%s\n\n%s\n\n%s\n" % (spec["title"], full_desc, hashtags), encoding="utf-8")
    meta = {
        "id": spec["id"], "kind": "compilation", "title": spec["title"], "description": full_desc,
        "tags": tags, "genre": (spec.get("fill_genre") or [None])[0] if isinstance(spec.get("fill_genre"), list)
        else spec.get("fill_genre"), "made_for_kids": True, "ai_generated": True,
        "duration_seconds": round(dur, 2), "episodes": [c[0] for c in chosen],
        "files": {fmt: mp4.name, "thumb_" + fmt: "thumb_%s.jpg" % fmt, "upload_text": "upload.txt"},
        "needs_review": needs, "status": "ready_for_approval", "request_id": spec.get("request_id"),
        "render_seconds": round(time.time() - t0, 1), "folder": str(out),
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    log("  compilation done: %s (%.1f min)" % (mp4.name, dur / 60))
    return meta


def run_pending(cfg, out_root, log=print, force=False):
    d = ROOT / "scripts" / "compilations"
    if not d.exists():
        return []
    built = []
    for p in sorted(d.glob("*.json")):
        try:
            spec = json.loads(p.read_text(encoding="utf-8-sig"))
            spec.setdefault("id", p.stem)
        except Exception as e:
            log("  bad compilation file %s: %s" % (p.name, e))
            continue
        log("compilation %s" % spec["id"])
        try:
            meta = build(spec, cfg, out_root, log, force)
        except Exception as e:
            log("  FAILED: %s" % e)
            continue
        if meta:
            done = ROOT / "scripts" / "done" / Path(out_root).name
            done.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), done / p.name)
            built.append(meta)
    return built
