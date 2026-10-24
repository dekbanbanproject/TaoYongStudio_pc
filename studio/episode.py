"""Turns a script into a timeline, mixes the audio, renders the video(s) and writes upload files."""
import json
import math
import random
import subprocess
import time
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from . import art, audio, tts
from .script import BG_ALIASES
from .textrender import load_font, text_block

LAYOUTS = {
    "vertical": dict(
        W=1080, H=1920, ground=1380,
        char_h={1: 680, 2: 600, 3: 520, 4: 450},
        xs={1: [0.5], 2: [0.29, 0.71], 3: [0.2, 0.5, 0.8], 4: [0.14, 0.38, 0.62, 0.86]},
        card=(540, 340), card_max=(860, 400), card_font=170,
        items_y=650, item_px=150, row_max=5,
        sub_y=1555, sub_w=880, sub_font=76,
        banner_y=560, banner_w=880, banner_font=92,
        cloud_band=(140, 620), wm=(40, 60),
    ),
    "horizontal": dict(
        W=1920, H=1080, ground=900,
        char_h={1: 560, 2: 520, 3: 450, 4: 400},
        xs={1: [0.5], 2: [0.22, 0.78], 3: [0.15, 0.5, 0.85], 4: [0.12, 0.37, 0.63, 0.88]},
        card=(960, 190), card_max=(900, 250), card_font=140,
        items_y=385, item_px=125, row_max=8,
        sub_y=995, sub_w=1500, sub_font=64,
        banner_y=330, banner_w=1200, banner_font=96,
        cloud_band=(60, 360), wm=(40, 36),
    ),
    "square": dict(
        W=1080, H=1080, ground=860,
        char_h={1: 520, 2: 460, 3: 400, 4: 340},
        xs={1: [0.5], 2: [0.26, 0.74], 3: [0.18, 0.5, 0.82], 4: [0.13, 0.38, 0.62, 0.87]},
        card=(540, 210), card_max=(820, 260), card_font=140,
        items_y=460, item_px=130, row_max=6,
        sub_y=950, sub_w=940, sub_font=66,
        banner_y=380, banner_w=920, banner_font=94,
        cloud_band=(80, 420), wm=(40, 40),
    ),
}


def get_scaled_layout(fmt, resolution="1080p"):
    """Scale layout proportionally based on requested resolution (480p, 720p, 1080p, 4k)."""
    base_fmt = fmt if fmt in LAYOUTS else "horizontal"
    base = LAYOUTS[base_fmt]
    scale_map = {
        "480p": 480 / 1080,
        "720p": 720 / 1080,
        "1080p": 1.0,
        "4k": 2.0,
    }
    scale = scale_map.get(str(resolution).lower(), 1.0)
    if scale == 1.0:
        d = dict(base)
        d["scale"] = 1.0
        return d

    W = int(round(base["W"] * scale))
    if W % 2 != 0:
        W += 1
    H = int(round(base["H"] * scale))
    if H % 2 != 0:
        H += 1

    return dict(
        W=W, H=H,
        ground=int(base["ground"] * scale),
        char_h={k: int(v * scale) for k, v in base["char_h"].items()},
        xs=base["xs"],
        card=(int(base["card"][0] * scale), int(base["card"][1] * scale)),
        card_max=(int(base["card_max"][0] * scale), int(base["card_max"][1] * scale)),
        card_font=max(16, int(base["card_font"] * scale)),
        items_y=int(base["items_y"] * scale),
        item_px=max(20, int(base["item_px"] * scale)),
        row_max=base["row_max"],
        sub_y=int(base["sub_y"] * scale),
        sub_w=int(base["sub_w"] * scale),
        sub_font=max(14, int(base["sub_font"] * scale)),
        banner_y=int(base["banner_y"] * scale),
        banner_w=int(base["banner_w"] * scale),
        banner_font=max(18, int(base["banner_font"] * scale)),
        cloud_band=(int(base["cloud_band"][0] * scale), int(base["cloud_band"][1] * scale)),
        wm=(int(base["wm"][0] * scale), int(base["wm"][1] * scale)),
        scale=scale,
    )

FONT = "fonts/Kanit-Bold.ttf"


def ease_back(x):
    x = min(1.0, max(0.0, x))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


# ------------------------------------------------------------------ timeline structures
@dataclass
class Line:
    start: float
    end: float
    who: str
    text: str
    voice_start: float = 0.0
    env: np.ndarray = None


@dataclass
class Span:
    start: float
    end: float
    data: dict = field(default_factory=dict)


@dataclass
class SceneT:
    start: float
    end: float
    bg: str
    cast: list
    lines: list = field(default_factory=list)
    actions: list = field(default_factory=list)  # Span(data={who, action, speaking_line})
    cards: list = field(default_factory=list)
    items: list = field(default_factory=list)
    kind: str = "scene"  # intro / scene / outro


class Episode:
    def __init__(self, script, cfg, log=print, resolution="1080p", fps=None, encoder="auto", engine_type="2d_cartoon"):
        self.s = script
        self.cfg = cfg
        self.log = log
        self.root = Path(cfg["_root"])
        self.resolution = resolution or "1080p"
        self.fps = int(fps) if fps else int(cfg["video"]["fps"])
        self.encoder = encoder or "auto"
        self.engine_type = engine_type or "2d_cartoon"
        self.engines_used = set()
        self.warnings = []
        self.seed = int(script.get("music_seed", zlib.crc32(str(script.get("id", "x")).encode("utf-8")) % 100000))

    # -------------------------------------------------------------- voices
    def _voice(self, who, text):
        vc = dict(self.cfg["voices"].get(who) or self.cfg["voices"]["narrator"])
        if self.cfg["tts"].get("azure_key"):
            vc["_azure_key"] = self.cfg["tts"]["azure_key"]
            vc["_azure_region"] = self.cfg["tts"].get("azure_region", "southeastasia")
        engines = list(self.cfg["tts"]["engines"])
        x, eng = tts.synth_with_fallback(text, vc, engines, self.root / "cache" / "tts", self.log,
                                         allow_test=bool(self.cfg.get("allow_test_voice", False)))
        self.engines_used.add(eng)
        return x * float(self.cfg["audio"].get("voice_volume", 1.0))

    # -------------------------------------------------------------- build timeline
    def build(self):
        s, cfg = self.s, self.cfg
        chars = s["characters"]
        gap = float(cfg.get("line_gap_seconds", 0.35))
        self.voice_clips = []  # (start, samples)
        self.sfx = []  # (start, name)
        self.scenes = []
        t = 0.0

        # intro
        first_bg = BG_ALIASES.get(s["scenes"][0].get("background", "meadow"), s["scenes"][0].get("background", "meadow"))
        intro_len = float(cfg.get("intro_seconds", 2.2))
        intro = SceneT(0.0, 0.0, first_bg, chars, kind="intro")
        if cfg.get("read_title", True):
            x = self._voice("narrator", s["title"])
            self.voice_clips.append((0.45, x))
            intro_len = max(intro_len, 0.45 + len(x) / audio.SR + 0.5)
        intro.end = intro_len
        intro.actions = [Span(0.35, intro_len, {"who": c, "action": "jump"}) for c in chars]
        self.sfx.append((0.12, "pop"))
        self.sfx.append((0.35, "boing"))
        self.scenes.append(intro)
        t = intro_len

        for si, sc in enumerate(s["scenes"]):
            bg = BG_ALIASES.get(sc.get("background", "meadow"), sc.get("background", "meadow"))
            cast = sc.get("cast", chars)
            scene = SceneT(t, t, bg, cast)
            self.sfx.append((max(0.0, t - 0.12), "whoosh"))
            t += 0.4
            card_open = None
            item_group = None  # dict(kind,color,slots,spans)
            groups = []
            beats = sc["beats"]
            for b in beats:
                text = b.get("say", b.get("text", "")).strip()
                who = b.get("who", "narrator")
                start = t
                if text:
                    x = self._voice(who, text)
                    dur = len(x) / audio.SR
                    vstart = start + 0.08
                    self.voice_clips.append((vstart, x))
                    length = max(1.0, dur + 0.08 + gap)
                    ln = Line(start, start + length, who, text, vstart, audio.envelope(x, self.fps))
                    scene.lines.append(ln)
                else:
                    length = float(b.get("pause", 1.0))
                    ln = None
                end = start + length
                # actions
                if who != "narrator" and who in cast:
                    scene.actions.append(Span(start, end, {"who": who, "action": b.get("action", "talk"), "line": ln}))
                if b.get("react"):
                    for c in cast:
                        if c != who:
                            scene.actions.append(Span(start, end, {"who": c, "action": b["react"]}))
                if b.get("action") in ("jump", "cheer"):
                    self.sfx.append((start + 0.05, "boing"))
                # card
                if "card" in b:
                    if card_open:
                        card_open.end = start
                        card_open = None
                    if b["card"] not in (None, ""):
                        card_open = Span(start, None, {"text": str(b["card"]), "color": b.get("card_color")})
                        scene.cards.append(card_open)
                        self.sfx.append((start + 0.05, "pop"))
                # items
                if "items" in b:
                    it = b["items"] or {}
                    kind, colr, n = it.get("kind"), it.get("color"), int(it.get("count", 1) if it else 0)
                    if not kind or n <= 0:
                        if item_group:
                            for sp in item_group["spans"]:
                                if sp.end is None:
                                    sp.end = start
                        item_group = None
                    else:
                        if item_group and (item_group["kind"], item_group["color"]) == (kind, colr):
                            live = [sp for sp in item_group["spans"] if sp.end is None]
                            if n > len(live):
                                for k in range(len(live), n):
                                    d = start + 0.1 + 0.18 * (k - len(live))
                                    item_group["spans"].append(Span(d, None, {"slot": k}))
                                    self.sfx.append((d, "pop"))
                            else:
                                for sp in live[n:]:
                                    sp.end = start
                            item_group["slots"] = max(item_group["slots"], n)
                        else:
                            if item_group:
                                for sp in item_group["spans"]:
                                    if sp.end is None:
                                        sp.end = start
                            item_group = {"kind": kind, "color": colr, "slots": n, "spans": []}
                            groups.append(item_group)
                            for k in range(n):
                                d = start + 0.1 + 0.18 * k
                                item_group["spans"].append(Span(d, None, {"slot": k}))
                                self.sfx.append((d, "pop"))
                t = end
            t += 0.45
            scene.end = t
            for c in scene.cards:
                if c.end is None:
                    c.end = t
            for g in groups:
                for sp in g["spans"]:
                    if sp.end is None:
                        sp.end = t
                    sp.data.update(kind=g["kind"], color=g["color"], slots=g["slots"])
                    scene.items.append(sp)
            self.scenes.append(scene)

        # outro
        last_bg = self.scenes[-1].bg
        outro_len = float(cfg.get("outro_seconds", 2.8))
        outro = SceneT(t, t, last_bg, chars, kind="outro")
        self.sfx.append((t + 0.1, "chime"))
        if cfg.get("read_outro", True) and cfg.get("outro_text"):
            x = self._voice("narrator", cfg["outro_text"])
            self.voice_clips.append((t + 0.35, x))
            outro_len = max(outro_len, 0.35 + len(x) / audio.SR + 0.9)
        outro.end = t + outro_len
        outro.actions = [Span(t, outro.end, {"who": c, "action": "wave"}) for c in chars]
        self.scenes.append(outro)
        self.duration = outro.end
        max_min = float(cfg.get("max_minutes", 4))
        if self.duration > max_min * 60:
            raise ValueError("episode is %.0fs, longer than max_minutes" % self.duration)
        return self

    # -------------------------------------------------------------- audio mix
    def mix_audio(self, path):
        n = int(math.ceil(self.duration * audio.SR)) + audio.SR // 10
        voice = np.zeros(n, dtype=np.float32)
        for st, x in self.voice_clips:
            audio._add(voice, st, x)
        fx = np.zeros(n, dtype=np.float32)
        lib = {"pop": audio.sfx_pop(), "whoosh": audio.sfx_whoosh(), "boing": audio.sfx_boing(),
               "chime": audio.sfx_chime()}
        for st, name in self.sfx:
            audio._add(fx, st, lib[name])
        music = self._music(n)
        # duck music under speech
        act = np.abs(voice)
        k = int(0.25 * audio.SR)
        act = np.convolve(act, np.ones(k) / k, mode="same")
        act = np.clip(act * 25, 0, 1)
        mvol = float(self.cfg["audio"]["music_volume"])
        mixd = voice + fx * float(self.cfg["audio"]["sfx_volume"]) + music * mvol * (1 - 0.5 * act)
        peak = np.abs(mixd).max()
        if peak > 0.97:
            mixd *= 0.97 / peak
        audio.write_wav(path, mixd)

    def _music(self, n):
        src = self.cfg["audio"].get("music", "auto")
        dur = n / audio.SR
        if src and src != "auto":
            folder = Path(src)
            if not folder.is_absolute():
                folder = self.root / folder
            files = sorted([p for p in folder.glob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg")])
            if files:
                pick = files[self.seed % len(files)]
                tmp = self.root / "cache" / "music_tmp.wav"
                tmp.parent.mkdir(parents=True, exist_ok=True)
                audio.to_wav(pick, tmp)
                m = audio.read_wav(tmp)
                reps = int(math.ceil(n / max(1, len(m))))
                m = np.tile(m, reps)[:n]
                f = int(1.2 * audio.SR)
                m[-f:] *= np.linspace(1, 0, f)
                pk = np.abs(m).max()
                self.music_source = pick.name
                return m / pk * 0.9 if pk > 0 else m
            self.warnings.append("music folder empty, generated music instead")
        self.music_source = "generated (seed %d)" % self.seed
        m = audio.make_music(dur, self.seed)
        return np.pad(m, (0, max(0, n - len(m))))[:n]

    # -------------------------------------------------------------- rendering
    def _prepare_format(self, fmt):
        L = get_scaled_layout(fmt, getattr(self, "resolution", "1080p"))
        self.L = L
        self.font = load_font(str(self.root / FONT))
        self.bg_cache = {}
        self.sprite_cache = {}
        self.img_cache = {}
        self.cloud = art.draw_cloud(int(L["W"] * 0.26 if fmt == "vertical" else (L["W"] * 0.22 if fmt == "square" else L["W"] * 0.16)))
        rnd = random.Random(self.seed)
        self.clouds = [(rnd.uniform(0, L["W"]), rnd.uniform(*L["cloud_band"]), rnd.uniform(14, 30)) for _ in range(3)]
        # blink schedule per character
        self.blinks = {}
        for c in art.SPECIES:
            r = random.Random(self.seed + zlib.crc32(c.encode()) % 1000)
            ts, tt = [], r.uniform(0.5, 2.5)
            while tt < self.duration + 5:
                ts.append(tt)
                tt += r.uniform(2.2, 4.8)
            self.blinks[c] = ts

    def _bg(self, kind):
        if kind not in self.bg_cache:
            L = self.L
            self.bg_cache[kind] = art.draw_background(kind, L["W"], L["H"], L["ground"], seed=self.seed)
        return self.bg_cache[kind]

    def _sprite(self, species, h, mouth, eyes, al, ar):
        key = (species, h, mouth, eyes, al, ar)
        if key not in self.sprite_cache:
            self.sprite_cache[key] = art.draw_character(species, mouth, eyes, al, ar, scale=h / art.CHAR_H)
        return self.sprite_cache[key]

    def _cached(self, key, fn):
        if key not in self.img_cache:
            self.img_cache[key] = fn()
        return self.img_cache[key]

    def _card_img(self, text, colr):
        L = self.L

        def make():
            fill = art.color(colr, art.INK) if colr else art.INK
            tb = text_block(self.font, text, L["card_font"], L["card_max"][0] - 80, fill=fill,
                            max_lines=2, min_size=60)
            if tb.height > L["card_max"][1] - 60:
                r = (L["card_max"][1] - 60) / tb.height
                tb = tb.resize((max(1, int(tb.width * r)), max(1, int(tb.height * r))), Image.LANCZOS)
            pw, ph = max(tb.width + 110, 260), tb.height + 90
            panel = art.draw_panel(pw, ph)
            panel.alpha_composite(tb, ((panel.width - tb.width) // 2, (panel.height - tb.height) // 2 + 4))
            return panel

        return self._cached(("card", text, colr), make)

    def _banner_img(self, text):
        L = self.L

        def make():
            tb = text_block(self.font, text, L["banner_font"], L["banner_w"] - 120, fill=art.INK,
                            max_lines=3, min_size=50)
            panel = art.draw_panel(tb.width + 120, tb.height + 110, fill="#FFD93D", radius=60)
            panel.alpha_composite(tb, ((panel.width - tb.width) // 2, (panel.height - tb.height) // 2 + 4))
            return panel

        return self._cached(("banner", text), make)

    def _sub_img(self, text):
        L = self.L
        def make():
            tb = text_block(self.font, text, L["sub_font"], L["sub_w"], fill="#FFFFFF", outline="#2B1D4A",
                            outline_px=5, max_lines=3, min_size=40)
            px, py = 34, 18
            pill = Image.new("RGBA", (tb.width + px * 2, tb.height + py * 2), (0, 0, 0, 0))
            from PIL import ImageDraw
            ImageDraw.Draw(pill).rounded_rectangle((0, 0, pill.width - 1, pill.height - 1),
                                                   radius=min(40, pill.height // 2), fill=(43, 29, 74, 140))
            pill.alpha_composite(tb, (px, py))
            return pill

        return self._cached(("sub", text), make)

    def _item_img(self, kind, colr, px):
        return self._cached(("item", kind, colr, px), lambda: art.draw_item(kind, colr, px))

    @staticmethod
    def _paste_center(frame, img, cx, cy, scale=1.0):
        if scale <= 0.02:
            return
        if abs(scale - 1.0) > 0.01:
            img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BILINEAR)
        frame.paste(img, (int(cx - img.width / 2), int(cy - img.height / 2)), img)

    def _pose(self, action, ta, side_sign, speaking, t, phase):
        """Return (arm_l, arm_r, lift_px, eyes_closed_override, dx)."""
        al = ar = 18
        lift, eyes, dx = 0.0, False, 0.0
        outer_is_left = side_sign < 0
        if action == "wave":
            ang = [128, 146, 164, 146][int(ta * 8) % 4]
            if outer_is_left:
                al = ang
            else:
                ar = ang
        elif action == "jump":
            if ta < 0.6:
                lift = 115 * math.sin(math.pi * ta / 0.6)
                al = ar = 140
        elif action == "cheer":
            al = ar = 150 + (8 if int(ta * 6) % 2 else -8)
            lift = 45 * abs(math.sin(math.pi * ta / 0.45))
        elif action == "point":
            if outer_is_left:
                ar = 95
            else:
                al = 95
        elif action == "happy":
            eyes = True
            lift = 18 * abs(math.sin(math.pi * ta / 0.35))
        elif action == "dance":
            dx = 26 * math.sin(ta * 6)
            k = int(ta * 4) % 2
            al, ar = (140, 30) if k else (30, 140)
            lift = 20 * abs(math.sin(ta * 6))
        if speaking and action in ("talk", "point", "wave"):
            lift += 7 * abs(math.sin(t * 8.5 + phase))
        return al, ar, lift, eyes, dx

    def _draw_frame(self, t):
        L = self.L
        sc = next((s for s in self.scenes if s.start <= t < s.end), self.scenes[-1])
        frame = self._bg(sc.bg).copy()
        is_parallax = getattr(self, "engine_type", "2d_cartoon") == "25d_parallax"
        scale = L.get("scale", 1.0)
        p_offset = int(12 * math.sin(t * 0.5) * scale) if is_parallax else 0

        if sc.bg in art.OUTDOOR:
            cw = self.cloud.width
            for x0, y0, sp in self.clouds:
                x = (x0 + sp * t + int(p_offset * 1.5)) % (L["W"] + cw) - cw
                frame.paste(self.cloud, (int(x), int(y0)), self.cloud)

        # characters
        cast = sc.cast
        n = len(cast)
        h = L["char_h"][min(n, 4)]
        h = int(h)
        cw, _ = art.char_size(h)
        speaking_line = next((ln for ln in sc.lines if ln.start <= t < ln.end), None)
        for idx, c in enumerate(cast):
            cx = L["W"] * L["xs"][min(n, 4)][idx] + int(p_offset * 0.7)
            side = -1 if cx < L["W"] / 2 else 1
            act = next((a for a in reversed(sc.actions) if a.data["who"] == c and a.start <= t < a.end), None)
            action = act.data["action"] if act else "none"
            ta = t - act.start if act else 0.0
            speaking = bool(act and act.data.get("line") is not None and speaking_line is act.data.get("line"))
            phase = idx * 1.7
            al, ar, lift, eyes_closed, dx = self._pose(action, ta, side, speaking, t, phase)
            mouth = 0
            if speaking:
                ln = act.data["line"]
                fi = int((t - ln.voice_start) * self.fps)
                if 0 <= fi < len(ln.env):
                    v = ln.env[fi]
                    mouth = 0 if v < 0.12 else (1 if v < 0.45 else 2)
            if not eyes_closed:
                eyes_closed = any(b <= t < b + 0.13 for b in self.blinks.get(c, []))
            if action == "happy":
                mouth = max(mouth, 0)
            breath = 4 * math.sin(t * 2.3 + phase)
            sprite = self._sprite(c, h, mouth, eyes_closed, int(al), int(ar))
            shadow = self._cached(("shadow", cw), lambda: art.shadow_sprite(cw * 0.62))
            sscale = max(0.5, 1 - lift / 500)
            self._paste_center(frame, shadow, cx + dx, L["ground"] - 4, sscale)
            x = int(cx + dx - sprite.width / 2)
            y = int(L["ground"] - sprite.height + 6 - lift + breath)
            frame.paste(sprite, (x, y), sprite)

        # items
        for sp in sc.items:
            if sp.start <= t < sp.end:
                d = sp.data
                slots = d["slots"]
                px = int(L["item_px"] * {1: 1.7, 2: 1.45, 3: 1.2}.get(slots, 1.0)) if slots <= L["row_max"] \
                    else int(L["item_px"] * 0.8)
                per_row = min(slots, L["row_max"])
                rows = int(math.ceil(slots / L["row_max"]))
                r, col = divmod(d["slot"], L["row_max"])
                in_row = per_row if r < rows - 1 else slots - per_row * (rows - 1)
                gap = px * 1.12
                cx = L["W"] / 2 + (col - (in_row - 1) / 2) * gap + int(p_offset * 1.2)
                cy = L["items_y"] + (r - (rows - 1) / 2) * gap - (gap * 0.25 if rows > 1 else 0)
                cy += 6 * math.sin(t * 3 + d["slot"])
                img = self._item_img(d["kind"], d["color"], px)
                self._paste_center(frame, img, cx, cy, ease_back((t - sp.start) / 0.35))

        # card
        for sp in sc.cards:
            if sp.start <= t < sp.end:
                img = self._card_img(sp.data["text"], sp.data.get("color"))
                card_x = L["card"][0] + int(p_offset * 1.0)
                self._paste_center(frame, img, card_x, L["card"][1], ease_back((t - sp.start) / 0.35))

        # intro / outro banner
        if sc.kind in ("intro", "outro"):
            text = self.s["title"] if sc.kind == "intro" else self.cfg.get("outro_text", "")
            if text:
                img = self._banner_img(text)
                ta = t - sc.start
                s_ = ease_back((ta - 0.1) / 0.4)
                wob = 1 + 0.02 * math.sin(ta * 4)
                self._paste_center(frame, img, L["W"] / 2, L["banner_y"], s_ * wob)

        # subtitles
        if speaking_line:
            img = self._sub_img(speaking_line.text)
            self._paste_center(frame, img, L["W"] / 2, L["sub_y"])

        # channel watermark
        if self.cfg.get("channel_name"):
            wm = self._cached(("wm",), lambda: text_block(self.font, self.cfg["channel_name"], 40, 600,
                                                          fill="#FFFFFF", outline="#2B1D4A", outline_px=4))
            frame.paste(wm, L["wm"], wm)

        # fade from white at each scene start
        k = t - sc.start
        if sc.kind == "scene" and k < 0.3:
            white = self._cached(("white",), lambda: Image.new("RGB", (L["W"], L["H"]), "#FFFFFF"))
            frame = Image.blend(white, frame, k / 0.3)
        return frame

    def render(self, fmt, out_mp4, audio_wav, log_every=5.0):
        self._prepare_format(fmt)
        L = self.L
        v = self.cfg["video"]

        # Choose encoder
        candidate = getattr(self, "encoder", "auto")
        if candidate == "auto" or not candidate:
            try:
                from . import hardware
                tests = hardware.detect_hardware().get("encoders", {})
                if tests.get("h264_nvenc", {}).get("ok"):
                    candidate = "h264_nvenc"
                elif tests.get("h264_qsv", {}).get("ok"):
                    candidate = "h264_qsv"
                elif tests.get("h264_mf", {}).get("ok"):
                    candidate = "h264_mf"
                else:
                    candidate = "libx264"
            except Exception:
                candidate = "libx264"

        def _get_ffmpeg_cmd(enc):
            c = [audio.ffmpeg_exe(), "-y", "-loglevel", "error",
                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (L["W"], L["H"]), "-r", str(self.fps),
                 "-i", "-", "-i", str(audio_wav)]
            if enc == "h264_nvenc":
                c += ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "22", "-pix_fmt", "yuv420p"]
            elif enc == "h264_qsv":
                c += ["-c:v", "h264_qsv", "-preset", "veryfast", "-global_quality", "22"]
            elif enc == "h264_mf":
                c += ["-c:v", "h264_mf", "-pix_fmt", "yuv420p"]
            else:
                c += ["-c:v", "libx264", "-preset", v.get("preset", "veryfast"), "-crf", str(v.get("crf", 21)),
                      "-pix_fmt", "yuv420p"]
            c += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-ac", "2",
                  "-c:a", "aac", "-b:a", "160k", "-shortest",
                  "-movflags", "+faststart", str(out_mp4)]
            return c

        active_encoder = candidate
        cmd = _get_ffmpeg_cmd(active_encoder)
        self.log("  encoder: %s (%dx%d @ %dfps)" % (active_encoder, L["W"], L["H"], self.fps))

        proc = None
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, **audio._no_window())
        except Exception as e:
            if active_encoder != "libx264":
                self.log("  %s start failed (%s), fallback to libx264" % (active_encoder, e))
                active_encoder = "libx264"
                cmd = _get_ffmpeg_cmd(active_encoder)
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, **audio._no_window())
            else:
                raise

        frames = int(math.ceil(self.duration * self.fps))
        t0 = time.time()
        last = t0
        try:
            for f in range(frames):
                img = self._draw_frame(f / self.fps)
                proc.stdin.write(img.tobytes())
                if time.time() - last > log_every:
                    last = time.time()
                    self.log("  %s %d%%" % (fmt, 100 * f // frames))
        finally:
            proc.stdin.close()
            rc = proc.wait()

        # Fallback if hardware encoder failed during run
        if rc != 0 and active_encoder != "libx264":
            self.log("  %s returned %d, retrying with CPU libx264..." % (active_encoder, rc))
            active_encoder = "libx264"
            cmd = _get_ffmpeg_cmd(active_encoder)
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, **audio._no_window())
            try:
                for f in range(frames):
                    img = self._draw_frame(f / self.fps)
                    proc.stdin.write(img.tobytes())
            finally:
                proc.stdin.close()
                rc = proc.wait()

        if rc != 0:
            raise RuntimeError("ffmpeg failed while writing %s (code %d)" % (out_mp4, rc))

        self.last_encoder_used = active_encoder
        return time.time() - t0

    def still(self, fmt, t):
        self._prepare_format(fmt)
        return self._draw_frame(t)

    # -------------------------------------------------------------- side files
    def srt(self):
        def ts(x):
            ms = int(round(x * 1000))
            return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)

        out, k = [], 1
        for sc in self.scenes:
            for ln in sc.lines:
                out.append("%d\n%s --> %s\n%s\n" % (k, ts(ln.start), ts(ln.end), ln.text))
                k += 1
        return "\n".join(out)


def produce(script, cfg, out_dir, formats=None, log=print,
            resolution="1080p", fps=None, encoder="auto", engine_type="2d_cartoon", device_id=None):
    """Full pipeline for one script. Returns a result dict for the batch report."""
    t0 = time.time()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = script["id"]
    ep = Episode(script, cfg, log, resolution=resolution, fps=fps, encoder=encoder, engine_type=engine_type).build()
    wav = out_dir / "_mix.wav"
    ep.mix_audio(wav)
    formats = formats or cfg["video"]["formats"]
    files = {}
    verifications = {}
    encoders_used = {}

    for fmt in formats:
        mp4 = out_dir / ("%s_%s.mp4" % (slug, fmt))
        secs = ep.render(fmt, mp4, wav)
        files[fmt] = mp4.name
        enc_name = getattr(ep, "last_encoder_used", "libx264")
        encoders_used[fmt] = enc_name
        log("  %s done in %.1fs (%s)" % (fmt, secs, enc_name))

        # Real verification using ffprobe/ffmpeg probe
        try:
            from . import hardware
            probe_res = hardware.probe_video(mp4)
            verifications[fmt] = probe_res
            if probe_res.get("ok"):
                log("  verified: %s, %.1fs, %s, %.2fMB" % (
                    probe_res["resolution"], probe_res["duration_seconds"],
                    probe_res["video_codec"], probe_res["size_mb"]))
            else:
                log("  verification warning: %s" % probe_res.get("error"))
        except Exception as e:
            verifications[fmt] = {"ok": False, "error": str(e)}

        thumb_t = min(ep.scenes[0].end - 0.3, 1.6)
        im = ep.still(fmt, thumb_t)
        if fmt == "horizontal" and im.width > 1280:
            im = im.resize((1280, 720), Image.LANCZOS)
        name = "thumb_%s.jpg" % fmt
        im.save(out_dir / name, quality=90)
        files["thumb_" + fmt] = name
    wav.unlink(missing_ok=True)
    (out_dir / "subtitles.srt").write_text(ep.srt(), encoding="utf-8")
    files["subtitles"] = "subtitles.srt"

    tags = script.get("tags", [])
    hashtags = " ".join("#" + str(x).replace(" ", "") for x in tags[:8])
    desc = script.get("description", "").strip()
    upload = "%s\n\n%s\n\n%s\n" % (script["title"], desc, hashtags)
    (out_dir / "upload.txt").write_text(upload, encoding="utf-8")
    files["upload_text"] = "upload.txt"

    review = []
    if not ep.engines_used & {"edge", "azure"}:
        review.append("voice used fallback engine(s): %s" % ", ".join(sorted(ep.engines_used)))
    if len(ep.engines_used) > 1:
        review.append("mixed voice engines in one clip: %s" % ", ".join(sorted(ep.engines_used)))
    review += ep.warnings
    meta = {
        "id": slug,
        "title": script["title"],
        "description": desc,
        "tags": tags,
        "genre": script.get("genre"),
        "request_id": script.get("request_id"),
        "shopee": script.get("shopee"),
        "made_for_kids": True,
        "ai_generated": True,
        "duration_seconds": round(ep.duration, 2),
        "files": files,
        "voice_engines": sorted(ep.engines_used),
        "music": getattr(ep, "music_source", ""),
        "needs_review": review,
        "status": "ready_for_approval",
        "render_seconds": round(time.time() - t0, 1),
        # Local GPU Studio V1 Metadata
        "engine_type": engine_type,
        "resolution": getattr(ep, "resolution", "1080p"),
        "fps": ep.fps,
        "encoders_used": encoders_used,
        "verifications": verifications,
        "device_id": device_id or getattr(ep, "encoder", "auto"),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta
    return meta
