"""Text-to-speech backends.

azure  : Microsoft Azure Speech (same neural Thai voices, official + commercial licence, free tier 0.5M chars/month)
edge   : Microsoft neural Thai voices via the free Edge read-aloud service (needs internet, best quality)
sapi   : Windows built-in voices (offline; needs the Thai speech pack installed in Windows Settings)
espeak : espeak-ng robot voice (offline, for testing only)
silent : no voice, timing estimated from text length (for layout tests)

Every result is cached in cache/tts so the same line is never synthesised twice.
"""
import asyncio
import hashlib
import json
import os
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

from . import audio


class TTSError(Exception):
    pass


def _key(engine, voice_cfg, text):
    clean = {k: v for k, v in voice_cfg.items() if not k.startswith("_")}
    raw = json.dumps([engine, clean, text], ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


# ------------------------------------------------------------------ azure (official, commercial use)
def _azure(text, vc, out_wav):
    import urllib.request
    from xml.sax.saxutils import escape

    key = os.environ.get("AZURE_SPEECH_KEY") or vc.get("_azure_key", "")
    region = os.environ.get("AZURE_SPEECH_REGION") or vc.get("_azure_region", "southeastasia")
    if not key:
        raise TTSError("no Azure key set (config tts.azure_key)")
    voice = vc.get("edge", "th-TH-PremwadeeNeural")
    ssml = ("<speak version='1.0' xml:lang='th-TH'><voice name='%s'><prosody rate='%s' pitch='%s'>%s"
            "</prosody></voice></speak>" % (voice, vc.get("rate", "+0%"), vc.get("pitch", "+0Hz"), escape(text)))
    req = urllib.request.Request(
        "https://%s.tts.speech.microsoft.com/cognitiveservices/v1" % region, data=ssml.encode("utf-8"),
        headers={"Ocp-Apim-Subscription-Key": key, "Content-Type": "application/ssml+xml",
                 "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm", "User-Agent": "TaoYongStudio"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    with open(out_wav, "wb") as f:
        f.write(data)


# ------------------------------------------------------------------ edge
def _edge(text, vc, out_mp3):
    import edge_tts

    async def go():
        c = edge_tts.Communicate(text, vc.get("edge", "th-TH-PremwadeeNeural"),
                                 rate=vc.get("rate", "+0%"), pitch=vc.get("pitch", "+0Hz"),
                                 volume=vc.get("volume", "+0%"))
        await asyncio.wait_for(c.save(str(out_mp3)), timeout=12.0)

    try:
        asyncio.run(go())
    except Exception as e:
        if "No audio" in str(e) or isinstance(e, asyncio.TimeoutError):
            raise TTSError("edge returned no audio for voice %s (timeout or service busy)" % vc.get("edge")) from e
        raise


# ------------------------------------------------------------------ sapi (Windows)
def _sapi(text, vc, out_wav):
    if os.name != "nt":
        raise TTSError("sapi works on Windows only")
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(text)
        txt = f.name
    rate = int(vc.get("sapi_rate", 0))
    name = vc.get("sapi_voice", "").replace("'", "''")
    out_wav = str(out_wav).replace("'", "''")
    txt_q = txt.replace("'", "''")
    ps = f"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$name = '{name}'
if ($name -ne '') {{ $s.SelectVoice($name) }} else {{
  $v = $s.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Culture.Name -eq 'th-TH' }} | Select-Object -First 1
  if (-not $v) {{ Write-Output 'NO_THAI_VOICE'; exit 3 }}
  $s.SelectVoice($v.VoiceInfo.Name)
}}
$s.Rate = {rate}
$s.SetOutputToWaveFile('{out_wav}')
$s.Speak([IO.File]::ReadAllText('{txt_q}', [Text.Encoding]::UTF8))
$s.Dispose()
"""
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                       capture_output=True, text=True, creationflags=0x08000000)
    os.unlink(txt)
    if r.returncode != 0:
        raise TTSError("Windows voice failed: " + (r.stdout + r.stderr).strip()[:300])


# ------------------------------------------------------------------ espeak (test voice)
_ESPEAK = {}


def _espeak(text, vc, out_wav):
    import ctypes
    import espeakng_loader

    if "lib" not in _ESPEAK:
        lib = ctypes.cdll.LoadLibrary(espeakng_loader.get_library_path())
        data = espeakng_loader.get_data_path()
        sr = lib.espeak_Initialize(2, 0, os.path.dirname(data).encode(), 0)
        if sr <= 0:
            sr = lib.espeak_Initialize(2, 0, data.encode(), 0)
        if sr <= 0:
            raise TTSError("espeak-ng could not start")
        CB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_void_p)
        chunks = []

        def cb(wav, n, ev):
            if n > 0:
                chunks.append(np.ctypeslib.as_array(wav, shape=(n,)).copy())
            return 0

        cbf = CB(cb)
        lib.espeak_SetSynthCallback(cbf)
        _ESPEAK.update(lib=lib, sr=sr, cb=cbf, chunks=chunks)
    lib, chunks = _ESPEAK["lib"], _ESPEAK["chunks"]
    chunks.clear()
    lib.espeak_SetVoiceByName(vc.get("espeak", "th").encode())
    lib.espeak_SetParameter(1, int(vc.get("espeak_rate", 150)), 0)
    lib.espeak_SetParameter(3, int(vc.get("espeak_pitch", 55)), 0)
    b = text.encode("utf-8") + b"\0"
    lib.espeak_Synth(ctypes.c_char_p(b), ctypes.c_size_t(len(b)), 0, 1, 0, 1 | 0x1000, None, None)
    pcm = np.concatenate(chunks) if chunks else np.zeros(1000, dtype=np.int16)
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_ESPEAK["sr"])
        w.writeframes(pcm.astype(np.int16).tobytes())


# ------------------------------------------------------------------ silent
def _silent(text, vc, out_wav):
    dur = max(0.8, 0.075 * len(text))
    n = int(dur * audio.SR)
    t = np.arange(n) / audio.SR
    # quiet syllable-like pulses so lip-sync still moves
    x = 0.004 * np.sin(2 * np.pi * 180 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 4.5 * t))
    audio.write_wav(out_wav, x)


ENGINES = {"azure": _azure, "edge": _edge, "sapi": _sapi, "espeak": _espeak, "silent": _silent}


def synth(text, voice_cfg, engine, cache_dir):
    """Return a float32 numpy array at 44.1 kHz. Raises TTSError on failure."""
    if engine not in ENGINES:
        raise TTSError("unknown TTS engine: %s" % engine)
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = _key(engine, voice_cfg, text)
    final = cache_dir / (key + ".wav")
    if not final.exists():
        raw = cache_dir / (key + (".mp3" if engine == "edge" else ".raw.wav"))
        try:
            ENGINES[engine](text, voice_cfg, raw)
            audio.to_wav(raw, final)
        except TTSError:
            raise
        except Exception as e:  # network errors etc.
            raise TTSError("%s: %s" % (engine, e)) from e
        finally:
            if raw.exists():
                raw.unlink()
    x = audio.read_wav(final)
    return audio.trim_silence(x) if engine != "silent" else x


_DIG = ["ศูนย์", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]
_POS = ["", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน"]


def _thai_int(n):
    if n == 0:
        return _DIG[0]
    if n >= 1000000:
        hi, lo = divmod(n, 1000000)
        return _thai_int(hi) + "ล้าน" + (_thai_int(lo) if lo else "")
    out, digits = "", str(n)
    L = len(digits)
    for i, ch in enumerate(digits):
        d, pos = int(ch), L - 1 - i
        if d == 0:
            continue
        if pos == 1 and d == 1:
            out += "สิบ"
        elif pos == 1 and d == 2:
            out += "ยี่สิบ"
        elif pos == 0 and d == 1 and L > 1:
            out += "เอ็ด"
        else:
            out += _DIG[d] + _POS[pos]
    return out


def spoken(text):
    """Text sent to the voice engine: digits become Thai words so every engine reads them the same way."""
    import re
    out = re.sub(r"\d[\d,]*", lambda m: " %s " % _thai_int(int(m.group().replace(",", ""))), text)
    return re.sub(r"\s+", " ", out).strip()


NETWORK = {"azure", "edge"}
TEST_ONLY = {"espeak", "silent"}
_HAS_NET = None


def has_internet():
    global _HAS_NET
    if _HAS_NET is not None:
        return _HAS_NET
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect(("8.8.8.8", 53))
        s.close()
        _HAS_NET = True
    except Exception:
        _HAS_NET = False
    return _HAS_NET


def synth_with_fallback(text, voice_cfg, engines, cache_dir, log, allow_test=False):
    import time
    say = spoken(text)
    last = None
    usable = []
    net_available = has_internet()
    for eng in engines:
        if eng == "azure" and not (os.environ.get("AZURE_SPEECH_KEY") or voice_cfg.get("_azure_key")):
            continue  # not configured, skip quietly
        if eng in NETWORK and not net_available:
            continue  # offline or sandboxed, don't stall
        if eng in TEST_ONLY and not allow_test:
            continue
        usable.append(eng)
    if not usable:
        raise TTSError("no usable voice engine (check config tts.engines)")
    for i, eng in enumerate(usable):
        # the free Edge service sometimes answers "No audio was received" for a while; wait it out
        waits = [1, 2, 3] if eng in NETWORK else []
        for k in range(len(waits) + 1):
            try:
                return synth(say, voice_cfg, eng, cache_dir), eng
            except TTSError as e:
                last = e
                if k < len(waits):
                    log("voice engine '%s' failed (%s), retry %d in %ds" % (eng, str(e)[:100], k + 1, waits[k]))
                    time.sleep(waits[k])
        log("voice engine '%s' failed (%s)%s" % (eng, str(last)[:160], ", trying next" if i + 1 < len(usable) else ""))
    # If all primary engines failed, try test engine if available
    for eng in engines:
        if eng in TEST_ONLY and eng not in usable:
            try:
                log("falling back to test voice engine '%s'" % eng)
                return synth(say, voice_cfg, eng, cache_dir), eng
            except TTSError:
                pass
    raise TTSError("all voice engines failed for line '%s': %s" % (text[:40], last))
