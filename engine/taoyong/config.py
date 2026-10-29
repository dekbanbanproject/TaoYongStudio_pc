import copy
import json
import os
import sys
from pathlib import Path


def _detect_root() -> Path:
    """Workspace root that holds scripts/, plans/, output/, fonts/, config.json.

    Order:
      1. TAOYONG_ROOT env var (set by the Tauri shell / dev scripts).
      2. Walk up from this file until a folder contains both `engine` and `scripts`.
      3. Fall back to the frozen-bundle directory (PyInstaller / Tauri sidecar).
    """
    env = os.environ.get("TAOYONG_ROOT", "").strip()
    if env:
        return Path(env).resolve()

    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / "engine").is_dir() and (candidate / "scripts").is_dir():
            return candidate
        if (candidate / "scripts").is_dir() and (candidate / "output").is_dir():
            return candidate

    frozen = getattr(sys, "frozen", False) if "sys" in globals() else False
    if frozen:
        return Path(sys.executable).resolve().parent
    return here.parent.parent.parent


ROOT = _detect_root()

DEFAULTS = {
    "channel_name": "",
    "tts": {
        "engines": ["azure", "edge", "sapi", "espeak"],
        "azure_key": "",
        "azure_region": "southeastasia",
        "comment": "tried in order. azure = official Microsoft voices for commercial use (needs key), edge = same voices via the free Edge read-aloud service, sapi = Windows Thai voice, espeak = robot test voice",
    },
    "voices": {
        "narrator": {"edge": "th-TH-PremwadeeNeural", "rate": "-5%", "pitch": "+0Hz", "espeak_pitch": 50},
        "bunny": {"edge": "th-TH-PremwadeeNeural", "rate": "+5%", "pitch": "+35Hz", "espeak_pitch": 75},
        "bear": {"edge": "th-TH-NiwatNeural", "rate": "-5%", "pitch": "-5Hz", "espeak_pitch": 35},
        "chick": {"edge": "th-TH-PremwadeeNeural", "rate": "+12%", "pitch": "+60Hz", "espeak_pitch": 90},
        "cat": {"edge": "th-TH-PremwadeeNeural", "rate": "-3%", "pitch": "+15Hz", "espeak_pitch": 65},
    },
    "video": {
        "fps": 30,
        "crf": 21,
        "preset": "veryfast",
        "formats": ["vertical", "horizontal"],
    },
    "audio": {
        "music": "auto",
        "music_comment": "'auto' = generate new music per clip, or a folder path containing your own licensed .mp3/.wav files",
        "music_volume": 0.16,
        "voice_volume": 1.0,
        "sfx_volume": 0.5,
    },
    "intro_seconds": 2.2,
    "read_title": True,
    "outro_text": "แล้วพบกันใหม่นะ!",
    "read_outro": True,
    "outro_seconds": 2.8,
    "line_gap_seconds": 0.35,
    "max_minutes": 12,
    "allow_test_voice": False,
}


def _merge(base, extra):
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def load(path=None):
    cfg = copy.deepcopy(DEFAULTS)
    p = Path(path) if path else ROOT / "config.json"
    if p.exists():
        with open(p, encoding="utf-8") as f:
            _merge(cfg, json.load(f))
    cfg["_root"] = str(ROOT)
    return cfg


def write_default(path=None):
    p = Path(path) if path else ROOT / "config.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(DEFAULTS, f, ensure_ascii=False, indent=2)
    return p
