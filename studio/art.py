"""All drawing: characters, backgrounds, props, cards. Pure Pillow, no image files needed.

Everything is drawn supersampled (SS x) and scaled down for smooth edges.
"""
import math
import random

from PIL import Image, ImageDraw, ImageFilter

SS = 2  # supersampling factor
INK = "#3A2A55"  # outline colour

COLORS = {
    "red": "#FF5A5F", "แดง": "#FF5A5F",
    "orange": "#FF9F1C", "ส้ม": "#FF9F1C",
    "yellow": "#FFD93D", "เหลือง": "#FFD93D",
    "green": "#5BC95B", "เขียว": "#5BC95B",
    "blue": "#4D96FF", "น้ำเงิน": "#4D96FF", "ฟ้า": "#6EC6FF",
    "purple": "#9B6CFF", "ม่วง": "#9B6CFF",
    "pink": "#FF8FC7", "ชมพู": "#FF8FC7",
    "brown": "#A9714B", "น้ำตาล": "#A9714B",
    "white": "#FFFFFF", "ขาว": "#FFFFFF",
    "black": "#333333", "ดำ": "#333333",
    "gray": "#A0A0A0", "เทา": "#A0A0A0",
}


def color(c, default="#FF5A5F"):
    if not c:
        return default
    c = str(c).strip()
    if c.startswith("#") and len(c) == 7:
        return c
    return COLORS.get(c.lower(), COLORS.get(c, default))


def rgba(hexc, a=255):
    hexc = hexc.lstrip("#")
    return (int(hexc[0:2], 16), int(hexc[2:4], 16), int(hexc[4:6], 16), a)


def mix(c1, c2, t):
    a, b = rgba(c1), rgba(c2)
    return "#%02X%02X%02X" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class Pen:
    """Draws in design units on a supersampled canvas."""

    def __init__(self, w, h, scale):
        self.k = scale * SS
        self.img = Image.new("RGBA", (max(1, int(w * self.k)), max(1, int(h * self.k))), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self.lw = max(1, int(6 * self.k))  # outline width

    def P(self, *v):
        return [x * self.k for x in v]

    def ellipse(self, cx, cy, rx, ry, fill, outline=INK, width=None):
        w = self.lw if width is None else max(1, int(width * self.k))
        self.d.ellipse(self.P(cx - rx, cy - ry, cx + rx, cy + ry), fill=fill,
                       outline=outline, width=w if outline else 0)

    def poly(self, pts, fill, outline=INK, width=None):
        w = self.lw if width is None else max(1, int(width * self.k))
        flat = [(x * self.k, y * self.k) for x, y in pts]
        self.d.polygon(flat, fill=fill, outline=outline, width=w if outline else 0)

    def rot_ellipse(self, cx, cy, rx, ry, ang, fill, outline=INK, width=None):
        a = math.radians(ang)
        pts = []
        for i in range(72):
            t = 2 * math.pi * i / 72
            x, y = rx * math.cos(t), ry * math.sin(t)
            pts.append((cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)))
        self.poly(pts, fill, outline, width)

    def line(self, pts, fill, width, round_caps=True):
        w = int(width * self.k)
        flat = [(x * self.k, y * self.k) for x, y in pts]
        self.d.line(flat, fill=fill, width=w, joint="curve")
        if round_caps:
            r = w / 2
            for x, y in (flat[0], flat[-1]):
                self.d.ellipse((x - r, y - r, x + r, y + r), fill=fill)

    def arc(self, cx, cy, rx, ry, start, end, fill=INK, width=6):
        self.d.arc(self.P(cx - rx, cy - ry, cx + rx, cy + ry), start, end, fill=fill,
                   width=max(1, int(width * self.k)))

    def rrect(self, x0, y0, x1, y1, r, fill, outline=INK, width=None):
        w = self.lw if width is None else max(1, int(width * self.k))
        self.d.rounded_rectangle(self.P(x0, y0, x1, y1), radius=r * self.k, fill=fill,
                                 outline=outline, width=w if outline else 0)

    def result(self):
        w, h = self.img.size
        return self.img.resize((max(1, w // SS), max(1, h // SS)), Image.LANCZOS)


# --------------------------------------------------------------------------- characters

SPECIES = {
    "bunny": dict(name="ปุยฝ้าย", body="#F4EFFF", belly="#FFE1EC", inner="#FFAFCB", accent="#FF8FC7"),
    "bear": dict(name="โกโก้", body="#B98057", belly="#EED3AE", inner="#EED3AE", accent="#7A4B2C"),
    "chick": dict(name="เจี๊ยบ", body="#FFD93D", belly="#FFF1A8", inner="#FFB627", accent="#FF9F1C"),
    "cat": dict(name="มิวมิว", body="#FFB86B", belly="#FFE7C7", inner="#FF9AA8", accent="#E07B39"),
}
CHAR_W, CHAR_H = 500, 720
SHOULDER_Y = 548
ARM_LEN = 105


def _arm(pen, side, ang, col):
    sx = 250 + side * 108
    sy = SHOULDER_Y
    a = math.radians(ang)
    hx, hy = sx + side * math.sin(a) * ARM_LEN, sy + math.cos(a) * ARM_LEN
    pen.line([(sx, sy), (hx, hy)], INK, 50)
    pen.line([(sx, sy), (hx, hy)], col, 38)
    pen.ellipse(hx, hy, 27, 27, col)


def draw_character(species, mouth=0, eyes_closed=False, arm_l=18, arm_r=18, scale=1.0):
    s = SPECIES.get(species, SPECIES["bunny"])
    p = Pen(CHAR_W, CHAR_H, scale)
    body, belly, inner, accent = s["body"], s["belly"], s["inner"], s["accent"]

    # ears / tufts behind the head
    if species == "bunny":
        for side in (-1, 1):
            p.rot_ellipse(250 + side * 62, 150, 40, 108, side * 9, body)
            p.rot_ellipse(250 + side * 62, 160, 20, 78, side * 9, inner, outline=None)
    elif species == "bear":
        for side in (-1, 1):
            p.ellipse(250 + side * 112, 212, 52, 52, body)
            p.ellipse(250 + side * 112, 212, 28, 28, inner, outline=None)
    elif species == "cat":
        for side in (-1, 1):
            bx = 250 + side * 100
            p.poly([(bx - 55, 250), (bx + side * 40, 120), (bx + 60, 250)][:: side or 1], body)
            p.poly([(bx - 30, 240), (bx + side * 30, 160), (bx + 35, 240)][:: side or 1], inner, outline=None)

    # feet + body
    for side in (-1, 1):
        p.ellipse(250 + side * 62, 690, 52, 26, body)
    _arm(pen=p, side=-1, ang=arm_l, col=body) if arm_l > 60 else None
    _arm(pen=p, side=1, ang=arm_r, col=body) if arm_r > 60 else None
    p.ellipse(250, 590, 122, 120, body)
    p.ellipse(250, 612, 78, 78, belly, outline=None)
    if arm_l <= 60:
        _arm(p, -1, arm_l, body)
    if arm_r <= 60:
        _arm(p, 1, arm_r, body)

    # head
    p.ellipse(250, 330, 152, 146, body)
    if species == "chick":
        for i, (dx, ang) in enumerate([(-22, -25), (0, 0), (22, 25)]):
            p.rot_ellipse(250 + dx, 178, 12, 34, ang, accent)
    if species == "bear":
        p.ellipse(250, 398, 70, 52, belly, outline=None)

    # cheeks (soft)
    cheek = Image.new("RGBA", p.img.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(cheek)
    k = p.k
    for side in (-1, 1):
        cx, cy = 250 + side * 92, 378
        cd.ellipse((k * (cx - 27), k * (cy - 17), k * (cx + 27), k * (cy + 17)), fill=rgba("#FF7FA8", 120))
    p.img.alpha_composite(cheek)

    # eyes
    for side in (-1, 1):
        ex, ey = 250 + side * 55, 322
        if eyes_closed:
            p.arc(ex, ey - 4, 20, 14, 20, 160, INK, 7)
        else:
            p.ellipse(ex, ey, 20, 27, INK, outline=None)
            p.ellipse(ex - 6, ey - 10, 7, 7, "#FFFFFF", outline=None)
            p.ellipse(ex + 7, ey + 9, 3.5, 3.5, "#FFFFFF", outline=None)

    # nose + mouth
    if species == "chick":
        top = 368
        gap = [0, 10, 22][mouth]
        p.poly([(222, top), (278, top), (250, top + 26)], accent, width=5)
        if gap:
            p.ellipse(250, top + 20 + gap / 2, 16, gap / 2 + 4, "#7A2E3A", outline=None)
            p.poly([(228, top + 22 + gap), (272, top + 22 + gap), (250, top + 40 + gap)], accent, width=5)
    else:
        if species == "bear":
            p.ellipse(250, 378, 22, 15, "#4A2E22", outline=None)
            my = 410
        elif species == "cat":
            p.poly([(240, 368), (260, 368), (250, 380)], "#FF7F96", width=4)
            my = 398
            for side in (-1, 1):
                for dy in (-8, 8):
                    p.line([(250 + side * 70, 380 + dy), (250 + side * 125, 372 + dy * 2)], INK, 4)
        else:
            p.poly([(240, 366), (260, 366), (250, 378)], accent, width=4)
            my = 398
        if mouth == 0:
            p.arc(250, my - 8, 22, 16, 20, 160, INK, 6)
        else:
            rx, ry = (17, 13) if mouth == 1 else (24, 24)
            p.ellipse(250, my + 2, rx, ry, "#7A2E3A", width=5)
            p.ellipse(250, my + ry * 0.55, rx * 0.6, ry * 0.4, "#FF8A9A", outline=None)
    return p.result()


def char_size(height):
    """(width, height) of a character sprite drawn for a given pixel height."""
    sc = height / CHAR_H
    return int(CHAR_W * sc), int(height)


def shadow_sprite(width):
    w, h = int(width), max(4, int(width * 0.18))
    img = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((0, 0, w * 2 - 1, h * 2 - 1), fill=(40, 30, 70, 70))
    return img.resize((w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(2))


# --------------------------------------------------------------------------- props

ITEM_KINDS = ["apple", "star", "ball", "heart", "balloon", "flower", "fish",
              "circle", "square", "triangle", "carrot", "car"]


def draw_item(kind, col=None, px=160):
    p = Pen(200, 200, px / 200)
    if kind == "apple":
        c = color(col, "#FF5A5F")
        p.line([(100, 52), (106, 22)], INK, 14)
        p.line([(100, 52), (106, 22)], "#8B5A2B", 8)
        p.ellipse(78, 112, 58, 62, c)
        p.ellipse(122, 112, 58, 62, c)
        p.ellipse(100, 115, 40, 50, c, outline=None)
        p.rot_ellipse(132, 40, 26, 12, -25, "#5BC95B", width=5)
        p.ellipse(72, 92, 12, 18, mix(c, "#FFFFFF", 0.55), outline=None)
    elif kind == "star":
        c = color(col, "#FFD93D")
        pts = []
        for i in range(10):
            r = 92 if i % 2 == 0 else 40
            a = math.radians(-90 + i * 36)
            pts.append((100 + r * math.cos(a), 108 + r * math.sin(a)))
        p.poly(pts, c, width=7)
        p.ellipse(84, 108, 7, 10, INK, outline=None)
        p.ellipse(116, 108, 7, 10, INK, outline=None)
        p.arc(100, 120, 12, 9, 20, 160, INK, 5)
    elif kind == "ball":
        c = color(col, "#4D96FF")
        p.ellipse(100, 100, 86, 86, c)
        p.rot_ellipse(100, 100, 84, 26, -30, "#FFFFFF", outline=None)
        p.ellipse(100, 100, 86, 86, None)
        p.ellipse(64, 70, 10, 14, mix(c, "#FFFFFF", 0.5), outline=None)
    elif kind == "heart":
        c = color(col, "#FF5A8A")
        pts = []
        for i in range(80):
            t = 2 * math.pi * i / 80
            x = 16 * math.sin(t) ** 3
            y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
            pts.append((100 + x * 5.2, 96 + y * 5.2))
        p.poly(pts, c, width=7)
        p.ellipse(68, 70, 10, 14, mix(c, "#FFFFFF", 0.55), outline=None)
    elif kind == "balloon":
        c = color(col, "#FF5A5F")
        p.line([(100, 150), (92, 170), (108, 185), (100, 198)], INK, 4)
        p.poly([(90, 152), (110, 152), (100, 138)], c, width=4)
        p.ellipse(100, 78, 60, 72, c)
        p.ellipse(78, 50, 12, 20, mix(c, "#FFFFFF", 0.55), outline=None)
    elif kind == "flower":
        c = color(col, "#FF8FC7")
        p.line([(100, 120), (100, 196)], "#3E9B45", 10)
        for i in range(6):
            a = math.radians(i * 60)
            p.ellipse(100 + 42 * math.cos(a), 82 + 42 * math.sin(a), 30, 30, c)
        p.ellipse(100, 82, 28, 28, "#FFD93D")
    elif kind == "fish":
        c = color(col, "#FF9F1C")
        p.poly([(40, 100), (8, 64), (8, 136)], c, width=6)
        p.ellipse(108, 100, 72, 50, c)
        p.ellipse(140, 90, 9, 9, INK, outline=None)
        p.arc(100, 100, 22, 30, 300, 60, INK, 5)
    elif kind == "circle":
        p.ellipse(100, 100, 82, 82, color(col, "#4D96FF"), width=8)
    elif kind == "square":
        p.rrect(22, 22, 178, 178, 14, color(col, "#5BC95B"), width=8)
    elif kind == "triangle":
        p.poly([(100, 18), (184, 176), (16, 176)], color(col, "#FFD93D"), width=8)
    elif kind == "carrot":
        c = color(col, "#FF9F1C")
        for dx, ang in ((-14, -20), (0, 0), (14, 20)):
            p.rot_ellipse(100 + dx, 40, 10, 30, ang, "#5BC95B", width=5)
        p.poly([(64, 70), (136, 70), (104, 194), (96, 194)], c, width=7)
        for y in (100, 130, 160):
            p.line([(84 + (y - 100) * 0.12, y), (98, y + 4)], INK, 4)
    elif kind == "car":
        c = color(col, "#FF5A5F")
        p.rrect(48, 60, 152, 112, 26, "#BDE3FF")
        p.rrect(14, 92, 186, 152, 24, c)
        p.ellipse(56, 154, 24, 24, "#555555")
        p.ellipse(144, 154, 24, 24, "#555555")
        p.ellipse(56, 154, 9, 9, "#DDDDDD", outline=None)
        p.ellipse(144, 154, 9, 9, "#DDDDDD", outline=None)
    else:
        return draw_item("star", col, px)
    return p.result()


def draw_panel(w, h, fill="#FFFFFF", border=INK, radius=48, shadow=True):
    pad = 18
    img = Image.new("RGBA", (int(w) + pad * 2, int(h) + pad * 2), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 12, pad + w, pad + h + 12), radius=radius,
                                              fill=(40, 30, 70, 90))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
    p = Pen(w + pad * 2, h + pad * 2, 1.0)
    p.rrect(pad, pad, pad + w, pad + h, radius, fill, border, width=8)
    img.alpha_composite(p.result())
    return img


# --------------------------------------------------------------------------- backgrounds

def _vgrad(d, w, h, top, bottom, y0=0, y1=None):
    y1 = h if y1 is None else y1
    a, b = rgba(top), rgba(bottom)
    for y in range(int(y0), int(y1)):
        t = (y - y0) / max(1, (y1 - y0 - 1))
        d.line([(0, y), (w, y)], fill=tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))


def draw_background(kind, W, H, ground_y, seed=1):
    """Return an RGB background. ground_y = where the characters' feet stand."""
    rnd = random.Random(seed)
    w, h = W * SS, H * SS
    g = ground_y * SS
    horizon = g - 0.16 * H * SS
    img = Image.new("RGB", (w, h), "#FFFFFF")
    d = ImageDraw.Draw(img)
    U = min(W, H) / 1080 * SS  # unit scale

    def hills(colors, base, amp):
        for k, col in enumerate(colors):
            pts = [(0, h)]
            ph = rnd.random() * 6
            for x in range(0, w + 40, 40):
                y = base - amp * (0.6 + 0.4 * k) * (0.5 + 0.5 * math.sin(x / (w / (2.2 + k)) + ph))
                pts.append((x, y + k * 40 * U))
            pts.append((w, h))
            d.polygon(pts, fill=col)

    if kind in ("meadow", "park", "ทุ่งหญ้า"):
        _vgrad(d, w, h, "#79C8FF", "#D9F4FF", 0, horizon + 200 * U)
        d.ellipse((w - 330 * U, 90 * U, w - 110 * U, 310 * U), fill="#FFE066")
        hills(["#A6DD84", "#8ED073"], horizon + 60 * U, 120 * U)
        d.rectangle((0, horizon + 70 * U, w, h), fill="#7CC864")
        _vgrad(d, w, h, "#7CC864", "#5DB24E", horizon + 70 * U, h)
        for _ in range(int(60 * W / 1080)):
            x, y = rnd.uniform(0, w), rnd.uniform(horizon + 120 * U, h)
            c = rnd.choice(["#FFFFFF", "#FFD93D", "#FF8FC7", "#FF9F1C"])
            r = rnd.uniform(6, 11) * U
            for i in range(5):
                a = i * 2 * math.pi / 5
                d.ellipse((x + math.cos(a) * r - r * 0.8, y + math.sin(a) * r - r * 0.8,
                           x + math.cos(a) * r + r * 0.8, y + math.sin(a) * r + r * 0.8), fill=c)
            d.ellipse((x - r * 0.6, y - r * 0.6, x + r * 0.6, y + r * 0.6), fill="#FFE066")
        # a tree on the left
        tx = 90 * U
        d.rectangle((tx - 22 * U, horizon - 40 * U, tx + 22 * U, horizon + 140 * U), fill="#9C6B43")
        for dx, dy, r in ((0, -140, 120), (-80, -60, 90), (80, -70, 95)):
            d.ellipse((tx + (dx - r) * U, horizon + (dy - r) * U, tx + (dx + r) * U, horizon + (dy + r) * U),
                      fill="#4FAE52")
    elif kind in ("beach", "ทะเล", "ชายหาด"):
        _vgrad(d, w, h, "#6CC5FF", "#DDF5FF", 0, horizon + 200 * U)
        d.ellipse((w - 320 * U, 100 * U, w - 120 * U, 300 * U), fill="#FFE066")
        _vgrad(d, w, h, "#3DB4E6", "#8FDCF5", horizon, horizon + 170 * U)
        for k in range(4):
            yy = horizon + (30 + k * 38) * U
            for x in range(-40, w, int(120 * U)):
                d.arc((x, yy - 10 * U, x + 120 * U, yy + 14 * U), 200, 340, fill="#FFFFFF", width=int(5 * U))
        d.rectangle((0, horizon + 170 * U, w, h), fill="#F6D9A6")
        _vgrad(d, w, h, "#F6D9A6", "#EBC385", horizon + 170 * U, h)
        for _ in range(int(25 * W / 1080)):
            x, y = rnd.uniform(0, w), rnd.uniform(horizon + 220 * U, h)
            d.ellipse((x - 9 * U, y - 6 * U, x + 9 * U, y + 6 * U), fill="#FFF3DD")
    elif kind in ("night", "กลางคืน"):
        _vgrad(d, w, h, "#1E2257", "#4B4E92", 0, horizon + 200 * U)
        for _ in range(int(140 * W / 1080)):
            x, y = rnd.uniform(0, w), rnd.uniform(0, horizon - 40 * U)
            r = rnd.uniform(2, 5) * U
            d.ellipse((x - r, y - r, x + r, y + r), fill="#FFF7C2")
        mx, my = w - 260 * U, 230 * U
        d.ellipse((mx - 110 * U, my - 110 * U, mx + 110 * U, my + 110 * U), fill="#FFF3B0")
        d.ellipse((mx - 50 * U, my - 140 * U, mx + 170 * U, my + 80 * U), fill="#2A2E6A")
        hills(["#2F5E66", "#284F55"], horizon + 60 * U, 110 * U)
        d.rectangle((0, horizon + 70 * U, w, h), fill="#2E5A4C")
        _vgrad(d, w, h, "#2E5A4C", "#23463B", horizon + 70 * U, h)
    elif kind in ("bedroom", "room", "ห้องนอน"):
        _vgrad(d, w, h, "#FFE9D9", "#FFDCC6", 0, horizon + 80 * U)
        for y in range(0, int(horizon + 80 * U), int(70 * U)):
            for x in range(int((y // int(70 * U)) % 2 * 35 * U), w, int(70 * U)):
                d.ellipse((x - 5 * U, y - 5 * U, x + 5 * U, y + 5 * U), fill="#FFC9B0")
        wx0, wy0 = w * 0.62, 130 * U
        d.rounded_rectangle((wx0, wy0, wx0 + 300 * U, wy0 + 330 * U), radius=20 * U, fill="#9AD8FF",
                            outline="#9C6B43", width=int(16 * U))
        d.line([(wx0 + 150 * U, wy0), (wx0 + 150 * U, wy0 + 330 * U)], fill="#9C6B43", width=int(12 * U))
        d.line([(wx0, wy0 + 165 * U), (wx0 + 300 * U, wy0 + 165 * U)], fill="#9C6B43", width=int(12 * U))
        floor = horizon + 80 * U
        d.rectangle((0, floor, w, h), fill="#E3B285")
        for x in range(0, w, int(140 * U)):
            d.line([(x, floor), (x, h)], fill="#D19E70", width=int(4 * U))
        d.ellipse((w * 0.12, g - 40 * U, w * 0.88, g + 110 * U), fill="#FFB3C6")
        d.ellipse((w * 0.18, g - 20 * U, w * 0.82, g + 90 * U), fill="#FFC9D6")
        # shelf with toys
        sx = 60 * U
        d.rectangle((sx, 260 * U, sx + 260 * U, 280 * U), fill="#9C6B43")
        d.rectangle((sx + 30 * U, 200 * U, sx + 90 * U, 260 * U), fill="#4D96FF")
        d.ellipse((sx + 120 * U, 205 * U, sx + 175 * U, 260 * U), fill="#FF5A5F")
        d.polygon([(sx + 200 * U, 260 * U), (sx + 230 * U, 200 * U), (sx + 255 * U, 260 * U)], fill="#FFD93D")
    elif kind in ("classroom", "school", "ห้องเรียน"):
        _vgrad(d, w, h, "#FFF4D6", "#FFEBC0", 0, horizon + 80 * U)
        floor = horizon + 80 * U
        d.rectangle((0, floor, w, h), fill="#C9A27A")
        for y in range(int(floor), h, int(60 * U)):
            d.line([(0, y), (w, y)], fill="#B98F66", width=int(3 * U))
        # bunting
        for i, x in enumerate(range(0, w, int(90 * U))):
            col = ["#FF5A5F", "#FFD93D", "#5BC95B", "#4D96FF", "#9B6CFF"][i % 5]
            d.polygon([(x, 40 * U), (x + 80 * U, 40 * U), (x + 40 * U, 110 * U)], fill=col)
        d.line([(0, 40 * U), (w, 40 * U)], fill="#9C6B43", width=int(5 * U))
        # alphabet blocks
        for i, (lt, col) in enumerate((("ก", "#FF5A5F"), ("ข", "#4D96FF"), ("ค", "#5BC95B"))):
            bx = w - (130 + i * 95) * U
            d.rounded_rectangle((bx, floor - 90 * U, bx + 85 * U, floor - 5 * U), radius=10 * U, fill=col)
    else:  # plain soft gradient
        _vgrad(d, w, h, "#BDE7FF", "#FFF0F6")
        d.rectangle((0, horizon + 80 * U, w, h), fill="#FFE3EC")
    return img.resize((W, H), Image.LANCZOS)


BACKGROUNDS = ["meadow", "beach", "night", "bedroom", "classroom"]
OUTDOOR = {"meadow", "park", "beach", "ทุ่งหญ้า", "ทะเล", "ชายหาด"}


def draw_cloud(px):
    p = Pen(300, 150, px / 300)
    for cx, cy, r in ((90, 95, 50), (150, 70, 62), (215, 95, 48), (150, 105, 45)):
        p.ellipse(cx, cy, r, r, "#FFFFFF", outline=None)
    return p.result()
