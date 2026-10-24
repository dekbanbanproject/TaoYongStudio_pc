"""Ask Gemini to prepare Thai post text from sampled video frames."""
import base64
import json
import os
import subprocess
from pathlib import Path

import requests

from .audio import ffmpeg_exe
from .platform_workspace import probe_video

MODEL = "gemini-3.8-flash"
URL = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % MODEL
PLATFORM_LABELS = {"tiktok": "TikTok", "youtube": "YouTube", "shopee": "Shopee",
                   "facebook_profile": "Facebook Profile", "facebook_page": "Facebook Page"}


def _frames(video):
    duration, _, _ = probe_video(video)
    for fraction in (0.12, 0.5, 0.88):
        at = duration * min(fraction, 0.7)
        def extract(position):
            return subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-ss", str(position),
                                   "-i", str(video), "-frames:v", "1", "-vf", "scale=480:-2",
                                   "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1"],
                                  capture_output=True, timeout=45)
        proc = extract(at)
        if not proc.stdout:
            proc = extract(0)
        if proc.returncode or not proc.stdout:
            raise RuntimeError("อ่านภาพจากวิดีโอไม่สำเร็จ")
        yield base64.b64encode(proc.stdout).decode("ascii")


def create_caption(video, platform, key=None, session=requests):
    key = key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise ValueError("ต้องตั้ง Gemini API key ก่อนให้ AI เขียนข้อความจากคลิป")
    if platform not in PLATFORM_LABELS:
        raise ValueError("แพลตฟอร์มไม่ถูกต้อง")
    prompt = ("You are the Thai social media editor for a children's cartoon studio. "
              "Look at these three frames from one video. Create a truthful Thai post for "
              f"{PLATFORM_LABELS[platform]}. Do not invent spoken words, characters, products, "
              "outcomes or claims that are not visible. Keep title under 80 characters, "
              "description 1-2 short sentences, and 3-6 relevant Thai hashtags without #. "
              "If the frames are not informative, say only what is visible. "
              "Return JSON object with title, description, tags (string array).")
    parts = [{"text": prompt}] + [{"inlineData": {"mimeType": "image/jpeg", "data": frame}}
                                for frame in _frames(video)]
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.4}}
    response = session.post(URL, headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                            json=body, timeout=(15, 120))
    if not response.ok:
        raise RuntimeError("Gemini API HTTP %s: %s" % (response.status_code, response.text[:300]))
    candidates = response.json().get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini ไม่ส่งข้อความโพสต์กลับมา")
    output = "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", []))
    data = json.loads(output)
    title = str(data.get("title", "")).strip()[:100]
    description = str(data.get("description", "")).strip()[:1000]
    tags = [str(t).strip().lstrip("#") for t in data.get("tags", []) if str(t).strip()][:8]
    if not title or not description or not tags:
        raise RuntimeError("AI ส่งชื่อเรื่อง คำอธิบาย หรือแฮชแท็กไม่ครบ")
    return {"title": title, "description": description, "tags": tags, "source": MODEL}


def caption_clip(folder, platform, key=None, session=requests, log=print):
    folder = Path(folder)
    path = folder / "meta.json"
    meta = json.loads(path.read_text(encoding="utf-8"))
    fmt = (meta.get("platform_formats") or {}).get(platform, "vertical")
    files = meta.get("files") or {}
    name = files.get(fmt) or files.get("vertical") or files.get("horizontal")
    if not name:
        raise FileNotFoundError("ไม่พบไฟล์วิดีโอในคลิป")
    result = create_caption(folder / name, platform, key, session)
    meta.setdefault("platform_captions", {})[platform] = result
    if meta.get("source") == "computer":
        meta.update({field: result[field] for field in ("title", "description", "tags")})
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    upload_name = (meta.get("files") or {}).get("upload_text")
    if upload_name:
        text = "%s\n\n%s\n\n%s\n" % (
            result["title"], result["description"], " ".join("#" + t.replace(" ", "") for t in result["tags"]))
        (folder / upload_name).write_text(text, encoding="utf-8")
    log("AI เขียนชื่อเรื่อง คำอธิบาย และแฮชแท็กแล้ว")
    return result
