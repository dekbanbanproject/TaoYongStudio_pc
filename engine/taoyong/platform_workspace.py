"""Bring locally made and Google-made videos into the shared clip library."""
import base64
import datetime as dt
import json
import os
import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import requests

from .audio import ffmpeg_exe
from .config import ROOT


FORMATS = {"vertical": (1080, 1920), "horizontal": (1920, 1080)}
GOOGLE_MODEL = "gemini-omni-1.1-flash"
GOOGLE_API = "https://generativelanguage.googleapis.com/v1beta"


def prompt_from_script(script, platform="tiktok", fmt="vertical"):
    """Turn the selected story into a ready-to-use video prompt."""
    title = str(script.get("title", "")).strip()
    description = str(script.get("description", "")).strip()
    lines = []
    for scene in script.get("scenes", [])[:4]:
        for beat in scene.get("beats", [])[:5]:
            if beat.get("say"):
                lines.append(str(beat["say"]).strip())
    dialogue = " / ".join(lines[:10])
    orientation = "9:16 vertical" if fmt == "vertical" else "16:9 horizontal"
    return (f"Create a cheerful, safe Thai children's cartoon video, {orientation}, for {platform}. "
            f"Story: {title}. {description} "
            f"Characters: {', '.join(script.get('characters', []))}. "
            f"Key Thai dialogue and story beats: {dialogue}. "
            "Bright 2D animation, clear visual storytelling, friendly expressions, no logos, "
            "no watermark, no unsafe content. Keep Thai words accurate if any text is shown.").strip()


def flow_prompts_from_script(script, fmt="vertical"):
    """Prepare a Flow Agent brief and shorter prompts for individual scenes."""
    orientation = "9:16 vertical" if fmt == "vertical" else "16:9 horizontal"
    characters = {
        "bunny": "Pui Fai, a small white rabbit with long ears and a pink nose",
        "bear": "Cocoa, a small warm-brown bear with round ears",
        "chick": "Jiab, a fluffy yellow chick with a tiny orange beak",
        "cat": "Miu Miu, a small cream-colored kitten with gentle eyes",
    }
    backgrounds = {
        "meadow": "a flower-filled meadow",
        "beach": "a sunny beach",
        "night": "a calm starry night sky",
        "bedroom": "a cozy child's bedroom",
        "classroom": "a cheerful classroom",
    }
    cast = "; ".join(characters.get(name, name) for name in script.get("characters", []))
    action_verbs = {"talk": "speaks gently", "wave": "waves", "jump": "jumps",
                    "cheer": "cheers", "point": "points", "happy": "smiles",
                    "dance": "dances", "none": "rests calmly"}
    style = (f"Polished children's animated film, {orientation}, gentle expressive character animation, "
             "smooth natural motion, layered backgrounds, soft cinematic lighting, warm colors, "
             "consistent character designs across every shot. Safe and calming for young children. "
             "No captions, logos, or written words on screen. ")
    scenes = []
    for number, scene in enumerate(script.get("scenes", []), 1):
        location = backgrounds.get(scene.get("background"), "a playful cartoon setting")
        actions = []
        for beat in scene.get("beats", []):
            if beat.get("who") and beat.get("say"):
                name = beat["who"]
                speech = str(beat["say"]).strip()
                if name == "narrator":
                    actions.append(f"Thai narrator voiceover: {speech}")
                else:
                    action = action_verbs.get(beat.get("action"), "speaks gently")
                    actions.append(f"{name} {action} and says: {speech}")
        scene_text = f"Scene {number}, {location}. " + " / ".join(actions)
        scenes.append(scene_text)
    story = str(script.get("title", "")).strip()
    overview = str(script.get("description", "")).strip()
    whole = ("Google Flow Agent / Scenebuilder brief. Make a sequence of short animated clips "
             "for this Thai children's story, keeping the same characters and art style in every clip. "
             "Create one variation of each 8-second shot and assemble them in story order. "
             f"Story: {story}. {overview} {style}Characters: {cast}. "
             + " ".join(scenes) + " If a single generation can only make one short clip, "
             "start with Scene 1 and continue scene by scene. Use gentle Thai voices only if the "
             "spoken words can be accurate; otherwise make the video without dialogue.")
    prompts = [("ทั้งเรื่อง (Flow Agent)", whole.strip())]
    for number, scene_text in enumerate(scenes, 1):
        prompt = (f"Create one 8-second animated shot for the story '{story}'. {style}"
                  f"Characters: {cast}. {scene_text} "
                  "Focus on the visible action and expressions. Keep character designs consistent "
                  "with the other shots. No dialogue unless the Thai words can be accurate.")
        prompts.append((f"ฉาก {number}", prompt.strip()))
    return prompts


def probe_video(path):
    result = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=30)
    info = result.stderr
    duration = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", info)
    video = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", info)
    if not duration or not video:
        raise ValueError("ไฟล์นี้ไม่ใช่วิดีโอที่อ่านได้ หรือไม่มีภาพวิดีโอ")
    seconds = int(duration[1]) * 3600 + int(duration[2]) * 60 + float(duration[3])
    if seconds <= 0:
        raise ValueError("วิดีโอต้องมีความยาวมากกว่า 0 วินาที")
    return seconds, int(video[1]), int(video[2])


def import_video(source_path, platform, title, description="", tags=None, fmt="vertical",
                 source="computer", ai_generated=False, made_for_kids=True, prompt="", root=ROOT,
                 log=print):
    """Convert a video to a publishable MP4 and add metadata used by the clip and post tabs."""
    src = Path(source_path)
    if not src.is_file():
        raise FileNotFoundError(src)
    if fmt not in FORMATS:
        raise ValueError("รูปแบบวิดีโอไม่ถูกต้อง")
    title = title.strip() or src.stem
    duration, _, _ = probe_video(src)
    clip_id = "custom-%s-%s" % (dt.datetime.now().strftime("%H%M%S"), uuid.uuid4().hex[:8])
    folder = Path(root) / "output" / dt.date.today().isoformat() / clip_id
    folder.mkdir(parents=True, exist_ok=False)
    width, height = FORMATS[fmt]
    mp4 = folder / (clip_id + "_" + fmt + ".mp4")
    vf = ("scale=%d:%d:force_original_aspect_ratio=decrease,"
          "pad=%d:%d:(ow-iw)/2:(oh-ih)/2:black,setsar=1") % (width, height, width, height)
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
           "-map", "0:v:0", "-map", "0:a:0?", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
           "-movflags", "+faststart", str(mp4)]
    try:
        log("กำลังแปลงวิดีโอเป็น %s..." % ("แนวตั้ง" if fmt == "vertical" else "แนวนอน"))
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode:
            raise RuntimeError("แปลงวิดีโอไม่สำเร็จ: " + result.stderr[-500:])
        duration, _, _ = probe_video(mp4)
        thumb = folder / ("thumb_%s.jpg" % fmt)
        subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-ss",
                        str(min(0.5, duration / 2)), "-i", str(mp4), "-frames:v", "1", str(thumb)],
                       capture_output=True, check=True)
        clean_tags = [str(tag).strip().lstrip("#") for tag in (tags or []) if str(tag).strip()]
        upload = "%s\n\n%s\n\n%s\n" % (title, description.strip(),
                                          " ".join("#" + tag.replace(" ", "") for tag in clean_tags[:8]))
        (folder / "upload.txt").write_text(upload, encoding="utf-8")
        files = {fmt: mp4.name, "thumb_" + fmt: thumb.name, "upload_text": "upload.txt"}
        meta = {"id": clip_id, "title": title, "description": description.strip(), "tags": clean_tags,
                "made_for_kids": bool(made_for_kids), "ai_generated": bool(ai_generated),
                "duration_seconds": round(duration, 2), "files": files, "source": source,
                "source_prompt": prompt.strip(), "target_platforms": [platform],
                "platform_formats": {platform: fmt}, "voice_engines": [], "music": "",
                "needs_review": ["ตรวจภาพ เสียง และข้อความก่อนเผยแพร่"],
                "status": "ready_for_approval", "posts": {}}
        (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        log("CREATED: " + str(folder))
        return folder
    except Exception:
        for file in folder.iterdir():
            file.unlink()
        folder.rmdir()
        raise


def _google_video_output(response):
    for step in response.get("steps", []):
        if step.get("type") == "model_output":
            for content in step.get("content", []):
                if content.get("type") == "video":
                    return content
    raise RuntimeError("Google ไม่ส่งไฟล์วิดีโอกลับมา: %s" % response.get("status", "ไม่ทราบสถานะ"))


def generate_google_video(prompt, platform, title, description="", tags=None, fmt="vertical",
                          resolution="720p", made_for_kids=True, root=ROOT, log=print,
                          api_key=None, session=requests):
    """Generate with the paid Gemini Omni Flash API, then register the clip locally."""
    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise ValueError("ต้องใส่ Gemini API key ของโปรเจกต์ที่เปิดการชำระเงิน")
    if not prompt.strip():
        raise ValueError("กรุณาใส่คำอธิบายวิดีโอ")
    if resolution not in ("360p", "720p", "1080p", "4k"):
        raise ValueError("ความละเอียดไม่ถูกต้อง")
    if fmt not in FORMATS:
        raise ValueError("รูปแบบวิดีโอไม่ถูกต้อง")
    headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
    body = {"model": GOOGLE_MODEL, "input": prompt.strip(), "background": False, "store": False,
            "stream": False, "response_format": {"type": "video", "delivery": "uri",
                                             "aspect_ratio": "9:16" if fmt == "vertical" else "16:9",
                                             "resolution": resolution}}
    log("กำลังขอวิดีโอจาก Google Gemini Omni Flash (มีค่าใช้จ่าย)...")
    response = session.post(GOOGLE_API + "/interactions", headers=headers, json=body, timeout=(15, 600))
    if not response.ok:
        raise RuntimeError("Google API HTTP %s: %s" % (response.status_code, response.text[:350]))
    video = _google_video_output(response.json())
    cache = Path(root) / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache) as tmp:
        path = Path(tmp) / "google_video.mp4"
        if video.get("data"):
            path.write_bytes(base64.b64decode(video["data"], validate=True))
        elif video.get("uri"):
            match = re.search(r"/files/([A-Za-z0-9_-]+)", video["uri"])
            if not match:
                raise RuntimeError("Google ส่งที่อยู่ไฟล์วิดีโอที่ไม่ถูกต้อง")
            file_id = match[1]
            log("กำลังรอ Google เตรียมไฟล์วิดีโอ...")
            for _ in range(120):
                info = session.get(GOOGLE_API + "/files/" + file_id, headers=headers, timeout=30)
                info.raise_for_status()
                state = info.json().get("state", "")
                state = state.get("name", "") if isinstance(state, dict) else state
                if state == "ACTIVE":
                    break
                if state == "FAILED":
                    raise RuntimeError("Google เตรียมไฟล์วิดีโอไม่สำเร็จ")
                time.sleep(5)
            else:
                raise TimeoutError("รอไฟล์จาก Google นานเกิน 10 นาที")
            download = session.get(GOOGLE_API + "/files/" + file_id + ":download?alt=media",
                                   headers=headers, stream=True, timeout=(15, 300))
            download.raise_for_status()
            with path.open("wb") as stream:
                for chunk in download.iter_content(1024 * 1024):
                    if chunk:
                        stream.write(chunk)
        else:
            raise RuntimeError("Google ไม่ส่งไฟล์วิดีโอกลับมา")
        return import_video(path, platform, title, description, tags, fmt, "google_omni", True,
                            made_for_kids, prompt, root, log)
