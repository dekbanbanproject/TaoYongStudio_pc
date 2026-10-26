"""3D Chibi Pastel Animation Production Pipeline.
Coordinates 3D Blender asset generation, camera motion, Thai TTS audio,
subtitles, and FFmpeg encoding into final broadcast-quality MP4.
"""
import os
import sys
import json
import time
import shutil
import subprocess
import threading
from pathlib import Path

from ..config import ROOT
from .. import audio
from .. import hardware

BLENDER_EXE = r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"
BUILDER_SCRIPT = Path(__file__).parent / "builder.py"


def get_blender_path():
    """Locate the Blender 4.2 LTS executable."""
    if os.path.exists(BLENDER_EXE):
        return BLENDER_EXE
    h_info = hardware.check_blender()
    if h_info.get("installed") and h_info.get("path"):
        return h_info["path"]
    which = shutil.which("blender")
    if which:
        return which
    return None


def select_best_encoder(requested="auto"):
    """Select the best verified hardware encoder for the machine."""
    if requested and requested != "auto":
        return requested
    try:
        hw = hardware.detect_hardware()
        encs = hw.get("encoders", {})
        if encs.get("h264_nvenc", {}).get("ok"):
            return "h264_nvenc"
        if encs.get("h264_qsv", {}).get("ok"):
            return "h264_qsv"
        if encs.get("h264_mf", {}).get("ok"):
            return "h264_mf"
    except Exception:
        pass
    return "libx264"


def render_chibi_animation(
    script_data,
    output_dir,
    options=None,
    progress_callback=None,
    cancel_event=None,
    logger=None,
    target_mp4=None,
):
    """
    Execute the full 3D Chibi Pastel Animation pipeline.
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
    temp_dir = (out_dir / "_chibi_tmp").resolve()
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 2. Extract options
    duration = float(options.get("duration", 6.0))
    fps = int(options.get("fps", 24))
    aspect = options.get("aspect", "9:16")
    preset = options.get("preset", "sweet_candy")
    character = options.get("character", "khao_hom")
    environment = options.get("environment", "garden_house")
    action = options.get("action", "wave")
    speech_text = options.get("speech_text", "")
    title = options.get("title", "")
    render_engine = options.get("render_engine", "BLENDER_WORKBENCH")

    # Map aspect ratio to format name
    fmt_name = "vertical" if aspect == "9:16" else ("square" if aspect == "1:1" else "horizontal")

    # Parse script data if available
    if script_data:
        if not title and script_data.get("title"):
            title = script_data["title"]
        if not speech_text:
            texts = []
            for sc in script_data.get("scenes", []):
                for ln in sc.get("lines", []):
                    if ln.get("text"):
                        texts.append(ln["text"])
            if texts:
                speech_text = " ".join(texts)
            elif script_data.get("text"):
                speech_text = script_data.get("text")

    if not title:
        title = "น้องข้าวหอม ตอน สนุกในสวนพาสเทล"

    # Determine resolution
    res_str = options.get("resolution", "1080p")
    if aspect == "9:16":
        if "720" in res_str:
            w, h = 720, 1280
        elif "480" in res_str:
            w, h = 480, 854
        else:
            w, h = 1080, 1920
    elif aspect == "1:1":
        if "720" in res_str:
            w, h = 720, 720
        elif "480" in res_str:
            w, h = 480, 480
        else:
            w, h = 1080, 1080
    else:  # 16:9
        if "720" in res_str:
            w, h = 1280, 720
        elif "480" in res_str:
            w, h = 854, 480
        else:
            w, h = 1920, 1080

    total_frames = int(duration * fps)
    encoder = select_best_encoder(options.get("encoder", "auto"))

    log(f"🎬 เริ่มต้นกระบวนการ 3D Chibi Pastel Animation: {title}")
    log(f"⚙️ สเปก: {w}x{h} ({aspect}) @ {fps} FPS, เวลา {duration:.1f} วิ ({total_frames} เฟรม)")
    log(f"🎨 ตัวละคร: {character} | ฉาก: {environment} | ท่าทาง: {action} | สี: {preset}")
    log(f"💻 ตัวเรนเดอร์: Blender 4.2 ({render_engine}) | ตัวเข้ารหัส: {encoder}")

    if progress_callback:
        progress_callback(5, "กำลังเตรียมฉาก 3D และทรัพยากรตัวละคร...")

    # 3. Audio Generation (Thai TTS speech & BGM)
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
                log("PROGRESS_STAGE: tts 40% (กำลังสังเคราะห์เสียงพากย์ภาษาไทย)")
                log(f"🎙️ สังเคราะห์เสียงพากย์ภาษาไทย: '{speech_text[:30]}...'")
                from .. import tts
                from ..config import load as load_cfg
                cfg = load_cfg()
                engines = cfg["tts"]["engines"]
                vc = cfg["voices"].get("chick", cfg["voices"].get("narrator", {}))
                tts_cache = ROOT / "cache" / "tts"
                tts_cache.mkdir(parents=True, exist_ok=True)
                allow_test = bool(cfg.get("allow_test_voice", False))
                voice_samples, eng_used = tts.synth_with_fallback(speech_text, vc, engines, tts_cache, log, allow_test=allow_test)
                log(f"🎙️ เสียงพากย์สร้างสำเร็จด้วยเอนจิน: {eng_used}")
                dur_voice = len(voice_samples) / audio.SR
                if dur_voice > duration:
                    duration = dur_voice + 0.8
                    total_frames = int(duration * fps)

                # Generate gentle cute BGM
                log("PROGRESS_STAGE: audio 70% (กำลังรวมแทร็กเสียงดนตรีประกอบ)")
                import numpy as np
                n_samples = int(duration * audio.SR)
                bgm_samples = np.zeros(n_samples, dtype=np.float32)
                try:
                    sfx_pop = audio.sfx_pop()
                    audio._add(bgm_samples, 0.2, sfx_pop * 0.3)
                    audio._add(bgm_samples, duration - 0.5, audio.sfx_chime() * 0.4)
                except Exception:
                    pass

                # Combine speech + soft BGM
                mix_audio = np.zeros(n_samples, dtype=np.float32)
                audio._add(mix_audio, 0.4, voice_samples * 1.0)
                mix_audio += bgm_samples * 0.2
                audio.write_wav(audio_wav_path, mix_audio)
                has_audio = True
                log("🎵 สร้างแทร็กเสียงพากย์และดนตรีประกอบสำเร็จ")
        except Exception as e:
            log(f"⚠️ การสร้างเสียงเพิ่มเติมขัดข้อง (สร้างแบบเสียงจำลอง): {e}")

        if not has_audio or not audio_wav_path.exists():
            import numpy as np
            n_samples = int(duration * audio.SR)
            ambient = np.zeros(n_samples, dtype=np.float32)
            try:
                audio._add(ambient, 0.1, audio.sfx_pop() * 0.2)
            except Exception:
                pass
            audio.write_wav(audio_wav_path, ambient)
            has_audio = True

    # 4. Generate Subtitles File (.srt)
    srt_path = temp_dir / "subtitles.srt"
    if speech_text:
        srt_content = (
            f"1\n00:00:00,400 --> 00:00:{int(duration):02d},{int((duration%1)*1000):03d}\n"
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
        "preset": preset,
        "character": character,
        "environment": environment,
        "action": action,
        "render_engine": render_engine,
        "output_frames_pattern": frames_pattern,
        "res_x": w,
        "res_y": h,
    }
    spec_path = temp_dir / "chibi_spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

    if progress_callback:
        progress_callback(15, f"กำลังเรนเดอร์โมเดล 3D ด้วย Blender ({render_engine})...")

    # 6. Execute Blender Rendering
    cmd_blender = [
        blender_path,
        "--background",
        "--python", str(BUILDER_SCRIPT),
        "--",
        "--spec", str(spec_path),
    ]

    log(f"🚀 เรียกใช้ Blender 3D Worker ({render_engine})...")
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
                pct = min(90, int(15 + (rendered_frames / max(1, total_frames)) * 75))
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

    if progress_callback:
        progress_callback(92, f"กำลังรวมแทร็กภาพ เสียง และเข้ารหัสวิดีโอ ({encoder})...")

    # 7. Encode Video with FFmpeg
    ff = audio.ffmpeg_exe()
    if target_mp4:
        out_video_path = Path(target_mp4).resolve()
        out_video_name = out_video_path.name
    else:
        out_video_name = f"chibi_{character}_{aspect.replace(':', 'x')}.mp4"
        out_video_path = out_dir / out_video_name

    input_img_seq = str(frames_dir / "frame_%04d.png")

    # Build FFmpeg command with selected hardware encoder
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
            from PIL import Image
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
        progress_callback(100, "🎉 สร้างแอนิเมชัน 3D Chibi เสร็จสมบูรณ์แล้ว!")

    log(f"🎉 สร้างวิดีโอ 3D Chibi สำเร็จเรียบร้อย: {out_video_path}")
    log(f"📊 ขนาดไฟล์: {os.path.getsize(out_video_path)/1024:.1f} KB | เวลาเรนเดอร์ทั้งหมด: {time.time()-t_start:.1f} วินาที")

    # Write meta.json
    meta = {
        "title": title,
        "engine": "3d_chibi_pastel",
        "engine_label": "3D Chibi Pastel Animation — การ์ตูน 3D น่ารัก",
        "character": character,
        "environment": environment,
        "action": action,
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
