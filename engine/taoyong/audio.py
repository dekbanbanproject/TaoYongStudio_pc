"""Audio helpers: wav io, ffmpeg conversion, lip-sync envelope, music + sound effects (all synthesised)."""
import math
import random
import subprocess
import wave

import numpy as np

SR = 44100


def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _no_window():
    import os
    return {"creationflags": 0x08000000} if os.name == "nt" else {}


def to_wav(src, dst):
    """Convert any audio file to 44.1 kHz mono 16-bit wav."""
    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", str(SR),
           "-sample_fmt", "s16", str(dst)]
    subprocess.run(cmd, check=True, **_no_window())


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        n = w.getnframes()
        data = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
        if w.getnchannels() == 2:
            data = data.reshape(-1, 2).mean(axis=1)
        if w.getframerate() != SR:
            raise ValueError("expected %d Hz wav" % SR)
    return data


def write_wav(path, data):
    data = np.clip(data, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((data * 32767).astype(np.int16).tobytes())


def trim_silence(x, thresh=0.012, keep=0.05):
    idx = np.where(np.abs(x) > thresh)[0]
    if len(idx) == 0:
        return x
    k = int(keep * SR)
    return x[max(0, idx[0] - k): min(len(x), idx[-1] + k)]


def envelope(x, fps):
    """Per-video-frame loudness 0..1 for lip sync."""
    hop = SR / fps
    n = int(math.ceil(len(x) / hop))
    out = np.zeros(n, dtype=np.float32)
    for i in range(n):
        seg = x[int(i * hop): int((i + 1) * hop)]
        if len(seg):
            out[i] = float(np.sqrt(np.mean(seg * seg)))
    m = out.max() if len(out) else 0
    return out / m if m > 0 else out


# ----------------------------------------------------------------------------- synthesis

def _env(n, a=0.01, r=0.15):
    t = np.arange(n) / SR
    e = np.minimum(1.0, t / max(a, 1e-4))
    e *= np.exp(-t / max(r, 1e-4))
    return e


def _tone(freq, dur, kind="sine", a=0.01, r=0.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    ph = 2 * np.pi * freq * t
    if kind == "sine":
        w = np.sin(ph)
    elif kind == "tri":
        w = 2 / np.pi * np.arcsin(np.sin(ph))
    elif kind == "soft_square":
        w = np.sin(ph) + 0.3 * np.sin(3 * ph) + 0.12 * np.sin(5 * ph)
        w /= 1.4
    elif kind == "bell":
        w = np.sin(ph) + 0.4 * np.sin(2 * ph) * np.exp(-t * 6) + 0.2 * np.sin(4.01 * ph) * np.exp(-t * 9)
        w /= 1.6
    else:
        w = np.sin(ph)
    return w * _env(n, a, r)


def _add(buf, start, sig, gain=1.0):
    i = int(start * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i] * gain


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def make_music(duration, seed=0, bpm=None):
    """Cheerful kids' background loop, generated fresh (no copyright issues)."""
    rnd = random.Random(seed)
    bpm = bpm or rnd.choice([100, 108, 116, 124])
    beat = 60.0 / bpm
    root = 60 + rnd.choice([0, 2, 5, 7, -3])  # C, D, F, G, A
    progs = [[0, 7, 9, 5], [0, 5, 7, 5], [0, 9, 5, 7], [0, 5, 0, 7]]
    prog = rnd.choice(progs)
    major = [0, 4, 7]
    minor = [0, 3, 7]
    scale = [0, 2, 4, 7, 9, 12, 14, 16]  # major pentatonic
    lead = rnd.choice(["bell", "soft_square", "tri"])
    buf = np.zeros(int((duration + 2) * SR), dtype=np.float32)
    # one 4-bar motif, repeated with small variations -> catchy
    motif = []
    deg = rnd.randrange(2, 5)
    for i in range(16):
        if rnd.random() < 0.22 and i % 4 != 0:
            motif.append(None)
            continue
        deg = max(0, min(len(scale) - 1, deg + rnd.choice([-2, -1, -1, 0, 1, 1, 2])))
        motif.append(deg)
    bars = int(duration / (4 * beat)) + 2
    for b in range(bars):
        t0 = b * 4 * beat
        off = prog[b % 4]
        tri = minor if off in (9, 2, 4) else major
        # bass
        for q in (0, 2):
            _add(buf, t0 + q * beat, _tone(midi_hz(root - 24 + off), beat * 1.6, "tri", 0.005, 0.35), 0.38)
        # arpeggio (8ths)
        for e in range(8):
            n = root - 12 + off + tri[e % 3] + (12 if e % 4 == 3 else 0)
            _add(buf, t0 + e * beat / 2, _tone(midi_hz(n), beat * 0.6, "sine", 0.004, 0.12), 0.10)
        # lead melody: motif on bars 0-1 and 2-3, varied every 4th bar
        for i in range(4):
            md = motif[(b % 4) * 4 + i] if b % 8 < 4 else motif[((b % 4) * 4 + i + 4) % 16]
            if md is None:
                continue
            n = root + scale[md]
            _add(buf, t0 + i * beat, _tone(midi_hz(n), beat * 0.9, lead, 0.008, 0.28), 0.16)
        # light percussion
        for q in range(4):
            tt = np.arange(int(0.18 * SR)) / SR
            kick = np.sin(2 * np.pi * (110 * tt - 160 * tt * tt)) * np.exp(-tt * 18)
            if q in (0, 2):
                _add(buf, t0 + q * beat, kick, 0.30)
            hat = np.random.RandomState(b * 4 + q).randn(int(0.04 * SR)) * np.exp(-np.arange(int(0.04 * SR)) / SR * 90)
            _add(buf, t0 + q * beat + beat / 2, hat, 0.035)
            if q in (1, 3):
                clap = np.random.RandomState(99 + q).randn(int(0.09 * SR)) * np.exp(-np.arange(int(0.09 * SR)) / SR * 35)
                _add(buf, t0 + q * beat, clap, 0.05)
    buf = buf[: int(duration * SR)]
    # fades
    f = int(min(1.5, duration / 4) * SR)
    if f > 0:
        buf[:f] *= np.linspace(0, 1, f)
        buf[-f:] *= np.linspace(1, 0, f)
    peak = np.abs(buf).max()
    return buf / peak * 0.9 if peak > 0 else buf


def sfx_pop():
    n = int(0.13 * SR)
    t = np.arange(n) / SR
    f = 520 + 1400 * t / 0.13
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 28) * 0.8


def sfx_whoosh():
    n = int(0.35 * SR)
    noise = np.random.RandomState(7).randn(n)
    k = 40
    noise = np.convolve(noise, np.ones(k) / k, mode="same")
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    return noise * env * 2.2


def sfx_boing():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 220 + 260 * t / 0.35 + 30 * np.sin(2 * np.pi * 18 * t)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7) * 0.6


def sfx_chime():
    out = np.zeros(int(0.8 * SR), dtype=np.float32)
    for i, m in enumerate((84, 88, 91, 96)):
        _add(out, i * 0.07, _tone(midi_hz(m), 0.6, "bell", 0.003, 0.25), 0.35)
    return out
