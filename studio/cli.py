"""Command line for TaoYongStudio.

  python -m studio check                     check that everything works on this computer
  python -m studio validate FILE.json        check a script without rendering
  python -m studio render FILE.json [--format vertical|horizontal|both] [--out DIR]
  python -m studio batch [--limit N]         render every script in scripts/inbox
  python -m studio still FILE.json --at 3.5  save one frame as a PNG (quick look)
  python -m studio voices                    list Thai voices
  python -m studio samples                   copy the sample scripts into scripts/inbox
"""
import argparse
import datetime as dt
import json
import shutil
import sys
import time
import traceback
from pathlib import Path

from . import config, script as scriptmod
from .config import ROOT


def _log(msg):
    stamp = dt.datetime.now().strftime("%H:%M:%S")
    line = "[%s] %s" % (stamp, msg)
    print(line, flush=True)
    logdir = ROOT / "logs"
    logdir.mkdir(exist_ok=True)
    with open(logdir / ("%s.log" % dt.date.today().isoformat()), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _formats(arg, cfg):
    if not arg or arg == "config":
        return cfg["video"]["formats"]
    return ["vertical", "horizontal"] if arg == "both" else [arg]


def cmd_check(a, cfg):
    ok = True
    try:
        from . import audio
        exe = audio.ffmpeg_exe()
        _log("ffmpeg: OK (%s)" % exe)
    except Exception as e:
        ok = False
        _log("ffmpeg: MISSING - %s" % e)
    font = ROOT / "fonts" / "Kanit-Bold.ttf"
    _log("Thai font: %s" % ("OK" if font.exists() else "MISSING " + str(font)))
    ok &= font.exists()
    from . import tts
    for eng in cfg["tts"]["engines"]:
        try:
            vc = dict(cfg["voices"]["narrator"], _azure_key=cfg["tts"].get("azure_key", ""),
                      _azure_region=cfg["tts"].get("azure_region", "southeastasia"))
            x = tts.synth("ทดสอบเสียงภาษาไทย", vc, eng, ROOT / "cache" / "tts")
            _log("voice engine '%s': OK (%.1fs of audio)" % (eng, len(x) / 44100))
        except Exception as e:
            _log("voice engine '%s': not available - %s" % (eng, str(e)[:160]))
    # every character voice must work in the main engine, otherwise clips fail later
    main = next((e for e in cfg["tts"]["engines"] if e != "azure" or cfg["tts"].get("azure_key")), None)
    if main in ("azure", "edge"):
        for who, vc0 in cfg["voices"].items():
            vc = dict(vc0, _azure_key=cfg["tts"].get("azure_key", ""),
                      _azure_region=cfg["tts"].get("azure_region", "southeastasia"))
            try:
                tts.synth_with_fallback("สวัสดีจ้ะ", vc, [main], ROOT / "cache" / "tts", lambda m: None)
                _log("voice for %-8s OK (%s)" % (who, vc0.get("edge")))
            except Exception as e:
                ok = False
                _log("voice for %-8s FAILED (%s) - change it in config.json -> voices" % (who, vc0.get("edge")))
    _log("READY" if ok else "NOT READY - see messages above")
    return 0 if ok else 1


def cmd_validate(a, cfg):
    sc = scriptmod.load(a.file)
    err, warn = scriptmod.validate(sc)
    for w in warn:
        print("WARNING:", w)
    for e in err:
        print("ERROR:", e)
    print("VALID" if not err else "INVALID")
    return 0 if not err else 2


def _render_one(path, cfg, out_root, formats, resolution="1080p", fps=None, encoder="auto", engine_type="2d_cartoon", device_id=None):
    from .episode import produce
    sc = scriptmod.load(path)
    err, warn = scriptmod.validate(sc)
    for w in warn:
        _log("  warning: " + w)
    if err:
        raise ValueError("; ".join(err))
    out = Path(out_root) / sc["id"]
    # a script may ask for specific formats (e.g. long stories: horizontal only)
    if sc.get("formats") and list(formats) == list(cfg["video"]["formats"]):
        wanted = [f for f in sc["formats"] if f in ("vertical", "horizontal", "square")]
        formats = wanted or formats
    meta = produce(sc, cfg, out, formats, log=_log,
                   resolution=resolution, fps=fps, encoder=encoder,
                   engine_type=engine_type, device_id=device_id)
    meta["script_warnings"] = warn
    meta["folder"] = str(out)
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def cmd_render(a, cfg):
    out = Path(a.out) if a.out else ROOT / "output" / dt.date.today().isoformat()
    _log("render %s" % a.file)
    res = getattr(a, "resolution", "1080p")
    fps = getattr(a, "fps", None)
    enc = getattr(a, "encoder", "auto")
    eng = getattr(a, "engine", "2d_cartoon")
    dev = getattr(a, "device", None)
    meta = _render_one(a.file, cfg, out, _formats(a.format, cfg),
                       resolution=res, fps=fps, encoder=enc, engine_type=eng, device_id=dev)
    _log("done: %s (%.1fs video, rendered in %.0fs)" % (meta["folder"], meta["duration_seconds"], meta["render_seconds"]))
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


def cmd_hardware(a, cfg):
    from . import hardware
    info = hardware.detect_hardware()
    print("=== TAOYONGSTUDIO HARDWARE DETECTION ===")
    print("CPU:", info["cpu"]["name"], "(%d threads @ %d MHz)" % (info["cpu"]["logical_cores"], info["cpu"]["mhz"]))
    print("RAM: Total %.2f GB, Avail %.2f GB (Load %d%%)" % (info["ram"]["total_gb"], info["ram"]["avail_gb"], info["ram"]["load_percent"]))
    print("Disk: Free %.1f GB / %.1f GB" % (info["disk"]["free_gb"], info["disk"]["total_gb"]))
    print("\n--- Display Adapters (GPUs) ---")
    for g in info["gpus"]:
        print(" * %s (Provider: %s, Driver: %s)" % (g["name"], g["provider"], g["driver_version"]))
    print("\n--- Hardware Video Encoders ---")
    for k, v in info["encoders"].items():
        status = "READY" if v["ok"] else ("FAILED: " + v["error"])
        print(" * %-12s: %s" % (k, status))
    print("\n--- Available Animation Engines ---")
    for k, v in info["engines"].items():
        print(" * %-20s: %s" % (v["name"], v["status"]))
    print("\n--- Detected Devices for Studio V1 ---")
    for d in info["devices"]:
        print(" [ %s ] %s\n   Status: %s\n   Encoder: %s\n" % (d["id"], d["label"], d["status"], d["encoder"]))
    return 0


def cmd_batch(a, cfg):
    inbox = ROOT / "scripts" / "inbox"
    today = dt.date.today().isoformat()
    out_root = ROOT / "output" / today
    done_dir = ROOT / "scripts" / "done" / today
    fail_dir = ROOT / "scripts" / "failed" / today
    files = sorted(inbox.glob("*.json"))
    if a.limit:
        files = files[: a.limit]
    if not files:
        _log("inbox is empty: %s" % inbox)
        _compilations(cfg, out_root)
        return 0
    _log("batch start: %d script(s)" % len(files))
    report = {"date": today, "started": dt.datetime.now().isoformat(timespec="seconds"), "clips": []}
    for i, p in enumerate(files, 1):
        _log("(%d/%d) %s" % (i, len(files), p.name))
        t0 = time.time()
        try:
            meta = _render_one(p, cfg, out_root, _formats(a.format, cfg))
            done_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), done_dir / p.name)
            report["clips"].append({"script": p.name, "ok": True, "folder": meta["folder"],
                                    "title": meta["title"], "duration": meta["duration_seconds"],
                                    "needs_review": meta["needs_review"]})
            _log("  OK in %.0fs" % (time.time() - t0))
        except Exception as e:
            fail_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), fail_dir / p.name)
            (fail_dir / (p.stem + ".error.txt")).write_text(traceback.format_exc(), encoding="utf-8")
            report["clips"].append({"script": p.name, "ok": False, "error": str(e)[:500]})
            _log("  FAILED: %s" % e)
    report["finished"] = dt.datetime.now().isoformat(timespec="seconds")
    ok = sum(1 for c in report["clips"] if c["ok"])
    report["summary"] = "%d ok, %d failed" % (ok, len(report["clips"]) - ok)
    out_root.mkdir(parents=True, exist_ok=True)
    rp = out_root / ("batch_report_%s.json" % dt.datetime.now().strftime("%H%M%S"))
    rp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _log("batch finished: %s -> %s" % (report["summary"], rp))
    _compilations(cfg, out_root)
    return 0 if ok == len(report["clips"]) else 3


def _compilations(cfg, out_root):
    from . import compile as comp
    try:
        built = comp.run_pending(cfg, out_root, log=_log)
        if built:
            _log("compilations built: %d" % len(built))
    except Exception as e:
        _log("compilations FAILED: %s" % e)


def cmd_compile(a, cfg):
    from . import compile as comp
    out_root = ROOT / "output" / dt.date.today().isoformat()
    if a.file:
        spec = json.loads(Path(a.file).read_text(encoding="utf-8-sig"))
        spec.setdefault("id", Path(a.file).stem)
        meta = comp.build(spec, cfg, out_root, log=_log, force=a.force)
        return 0 if meta else 4
    comp.run_pending(cfg, out_root, log=_log, force=a.force)
    return 0


def cmd_still(a, cfg):
    from .episode import Episode
    sc = scriptmod.load(a.file)
    err, _ = scriptmod.validate(sc)
    if err:
        print("\n".join("ERROR: " + e for e in err))
        return 2
    ep = Episode(sc, cfg, _log).build()
    fmt = _formats(a.format, cfg)[0]
    out = Path(a.out or (ROOT / "output" / ("still_%s_%s.png" % (sc["id"], fmt))))
    out.parent.mkdir(parents=True, exist_ok=True)
    ep.still(fmt, min(a.at, ep.duration - 0.01)).save(out)
    print(out)
    return 0


def cmd_voices(a, cfg):
    try:
        import asyncio
        import edge_tts
        vs = asyncio.run(edge_tts.list_voices())
        for v in vs:
            if v["Locale"].startswith("th"):
                print("edge:", v["ShortName"], v["Gender"])
    except Exception as e:
        print("edge voices unavailable:", e)
    import os
    if os.name == "nt":
        import subprocess
        ps = ("Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer)"
              ".GetInstalledVoices() | % { $_.VoiceInfo.Name + ' | ' + $_.VoiceInfo.Culture }")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
        for ln in r.stdout.splitlines():
            print("sapi:", ln)
    return 0


def cmd_samples(a, cfg):
    src = ROOT / "scripts" / "samples"
    dst = ROOT / "scripts" / "inbox"
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in sorted(src.glob("*.json")):
        shutil.copy(p, dst / p.name)
        n += 1
    print("copied %d sample script(s) to %s" % (n, dst))
    return 0


def cmd_publish(a, cfg):
    from . import publish
    if a.what == "auto":
        _log("auto post start")
        publish.run_auto(cfg, log=_log, per_run=a.per_run)
        return 0
    if a.what == "status":
        st = publish.settings(cfg)
        print("mode:", st["mode"], " max/day:", st["max_per_day"], " times:", ", ".join(st["post_times"]))
        for p in publish.PLATFORMS:
            print("%-14s enabled=%s connected=%s %s" % (p, st[p].get("enabled"), publish.is_connected(p),
                                                     publish.account_name(p)))
        return 0
    if a.what == "clip":
        if not a.folder or not a.to:
            print("usage: studio publish clip --folder OUTPUT_FOLDER --to youtube|facebook_page|tiktok")
            return 2
        publish.post_clip(a.folder, a.to, cfg, log=_log, force=a.force)
        return 0
    return 2


def cmd_import_video(a, cfg):
    from .platform_workspace import import_video
    import_video(a.file, a.platform, a.title, a.description, a.tags, a.format,
                 a.source, a.ai_generated, a.made_for_kids, a.prompt, log=_log)
    return 0


def cmd_google_video(a, cfg):
    from .platform_workspace import generate_google_video
    generate_google_video(a.prompt, a.platform, a.title, a.description, a.tags, a.format,
                          a.resolution, a.made_for_kids, log=_log)
    return 0


def cmd_caption_video(a, cfg):
    from .caption_ai import caption_clip
    caption_clip(a.folder, a.platform, log=_log)
    return 0


def cmd_plan_generate(a, cfg):
    from .planner_generate import generate_request
    ids, comp = generate_request(a.request)
    _log("AI เขียนบทแล้ว %d บท%s" % (len(ids), " และคลิปรวม " + comp if comp else ""))
    return 0


def cmd_product_ideas(a, cfg):
    from .product_clips import build_ideas
    items = build_ideas(a.count, min_price=a.min_price, min_score=a.min_score)
    for it in items[:8]:
        _log("%s | %s" % (it["genre"], it["title"]))
    _log("สร้างไอเดียคลิปสินค้า %d รายการ → plans/product_ideas.json (พรอมต์ใน plans/product_prompts)" % len(items))
    return 0


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="studio", description="TaoYongStudio - Thai kids' cartoon clip maker")
    ap.add_argument("--config", help="path to config.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("hardware")
    p = sub.add_parser("validate")
    p.add_argument("file")
    p = sub.add_parser("render")
    p.add_argument("file")
    p.add_argument("--format", choices=["vertical", "horizontal", "square", "both", "config"], default="config")
    p.add_argument("--resolution", choices=["480p", "720p", "1080p", "4k"], default="1080p")
    p.add_argument("--fps", type=int, choices=[12, 24, 30], default=None)
    p.add_argument("--encoder", choices=["auto", "h264_nvenc", "h264_qsv", "h264_mf", "libx264"], default="auto")
    p.add_argument("--engine", choices=["2d_cartoon", "25d_parallax", "3d_blender", "ai_image_to_video", "ai_text_to_video"], default="2d_cartoon")
    p.add_argument("--device", default=None)
    p.add_argument("--out")
    p = sub.add_parser("batch")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--format", choices=["vertical", "horizontal", "both", "config"], default="config")
    p = sub.add_parser("still")
    p.add_argument("file")
    p.add_argument("--at", type=float, default=3.0)
    p.add_argument("--format", choices=["vertical", "horizontal"], default="vertical")
    p.add_argument("--out")
    p = sub.add_parser("compile")
    p.add_argument("file", nargs="?")
    p.add_argument("--force", action="store_true", help="build even if shorter than the target")
    p = sub.add_parser("publish")
    p.add_argument("what", choices=["auto", "status", "clip"])
    p.add_argument("--folder")
    p.add_argument("--to", choices=["youtube", "facebook_page", "tiktok"])
    p.add_argument("--per-run", type=int, default=1)
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("import-video")
    p.add_argument("file")
    p.add_argument("--platform", required=True, choices=["tiktok", "youtube", "shopee",
                                                          "facebook_profile", "facebook_page"])
    p.add_argument("--title", required=True)
    p.add_argument("--description", default="")
    p.add_argument("--tags", nargs="*", default=[])
    p.add_argument("--format", choices=["vertical", "horizontal"], default="vertical")
    p.add_argument("--source", choices=["computer", "google_flow"], default="computer")
    p.add_argument("--ai-generated", action="store_true")
    p.add_argument("--made-for-kids", action="store_true")
    p.add_argument("--prompt", default="")
    p = sub.add_parser("google-video")
    p.add_argument("--platform", required=True, choices=["tiktok", "youtube", "shopee",
                                                          "facebook_profile", "facebook_page"])
    p.add_argument("--title", required=True)
    p.add_argument("--description", default="")
    p.add_argument("--tags", nargs="*", default=[])
    p.add_argument("--format", choices=["vertical", "horizontal"], default="vertical")
    p.add_argument("--resolution", choices=["360p", "720p", "1080p", "4k"], default="720p")
    p.add_argument("--made-for-kids", action="store_true")
    p.add_argument("--prompt", required=True)
    p = sub.add_parser("caption-video")
    p.add_argument("--folder", required=True)
    p.add_argument("--platform", required=True, choices=["tiktok", "youtube", "shopee",
                                                          "facebook_profile", "facebook_page"])
    p = sub.add_parser("plan-generate")
    p.add_argument("--request", required=True)
    p = sub.add_parser("product-ideas")
    p.add_argument("--count", type=int, default=20)
    p.add_argument("--min-price", type=float, default=50.0)
    p.add_argument("--min-score", type=float, default=0)
    sub.add_parser("voices")
    sub.add_parser("samples")
    a = ap.parse_args(argv)
    cfg = config.load(a.config)
    fn = {"check": cmd_check, "hardware": cmd_hardware, "validate": cmd_validate, "render": cmd_render, "batch": cmd_batch,
          "still": cmd_still, "voices": cmd_voices, "samples": cmd_samples,
          "publish": cmd_publish, "compile": cmd_compile,
          "import-video": cmd_import_video, "google-video": cmd_google_video,
          "caption-video": cmd_caption_video, "plan-generate": cmd_plan_generate,
          "product-ideas": cmd_product_ideas}[a.cmd]
    return fn(a, cfg)
