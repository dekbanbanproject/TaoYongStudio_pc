"""Pipeline orchestrator for Cute Toy Product Ad Animation with Thai Graphic Overlays."""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .. import audio
from ..config import ROOT

SCRIPT_DIR = Path(__file__).resolve().parent
BUILDER_SCRIPT = SCRIPT_DIR / "builder.py"


def get_blender_path():
    """Locate Blender 4.2+ executable."""
    common_paths = [
        Path(r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"),
        Path(r"C:\Program Files\Blender Foundation\Blender\blender.exe"),
    ]
    for p in common_paths:
        if p.exists():
            return str(p)
    system_blender = shutil.which("blender")
    if system_blender:
        return system_blender
    return None


def select_best_encoder(preferred="auto"):
    """Select best hardware video encoder available."""
    from .. import hardware
    hw = hardware.detect_hardware()
    encoders = hw.get("encoders", {})
    if preferred != "auto" and encoders.get(preferred, {}).get("ok"):
        return preferred
    if encoders.get("h264_nvenc", {}).get("ok"):
        return "h264_nvenc"
    if encoders.get("h264_qsv", {}).get("ok"):
        return "h264_qsv"
    if encoders.get("h264_mf", {}).get("ok"):
        return "h264_mf"
    return "libx264"


_FONT_CACHE = {}


def _get_cached_font(size):
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    font_path = ROOT / "fonts" / "Prompt-Bold.ttf"
    if font_path.exists():
        try:
            f = ImageFont.truetype(str(font_path), size)
            _FONT_CACHE[size] = f
            return f
        except Exception:
            pass
    f = ImageFont.load_default()
    _FONT_CACHE[size] = f
    return f


def apply_product_ad_overlays(frame_path, price_text="฿99", promo_text="ลด 50% ส่งฟรี", cta_text="🛒 สั่งซื้อที่ตะกร้าเหลือง"):
    """Apply crisp Thai promotional badges and price graphics onto rendered frame."""
    try:
        im = Image.open(frame_path).convert("RGBA")
        W, H = im.size
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        font_large = _get_cached_font(int(H * 0.045))
        font_med = _get_cached_font(int(H * 0.028))
        font_small = _get_cached_font(int(H * 0.024))

        # 1. Price Badge (Top-Right / Top-Left)
        badge_w = int(W * 0.38)
        badge_h = int(H * 0.11)
        bx0 = int(W * 0.05)
        by0 = int(H * 0.06)
        bx1 = bx0 + badge_w
        by1 = by0 + badge_h

        # Rounded Red-Orange Badge
        draw.rounded_rectangle([bx0, by0, bx1, by1], radius=16, fill=(245, 60, 50, 235), outline=(255, 255, 255, 255), width=3)
        # Price Text
        draw.text((bx0 + 16, by0 + 10), price_text, font=font_large, fill=(255, 255, 255, 255))
        # Promo pill
        draw.rounded_rectangle([bx0 + 16, by0 + int(badge_h * 0.58), bx1 - 16, by1 - 10], radius=8, fill=(255, 220, 40, 245))
        draw.text((bx0 + 24, by0 + int(badge_h * 0.60)), promo_text, font=font_small, fill=(40, 20, 10, 255))

        # 2. Bottom Call-To-Action (CTA) Pill
        cta_w = int(W * 0.86)
        cta_h = int(H * 0.065)
        cx0 = int((W - cta_w) / 2)
        cy0 = int(H * 0.88)
        cx1 = cx0 + cta_w
        cy1 = cy0 + cta_h

        draw.rounded_rectangle([cx0, cy0, cx1, cy1], radius=24, fill=(255, 87, 34, 240), outline=(255, 255, 255, 255), width=3)
        draw.text((cx0 + int(cta_w * 0.12), cy0 + int(cta_h * 0.22)), cta_text, font=font_med, fill=(255, 255, 255, 255))

        out = Image.alpha_composite(im, overlay).convert("RGB")
        out.save(frame_path, "PNG")
    except Exception:
        pass


def render_toy_ad_animation(
    script_data,
    output_dir,
    options=None,
    progress_callback=None,
    cancel_event=None,
    logger=None,
    target_mp4=None,
):
    """
    Execute the full Cute Toy Product Ad Animation pipeline.
    Returns dict with generated video file info, duration, resolution, fps, and render metrics.
    """
    options = options or {}
    logger = logger or print

    def log(msg):
        try:
            logger(msg)
        except Exception:
            try:
                clean = msg.encode("ascii", "replace").decode("ascii")
                logger(clean)
            except Exception:
                pass

    # 1. Verify Blender
    blender_path = get_blender_path()
    if not blender_path:
        raise RuntimeError("ไม่พบโปรแกรม Blender 4.2+ บนเครื่อง กรุณาติดตั้ง Blender 4.2 LTS ก่อนใช้งาน Engine นี้")

    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = (out_dir / "_toy_tmp").resolve()
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 2. Extract options
    duration = float(options.get("duration", 6.0))
    fps = int(options.get("fps", 24))
    aspect = options.get("aspect", "9:16")  # Default vertical 9:16 for Reels/TikTok/Shopee
    character = options.get("character", "vinyl_bear")
    environment = options.get("environment", "cozy_desk")
    product_image = options.get("product_image", None)
    price_text = options.get("price_text", "฿99")
    promo_text = options.get("promo_text", "ลด 50% ส่งฟรี")
    cta_text = options.get("cta_text", "🛒 สั่งซื้อที่ตะกร้าเหลือง")
    speech_text = options.get("speech_text", "")
    title = options.get("title", "")
    render_engine = options.get("render_engine", "BLENDER_WORKBENCH")

    fmt_name = "vertical" if aspect == "9:16" else ("square" if aspect == "1:1" else "horizontal")

    # Extract info from script_data
    if script_data:
        if not title and script_data.get("title"):
            title = script_data["title"]
        if not speech_text:
            texts = []
            for sc in script_data.get("scenes", []):
                for b in sc.get("beats", []):
                    txt = b.get("say", b.get("text", "")).strip()
                    if txt:
                        texts.append(txt)
            if texts:
                speech_text = " ".join(texts)
            elif script_data.get("text"):
                speech_text = script_data.get("text")

    if not title:
        title = "โฆษณาสินค้าน่ารัก 3D ฟิกเกอร์สตูดิโอ"

    # Resolution mapping
    res_str = options.get("resolution", "1080p")
    if aspect == "9:16":
        if "720" in res_str:
            w, h = 720, 1280
        elif "480" in res_str:
            w, h = 480, 854
        else:
            w, h = 1080, 1920
    else:  # 16:9
        if "720" in res_str:
            w, h = 1280, 720
        elif "480" in res_str:
            w, h = 854, 480
        else:
            w, h = 1920, 1080

    total_frames = int(duration * fps)
    encoder = select_best_encoder(options.get("encoder", "auto"))

    log(f"🎬 เริ่มต้นกระบวนการ Cute Toy Product Ad Animation: {title}")
    log(f"⚙️ สเปก: {w}x{h} ({aspect}) @ {fps} FPS, เวลา {duration:.1f} วิ ({total_frames} เฟรม)")
    log(f"🧸 ฟิกเกอร์: {character} | ฉาก: {environment} | ราคา: {price_text} ({promo_text})")
    log(f"💻 ตัวเรนเดอร์: Blender 4.2 ({render_engine}) | ตัวเข้ารหัส: {encoder}")

    if progress_callback:
        progress_callback(5, "กำลังเตรียมฉากสตูดิโอและแท่นโชว์สินค้า 3D...")

    # 3. Audio Track Setup
    custom_wav = options.get("audio_wav")
    audio_wav_path = temp_dir / "audio_track.wav"
    has_audio = False

    if custom_wav and Path(custom_wav).exists():
        audio_wav_path = Path(custom_wav)
        has_audio = True
        log(f"PROGRESS_STAGE: audio 100% (ใช้แทร็กเสียงพากย์และดนตรีที่จัดเตรียมไว้: {audio_wav_path.name})")
    else:
        try:
            if speech_text:
                log("PROGRESS_STAGE: tts 40% (กำลังสังเคราะห์เสียงพากย์โฆษณาภาษาไทย)")
                from .. import tts
                from ..config import load as load_cfg
                cfg = load_cfg()
                engines = cfg["tts"]["engines"]
                vc = cfg["voices"].get("chick", cfg["voices"].get("narrator", {}))
                tts_cache = ROOT / "cache" / "tts"
                tts_cache.mkdir(parents=True, exist_ok=True)
                voice_samples, eng_used = tts.synth_with_fallback(speech_text, vc, engines, tts_cache, log, allow_test=True)
                dur_voice = len(voice_samples) / audio.SR
                if dur_voice > duration:
                    duration = dur_voice + 0.8
                    total_frames = int(duration * fps)

                # Upbeat cheerful commercial sound
                log("PROGRESS_STAGE: audio 70% (กำลังรวมแทร็กเสียงดนตรีโฆษณา)")
                import numpy as np
                n_samples = int(duration * audio.SR)
                mix_audio = np.zeros(n_samples, dtype=np.float32)
                audio._add(mix_audio, 0.2, voice_samples * 1.0)
                try:
                    sfx_pop = audio.sfx_pop()
                    audio._add(mix_audio, 0.1, sfx_pop * 0.3)
                    audio._add(mix_audio, duration - 0.5, audio.sfx_chime() * 0.45)
                except Exception:
                    pass
                audio.write_wav(audio_wav_path, mix_audio)
                has_audio = True
        except Exception as e:
            log(f"⚠️ การสร้างเสียงพากย์ขัดข้อง: {e}")

        if not has_audio or not audio_wav_path.exists():
            import numpy as np
            n_samples = int(duration * audio.SR)
            ambient = np.zeros(n_samples, dtype=np.float32)
            try:
                audio._add(ambient, 0.1, audio.sfx_pop() * 0.25)
            except Exception:
                pass
            audio.write_wav(audio_wav_path, ambient)
            has_audio = True

    # 4. Generate Subtitles File (.srt)
    srt_path = temp_dir / "subtitles.srt"
    if speech_text:
        srt_content = (
            f"1\n00:00:00,200 --> 00:00:{int(duration):02d},{int((duration%1)*1000):03d}\n"
            f"{speech_text}\n"
        )
        srt_path.write_text(srt_content, encoding="utf-8")
        shutil.copyfile(srt_path, out_dir / "subtitles.srt")

    # 5. Write Blender Spec JSON
    frames_dir = (temp_dir / "frames").resolve()
    frames_dir.mkdir(parents=True, exist_ok=True)
    frames_pattern = str(frames_dir / "frame_")

    spec = {
        "duration": duration,
        "fps": fps,
        "aspect": aspect,
        "character": character,
        "environment": environment,
        "product_image": str(product_image) if product_image else None,
        "render_engine": render_engine,
        "output_frames_pattern": frames_pattern,
        "res_x": w,
        "res_y": h,
    }
    spec_path = temp_dir / "toy_ad_spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

    if progress_callback:
        progress_callback(15, f"กำลังเรนเดอร์โมเดล 3D Toy Product ด้วย Blender ({render_engine})...")

    # 6. Execute Blender Rendering
    cmd_blender = [
        blender_path,
        "--background",
        "--python", str(BUILDER_SCRIPT),
        "--",
        "--spec", str(spec_path),
    ]

    log(f"🚀 เรียกใช้ Blender 3D Toy Ad Worker ({render_engine})...")
    t_start = time.time()
    proc = subprocess.Popen(
        cmd_blender,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )

    rendered_frames = 0
    while True:
        if cancel_event and cancel_event.is_set():
            proc.kill()
            log("🛑 ผู้ใช้กดยกเลิกการสร้างแอนิเมชัน 3D")
            raise RuntimeError("ผู้ใช้กดยกเลิกการทำงาน")

        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break

        line_clean = line.strip()
        if line_clean:
            if "Saved:" in line_clean or "Fra:" in line_clean:
                rendered_frames += 1
                pct = min(85, int(15 + (rendered_frames / max(1, total_frames)) * 70))
                now = time.time()
                elapsed = now - t_start
                fps_now = rendered_frames / max(0.01, elapsed)
                eta = int((total_frames - rendered_frames) / max(0.1, fps_now))
                log(f"PROGRESS: stage=render fmt={fmt_name} pct={pct} frame={rendered_frames} total_frames={total_frames} fps={fps_now:.1f} eta={eta}s")
                if rendered_frames % max(1, total_frames // 8) == 0 or rendered_frames == total_frames:
                    log(f"  {fmt_name} {pct}% (เฟรม {rendered_frames}/{total_frames})")
                if progress_callback:
                    progress_callback(pct, f"กำลังเรนเดอร์เฟรม 3D: {rendered_frames}/{total_frames} ({pct}%)")
            elif "Extensions: writing cache failed" not in line_clean:
                if any(k in line_clean for k in ["STARTING", "COMPLETE", "Mem:", "Time:"]):
                    log(f"  [Blender] {line_clean}")

    ret = proc.poll()
    render_time = time.time() - t_start
    if ret != 0:
        raise RuntimeError(f"Blender ทำงานผิดพลาด (exit code {ret})")

    log(f"✅ เรนเดอร์ภาพ 3D ครบ {total_frames} เฟรม ใช้เวลา {render_time:.2f} วินาที ({render_time/max(1,total_frames):.2f}s/frame)")

    # 7. Apply Promotional Graphic Overlays onto Frames
    log(f"🎨 เพิ่มกราฟิกราคา '{price_text}', โปรโมชั่น '{promo_text}' และปุ่มสั่งซื้อภาษาไทย...")
    for f_idx in range(1, total_frames + 1):
        f_path = frames_dir / f"frame_{f_idx:04d}.png"
        if f_path.exists():
            apply_product_ad_overlays(f_path, price_text=price_text, promo_text=promo_text, cta_text=cta_text)

    if progress_callback:
        progress_callback(92, f"กำลังรวมแทร็กภาพ เสียง และเข้ารหัสวิดีโอ ({encoder})...")

    # 8. Encode Video with FFmpeg
    ff = audio.ffmpeg_exe()
    if target_mp4:
        out_video_path = Path(target_mp4).resolve()
        out_video_name = out_video_path.name
    else:
        out_video_name = f"toy_ad_{character}_{aspect.replace(':', 'x')}.mp4"
        out_video_path = out_dir / out_video_name

    input_img_seq = str(frames_dir / "frame_%04d.png")

    cmd_ffmpeg = [
        ff, "-y",
        "-framerate", str(fps),
        "-i", input_img_seq,
        "-i", str(audio_wav_path),
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
    ]

    if encoder == "h264_qsv":
        cmd_ffmpeg.extend(["-c:v", "h264_qsv", "-global_quality", "22", "-preset", "veryfast"])
    elif encoder == "h264_nvenc":
        cmd_ffmpeg.extend(["-c:v", "h264_nvenc", "-cq", "22", "-preset", "p4"])
    elif encoder == "h264_mf":
        cmd_ffmpeg.extend(["-c:v", "h264_mf"])
    else:
        cmd_ffmpeg.extend(["-c:v", "libx264", "-crf", "22", "-preset", "veryfast"])

    cmd_ffmpeg.append(str(out_video_path))

    log(f"📦 รวมไฟล์วิดีโอด้วย FFmpeg ({encoder})...")
    res_ff = subprocess.run(cmd_ffmpeg, capture_output=True, text=True, errors="ignore")
    if res_ff.returncode != 0:
        log(f"⚠️ Encoder {encoder} ล้มเหลว ({res_ff.stderr.strip()[:160]}) ลองใช้ libx264...")
        encoder = "libx264"
        cmd_fallback = [
            ff, "-y",
            "-framerate", str(fps),
            "-i", input_img_seq,
            "-i", str(audio_wav_path),
            "-c:v", "libx264",
            "-crf", "22",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(out_video_path),
        ]
        res_ff2 = subprocess.run(cmd_fallback, capture_output=True, text=True, errors="ignore")
        if res_ff2.returncode != 0:
            raise RuntimeError(f"FFmpeg encoding failed: {res_ff2.stderr[:300]}")

    # Generate Thumbnails (.jpg)
    thumb_fmt_path = out_dir / f"thumb_{fmt_name}.jpg"
    thumb_gen_path = out_dir / "thumb.jpg"
    first_frame = frames_dir / "frame_0001.png"
    if first_frame.exists():
        try:
            im = Image.open(first_frame).convert("RGB")
            im.save(thumb_fmt_path, "JPEG", quality=92)
            im.save(thumb_gen_path, "JPEG", quality=92)
        except Exception:
            pass

    # Clean temporary frame files
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass

    # Probe Video
    probe_res = {}
    try:
        from .. import hardware
        log(f"PROGRESS_STAGE: verify 100% (กำลังตรวจสอบความสมบูรณ์ของไฟล์วิดีโอ {fmt_name})")
        probe_res = hardware.probe_video(out_video_path)
        if probe_res.get("ok"):
            log(f"  verified: {probe_res['resolution']}, {probe_res['duration_seconds']}s, {probe_res['video_codec']}, {probe_res['size_mb']}MB")
    except Exception as e:
        probe_res = {"ok": False, "error": str(e)}

    if progress_callback:
        progress_callback(100, "🎉 สร้างแอนิเมชัน Cute Toy Product Ad เสร็จสมบูรณ์แล้ว!")

    log(f"🎉 สร้างวิดีโอ Toy Product Ad สำเร็จเรียบร้อย: {out_video_path}")
    log(f"📊 ขนาดไฟล์: {os.path.getsize(out_video_path)/1024:.1f} KB | เวลาเรนเดอร์ทั้งหมด: {time.time()-t_start:.1f} วินาที")

    meta = {
        "title": title,
        "engine": "cute_toy_ad",
        "engine_label": "Cute Toy Product Ad Animation — โฆษณาสินค้า 3D ของเล่น",
        "character": character,
        "environment": environment,
        "price_text": price_text,
        "promo_text": promo_text,
        "product_image": str(product_image) if product_image else None,
        "aspect": aspect,
        "resolution": f"{w}x{h}",
        "fps": fps,
        "duration": duration,
        "render_time_sec": round(render_time, 2),
        "encoder": encoder,
        "video_file": str(out_video_path),
        "speech_text": speech_text,
        "probe": probe_res,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return meta
