"""Thai-correct text rendering (HarfBuzz shaping + FreeType rasterising).

Pillow's built-in layout cannot place Thai vowels and tone marks correctly
on Windows, so we shape with HarfBuzz and draw glyphs ourselves.
"""
import io
import math
from functools import lru_cache

import freetype
import numpy as np
import uharfbuzz as hb
from PIL import Image

# Thai characters that attach to the previous character (never start a line)
_THAI_ATTACH_PREV = set(
    [0x0E31, 0x0E33] + list(range(0x0E34, 0x0E3B)) + list(range(0x0E47, 0x0E4F))
)
# Thai leading vowels that attach to the next character (never end a line)
_THAI_ATTACH_NEXT = set(range(0x0E40, 0x0E45))


class Font:
    def __init__(self, path):
        self.path = str(path)
        with open(self.path, "rb") as f:
            data = f.read()
        self.hb_face = hb.Face(data)
        self.hb_font = hb.Font(self.hb_face)
        self.upem = self.hb_face.upem
        self.ft = freetype.Face(io.BytesIO(data))  # from memory: safe with Thai folder names on Windows

    def _shape(self, text):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb_font, buf, {"kern": True, "liga": True})
        return buf.glyph_infos, buf.glyph_positions

    def measure(self, text, size):
        _, pos = self._shape(text)
        return sum(p.x_advance for p in pos) * size / self.upem

    def mask(self, text, size):
        """Return an L-mode mask of the text plus the baseline y position."""
        infos, pos = self._shape(text)
        scale = size / self.upem
        self.ft.set_pixel_sizes(0, int(size))
        pad = int(size * 0.35) + 4
        asc = size * 1.05
        desc = size * 0.45
        width = int(math.ceil(sum(p.x_advance for p in pos) * scale)) + pad * 2
        height = int(math.ceil(asc + desc)) + pad * 2
        canvas = np.zeros((height, width), dtype=np.uint8)
        pen_x = float(pad)
        baseline = pad + asc
        for info, p in zip(infos, pos):
            self.ft.load_glyph(info.codepoint, freetype.FT_LOAD_DEFAULT | freetype.FT_LOAD_NO_HINTING)
            g = self.ft.glyph
            g.render(freetype.FT_RENDER_MODE_NORMAL)
            bm = g.bitmap
            if bm.width and bm.rows:
                arr = np.array(bm.buffer, dtype=np.uint8).reshape(bm.rows, bm.pitch)[:, : bm.width]
                x = int(round(pen_x + p.x_offset * scale + g.bitmap_left))
                y = int(round(baseline - p.y_offset * scale - g.bitmap_top))
                x0, y0 = max(x, 0), max(y, 0)
                x1, y1 = min(x + bm.width, width), min(y + bm.rows, height)
                if x1 > x0 and y1 > y0:
                    sub = arr[y0 - y : y1 - y, x0 - x : x1 - x]
                    canvas[y0:y1, x0:x1] = np.maximum(canvas[y0:y1, x0:x1], sub)
            pen_x += p.x_advance * scale
        return Image.fromarray(canvas, "L"), baseline


def _dilate(mask_arr, r):
    if r <= 0:
        return mask_arr
    h, w = mask_arr.shape
    padded = np.zeros((h + 2 * r, w + 2 * r), dtype=np.uint8)
    padded[r : r + h, r : r + w] = mask_arr
    out = np.zeros_like(padded)
    step = max(1, r // 6)
    for dy in range(-r, r + 1, step):
        for dx in range(-r, r + 1, step):
            if dx * dx + dy * dy <= r * r:
                out[r + dy : r + dy + h, r + dx : r + dx + w] = np.maximum(
                    out[r + dy : r + dy + h, r + dx : r + dx + w], mask_arr
                )
    return out


def _crop_alpha(img):
    bbox = img.getchannel("A").getbbox()
    return img.crop(bbox) if bbox else img


def hex_rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))


def text_line(font, text, size, fill="#FFFFFF", outline=None, outline_px=0, crop=True):
    """Render one line of text to an RGBA image (cropped to ink unless crop=False)."""
    m, _ = font.mask(text, size)
    arr = np.array(m)
    r = int(outline_px)
    if outline and r > 0:
        big = _dilate(arr, r)
        body = np.zeros_like(big)
        body[r : r + arr.shape[0], r : r + arr.shape[1]] = arr
        h, w = big.shape
        out = np.zeros((h, w, 4), dtype=np.uint8)
        oc, fc = hex_rgb(outline), hex_rgb(fill)
        a_body = body.astype(np.float32) / 255.0
        for i in range(3):
            out[..., i] = (oc[i] * (1 - a_body) + fc[i] * a_body).astype(np.uint8)
        out[..., 3] = big
        img = Image.fromarray(out, "RGBA")
    else:
        fc = hex_rgb(fill)
        out = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.uint8)
        out[..., 0], out[..., 1], out[..., 2] = fc
        out[..., 3] = arr
        img = Image.fromarray(out, "RGBA")
    return _crop_alpha(img) if crop else img


def _clusters(word):
    """Split a word into break-safe clusters (keeps Thai marks attached)."""
    out = []
    cur = ""
    for ch in word:
        cp = ord(ch)
        if cur and cp not in _THAI_ATTACH_PREV and not (ord(cur[-1]) in _THAI_ATTACH_NEXT):
            out.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def wrap(font, text, size, max_width):
    """Greedy wrap on spaces / zero-width spaces; long words break between clusters."""
    lines = []
    for para in str(text).split("\n"):
        words = [w for w in para.replace("​", " ").split(" ") if w]
        cur = ""
        for w in words:
            trial = (cur + " " + w) if cur else w
            if font.measure(trial, size) <= max_width:
                cur = trial
                continue
            if cur:
                lines.append(cur)
                cur = ""
            if font.measure(w, size) <= max_width:
                cur = w
                continue
            piece = ""
            for c in _clusters(w):
                if font.measure(piece + c, size) <= max_width or not piece:
                    piece += c
                else:
                    lines.append(piece)
                    piece = c
            cur = piece
        if cur:
            lines.append(cur)
    return lines or [""]


def text_block(font, text, size, max_width, fill="#FFFFFF", outline=None, outline_px=0,
               line_gap=0.18, align="center", max_lines=None, min_size=None):
    """Wrap + render a block. Shrinks the font if it needs more than max_lines."""
    size = int(size)
    while True:
        lines = wrap(font, text, size, max_width)
        if max_lines is None or len(lines) <= max_lines or (min_size and size <= min_size):
            break
        size = int(size * 0.9)
    imgs = [text_line(font, ln, size, fill, outline, outline_px, crop=False) for ln in lines]
    # trim horizontal padding per line, keep the shared vertical metrics
    trimmed = []
    for im in imgs:
        bb = im.getchannel("A").getbbox()
        trimmed.append(im.crop((bb[0], 0, bb[2], im.height)) if bb else im)
    lh = int(size * (1.25 + line_gap))
    width = max(i.width for i in trimmed)
    height = lh * (len(trimmed) - 1) + trimmed[-1].height
    block = Image.new("RGBA", (max(width, 1), max(height, 1)), (0, 0, 0, 0))
    for k, im in enumerate(trimmed):
        x = (width - im.width) // 2 if align == "center" else 0
        block.alpha_composite(im, (x, k * lh))
    return _crop_alpha(block)


@lru_cache(maxsize=8)
def load_font(path):
    return Font(path)
