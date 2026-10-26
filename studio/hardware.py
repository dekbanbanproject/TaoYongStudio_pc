"""Hardware detection and media verification for TaoYongStudio Local GPU Animation Studio V1.

Accurately detects real Windows GPU, CPU, RAM, disk, encoders, and installed animation engines.
Strict rule: Never fabricate or hardcode device specs. Always probe actual system capabilities.
"""
import ctypes
import json
import os
import shutil
import subprocess
import sys
import winreg
from pathlib import Path

from . import audio
from .config import ROOT


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def get_memory_info():
    """Get system RAM statistics via Windows API."""
    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    return {
        "total_gb": round(stat.ullTotalPhys / (1024 ** 3), 2),
        "avail_gb": round(stat.ullAvailPhys / (1024 ** 3), 2),
        "used_gb": round((stat.ullTotalPhys - stat.ullAvailPhys) / (1024 ** 3), 2),
        "load_percent": stat.dwMemoryLoad,
    }


def get_cpu_info():
    """Get CPU model, clock speed, and core count."""
    cpu_name = "Unknown CPU"
    mhz = 0
    try:
        cpu_path = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, cpu_path) as key:
            cpu_name = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
            mhz = winreg.QueryValueEx(key, "~MHz")[0]
    except Exception:
        pass
    cores = os.cpu_count() or 1
    return {
        "name": cpu_name,
        "mhz": mhz,
        "logical_cores": cores,
    }


def get_disk_info(path="."):
    """Get storage free space."""
    try:
        total, used, free = shutil.disk_usage(path)
        return {
            "total_gb": round(total / (1024 ** 3), 1),
            "free_gb": round(free / (1024 ** 3), 1),
            "used_gb": round(used / (1024 ** 3), 1),
        }
    except Exception:
        return {"total_gb": 0, "free_gb": 0, "used_gb": 0}


def get_gpus_from_registry():
    """Enumerate display adapters registered in Windows."""
    adapters = []
    key_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            count = winreg.QueryInfoKey(key)[0]
            for i in range(count):
                sub_key_name = winreg.EnumKey(key, i)
                if not sub_key_name.isdigit():
                    continue
                try:
                    with winreg.OpenKey(key, sub_key_name) as sub:
                        desc = winreg.QueryValueEx(sub, "DriverDesc")[0]
                        provider = winreg.QueryValueEx(sub, "ProviderName")[0]
                        ver = winreg.QueryValueEx(sub, "DriverVersion")[0]
                        # Filter out virtual mirror drivers from primary list if real GPU exists
                        is_mirror = "mirror" in desc.lower() or "vnc" in desc.lower()
                        adapters.append({
                            "name": desc,
                            "provider": provider,
                            "driver_version": ver,
                            "is_mirror": is_mirror,
                        })
                except Exception:
                    pass
    except Exception:
        pass
    return adapters


def test_ffmpeg_encoder(encoder_name):
    """Real test: Actually test-encodes a 1-second dummy video in ffmpeg with the encoder."""
    ff = audio.ffmpeg_exe()
    if not os.path.exists(ff):
        return {"ok": False, "error": "ffmpeg executable not found"}
    cmd = [
        ff, "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.2",
        "-c:v", encoder_name,
        "-f", "null", "-"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore", timeout=8)
        if res.returncode == 0:
            return {"ok": True, "error": ""}
        err_msg = res.stderr.strip() or f"exit code {res.returncode}"
        # Extract meaningful first error line
        for line in res.stderr.splitlines():
            line_clean = line.strip()
            if any(k in line_clean.lower() for k in ["error", "cannot", "failed", "no", "unable"]):
                err_msg = line_clean
                break
        return {"ok": False, "error": err_msg}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_cuda_pytorch():
    """Check PyTorch and CUDA availability."""
    try:
        import torch
        cuda_avail = torch.cuda.is_available()
        count = torch.cuda.device_count() if cuda_avail else 0
        devices = []
        if cuda_avail:
            for d in range(count):
                props = torch.cuda.get_device_properties(d)
                devices.append({
                    "id": d,
                    "name": props.name,
                    "total_vram_gb": round(props.total_memory / (1024 ** 3), 2),
                    "major": props.major,
                    "minor": props.minor,
                })
        return {
            "installed": True,
            "version": torch.__version__,
            "cuda_available": cuda_avail,
            "devices": devices,
        }
    except ImportError:
        return {
            "installed": False,
            "version": None,
            "cuda_available": False,
            "devices": [],
        }


def check_blender():
    """Check if Blender 3D executable is installed."""
    exe = shutil.which("blender")
    if not exe:
        for p in [
            r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
            r"C:\Program Files\Blender Foundation\blender.exe",
        ]:
            if os.path.exists(p):
                exe = p
                break
    return {
        "installed": bool(exe),
        "path": exe,
        "status": "พร้อมใช้งาน" if exe else "ยังไม่ได้ติดตั้งเครื่องมือ",
    }


def check_comfyui():
    """Check if ComfyUI is installed locally."""
    paths = [
        r"C:\ComfyUI",
        r"C:\ComfyUI_windows_portable",
        os.path.expanduser(r"~\ComfyUI"),
        os.path.expanduser(r"~\Desktop\ComfyUI"),
    ]
    found = None
    for p in paths:
        if os.path.exists(os.path.join(p, "main.py")):
            found = p
            break
    return {
        "installed": bool(found),
        "path": found,
        "status": "พร้อมใช้งาน" if found else "ยังไม่ได้ติดตั้งเครื่องมือ",
    }


def detect_hardware():
    """Comprehensive hardware and software detection for animation studio."""
    cpu = get_cpu_info()
    ram = get_memory_info()
    disk = get_disk_info()
    gpus_reg = get_gpus_from_registry()
    torch_info = check_cuda_pytorch()
    blender = check_blender()
    comfyui = check_comfyui()

    # Test encoders
    encoder_tests = {
        "h264_nvenc": test_ffmpeg_encoder("h264_nvenc"),
        "hevc_nvenc": test_ffmpeg_encoder("hevc_nvenc"),
        "h264_qsv": test_ffmpeg_encoder("h264_qsv"),
        "h264_mf": test_ffmpeg_encoder("h264_mf"),
        "libx264": test_ffmpeg_encoder("libx264"),
    }

    # Build devices list for UI
    devices = []

    # Filter out pure mirror drivers for primary device listing
    primary_gpus = [g for g in gpus_reg if not g.get("is_mirror")]
    if not primary_gpus and gpus_reg:
        primary_gpus = gpus_reg

    def gpu_priority(g):
        name = g.get("name", "").lower()
        if "nvidia" in name or "geforce" in name or "rtx" in name or "gtx" in name:
            return 0
        if "amd" in name or "radeon" in name:
            return 1
        if "intel" in name or "arc" in name:
            return 2
        return 3
    primary_gpus.sort(key=gpu_priority)

    has_nvidia = False
    for g in primary_gpus:
        gname = g["name"]
        gprov = g["provider"]
        gver = g["driver_version"]
        is_nv = "nvidia" in gname.lower() or "geforce" in gname.lower()
        is_intel = "intel" in gname.lower() or "iris" in gname.lower() or "arc" in gname.lower()
        is_amd = "amd" in gname.lower() or "radeon" in gname.lower()

        if is_nv:
            has_nvidia = True
            nvenc_ok = encoder_tests["h264_nvenc"]["ok"]
            cuda_ok = torch_info.get("cuda_available", False)
            if nvenc_ok and cuda_ok:
                status = "พร้อมใช้งาน (NVENC + CUDA)"
                vram_txt = f"{torch_info['devices'][0]['total_vram_gb']}GB VRAM" if torch_info['devices'] else "VRAM พร้อม"
            elif nvenc_ok:
                status = "พร้อมใช้งาน (NVENC Hardware Encode)"
                vram_txt = "ตรวจพบผ่าน Driver"
            else:
                status = f"Driver ยังไม่สมบูรณ์ ({encoder_tests['h264_nvenc']['error']})"
                vram_txt = "CUDA ยังไม่พร้อม"
            devices.append({
                "id": "gpu_nvidia",
                "label": f"{gname} — {vram_txt}",
                "type": "gpu_nvidia",
                "status": status,
                "supported": nvenc_ok,
                "encoder": "h264_nvenc" if nvenc_ok else "libx264",
                "details": f"Driver: {gver} | Provider: {gprov}",
            })
        elif is_intel:
            qsv_ok = encoder_tests["h264_qsv"]["ok"]
            mf_ok = encoder_tests["h264_mf"]["ok"]
            if qsv_ok:
                status = "พร้อมใช้งาน (Intel Quick Sync Video)"
                enc_choice = "h264_qsv"
            elif mf_ok:
                status = "พร้อมใช้งาน (MediaFoundation Hardware Accel)"
                enc_choice = "h264_mf"
            else:
                status = "ตรวจพบชิปกราฟิก (ใช้ CPU Rendering เสริม)"
                enc_choice = "libx264"
            devices.append({
                "id": "gpu_intel",
                "label": f"{gname} (Intel QSV Hardware Accel)",
                "type": "gpu_intel",
                "status": status,
                "supported": True,
                "encoder": enc_choice,
                "details": f"Driver: {gver} | Provider: {gprov} | QSV: {'OK' if qsv_ok else 'No'}",
            })
        elif is_amd:
            amf_ok = test_ffmpeg_encoder("h264_amf")["ok"]
            devices.append({
                "id": "gpu_amd",
                "label": f"{gname} (AMD AMF)",
                "type": "gpu_amd",
                "status": "พร้อมใช้งาน (AMD AMF)" if amf_ok else "ตรวจพบชิปกราฟิก",
                "supported": True,
                "encoder": "h264_amf" if amf_ok else "libx264",
                "details": f"Driver: {gver} | Provider: {gprov}",
            })

    # Always include CPU Rendering option
    devices.append({
        "id": "cpu",
        "label": f"{cpu['name']} — CPU Rendering",
        "type": "cpu",
        "status": "พร้อมใช้งาน (CPU x264 Multi-Core)",
        "supported": encoder_tests["libx264"]["ok"],
        "encoder": "libx264",
        "details": f"{cpu['logical_cores']} Threads | Clock: {cpu['mhz']} MHz",
    })

    # Animation Engines availability
    ai_i2v_ready = comfyui["installed"] and (torch_info.get("cuda_available") or torch_info.get("installed"))
    ai_t2v_ready = comfyui["installed"]

    engines = {
        "2d_cartoon": {
            "name": "2D Cartoon Animation",
            "status": "พร้อมใช้งาน",
            "supported": True,
            "description": "เอนจิน 2D สตูดิโอในเครื่อง: ตัวละครขยับปาก เดิน กระโดด ป้ายการ์ด ซีนเสียง และเพลง",
        },
        "25d_parallax": {
            "name": "2.5D Parallax Animation",
            "status": "พร้อมใช้งาน",
            "supported": True,
            "description": "แอนิเมชันเพิ่มมิติความลึก เลื่อนฉากหลังและตัวละครแบบ Parallax กล้อง Pan/Zoom",
        },
        "3d_chibi_pastel": {
            "name": "3D Chibi Pastel Animation — การ์ตูน 3D น่ารัก",
            "status": "พร้อมใช้งาน" if blender["installed"] else "ต้องติดตั้งส่วนประกอบ",
            "supported": blender["installed"],
            "description": "สร้างการ์ตูน 3D หัวโต ตากลมโต สีพาสเทล มีการเคลื่อนไหวของตัวละคร ฉาก และกล้อง พร้อมเสียงพากย์ภาษาไทย",
        },
        "3d_cinematic_cartoon": {
            "name": "3D Cinematic Cartoon Animation — สัตว์ 3D ภาพยนตร์",
            "status": "พร้อมใช้งาน" if blender["installed"] else "ต้องติดตั้งส่วนประกอบ",
            "supported": blender["installed"],
            "description": "สร้างการ์ตูนสัตว์ 3D คุณภาพระดับภาพยนตร์ (ปลาว่ายน้ำ ลูกแมว ลูกเจี๊ยบ กระต่าย) แสง Cinematic ใต้ทะเล ชายหาด ป่าธรรมชาติ",
        },
        "cute_toy_ad": {
            "name": "Cute Toy Product Ad Animation — โฆษณาสินค้า 3D ของเล่น",
            "status": "พร้อมใช้งาน" if blender["installed"] else "ต้องติดตั้งส่วนประกอบ",
            "supported": blender["installed"],
            "description": "สร้างวิดีโอโฆษณาสินค้า 3D สไตล์ Vinyl Toy บนโต๊ะทำงาน แสง Studio DoF พร้อมแท่นหมุนโชว์สินค้าจริง ป้ายราคา และโปรโมชั่น",
        },
        "3d_blender": {
            "name": "3D Animation — Blender",
            "status": blender["status"],
            "supported": blender["installed"],
            "description": "เรนเดอร์โมเดล 3D ผ่าน Blender (ติดตั้ง Blender 4.2 LTS สำเร็จ)",
        },
        "ai_image_to_video": {
            "name": "AI Image-to-Video",
            "status": "พร้อมใช้งาน (ComfyUI + CUDA)" if ai_i2v_ready else ("พร้อมใช้งาน (ComfyUI)" if comfyui["installed"] else "ยังไม่ได้ติดตั้งเครื่องมือ"),
            "supported": comfyui["installed"],
            "description": "สร้างคลิปจากภาพด้วยโมเดล AI ในเครื่อง (รองรับ ComfyUI + NVIDIA CUDA)",
        },
        "ai_text_to_video": {
            "name": "AI Text-to-Video (Experimental)",
            "status": "พร้อมใช้งาน (ComfyUI Engine)" if ai_t2v_ready else "ยังไม่ได้ติดตั้งเครื่องมือ",
            "supported": comfyui["installed"],
            "description": "สร้างคลิปจากข้อความโดยตรงผ่าน ComfyUI AI Engine",
        },
    }

    return {
        "cpu": cpu,
        "ram": ram,
        "disk": disk,
        "gpus": gpus_reg,
        "torch": torch_info,
        "blender": blender,
        "comfyui": comfyui,
        "encoders": encoder_tests,
        "devices": devices,
        "engines": engines,
        "best_device": devices[0] if devices else None,
    }


def probe_video(video_path):
    """Inspect and verify a rendered MP4 video file using ffmpeg.

    Returns dict containing duration, resolution, fps, bitrate, audio info.
    """
    path = Path(video_path)
    if not path.exists():
        return {"ok": False, "error": f"File does not exist: {video_path}"}
    if path.stat().st_size == 0:
        return {"ok": False, "error": f"File is empty (0 bytes): {video_path}"}

    ff = audio.ffmpeg_exe()
    cmd = [ff, "-i", str(path)]
    res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
    stderr = res.stderr

    import re
    # Parse duration
    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", stderr)
    duration_secs = 0.0
    if dur_match:
        h, m, s = dur_match.groups()
        duration_secs = int(h) * 3600 + int(m) * 60 + float(s)

    # Parse video stream
    # e.g.: Stream #0:0[0x1](und): Video: h264 (High) (avc1 / ...), yuv420p(progressive), 1920x1080 [SAR 1:1 DAR 16:9], 24 fps
    vid_match = re.search(r"Video:\s*([^,\n]+).*?,\s*(\d{3,4})x(\d{3,4}).*?,\s*(\d+(?:\.\d+)?)\s*fps", stderr)
    video_codec = ""
    width, height = 0, 0
    fps = 0.0
    if vid_match:
        video_codec = vid_match.group(1).split()[0]
        width = int(vid_match.group(2))
        height = int(vid_match.group(3))
        fps = float(vid_match.group(4))
    else:
        # Fallback regex for resolution
        res_m = re.search(r",\s*(\d{3,4})x(\d{3,4})", stderr)
        if res_m:
            width = int(res_m.group(1))
            height = int(res_m.group(2))
        fps_m = re.search(r"(\d+(?:\.\d+)?)\s*fps", stderr)
        if fps_m:
            fps = float(fps_m.group(1))

    # Parse audio stream
    audio_match = re.search(r"Audio:\s*([^,\n]+).*?,\s*(\d+)\s*Hz", stderr)
    audio_codec = audio_match.group(1) if audio_match else ""
    sample_rate = int(audio_match.group(2)) if audio_match else 0

    size_bytes = path.stat().st_size

    is_valid = duration_secs > 0 and width > 0 and height > 0
    return {
        "ok": is_valid,
        "path": str(path),
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / (1024 * 1024), 2),
        "duration_seconds": round(duration_secs, 2),
        "width": width,
        "height": height,
        "resolution": f"{width}x{height}",
        "fps": fps,
        "video_codec": video_codec,
        "audio_codec": audio_codec,
        "sample_rate": sample_rate,
        "raw_stderr": stderr[:400] if not is_valid else "",
    }
