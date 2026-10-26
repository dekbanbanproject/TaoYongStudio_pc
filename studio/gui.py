"""TaoYongStudio desktop window (Tkinter, ships with Python on Windows).

Start with:  TaoYongStudio.bat   (or: .venv\\Scripts\\pythonw -m studio.gui)
"""
import ctypes
import datetime as dt
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, simpledialog, ttk

from PIL import Image, ImageDraw, ImageTk

from . import config as cfgmod
from . import script as scriptmod
from .config import ROOT

IS_WIN = os.name == "nt"
NOWIN = {"creationflags": 0x08000000} if IS_WIN else {}
TASK_NAME = "KidsStudio Daily Batch"

# palette
BG = "#F6F3FF"
CARD = "#FFFFFF"
INK = "#2B1D4A"
MUTED = "#6E6487"
ACCENT = "#7B5CFF"
ACCENT_D = "#5B3FE0"
GOOD = "#2E9E5B"
WARN = "#D9822B"
BAD = "#D64545"
LINE = "#E4DEF5"

CHAR_NAMES = {"narrator": "ผู้บรรยาย", "bunny": "ปุยฝ้าย (กระต่าย)", "bear": "โกโก้ (หมี)",
              "chick": "เจี๊ยบ (ลูกไก่)", "cat": "มิวมิว (แมว)",
              "khao_hom": "น้องข้าวหอม (เด็กหญิง)", "ton_kla": "น้องต้นกล้า (เด็กชาย)"}
VOICE_CHOICES = ["th-TH-PremwadeeNeural", "th-TH-NiwatNeural"]
STATUS_TH = {"ready_for_approval": "รอตรวจ", "approved": "อนุมัติแล้ว", "posted": "โพสต์แล้ว",
             "rejected": "ไม่ใช้"}
WORKSPACES = (("tiktok", "TikTok", "vertical"), ("youtube", "YouTube", "vertical"),
              ("shopee", "Shopee", "vertical"), ("facebook_profile", "Facebook Profile", "vertical"),
              ("facebook_page", "Facebook Page", "vertical"))


def pick_font():
    if IS_WIN:
        return "Leelawadee UI"
    return "Loma"


def _get_real_ffplay():
    """Resolve direct ffplay.exe binary, bypassing scoop console shims if present."""
    p = shutil.which("ffplay")
    if p and "scoop\\shims" in p.lower():
        try:
            apps_dir = Path(p).parent.parent / "apps" / "ffmpeg"
            if apps_dir.exists():
                candidates = sorted(list(apps_dir.glob("*/bin/ffplay.exe")), reverse=True)
                if candidates:
                    return str(candidates[0])
        except Exception:
            pass
    return p


def open_path(p):
    p = str(p)
    if IS_WIN:
        os.startfile(p)  # noqa
    elif sys.platform == "darwin":
        subprocess.Popen(["open", p])
    else:
        subprocess.Popen(["xdg-open", p])


def python_exe(windowed=False):
    exe = Path(sys.executable)
    if IS_WIN and exe.name.lower() == "pythonw.exe" and not windowed:
        alt = exe.with_name("python.exe")
        if alt.exists():
            return str(alt)
    return str(exe)


class SideTabBar(tk.Frame):
    """Vertical modern sidebar navigation with strictly left-aligned icons and labels."""
    def __init__(self, parent, font_family="Leelawadee UI"):
        super().__init__(parent, bg="#F0ECFD", width=180)
        self.font_family = font_family
        self.notebook = None
        self.tabs = {}
        self._pill_cache = {}

        # Container for vertical tab buttons
        self.bar = tk.Frame(self, bg="#F0ECFD")
        self.bar.pack(side="top", fill="x", pady=(2, 6))

        # Bottom container for Temple image & version info
        self.bot_frame = tk.Frame(self, bg="#F0ECFD")
        self.bot_frame.pack(side="bottom", fill="x", pady=(6, 2))
        try:
            self._temple_img = ImageTk.PhotoImage(Image.open(ROOT / "studio" / "asset_side_temple_round.png").resize((136, 160)))
            tk.Label(self.bot_frame, image=self._temple_img, bg="#F0ECFD").pack(anchor="center", pady=(0, 4))
        except Exception:
            pass

        v_lbl = tk.Label(self.bot_frame, text="TaoYongStudio v1.0.0\nAI Cartoon Video Production\nfor Thai Kids",
                         bg="#F0ECFD", fg="#9C95BA", font=(self.font_family, 7), justify="center")
        v_lbl.pack(anchor="center")

    def _get_pill(self, w, h, r, fill_color):
        key = (w, h, r, fill_color)
        if key in self._pill_cache:
            return self._pill_cache[key]
        scale = 3
        img = Image.new("RGBA", (w * scale, h * scale), (240, 236, 253, 0))
        draw = ImageDraw.Draw(img)
        rect = [0, 0, w * scale - 1, h * scale - 1]
        draw.rounded_rectangle(rect, radius=r * scale, fill=fill_color)
        img = img.resize((w, h), Image.Resampling.LANCZOS)
        tk_img = ImageTk.PhotoImage(img)
        self._pill_cache[key] = tk_img
        return tk_img

    def setup_tabs(self, notebook, tabs_def):
        self.notebook = notebook
        tab_w = 172
        tab_h = 36
        radius = 8

        img_norm = self._get_pill(tab_w, tab_h, radius, "#F0ECFD")
        img_hover = self._get_pill(tab_w, tab_h, radius, "#E6DFFD")
        img_active = self._get_pill(tab_w, tab_h, radius, "#8E6CF7")

        emoji_font = "Segoe UI Emoji" if IS_WIN else self.font_family

        for frame, name, icon in tabs_def:
            cv = tk.Canvas(
                self.bar,
                width=tab_w,
                height=tab_h,
                bg="#F0ECFD",
                highlightthickness=0,
                bd=0,
                cursor="hand2"
            )
            cv.pack(side="top", pady=2, padx=4)

            bg_id = cv.create_image(tab_w // 2, tab_h // 2, image=img_norm)
            icon_id = cv.create_text(
                22, tab_h // 2,
                text=icon,
                font=(emoji_font, 11),
                fill="#473F68",
                anchor="center"
            )
            text_id = cv.create_text(
                40, tab_h // 2,
                text=name,
                font=(self.font_family, 10),
                fill="#473F68",
                anchor="w"
            )

            info = {
                "frame": frame,
                "canvas": cv,
                "label": cv,
                "bg_id": bg_id,
                "icon_id": icon_id,
                "text_id": text_id,
                "name": name,
                "img_norm": img_norm,
                "img_hover": img_hover,
                "img_active": img_active,
                "is_active": False
            }

            select_cmd = lambda e, f=frame: self.notebook.select(f)
            cv.bind("<Button-1>", select_cmd)
            cv.tag_bind("all", "<Button-1>", select_cmd)
            cv.bind("<Enter>", lambda e, i=info: self._on_enter(i))
            cv.bind("<Leave>", lambda e, i=info: self._on_leave(i))

            self.tabs[str(frame)] = info

        self.sync_selection()

    def _on_enter(self, info):
        if not info["is_active"]:
            cv = info["canvas"]
            cv.itemconfigure(info["bg_id"], image=info["img_hover"])
            cv.itemconfigure(info["icon_id"], fill="#7C5CEF")
            cv.itemconfigure(info["text_id"], fill="#7C5CEF")

    def _on_leave(self, info):
        if not info["is_active"]:
            cv = info["canvas"]
            cv.itemconfigure(info["bg_id"], image=info["img_norm"])
            cv.itemconfigure(info["icon_id"], fill="#473F68")
            cv.itemconfigure(info["text_id"], fill="#473F68")

    def sync_selection(self):
        if not self.notebook:
            return
        current = self.notebook.select()
        for f_id, info in self.tabs.items():
            cv = info["canvas"]
            if f_id == current:
                info["is_active"] = True
                cv.itemconfigure(info["bg_id"], image=info["img_active"])
                cv.itemconfigure(info["icon_id"], fill="#FFFFFF")
                cv.itemconfigure(info["text_id"], fill="#FFFFFF", font=(self.font_family, 10, "bold"))
            else:
                info["is_active"] = False
                cv.itemconfigure(info["bg_id"], image=info["img_norm"])
                cv.itemconfigure(info["icon_id"], fill="#473F68")
                cv.itemconfigure(info["text_id"], fill="#473F68", font=(self.font_family, 10, "normal"))


WebTabBar = SideTabBar


class ModernProgressBar(tk.Canvas):
    """Custom pastel rounded progress bar that works consistently across all OS/themes."""
    def __init__(self, parent, height=14, bg_color="#ECE7FB", fill_color="#8E6CF7", border_color="#D8CEF8", **kwargs):
        bg = parent.cget("bg") if hasattr(parent, "cget") else "#FFFFFF"
        super().__init__(parent, height=height, bg=bg, highlightthickness=0, **kwargs)
        self.height = height
        self.bg_color = bg_color
        self.fill_color = fill_color
        self.border_color = border_color
        self._val = 0.0
        self.bind("<Configure>", self._draw)

    def set(self, val):
        self._val = max(0.0, min(100.0, float(val)))
        self._draw()

    def configure(self, **kwargs):
        if "value" in kwargs:
            self.set(kwargs.pop("value"))
        super().configure(**kwargs)

    config = configure

    def _draw(self, event=None):
        self.delete("all")
        w = self.winfo_width()
        h = self.height
        if w <= 1:
            return
        r = h // 2
        self.create_rounded_rect(1, 1, w - 2, h - 2, r, fill=self.bg_color, outline=self.border_color)
        fill_w = (w - 2) * (self._val / 100.0)
        if fill_w > 4:
            self.create_rounded_rect(1, 1, fill_w, h - 2, r, fill=self.fill_color, outline="")

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2, x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
        return self.create_polygon(points, smooth=True, **kwargs)


class RoundedButton(tk.Canvas):
    """
    Modern Anti-Aliased Rounded Button for Tkinter.
    Provides smooth corner radius on all 4 corners, customizable border,
    dynamic resizing, and seamless parent background blending.
    """
    _img_cache = {}

    def __init__(self, parent, text="", command=None, bg="#8E6CF7", fg="#FFFFFF",
                 hover_bg=None, activebackground=None, activeforeground=None,
                 border=None, bd=0, relief="flat", radius=8, font=None,
                 padx=10, pady=5, height=None, width=None, parent_bg=None,
                 cursor="hand2", state="normal", image=None, compound="left", **kwargs):
        self.parent = parent
        self.text = text or ""
        self.command = command
        self.radius = radius
        self.padx = padx
        self.pady = pady
        self.fixed_width = width
        self.fixed_height = height
        self._state = state
        self.cursor_style = cursor
        self.btn_image = image
        self.compound = compound

        for k in ['activebackground', 'activeforeground', 'bd', 'relief', 'style', 'compound',
                  'anchor', 'justify', 'wraplength', 'highlightthickness', 'highlightbackground',
                  'highlightcolor', 'takefocus', 'default', 'overrelief', 'underline',
                  'repeatdelay', 'repeatinterval']:
            kwargs.pop(k, None)

        if parent_bg is None:
            p = parent
            detected = None
            while p is not None:
                try:
                    detected = p.cget("bg")
                    if detected and str(detected).startswith("#"):
                        break
                except Exception:
                    pass
                p = getattr(p, "master", None)
            self.parent_bg = detected if detected else "#FFFFFF"
        else:
            self.parent_bg = parent_bg

        self.bg_color = bg or "#8E6CF7"
        self.fg_color = fg or "#FFFFFF"

        if border:
            self.border_color = border
            self.border_width = bd if bd > 0 else 1
        elif bd > 0 or relief == "solid":
            self.border_color = self._calc_border(self.bg_color, self.fg_color)
            self.border_width = bd if bd > 0 else 1
        else:
            self.border_color = None
            self.border_width = 0

        self.hover_bg = hover_bg or activebackground or self._calc_hover(self.bg_color)
        self.hover_fg = activeforeground or self.fg_color

        self.btn_font = font or ("Segoe UI", 9, "bold")
        self.is_hover = False
        self.is_pressed = False

        try:
            import tkinter.font as tkfont
            f = tkfont.Font(font=self.btn_font)
            tw = f.measure(self.text)
            th = f.metrics("linespace")
        except Exception:
            tw = len(self.text) * 8
            th = 16

        iw = self.btn_image.width() if hasattr(self.btn_image, "width") else 0
        ih = self.btn_image.height() if hasattr(self.btn_image, "height") else 0
        spacing = 6 if (tw and iw) else 0
        nat_w = width if width else (tw + iw + spacing + padx * 2)
        nat_h = height if height else max(26, max(th, ih) + pady * 2)
        self.calc_w = nat_w
        self.calc_h = nat_h

        super().__init__(parent, width=nat_w, height=nat_h, bg=self.parent_bg,
                         highlightthickness=0, bd=0, cursor=cursor if state != "disabled" else "arrow", **kwargs)

        self.bind("<Configure>", self._on_resize)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._redraw()

    @staticmethod
    def _calc_border(bg, fg):
        if not bg or not bg.startswith("#") or len(bg) != 7:
            return "#D8CEF8"
        try:
            r = int(bg[1:3], 16)
            g = int(bg[3:5], 16)
            b = int(bg[5:7], 16)
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            if lum > 200:
                nr = max(0, int(r * 0.88))
                ng = max(0, int(g * 0.88))
                nb = max(0, int(b * 0.88))
                return f"#{nr:02x}{ng:02x}{nb:02x}"
            else:
                return bg
        except Exception:
            return "#D8CEF8"

    @staticmethod
    def _calc_hover(hex_color):
        if not hex_color or not hex_color.startswith("#") or len(hex_color) != 7:
            return hex_color
        try:
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            delta = -18 if lum > 150 else 18
            nr = max(0, min(255, r + delta))
            ng = max(0, min(255, g + delta))
            nb = max(0, min(255, b + delta))
            return f"#{nr:02x}{ng:02x}{nb:02x}"
        except Exception:
            return hex_color

    def _render_bg(self, w, h, fill, border, bw, r, pbg):
        key = (w, h, fill, border, bw, r, pbg)
        if key in self._img_cache:
            return self._img_cache[key]
        scale = 3
        sw, sh = max(1, w * scale), max(1, h * scale)
        sr = min(r * scale, sw // 2, sh // 2)
        im = Image.new("RGBA", (sw, sh), pbg)
        draw = ImageDraw.Draw(im)
        inset = (bw * scale) // 2 if bw else 0
        draw.rounded_rectangle([inset, inset, sw - 1 - inset, sh - 1 - inset],
                               radius=sr, fill=fill, outline=border, width=bw * scale if bw else 0)
        im = im.resize((w, h), Image.LANCZOS)
        photo = ImageTk.PhotoImage(im)
        self._img_cache[key] = photo
        return photo

    def _redraw(self):
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 4:
            w = self.calc_w
        if h <= 4:
            h = self.calc_h

        self.delete("all")
        if self._state == "disabled":
            fill = "#F3F4F6"
            fg = "#9CA3AF"
            border = "#E5E7EB"
            bw = 1
        else:
            fill = self.hover_bg if self.is_hover else self.bg_color
            fg = self.hover_fg if self.is_hover else self.fg_color
            border = self.border_color
            bw = self.border_width

        try:
            self._photo = self._render_bg(w, h, fill, border, bw, self.radius, self.parent_bg)
            self.create_image(w // 2, h // 2, image=self._photo)
            offset = 1 if self.is_pressed else 0
            if self.btn_image:
                if not self.text:
                    self.create_image(w // 2, (h // 2) + offset, image=self.btn_image)
                else:
                    iw = self.btn_image.width() if hasattr(self.btn_image, "width") else 16
                    self.create_image(self.padx + (iw // 2), (h // 2) + offset, image=self.btn_image)
                    self.create_text(self.padx + iw + 6, (h // 2) + offset, text=self.text, font=self.btn_font, fill=fg, anchor="w")
            else:
                self.create_text(w // 2, (h // 2) + offset, text=self.text, font=self.btn_font, fill=fg)
        except Exception:
            pass

    def _on_resize(self, e):
        self._redraw()

    def _on_enter(self, e):
        if self._state == "normal":
            self.is_hover = True
            self._redraw()

    def _on_leave(self, e):
        self.is_hover = False
        self.is_pressed = False
        self._redraw()

    def _on_press(self, e):
        if self._state == "normal":
            self.is_pressed = True
            self._redraw()

    def _on_release(self, e):
        if self._state == "normal":
            was_pressed = self.is_pressed
            self.is_pressed = False
            self._redraw()
            if was_pressed and self.command:
                self.command()

    def invoke(self):
        if self._state == "normal" and self.command:
            return self.command()

    def configure(self, **kwargs):
        if "font" in kwargs:
            self.btn_font = kwargs.pop("font")
        if "image" in kwargs:
            self.btn_image = kwargs.pop("image")
        if "radius" in kwargs:
            self.radius = kwargs.pop("radius")
        if "text" in kwargs:
            self.text = kwargs.pop("text")
            try:
                import tkinter.font as tkfont
                f = tkfont.Font(font=self.btn_font)
                tw = f.measure(self.text)
                th = f.metrics("linespace")
            except Exception:
                tw = len(self.text) * 8
                th = 16
            self.calc_w = self.fixed_width if self.fixed_width else (tw + self.padx * 2)
            self.calc_h = self.fixed_height if self.fixed_height else max(26, th + self.pady * 2)
            if not self.fixed_width:
                super().configure(width=self.calc_w)
            if not self.fixed_height:
                super().configure(height=self.calc_h)
        if "command" in kwargs:
            self.command = kwargs.pop("command")
        if "state" in kwargs:
            self._state = kwargs.pop("state")
            self.configure(cursor="hand2" if self._state == "normal" else "arrow")
        if "bg" in kwargs:
            self.bg_color = kwargs.pop("bg")
            self.hover_bg = self._calc_hover(self.bg_color)
            if self.border_width > 0 and not self.border_color:
                self.border_color = self._calc_border(self.bg_color, self.fg_color)
        if "fg" in kwargs:
            self.fg_color = kwargs.pop("fg")
        if "activebackground" in kwargs:
            self.hover_bg = kwargs.pop("activebackground")
        if "activeforeground" in kwargs:
            self.hover_fg = kwargs.pop("activeforeground")
        for k in ['bd', 'relief', 'style', 'compound', 'anchor', 'justify', 'wraplength',
                  'highlightthickness', 'highlightbackground', 'highlightcolor', 'takefocus',
                  'default', 'overrelief', 'underline', 'repeatdelay', 'repeatinterval',
                  'font', 'radius']:
            kwargs.pop(k, None)
        if kwargs:
            super().configure(**kwargs)
        self._redraw()

    config = configure

    def cget(self, key):
        if key == "text":
            return self.text
        if key == "state":
            return self._state
        if key == "bg":
            return self.bg_color
        if key == "fg":
            return self.fg_color
        return super().cget(key)

    def __getitem__(self, key):
        return self.cget(key)

    def __setitem__(self, key, value):
        self.configure(**{key: value})


class RoundedCard(tk.Canvas):
    """
    Modern Anti-Aliased Rounded Card Container for Tkinter.
    Draws a 3x supersampled anti-aliased rounded rectangle with customizable
    corner radius, background color, and border.
    Embeds an inner tk.Frame for packing or gridding child widgets.
    Supports auto_height to automatically shrink/expand height according to inner content.
    """
    _card_cache = {}

    def __init__(self, parent, bg_color="#FFFFFF", border_color="#E8E2F8", border_width=1,
                 radius=16, parent_bg=None, padx=16, pady=14, auto_height=True, **kwargs):
        self.parent = parent
        self.bg_color = bg_color
        self.border_color = border_color
        self.border_width = border_width
        self.radius = radius
        self.pad_x = padx
        self.pad_y = pady
        self.auto_height = auto_height

        if parent_bg:
            self.parent_bg = parent_bg
        else:
            p = parent
            detected = None
            while p is not None:
                try:
                    detected = p.cget("bg")
                    if detected and str(detected).startswith("#"):
                        break
                except Exception:
                    pass
                p = getattr(p, "master", None)
            self.parent_bg = detected if detected else "#F0ECFD"

        for k in ['bd', 'relief', 'highlightthickness', 'highlightbackground']:
            kwargs.pop(k, None)

        super().__init__(parent, bg=self.parent_bg, highlightthickness=0, bd=0, **kwargs)

        self.inner = tk.Frame(self, bg=bg_color)
        self.win_id = self.create_window(padx, pady, window=self.inner, anchor="nw")

        self.bind("<Configure>", self._on_canvas_resize)
        if self.auto_height:
            self.inner.bind("<Configure>", self._on_inner_resize)

    def _render_card_bg(self, w, h, fill, border, bw, r, pbg):
        key = (w, h, fill, border, bw, r, pbg)
        if key in self._card_cache:
            return self._card_cache[key]
        scale = 3
        sw, sh = max(1, w * scale), max(1, h * scale)
        sr = min(r * scale, sw // 2, sh // 2)
        im = Image.new("RGBA", (sw, sh), pbg)
        draw = ImageDraw.Draw(im)
        inset = (bw * scale) // 2 if bw else 0
        draw.rounded_rectangle([inset, inset, sw - 1 - inset, sh - 1 - inset],
                               radius=sr, fill=fill, outline=border, width=bw * scale if bw else 0)
        im = im.resize((w, h), Image.LANCZOS)
        photo = ImageTk.PhotoImage(im)
        self._card_cache[key] = photo
        return photo

    def _on_inner_resize(self, event=None):
        if not self.auto_height:
            return
        req_h = self.inner.winfo_reqheight() + self.pad_y * 2
        cur_h = self.winfo_height()
        if cur_h <= 1 or abs(cur_h - req_h) >= 2:
            self.configure(height=req_h)

    def _on_canvas_resize(self, event):
        w = event.width
        h = event.height
        if w <= 4 or h <= 4:
            return
        self.delete("card_bg")
        self._photo = self._render_card_bg(w, h, self.bg_color, self.border_color,
                                           self.border_width, self.radius, self.parent_bg)
        self.create_image(w // 2, h // 2, image=self._photo, tags="card_bg")
        self.tag_lower("card_bg")
        inner_w = max(1, w - self.pad_x * 2)
        if not self.auto_height:
            inner_h = max(1, h - self.pad_y * 2)
            self.itemconfigure(self.win_id, width=inner_w, height=inner_h)
        else:
            self.itemconfigure(self.win_id, width=inner_w)


# Globally apply RoundedButton to all buttons across TaoYongStudio
_OriginalTkButton = tk.Button
_OriginalTtkButton = ttk.Button
tk.Button = RoundedButton
ttk.Button = RoundedButton


class StudioApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TaoYongStudio - สตูดิโอการ์ตูนเด็ก")
        self.geometry("1480x880")
        self.minsize(1100, 700)
        if IS_WIN:
            try:
                self.state("zoomed")  # open maximised like a normal desktop program
            except tk.TclError:
                pass
        self.configure(bg=BG)
        self.F = pick_font()
        self.cfg = cfgmod.load()
        self.proc = None
        self.q = queue.Queue()
        self._img_refs = []
        self._set_icon()
        self._styles()
        self._build()
        self.after(150, self._poll)
        self._last_worker_minute = None
        self.after(5000, self._worker_heartbeat)
        self.protocol("WM_DELETE_WINDOW", self._on_app_close)
        self.refresh_all()

    def _on_app_close(self):
        self._stop_clip_player()
        self.destroy()

    # ------------------------------------------------------------------ look
    def _set_icon(self):
        ico = ROOT / "studio" / "app.ico"
        png = ROOT / "studio" / "tys_icon.png"
        if not png.exists():
            png = ROOT / "studio" / "app.png"
        try:
            if png.exists():
                img = Image.open(png)
                self._icon_photos = [
                    ImageTk.PhotoImage(img.resize((16, 16), Image.Resampling.LANCZOS)),
                    ImageTk.PhotoImage(img.resize((24, 24), Image.Resampling.LANCZOS)),
                    ImageTk.PhotoImage(img.resize((32, 32), Image.Resampling.LANCZOS)),
                    ImageTk.PhotoImage(img.resize((48, 48), Image.Resampling.LANCZOS)),
                    ImageTk.PhotoImage(img.resize((64, 64), Image.Resampling.LANCZOS)),
                    ImageTk.PhotoImage(img.resize((128, 128), Image.Resampling.LANCZOS)),
                ]
                self.iconphoto(True, *self._icon_photos)
            if IS_WIN and ico.exists():
                self.iconbitmap(str(ico))
                try:
                    import ctypes
                    WM_SETICON = 0x0080
                    ICON_SMALL = 0
                    ICON_BIG = 1
                    IMAGE_ICON = 1
                    LR_LOADFROMFILE = 0x00000010
                    h_sm = ctypes.windll.user32.LoadImageW(None, str(ico), IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
                    h_bg = ctypes.windll.user32.LoadImageW(None, str(ico), IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
                    hwnd = self.winfo_id()
                    p_hwnd = ctypes.windll.user32.GetParent(hwnd)
                    target = p_hwnd if p_hwnd else hwnd
                    if h_sm:
                        ctypes.windll.user32.SendMessageW(target, WM_SETICON, ICON_SMALL, h_sm)
                    if h_bg:
                        ctypes.windll.user32.SendMessageW(target, WM_SETICON, ICON_BIG, h_bg)
                except Exception:
                    pass
        except Exception:
            pass

    def _styles(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        F = self.F
        s.configure(".", font=(F, 10), background=BG, foreground=INK)
        s.configure("TFrame", background=BG)
        s.configure("Card.TFrame", background=CARD, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE, relief="flat", borderwidth=1)
        s.configure("TLabel", background=BG, foreground=INK)
        s.configure("Card.TLabel", background=CARD, foreground=INK)
        s.configure("Muted.TLabel", background=CARD, foreground=MUTED)
        s.configure("H1.TLabel", font=(F, 16, "bold"), background=BG, foreground=INK)
        s.configure("H2.TLabel", font=(F, 12, "bold"), background=CARD, foreground=INK)
        s.configure("Big.TLabel", font=(F, 26, "bold"), background=CARD, foreground=ACCENT)

        # Hidden notebook container (clean borderless)
        s.layout("Hidden.TNotebook", [("Notebook.client", {"sticky": "nswe"})])
        s.layout("Hidden.TNotebook.Tab", [])
        s.configure("Hidden.TNotebook", background=BG, borderwidth=0, relief="flat")
        s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(12, 6, 12, 0))
        s.configure("TNotebook.Tab", font=(F, 10), padding=(4, 7), background="#E9E3FF", foreground=INK,
                    borderwidth=0)
        s.map("TNotebook.Tab", background=[("selected", CARD)], foreground=[("selected", ACCENT_D)])

        # ==============================================================
        # 1. BUTTONS (Modern Web Style)
        # ==============================================================
        # Default / Secondary Button (White card, subtle border, smooth lavender hover)
        s.configure("TButton",
                    font=(F, 10, "bold"),
                    padding=(14, 7),
                    background="#FFFFFF",
                    foreground=INK,
                    bordercolor=LINE,
                    lightcolor="#FFFFFF",
                    darkcolor="#FFFFFF",
                    relief="flat",
                    borderwidth=1,
                    focusthickness=0)
        s.map("TButton",
              background=[("disabled", "#F5F3FA"), ("pressed", "#E8E0FF"), ("active", "#F4F0FF")],
              bordercolor=[("disabled", "#E8E4F2"), ("pressed", ACCENT_D), ("active", ACCENT)],
              lightcolor=[("active", "#F4F0FF"), ("pressed", "#E8E0FF")],
              darkcolor=[("active", "#F4F0FF"), ("pressed", "#E8E0FF")],
              foreground=[("disabled", "#AAA3BF"), ("pressed", ACCENT_D), ("active", ACCENT_D)])

        # Accent / Primary Button (Vibrant modern purple, bold white text)
        s.configure("Accent.TButton",
                    font=(F, 11, "bold"),
                    padding=(18, 9),
                    background=ACCENT,
                    foreground="#FFFFFF",
                    bordercolor=ACCENT_D,
                    lightcolor=ACCENT,
                    darkcolor=ACCENT,
                    relief="flat",
                    borderwidth=1,
                    focusthickness=0)
        s.map("Accent.TButton",
              background=[("disabled", "#D1C7F8"), ("pressed", "#4930C2"), ("active", ACCENT_D)],
              bordercolor=[("disabled", "#C4B8F5"), ("pressed", "#39229D"), ("active", "#4930C2")],
              lightcolor=[("active", ACCENT_D), ("pressed", "#4930C2")],
              darkcolor=[("active", ACCENT_D), ("pressed", "#4930C2")],
              foreground=[("!disabled", "#FFFFFF")])

        # Danger Button (Soft red card, bright red text, hover pink)
        s.configure("Danger.TButton",
                    font=(F, 10, "bold"),
                    padding=(14, 7),
                    background="#FFF0F0",
                    foreground=BAD,
                    bordercolor="#F7C6C6",
                    lightcolor="#FFF0F0",
                    darkcolor="#FFF0F0",
                    relief="flat",
                    borderwidth=1,
                    focusthickness=0)
        s.map("Danger.TButton",
              background=[("disabled", "#F5F3FA"), ("pressed", "#F8B4B4"), ("active", "#FDE0E0")],
              bordercolor=[("disabled", "#E8E4F2"), ("pressed", "#AD2929"), ("active", BAD)],
              lightcolor=[("active", "#FDE0E0"), ("pressed", "#F8B4B4")],
              darkcolor=[("active", "#FDE0E0"), ("pressed", "#F8B4B4")],
              foreground=[("disabled", "#AAA3BF"), ("pressed", "#8F1E1E"), ("active", "#AD2929")])

        # Tag / Status Buttons
        for name, color, hover in (("Selected", ACCENT_D, "#4930C2"),
                                   ("Posted", GOOD, "#237D47"),
                                   ("Rejected", BAD, "#AD2929"),
                                   ("Draft", WARN, "#B56B20")):
            style = name + ".TButton"
            s.configure(style, background=color, foreground="#FFFFFF", font=(F, 10, "bold"),
                        bordercolor=color, lightcolor=color, darkcolor=color, relief="flat",
                        borderwidth=1, focusthickness=0, padding=(12, 6))
            s.map(style,
                  background=[("disabled", "#F2F0F7"), ("pressed", hover), ("active", hover)],
                  bordercolor=[("disabled", "#E8E4F2"), ("pressed", hover), ("active", hover)],
                  lightcolor=[("active", hover), ("pressed", hover)],
                  darkcolor=[("active", hover), ("pressed", hover)],
                  foreground=[("disabled", "#AAA3BF"), ("!disabled", "#FFFFFF")])

        # Platform Navigation Buttons
        s.configure("PlatformNav.TButton", font=(F, 11, "bold"), padding=(14, 10),
                    background="#FFFFFF", foreground=INK, bordercolor=LINE,
                    lightcolor="#FFFFFF", darkcolor="#FFFFFF", relief="flat", borderwidth=1)
        s.map("PlatformNav.TButton",
              background=[("pressed", "#E8E0FF"), ("active", "#F4F0FF")],
              bordercolor=[("pressed", ACCENT_D), ("active", ACCENT)],
              lightcolor=[("active", "#F4F0FF"), ("pressed", "#E8E0FF")],
              darkcolor=[("active", "#F4F0FF"), ("pressed", "#E8E0FF")],
              foreground=[("pressed", ACCENT_D), ("active", ACCENT_D)])
        s.configure("PlatformNavSelected.TButton", font=(F, 11, "bold"), padding=(14, 10),
                    background=ACCENT, foreground="#FFFFFF", bordercolor=ACCENT_D,
                    lightcolor=ACCENT, darkcolor=ACCENT, relief="flat", borderwidth=1)
        s.map("PlatformNavSelected.TButton",
              background=[("pressed", "#4930C2"), ("active", ACCENT_D)],
              bordercolor=[("pressed", "#39229D"), ("active", "#4930C2")],
              lightcolor=[("active", ACCENT_D), ("pressed", "#4930C2")],
              darkcolor=[("active", ACCENT_D), ("pressed", "#4930C2")],
              foreground=[("!disabled", "#FFFFFF")])

        # ==============================================================
        # 2. SELECTS / COMBOBOXES (Modern Web Dropdowns)
        # ==============================================================
        s.configure("TCombobox",
                    font=(F, 10),
                    padding=(10, 7),
                    background="#FFFFFF",
                    fieldbackground="#FFFFFF",
                    foreground=INK,
                    arrowcolor=ACCENT_D,
                    arrowsize=13,
                    bordercolor=LINE,
                    lightcolor="#FFFFFF",
                    darkcolor="#FFFFFF",
                    relief="flat",
                    borderwidth=1)
        s.map("TCombobox",
              fieldbackground=[("readonly", "#FFFFFF"), ("disabled", "#F5F3FA")],
              background=[("readonly", "#FFFFFF"), ("active", "#F4F0FF"), ("pressed", "#E8E0FF")],
              bordercolor=[("focus", ACCENT), ("active", ACCENT), ("hover", ACCENT), ("disabled", "#ECE7F6")],
              lightcolor=[("focus", ACCENT), ("active", ACCENT), ("hover", ACCENT)],
              darkcolor=[("focus", ACCENT), ("active", ACCENT), ("hover", ACCENT)],
              arrowcolor=[("active", ACCENT_D), ("focus", ACCENT), ("disabled", "#AAA3BF")])

        # Combobox Popdown Listbox Styling
        self.option_add("*TCombobox*Listbox.font", (F, 10))
        self.option_add("*TCombobox*Listbox.background", "#FFFFFF")
        self.option_add("*TCombobox*Listbox.foreground", INK)
        self.option_add("*TCombobox*Listbox.selectBackground", "#F0EBFF")
        self.option_add("*TCombobox*Listbox.selectForeground", ACCENT_D)
        self.option_add("*TCombobox*Listbox.relief", "flat")
        self.option_add("*TCombobox*Listbox.borderWidth", "0")
        self.option_add("*TCombobox*Listbox.highlightThickness", "1")
        self.option_add("*TCombobox*Listbox.highlightColor", ACCENT)
        self.option_add("*TCombobox*Listbox.highlightBackground", LINE)

        # ==============================================================
        # 3. INPUTS / ENTRIES (Modern Web Input Fields)
        # ==============================================================
        s.configure("TEntry",
                    font=(F, 10),
                    padding=(10, 7),
                    fieldbackground="#FFFFFF",
                    foreground=INK,
                    bordercolor=LINE,
                    lightcolor="#FFFFFF",
                    darkcolor="#FFFFFF",
                    relief="flat",
                    borderwidth=1)
        s.map("TEntry",
              fieldbackground=[("disabled", "#F5F3FA")],
              bordercolor=[("focus", ACCENT), ("active", ACCENT), ("hover", ACCENT_D), ("disabled", "#ECE7F6")],
              lightcolor=[("focus", ACCENT), ("active", ACCENT), ("hover", ACCENT_D)],
              darkcolor=[("focus", ACCENT), ("active", ACCENT), ("hover", ACCENT_D)])

        # Generic Text & Entry Widget Options
        self.option_add("*Text.background", "#FFFFFF")
        self.option_add("*Text.foreground", INK)
        self.option_add("*Text.relief", "flat")
        self.option_add("*Text.highlightThickness", "1")
        self.option_add("*Text.highlightColor", ACCENT)
        self.option_add("*Text.highlightBackground", LINE)
        self.option_add("*Text.padx", "8")
        self.option_add("*Text.pady", "6")

        self.option_add("*Entry.relief", "flat")
        self.option_add("*Entry.highlightThickness", "1")
        self.option_add("*Entry.highlightColor", ACCENT)
        self.option_add("*Entry.highlightBackground", LINE)

        # ==============================================================
        # 4. SPINBOXES (Modern Web Number Inputs)
        # ==============================================================
        s.configure("TSpinbox",
                    font=(F, 10),
                    padding=(6, 6),
                    fieldbackground="#FFFFFF",
                    background="#FFFFFF",
                    foreground=INK,
                    arrowcolor=ACCENT_D,
                    arrowsize=11,
                    bordercolor=LINE,
                    lightcolor="#FFFFFF",
                    darkcolor="#FFFFFF",
                    relief="flat",
                    borderwidth=1)
        s.map("TSpinbox",
              fieldbackground=[("disabled", "#F5F3FA")],
              background=[("active", "#F4F0FF")],
              bordercolor=[("focus", ACCENT), ("active", ACCENT), ("hover", ACCENT), ("disabled", "#ECE7F6")],
              lightcolor=[("focus", ACCENT), ("active", ACCENT), ("hover", ACCENT)],
              darkcolor=[("focus", ACCENT), ("active", ACCENT), ("hover", ACCENT)],
              arrowcolor=[("active", ACCENT_D), ("focus", ACCENT)])

        # ==============================================================
        # 5. CHECKBOXES & RADIO BUTTONS (Modern Web Checks)
        # ==============================================================
        s.configure("Card.TRadiobutton",
                    font=(F, 10),
                    background=CARD,
                    foreground=INK,
                    indicatorbackground="#FFFFFF",
                    indicatorforeground=ACCENT_D,
                    upperbordercolor=LINE,
                    lowerbordercolor=LINE,
                    padding=4)
        s.map("Card.TRadiobutton",
              indicatorbackground=[("selected", "#FFFFFF"), ("active", "#F4F0FF")],
              indicatorforeground=[("selected", ACCENT_D), ("active", ACCENT)],
              upperbordercolor=[("selected", ACCENT), ("active", ACCENT)],
              lowerbordercolor=[("selected", ACCENT), ("active", ACCENT)])

        s.configure("TRadiobutton",
                    font=(F, 10),
                    background=BG,
                    foreground=INK,
                    indicatorbackground="#FFFFFF",
                    indicatorforeground=ACCENT_D,
                    upperbordercolor=LINE,
                    lowerbordercolor=LINE,
                    padding=4)
        s.map("TRadiobutton",
              indicatorbackground=[("selected", "#FFFFFF"), ("active", "#F4F0FF")],
              indicatorforeground=[("selected", ACCENT_D), ("active", ACCENT)],
              upperbordercolor=[("selected", ACCENT), ("active", ACCENT)],
              lowerbordercolor=[("selected", ACCENT), ("active", ACCENT)])

        s.configure("TCheckbutton",
                    font=(F, 10),
                    background=CARD,
                    foreground=INK,
                    indicatorbackground="#FFFFFF",
                    indicatorforeground=ACCENT,
                    upperbordercolor=LINE,
                    lowerbordercolor=LINE,
                    padding=4)
        s.map("TCheckbutton",
              indicatorbackground=[("selected", ACCENT), ("active", "#F4F0FF")],
              indicatorforeground=[("selected", "#FFFFFF")],
              upperbordercolor=[("selected", ACCENT_D), ("active", ACCENT)],
              lowerbordercolor=[("selected", ACCENT_D), ("active", ACCENT)])

        # ==============================================================
        # 6. TREEVIEW / TABLES (Modern Clean Web Tables)
        # ==============================================================
        s.configure("Treeview", font=(F, 10), rowheight=32, background=CARD, fieldbackground=CARD,
                    bordercolor=LINE, borderwidth=1)
        s.configure("Treeview.Heading", font=(F, 10, "bold"), background="#F5F2FE", foreground=INK,
                    bordercolor=LINE, lightcolor="#F5F2FE", darkcolor="#F5F2FE", relief="flat",
                    borderwidth=1, padding=(8, 7))
        s.map("Treeview", background=[("selected", "#EDE7FF")], foreground=[("selected", ACCENT_D)])
        s.map("Treeview.Heading", background=[("active", "#EDE8FF")])

        # ==============================================================
        # 7. SCROLLBARS & PROGRESSBARS (Slim Modern Web Look)
        # ==============================================================
        s.configure("Vertical.TScrollbar", troughcolor="#F6F3FF", background="#DDD6F3",
                    bordercolor="#F6F3FF", lightcolor="#DDD6F3", darkcolor="#DDD6F3",
                    arrowcolor="#6E6487", width=12)
        s.map("Vertical.TScrollbar", background=[("active", ACCENT), ("pressed", ACCENT_D)])
        s.configure("Horizontal.TScrollbar", troughcolor="#F6F3FF", background="#DDD6F3",
                    bordercolor="#F6F3FF", lightcolor="#DDD6F3", darkcolor="#DDD6F3",
                    arrowcolor="#6E6487", width=12)
        s.map("Horizontal.TScrollbar", background=[("active", ACCENT), ("pressed", ACCENT_D)])

        s.configure("Horizontal.TProgressbar", troughcolor="#ECE7FB", background=ACCENT, thickness=8,
                    borderwidth=0)

        # Labels & Frames
        s.configure("TLabelframe", background=CARD, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE, borderwidth=1)
        s.configure("TLabelframe.Label", background=CARD, font=(F, 10, "bold"), foreground=INK)

        # ==============================================================
        # 8. HAND CURSOR FOR ALL CLICKABLE ELEMENTS
        # ==============================================================
        for cls in ("TButton", "TCombobox", "TCheckbutton", "TRadiobutton", "Treeview.Heading"):
            self.bind_class(cls, "<Enter>", lambda event: event.widget.configure(cursor="hand2"), add="+")
        self.bind_class("TButton", "<ButtonPress-1>", lambda event: event.widget.focus_set(), add="+")

    def card(self, parent, **pack):
        f = ttk.Frame(parent, bg="#FFFFFF", padding=16)
        if pack:
            f.pack(**pack)
        return f

    # ------------------------------------------------------------------ layout
    def _build(self):
        self.configure(bg="#F0ECFD")

        # Top Header Bar (Height ~ 68px, Background: #F0ECFD)
        head = tk.Frame(self, bg="#F0ECFD", height=68)
        head.pack(fill="x", padx=12, pady=(6, 4))

        # 1. Left side of header: Logo + Title + Subtitle
        logo_frame = tk.Frame(head, bg="#F0ECFD")
        logo_frame.pack(side="left")

        tys_icon_file = ROOT / "studio" / "tys_icon.png"
        icon_to_open = tys_icon_file if tys_icon_file.is_file() else (ROOT / "studio" / "asset_avatar_circle.png")
        try:
            self._head_avatar = ImageTk.PhotoImage(Image.open(icon_to_open).resize((46, 46), Image.Resampling.LANCZOS))
            logo_btn = tk.Label(logo_frame, image=self._head_avatar, bg="#F0ECFD", cursor="hand2")
            logo_btn.pack(side="left", padx=(4, 10))
            logo_btn.bind("<Button-1>", lambda e: self.nb.select(self.tab_home))
        except Exception:
            pass

        title_box = tk.Frame(logo_frame, bg="#F0ECFD")
        title_box.pack(side="left")

        title_line = tk.Frame(title_box, bg="#F0ECFD")
        title_line.pack(anchor="w")
        tk.Label(title_line, text="TaoYong", bg="#F0ECFD", fg="#2C1D63", font=(self.F, 16, "bold")).pack(side="left")
        tk.Label(title_line, text="Studio", bg="#F0ECFD", fg="#EC4899", font=(self.F, 16, "bold")).pack(side="left")

        tk.Label(title_box, text="สร้างวิดีโอการ์ตูนเด็กด้วย AI สำหรับเด็กไทย", bg="#F0ECFD", fg="#7B7496",
                 font=(self.F, 9)).pack(anchor="w")

        # 2. Center of header: Banner with cute cartoon kids & floating pill
        try:
            self._top_banner_img = ImageTk.PhotoImage(Image.open(ROOT / "studio" / "asset_top_banner.png").resize((380, 72)))
            tk.Label(head, image=self._top_banner_img, bg="#F0ECFD").pack(side="left", expand=True)
        except Exception:
            pass

        # 3. Right side of header: Quick icons + User Badge
        right_head = tk.Frame(head, bg="#F0ECFD")
        right_head.pack(side="right")

        for ic in ("🔔", "❓"):
            b = tk.Label(right_head, text=ic, bg="#F0ECFD", fg="#473F68", font=(self.F, 12), cursor="hand2")
            b.pack(side="left", padx=4)

        user_pill = tk.Frame(right_head, bg="#FFFFFF", padx=10, pady=4, highlightbackground="#E2DCF8", highlightcolor="#E2DCF8", highlightthickness=1, bd=0)
        user_pill.pack(side="left", padx=(8, 4))
        try:
            self._user_avatar = ImageTk.PhotoImage(Image.open(ROOT / "studio" / "asset_avatar_circle.png").resize((26, 26)))
            tk.Label(user_pill, image=self._user_avatar, bg="#FFFFFF").pack(side="left", padx=(0, 6))
        except Exception:
            pass
        u_box = tk.Frame(user_pill, bg="#FFFFFF")
        u_box.pack(side="left")
        tk.Label(u_box, text="สวัสดีครับ", bg="#FFFFFF", fg="#7B7496", font=(self.F, 8)).pack(anchor="w")
        tk.Label(u_box, text="TaoYong", bg="#FFFFFF", fg="#2C1D63", font=(self.F, 9, "bold")).pack(anchor="w")
        tk.Label(user_pill, text=" ⌄", bg="#FFFFFF", fg="#7B7496", font=(self.F, 9)).pack(side="left", padx=(4, 0))

        # Main Workspace Container: Left Sidebar + Right Content Area
        work_area = tk.Frame(self, bg="#F0ECFD")
        work_area.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        # Sidebar
        self.web_tab_bar = SideTabBar(work_area, font_family=self.F)
        self.web_tab_bar.pack(side="left", fill="y", padx=(0, 8))

        # Right Area
        right_area = tk.Frame(work_area, bg="#F0ECFD")
        right_area.pack(side="left", fill="both", expand=True)

        self.nb = ttk.Notebook(right_area, style="Hidden.TNotebook")
        self.nb.pack(fill="both", expand=True)

        # Tab Frames
        self.tab_home = ttk.Frame(self.nb)
        self.tab_plan = ttk.Frame(self.nb, padding=14)
        self.tab_scripts = ttk.Frame(self.nb, padding=14)
        self.tab_clips = ttk.Frame(self.nb, padding=14)
        self.tab_platforms = ttk.Frame(self.nb, padding=10)
        self.tab_post = ttk.Frame(self.nb, padding=14)
        self.tab_sched = ttk.Frame(self.nb, padding=14)
        self.tab_set = ttk.Frame(self.nb, padding=14)
        self.tab_fb_profile = ttk.Frame(self.nb, padding=14)

        tabs = ((self.tab_home, "หน้าแรก", "🏠"),
                (self.tab_plan, "วางแผน", "📅"),
                (self.tab_scripts, "บท", "📄"),
                (self.tab_clips, "คลิป", "🎬"),
                (self.tab_platforms, "สร้างและโพสต์", "✨"),
                (self.tab_post, "ตั้งค่าโพสต์", "⚙️"),
                (self.tab_sched, "ตั้งเวลา", "⏰"),
                (self.tab_set, "ตั้งค่า", "🔧"),
                (self.tab_fb_profile, "Facebook Profile", "👤"))
        for t, name, _icon in tabs:
            self.nb.add(t, text=name)
        self.web_tab_bar.setup_tabs(self.nb, tabs)
        self.nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self._build_home()
        self._build_plan()
        self._build_scripts()
        self._build_clips()
        self._build_platforms()
        self._build_post()
        self._build_sched()
        self._build_settings()
        self._build_fb_profile()

        # Bottom Collapsible Progress & Log Tray
        bottom = tk.Frame(right_area, bg="#F0ECFD", pady=2)
        # packed before the notebook so the tray is never pushed out of view on small windows
        bottom.pack(side="bottom", fill="x", before=self.nb)
        self.tray = bottom
        self.tray_home = right_area

        top = tk.Frame(bottom, bg="#F0ECFD")
        top.pack(fill="x")
        self.prog_label = tk.Label(top, text="พร้อมทำงาน", bg="#F0ECFD", fg="#2C1D63", font=(self.F, 9, "bold"))
        self.prog_label.pack(side="left")
        self.prog_pct = tk.Label(top, text="0%", bg="#F0ECFD", fg="#6C47FF", font=(self.F, 9, "bold"))
        self.prog_pct.pack(side="left", padx=8)
        self.btn_stop = tk.Button(top, text="หยุด", bg="#8E6CF7", fg="#FFFFFF", command=self.stop_job,
                                   state="disabled")
        self.btn_stop.pack(side="right")
        self.btn_log = ttk.Button(top, text="แสดงบันทึก", command=self._toggle_log)
        self.btn_log.pack(side="right", padx=6)
        self.prog = ModernProgressBar(bottom, height=12, bg_color="#E0D6F9", fill_color="#8E6CF7", border_color="#D0C2F5")
        self.prog.pack(fill="x", pady=(4, 4))
        self.log = tk.Text(bottom, height=4, bg="#1F1636", fg="#E8E2FF", insertbackground="#FFFFFF",
                           font=("Consolas" if IS_WIN else "DejaVu Sans Mono", 9), relief="flat",
                           padx=10, pady=4, wrap="word")
        self.log.tag_configure("bad", foreground="#FF9C9C")
        self.log.tag_configure("good", foreground="#9CF0B8")
        self.log.pack(fill="x")
        self.btn_log.configure(text="ซ่อนบันทึก")
        self.head_status = tk.Label(head, text="")

    def _dock_tray(self):
        """Show the progress/log tray in the bottom box of the clips and scripts pages, and at the window bottom elsewhere."""
        tray = getattr(self, "tray", None)
        if tray is None:
            return
        try:
            cur = self.nb.select()
            dock = None
            for tab, name in ((self.tab_clips, "clip_dock"), (self.tab_scripts, "script_dock")):
                if cur == str(tab):
                    dock = getattr(self, name, None)
            if dock is not None:
                if tray.pack_info().get("in") is not dock:
                    tray.pack_forget()
                    tray.pack(in_=dock, side="top", fill="x", padx=6, pady=(2, 4))
                    tray.lift()
                    self.log.configure(height=10)
            elif tray.pack_info().get("in") is not self.tray_home:
                tray.pack_forget()
                tray.pack(in_=self.tray_home, side="bottom", fill="x", before=self.nb)
                self.log.configure(height=4)
        except Exception:
            pass

    def _on_tab_changed(self, event=None):
        if hasattr(self, "web_tab_bar"):
            self.web_tab_bar.sync_selection()
        self._dock_tray()
        if hasattr(self, "tab_clips") and hasattr(self, "nb"):
            try:
                if self.nb.select() != str(self.tab_clips):
                    self._stop_clip_player()
            except Exception:
                pass
        self.refresh_all()

    def _toggle_log(self):
        if self.log.winfo_ismapped():
            self.log.pack_forget()
            self.btn_log.configure(text="แสดงบันทึก")
        else:
            self.log.pack(fill="x")
            self.btn_log.configure(text="ซ่อนบันทึก")

    # ------------------------------------------------------------------ home tab
    def _build_home(self):
        t = self.tab_home
        self._home_img_cache = []

        h_canvas = tk.Canvas(t, bg="#F0ECFD", highlightthickness=0)
        h_scroll = ttk.Scrollbar(t, orient="vertical", command=h_canvas.yview)
        h_box = tk.Frame(h_canvas, bg="#F0ECFD")
        h_win = h_canvas.create_window((0, 0), window=h_box, anchor="nw")

        h_box.bind("<Configure>", lambda e: h_canvas.configure(scrollregion=h_canvas.bbox("all")))
        h_canvas.bind("<Configure>", lambda e: h_canvas.itemconfigure(h_win, width=e.width - 6))
        h_canvas.configure(yscrollcommand=h_scroll.set)

        h_scroll.pack(side="right", fill="y")
        h_canvas.pack(side="left", fill="both", expand=True)

        h_canvas.bind_all("<MouseWheel>", lambda e: h_canvas.yview_scroll(int(-e.delta / 120), "units")
                          if self.nb.select() == str(self.tab_home) else None, add="+")

        # 1. Welcome Card
        w_card = tk.Frame(h_box, bg="#FFFFFF", padx=16, pady=12, highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        w_card.pack(fill="x", padx=12, pady=(8, 8))

        w_title = tk.Frame(w_card, bg="#FFFFFF")
        w_title.pack(anchor="w")
        tk.Label(w_title, text="ยินดีต้อนรับสู่ ", font=(self.F, 16, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left")
        tk.Label(w_title, text="TaoYong", font=(self.F, 16, "bold"), fg="#6C47FF", bg="#FFFFFF").pack(side="left")
        tk.Label(w_title, text="Studio", font=(self.F, 16, "bold"), fg="#EC4899", bg="#FFFFFF").pack(side="left")
        tk.Label(w_title, text=" !", font=(self.F, 16, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left")

        tk.Label(w_card, text="สตูดิโอสร้างวิดีโอการ์ตูนเด็กด้วย AI สำหรับเด็กไทย — เปลี่ยนจินตนาการให้เป็นวิดีโอสุดน่ารักได้ง่ายๆ",
                 font=(self.F, 9), fg="#7C7895", bg="#FFFFFF").pack(anchor="w", pady=(2, 0))

        # 2. 4 Stat Cards
        stats_frame = tk.Frame(h_box, bg="#F0ECFD")
        stats_frame.pack(fill="x", padx=12, pady=(0, 10))
        for i in range(4):
            stats_frame.columnconfigure(i, weight=1, uniform="stat")

        stat_defs = [
            ("inbox", "บทที่รอสร้าง", "12 บท", "จากทั้งหมด 28 บท", "ui_stat_icon1.png", "#FAF8FE", "#EAE4F8", "#6C47FF", self.tab_scripts),
            ("today", "คลิปที่สร้างวันนี้", "8 คลิป", "↑ +3 จากเมื่อวาน", "ui_stat_icon2.png", "#F4FDF9", "#D5F5E7", "#0E9F6E", self.tab_clips),
            ("review", "คลิปที่รอการตรวจสอบ", "5 คลิป", "รอตรวจสอบคุณภาพ", "ui_stat_icon3.png", "#FFF9F2", "#FFE6CB", "#F97316", self.tab_clips),
            ("next", "รันอัตโนมัติครั้งถัดไป", "วันนี้ 20:00 น.", "สร้างและโพสต์อัตโนมัติ", "ui_stat_icon4.png", "#FFF5F8", "#FFDBE4", "#E0245E", self.tab_sched),
        ]

        self.stat_vals = {}
        self.stat_subs = {}

        for i, (k, title, val, sub, icon_file, bg_color, border_color, val_color, target_tab) in enumerate(stat_defs):
            sc = tk.Frame(stats_frame, bg=bg_color, padx=12, pady=10, highlightbackground=border_color, highlightcolor=border_color, highlightthickness=1, bd=0)
            sc.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0))

            try:
                img = ImageTk.PhotoImage(Image.open(ROOT / "studio" / icon_file).resize((34, 34)))
                self._home_img_cache.append(img)
                tk.Label(sc, image=img, bg=bg_color).pack(side="left", padx=(0, 10))
            except Exception:
                pass

            info = tk.Frame(sc, bg=bg_color)
            info.pack(side="left", fill="both", expand=True)

            tk.Label(info, text=title, font=(self.F, 9), fg="#6B6387", bg=bg_color).pack(anchor="w")
            v_lbl = tk.Label(info, text=val, font=(self.F, 13 if len(val) > 8 else 16, "bold"), fg=val_color, bg=bg_color)
            v_lbl.pack(anchor="w")
            self.stat_vals[k] = v_lbl

            s_lbl = tk.Label(info, text=sub, font=(self.F, 8, "bold" if "↑" in sub else "normal"),
                             fg=val_color if "↑" in sub else "#9991B3", bg=bg_color)
            s_lbl.pack(anchor="w")
            self.stat_subs[k] = s_lbl

            btn = tk.Label(sc, text=" › ", font=(self.F, 13, "bold"), fg=val_color, bg=bg_color, cursor="hand2")
            btn.pack(side="right")
            btn.bind("<Button-1>", lambda e, tt=target_tab: self.nb.select(tt))
            sc.bind("<Button-1>", lambda e, tt=target_tab: self.nb.select(tt))

        # 3. Quick Actions
        act_frame = tk.Frame(h_box, bg="#F0ECFD")
        act_frame.pack(fill="x", padx=12, pady=(0, 10))

        head_act = tk.Frame(act_frame, bg="#F0ECFD")
        head_act.pack(fill="x", pady=(0, 6))
        tk.Label(head_act, text="⚡ เมนูด่วน", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#F0ECFD").pack(side="left")
        tk.Label(head_act, text="เริ่มทำงานได้ทันที ด้วยเครื่องมือที่ใช้งานบ่อย", font=(self.F, 9), fg="#7C7895", bg="#F0ECFD").pack(side="left", padx=10)

        act_grid = tk.Frame(act_frame, bg="#F0ECFD")
        act_grid.pack(fill="x")
        for i in range(5):
            act_grid.columnconfigure(i, weight=1, uniform="act")

        act_defs = [
            ("สร้างวิดีโอจาก\nทุกบทที่รออยู่", "ใช้ AI สร้างคลิปจากบททั้งหมด\nที่ยังไม่ได้สร้าง", "ui_icon_act1.png", "#FAF8FE", "#EAE4F8", "#6C47FF", self.run_batch),
            ("ดูคลิปที่สร้างแล้ว", "เปิดดูคลิปทั้งหมด\nและจัดการไฟล์", "ui_icon_act2.png", "#F3FBFB", "#D2F4F2", "#14B8A6", lambda: self.nb.select(self.tab_clips)),
            ("นำเข้าบทจากไฟล์", "รองรับไฟล์ Excel, CSV\nหรือข้อความ", "ui_icon_act3.png", "#FFF6FA", "#FCDDEB", "#EC4899", self.import_scripts),
            ("เปิดโฟลเดอร์ผลลัพธ์", "เปิดโฟลเดอร์ที่เก็บคลิป\nวิดีโอที่สร้างแล้ว", "ui_icon_act4.png", "#F4F8FE", "#D8E7FD", "#3B82F6", lambda: open_path(ROOT / "output")),
            ("ตรวจสอบความพร้อม\nของระบบ", "เช็คสถานะ AI และการตั้งค่า\nทั้งหมด", "ui_icon_act5.png", "#FFF9F2", "#FFE8D1", "#F97316", self.run_check),
        ]

        for i, (title, desc, icon_file, bg_color, border_color, tint_color, action_cmd) in enumerate(act_defs):
            ac = tk.Frame(act_grid, bg=bg_color, padx=10, pady=10, highlightbackground=border_color, highlightcolor=border_color, highlightthickness=1, bd=0, cursor="hand2")
            ac.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0))

            try:
                img = ImageTk.PhotoImage(Image.open(ROOT / "studio" / icon_file).resize((32, 32)))
                self._home_img_cache.append(img)
                tk.Label(ac, image=img, bg=bg_color).pack(anchor="w", pady=(0, 4))
            except Exception:
                pass

            tk.Label(ac, text=title, font=(self.F, 9, "bold"), fg="#2C1D63", bg=bg_color, justify="left").pack(anchor="w")
            tk.Label(ac, text=desc, font=(self.F, 8), fg="#7C7895", bg=bg_color, justify="left").pack(anchor="w", pady=(2, 6))

            arr = tk.Label(ac, text=" › ", font=(self.F, 11, "bold"), fg=tint_color, bg=bg_color)
            arr.pack(anchor="e")

            ac.bind("<Button-1>", lambda e, cmd=action_cmd: cmd())
            for ch in ac.winfo_children():
                ch.bind("<Button-1>", lambda e, cmd=action_cmd: cmd())

        # 4. 3 Bottom Sections
        bot_grid = tk.Frame(h_box, bg="#F0ECFD")
        bot_grid.pack(fill="x", padx=12, pady=(0, 12))
        bot_grid.columnconfigure(0, weight=5, uniform="bot")
        bot_grid.columnconfigure(1, weight=3, uniform="bot")
        bot_grid.columnconfigure(2, weight=3, uniform="bot")

        # Card A: ขั้นตอนการทำงาน
        c_a = tk.Frame(bot_grid, bg="#FFFFFF", padx=12, pady=10, highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        c_a.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        h_a = tk.Frame(c_a, bg="#FFFFFF")
        h_a.pack(fill="x", pady=(0, 6))
        tk.Label(h_a, text="📖 ขั้นตอนการทำงาน", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left")
        tk.Label(h_a, text="สร้างวิดีโอการ์ตูนเด็กแบบง่ายๆ ใน 4 ขั้นตอน", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF").pack(side="left", padx=8)

        step_row = tk.Frame(c_a, bg="#FFFFFF")
        step_row.pack(fill="x", pady=(2, 6))
        step_targets = [self.tab_plan, self.tab_platforms, self.tab_clips, self.tab_sched]
        for i, sf in enumerate(["ui_step_1.png", "ui_step_2.png", "ui_step_3.png", "ui_step_4.png"]):
            try:
                img = ImageTk.PhotoImage(Image.open(ROOT / "studio" / sf).resize((86, 110)))
                self._home_img_cache.append(img)
                lbl_st = tk.Label(step_row, image=img, bg="#FFFFFF", cursor="hand2")
                lbl_st.pack(side="left", padx=2)
                lbl_st.bind("<Button-1>", lambda e, tt=step_targets[i]: self.nb.select(tt))
            except Exception:
                pass
            if i < 3:
                tk.Label(step_row, text=" › ", font=(self.F, 13, "bold"), fg="#D1C9E8", bg="#FFFFFF").pack(side="left")

        quote_box = tk.Frame(c_a, bg="#F3EFFE", padx=10, pady=5, highlightbackground="#E2D7F8", highlightcolor="#E2D7F8", highlightthickness=1, bd=0)
        quote_box.pack(fill="x", pady=(6, 0))
        tk.Label(quote_box, text='💡 "เปลี่ยนไอเดียเล็กๆ ให้เป็นวิดีโอการ์ตูนแสนสนุก สร้างรอยยิ้มและจินตนาการที่ไม่มีสิ้นสุดให้กับเด็กไทย" 💖',
                 font=(self.F, 8, "bold"), fg="#6C47FF", bg="#F3EFFE", justify="center").pack(anchor="center")

        # Card B: สถานะระบบ
        c_b = tk.Frame(bot_grid, bg="#FFFFFF", padx=12, pady=10, highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        c_b.grid(row=0, column=1, sticky="nsew", padx=(0, 6))

        h_b = tk.Frame(c_b, bg="#FFFFFF")
        h_b.pack(fill="x", pady=(0, 6))
        tk.Label(h_b, text="✔", font=(self.F, 9, "bold"), fg="#FFFFFF", bg="#0E9F6E", padx=4, pady=1).pack(side="left", padx=(0, 4))
        tk.Label(h_b, text="สถานะระบบ", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left")
        tk.Label(h_b, text="ทุกระบบพร้อมใช้งาน", font=(self.F, 8), fg="#0E9F6E", bg="#FFFFFF").pack(side="left", padx=6)

        sys_items = [
            ("⚙️  การเชื่อมต่อ AI", "• พร้อมใช้งาน"),
            ("🎨  การสร้างภาพ (Image AI)", "• พร้อมใช้งาน"),
            ("🔊  การสร้างเสียง (TTS)", "• พร้อมใช้งาน"),
            ("🎬  การตัดต่อวิดีโอ", "• พร้อมใช้งาน"),
            ("👤  การเชื่อมต่อ Facebook", "• พร้อมใช้งาน"),
        ]
        for title, st in sys_items:
            row = tk.Frame(c_b, bg="#FFFFFF")
            row.pack(fill="x", pady=2)
            tk.Label(row, text=title, font=(self.F, 8), fg="#473F68", bg="#FFFFFF").pack(side="left")
            tk.Label(row, text=st, font=(self.F, 8, "bold"), fg="#0E9F6E", bg="#FFFFFF").pack(side="right")

        try:
            total, used, free = shutil.disk_usage(ROOT)
            used_gb = used // (2**30)
            total_gb = total // (2**30)
            pct = int((used / total) * 100)
        except Exception:
            used_gb, total_gb, pct = 128, 500, 25

        stor_row = tk.Frame(c_b, bg="#FFFFFF")
        stor_row.pack(fill="x", pady=(6, 2))
        tk.Label(stor_row, text="💾 พื้นที่จัดเก็บข้อมูล", font=(self.F, 8), fg="#473F68", bg="#FFFFFF").pack(side="left")
        tk.Label(stor_row, text=f"{used_gb} GB / {total_gb} GB", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF").pack(side="right")

        p_bg = tk.Frame(c_b, bg="#EDE8FD", height=6)
        p_bg.pack(fill="x", pady=(0, 6))
        p_fill = tk.Frame(p_bg, bg="#8E6CF7", height=6, width=max(10, int(150 * (pct / 100))))
        p_fill.pack(side="left", fill="y")

        pill_st = tk.Frame(c_b, bg="#E6F8F0", padx=6, pady=3, highlightbackground="#B8F0D6", highlightcolor="#B8F0D6", highlightthickness=1, bd=0)
        pill_st.pack(fill="x", pady=(2, 0))
        tk.Label(pill_st, text="✔ ระบบทำงานปกติ พร้อมสำหรับการสร้างวิดีโอ  ⚙️", font=(self.F, 7, "bold"), fg="#0E9F6E", bg="#E6F8F0").pack(anchor="center")

        # Card C: กิจกรรมล่าสุด
        c_c = tk.Frame(bot_grid, bg="#FFFFFF", padx=12, pady=10, highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        c_c.grid(row=0, column=2, sticky="nsew")

        h_c = tk.Frame(c_c, bg="#FFFFFF")
        h_c.pack(fill="x", pady=(0, 6))
        tk.Label(h_c, text="🕒 กิจกรรมล่าสุด", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left")
        btn_view_all = tk.Label(h_c, text="ดูทั้งหมด ›", font=(self.F, 8), fg="#6C47FF", bg="#FFFFFF", cursor="hand2")
        btn_view_all.pack(side="right")
        btn_view_all.bind("<Button-1>", lambda e: self.nb.select(self.tab_clips))

        act_items = [
            ("thumb_act_1.png", "สร้างคลิปสำเร็จ", "นิทานกระต่ายกับเต่า", "14:32  ✔", "#0E9F6E"),
            ("thumb_act_2.png", "โพสต์ลง Facebook แล้ว", "ความสำคัญของการแบ่งปัน", "12:15  👤", "#3B82F6"),
            ("thumb_act_3.png", "นำเข้าบทจากไฟล์", "kids_story_batch1.xlsx", "10:48  ✔", "#0E9F6E"),
            ("thumb_act_4.png", "สร้างคลิปสำเร็จ", "น้องหมากับเพื่อนใหม่", "09:20  ✔", "#0E9F6E"),
            ("thumb_act_5.png", "ตั้งเวลารันอัตโนมัติ", "วันนี้ 20:00 น.", "08:11  ⏰", "#F97316"),
        ]

        for tf, title, desc, meta, meta_col in act_items:
            row = tk.Frame(c_c, bg="#FFFFFF")
            row.pack(fill="x", pady=2)

            try:
                img = ImageTk.PhotoImage(Image.open(ROOT / "studio" / tf).resize((26, 26)))
                self._home_img_cache.append(img)
                tk.Label(row, image=img, bg="#FFFFFF").pack(side="left", padx=(0, 6))
            except Exception:
                pass

            tb = tk.Frame(row, bg="#FFFFFF")
            tb.pack(side="left", fill="both", expand=True)
            tk.Label(tb, text=title, font=(self.F, 8, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")
            tk.Label(tb, text=desc, font=(self.F, 7), fg="#7C7895", bg="#FFFFFF").pack(anchor="w")

            tk.Label(row, text=meta, font=(self.F, 7, "bold"), fg=meta_col, bg="#FFFFFF").pack(side="right")

    # ------------------------------------------------------------------ scripts tab
    def _build_scripts(self):
        t = self.tab_scripts
        self._scripts_img_cache = []

        # Top Bar Card
        bar = tk.Frame(t, bg="#FFFFFF", padx=16, pady=10, highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        bar.pack(fill="x", padx=4, pady=(2, 8))

        b_left = tk.Frame(bar, bg="#FFFFFF")
        b_left.pack(side="left")

        # Document icon box
        doc_box = tk.Frame(b_left, bg="#EDE7FE", padx=8, pady=6, highlightbackground="#D2C3F8", highlightthickness=1, bd=0)
        doc_box.pack(side="left", padx=(0, 10))
        tk.Label(doc_box, text="📄", font=(self.F, 16), bg="#EDE7FE").pack()

        t_box = tk.Frame(b_left, bg="#FFFFFF")
        t_box.pack(side="left")
        tk.Label(t_box, text="บทที่รอสร้างคลิป", font=(self.F, 16, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")
        tk.Label(t_box, text="จัดการบทการ์ตูน เลือกสร้างคลิป หรือแก้ไขเนื้อหาก่อนผลิตเป็นวิดีโอ",
                 font=(self.F, 9), fg="#7C7895", bg="#FFFFFF").pack(anchor="w")

        # Right Action Buttons
        b_right = tk.Frame(bar, bg="#FFFFFF")
        b_right.pack(side="right")

        btn_ref = RoundedButton(b_right, text="🔄 รีเฟรช", bg="#F4F0FD", fg="#6C47FF", border="#E0D6F8", bd=1,
                                radius=8, padx=12, pady=5, command=self.refresh_scripts)
        btn_ref.pack(side="left", padx=4)

        btn_imp = RoundedButton(b_right, text="⬆ เพิ่มบทจากไฟล์...", bg="#8E6CF7", fg="#FFFFFF",
                                radius=8, padx=14, pady=5, command=self.import_scripts)
        btn_imp.pack(side="left", padx=4)

        btn_samp = RoundedButton(b_right, text="➕ เพิ่มบทตัวอย่าง", bg="#0E9F6E", fg="#FFFFFF",
                                 radius=8, padx=14, pady=5, command=self.add_samples)
        btn_samp.pack(side="left", padx=4)

        btn_del = RoundedButton(b_right, text="🗑 ลบบทที่เลือก", bg="#FFF5F5", fg="#EF4444", border="#FFCFCF", bd=1,
                                radius=8, padx=12, pady=5, command=self.remove_scripts)
        btn_del.pack(side="left", padx=4)

        # bottom box: shows what the app is doing right now (progress bar + live log)
        self.script_dock = tk.Frame(t, bg="#F0ECFD", highlightbackground="#D8CEF8", highlightthickness=1, bd=0)
        self.script_dock.pack(side="bottom", fill="x", padx=4, pady=(0, 2))

        # Main Workspace: Left Panel (Scripts List) + Right Panel (Preview & Animation Studio)
        main = tk.Frame(t, bg="#F0ECFD")
        main.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        # --- LEFT PANEL: Scripts List Card ---
        left = tk.Frame(main, bg="#FFFFFF", padx=12, pady=10, highlightbackground="#EAE4F8", highlightthickness=1, bd=0)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        # Search & Filter Row
        f_row = tk.Frame(left, bg="#FFFFFF")
        f_row.pack(fill="x", pady=(0, 8))

        s_box = tk.Frame(f_row, bg="#F9F8FD", padx=8, pady=4, highlightbackground="#EAE4F8", highlightthickness=1, bd=0)
        s_box.pack(side="left", fill="x", expand=True, padx=(0, 8))
        tk.Label(s_box, text="🔍", font=(self.F, 9), bg="#F9F8FD").pack(side="left", padx=(0, 4))
        self.script_search_var = tk.StringVar()
        s_ent = tk.Entry(s_box, textvariable=self.script_search_var, bg="#F9F8FD", relief="flat", font=(self.F, 9))
        s_ent.pack(side="left", fill="x", expand=True)

        self.script_cat_var = tk.StringVar(value="ทุกหมวดหมู่")
        cb_cat = ttk.Combobox(f_row, textvariable=self.script_cat_var, state="readonly", width=14,
                              values=["ทุกหมวดหมู่", "ธรรมชาติ", "สอนใจ", "วิทยาศาสตร์", "นิทาน"])
        cb_cat.pack(side="left", padx=(0, 6))

        self.script_sort_var = tk.StringVar(value="เรียงล่าสุด")
        cb_sort = ttk.Combobox(f_row, textvariable=self.script_sort_var, state="readonly", width=12,
                               values=["เรียงล่าสุด", "ชื่อเรื่อง", "ตัวละคร"])
        cb_sort.pack(side="left")

        # Treeview for Scripts
        cols = ("title", "chars", "check", "date")
        self.tv_s = ttk.Treeview(left, columns=cols, show="headings", selectmode="extended")
        for c, w, txt in (("title", 280, "ชื่อเรื่อง"), ("chars", 150, "ตัวละคร"),
                          ("check", 130, "ผลตรวจบท"), ("date", 110, "วันที่สร้าง")):
            self.tv_s.heading(c, text=txt)
            self.tv_s.column(c, width=w, anchor="w")
        self.tv_s.pack(fill="both", expand=True)
        self.tv_s.tag_configure("bad", foreground=BAD)
        self.tv_s.tag_configure("warn", foreground=WARN)
        self.tv_s.tag_configure("good", foreground=GOOD)
        self.tv_s.bind("<<TreeviewSelect>>", lambda e: self.show_script())
        self.tv_s.bind("<Double-1>", lambda e: self.edit_script())
        self.tv_s.bind("<Delete>", lambda e: self.remove_scripts())

        # Right-click context menu
        menu_s = tk.Menu(self.tv_s, tearoff=0)
        menu_s.add_command(label="▶ สร้างคลิปเรื่องนี้", command=self.render_selected)
        menu_s.add_command(label="✦ ส่งไปสร้างด้วย Google Flow", command=self.send_script_to_flow)
        menu_s.add_command(label="👁 ดูภาพตัวอย่าง", command=self.preview_script)
        menu_s.add_command(label="✏ แก้ไขบท (Notepad)", command=self.edit_script)
        menu_s.add_separator()
        menu_s.add_command(label="🗑 ลบบทที่เลือก", command=self.remove_scripts)

        def _on_s_right_click(event):
            item = self.tv_s.identify_row(event.y)
            if item:
                if item not in self.tv_s.selection():
                    self.tv_s.selection_set(item)
                    self.show_script()
                menu_s.post(event.x_root, event.y_root)
        self.tv_s.bind("<Button-3>", _on_s_right_click)

        # Pagination & Counter Bar
        bot_bar = tk.Frame(left, bg="#FFFFFF")
        bot_bar.pack(fill="x", pady=(6, 0))
        self.lbl_s_count = tk.Label(bot_bar, text="เลือกแล้ว 1 รายการ", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF")
        self.lbl_s_count.pack(side="left")
        self.lbl_s_pages = tk.Label(bot_bar, text="แสดงทั้งหมด  ‹ [1] ›", font=(self.F, 8), fg="#6C47FF", bg="#FFFFFF")
        self.lbl_s_pages.pack(side="right")

        # --- RIGHT PANEL: Details & Animation Studio ---
        right = tk.Frame(main, bg="#FFFFFF", padx=12, pady=10, width=490, highlightbackground="#EAE4F8", highlightthickness=1, bd=0)
        right.pack(side="right", fill="y", padx=(6, 0))
        right.pack_propagate(False)

        btns = tk.Frame(right, bg="#FFFFFF")
        btns.pack(side="bottom", fill="x", pady=(6, 0))

        # Scrollable container for script preview, characters, and animation tools
        canvas = tk.Canvas(right, bg="#FFFFFF", highlightthickness=0)
        scroll = ttk.Scrollbar(right, orient="vertical", command=canvas.yview)
        scroll_content = tk.Frame(canvas, bg="#FFFFFF")
        win_id = canvas.create_window((0, 0), window=scroll_content, anchor="nw")

        scroll_content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win_id, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)

        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        def _on_right_wheel(e):
            if self.nb.select() == str(self.tab_scripts) and canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_right_wheel, add="+")

        # Top Preview Banner Image
        try:
            self._script_banner_img = ImageTk.PhotoImage(Image.open(ROOT / "studio" / "script_large_banner_round.png").resize((220, 130)))
            self._scripts_img_cache.append(self._script_banner_img)
        except Exception:
            self._script_banner_img = None

        prev_box = tk.Frame(scroll_content, bg="#FFFFFF")
        prev_box.pack(fill="x", pady=(0, 6))

        # Row 1: Large Banner + Script Title & Meta
        row_top_meta = tk.Frame(prev_box, bg="#FFFFFF")
        row_top_meta.pack(fill="x")

        self.s_preview = tk.Label(row_top_meta, bg="#FFFFFF", image=self._script_banner_img if self._script_banner_img else "")
        self.s_preview.pack(side="left", padx=(0, 10))

        info_meta = tk.Frame(row_top_meta, bg="#FFFFFF")
        info_meta.pack(side="left", fill="both", expand=True)

        self.lbl_s_detail_title = tk.Label(info_meta, text="ช้างน้อยกับป่าที่หายไป", font=(self.F, 12, "bold"), fg="#2C1D63", bg="#FFFFFF", wraplength=210, justify="left")
        self.lbl_s_detail_title.pack(anchor="w")

        self.lbl_s_detail_cat = tk.Label(info_meta, text="หมวดหมู่ ธรรมชาติ / สิ่งแวดล้อม", font=(self.F, 8, "bold"), fg="#6C47FF", bg="#F0EBFF", padx=6, pady=2)
        self.lbl_s_detail_cat.pack(anchor="w", pady=(3, 2))

        self.lbl_s_detail_len = tk.Label(info_meta, text="🕒 ความยาวโดยประมาณ 4-6 นาที", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF")
        self.lbl_s_detail_len.pack(anchor="w", pady=(1, 3))

        # Synopsis
        tk.Label(prev_box, text="เรื่องย่อ:", font=(self.F, 9, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w", pady=(4, 2))
        self.s_info = tk.Label(prev_box, text="ช้างน้อยออกเดินทางกับเพื่อนๆ เพื่อค้นหาว่าทำไมป่าที่เคยเขียวขจีถึงเริ่มเหี่ยวแห้ง พวกเขาจึงร่วมมือกันปลูกต้นไม้ ดูแลธรรมชาติ และเรียนรู้ว่าทุกคนสามารถช่วยโลกได้ แม้จะเป็นเด็กตัวเล็กๆ ก็ตาม",
                               font=(self.F, 8), fg="#5A5174", bg="#FFFFFF", wraplength=430, justify="left")
        self.s_info.pack(anchor="w", fill="x")

        # Characters Section (ตัวละคร)
        char_card = tk.Frame(scroll_content, bg="#FBF9FE", padx=10, pady=8, highlightbackground="#EAE4F8", highlightthickness=1, bd=0)
        char_card.pack(fill="x", pady=(4, 8))

        c_head = tk.Frame(char_card, bg="#FBF9FE")
        c_head.pack(fill="x", pady=(0, 4))
        tk.Label(c_head, text="🏰 ตัวละคร", font=(self.F, 10, "bold"), fg="#2C1D63", bg="#FBF9FE").pack(side="left")

        c_row = tk.Frame(char_card, bg="#FBF9FE")
        c_row.pack(fill="x")
        char_defs = [
            ("ช้างน้อย", "(พระเอก)", "char_avatar_circle_1.png"),
            ("ตะวัน", "(เด็กชาย)", "char_avatar_circle_2.png"),
            ("ใบตอง", "(เด็กหญิง)", "char_avatar_circle_3.png"),
            ("ลุงช้าง", "(ผู้ใหญ่ใจดี)", "char_avatar_circle_4.png"),
            ("กระรอกน้อย", "(เพื่อนสัตว์)", "char_avatar_circle_5.png"),
            ("นกแก้ว", "(เพื่อนสัตว์)", "char_avatar_circle_6.png"),
        ]
        for name, role, af in char_defs:
            col = tk.Frame(c_row, bg="#FBF9FE")
            col.pack(side="left", fill="x", expand=True, padx=2)
            try:
                c_img = ImageTk.PhotoImage(Image.open(ROOT / "studio" / af).resize((36, 36)))
                self._scripts_img_cache.append(c_img)
                tk.Label(col, image=c_img, bg="#FBF9FE").pack()
            except Exception:
                pass
            tk.Label(col, text=name, font=(self.F, 8, "bold"), fg="#2C1D63", bg="#FBF9FE").pack()
            tk.Label(col, text=role, font=(self.F, 7), fg="#7C7895", bg="#FBF9FE").pack()

        # ==============================================================
        # Panel: เครื่องมือสร้างแอนิเมชัน (Local GPU Animation Studio V1)
        # ==============================================================
        self._build_animation_tools_panel(scroll_content)

        # Live Rendering Progress Card
        self.anim_render_card = tk.Frame(btns, bg="#FAF7FE", highlightbackground="#D5C4FF", highlightthickness=1, padx=10, pady=8)
        self.anim_render_card.pack(fill="x", pady=(0, 6))

        # Row 1: Header + Percentage
        row_card_head = tk.Frame(self.anim_render_card, bg="#FAF7FE")
        row_card_head.pack(fill="x")
        self.anim_card_icon = tk.Label(row_card_head, text="🎬", font=(self.F, 11), bg="#FAF7FE")
        self.anim_card_icon.pack(side="left", padx=(0, 4))
        self.anim_card_title = tk.Label(row_card_head, text="พร้อมสร้างคลิป", font=(self.F, 9, "bold"), fg="#2C1D63", bg="#FAF7FE")
        self.anim_card_title.pack(side="left")
        self.anim_card_pct = tk.Label(row_card_head, text="0%", font=(self.F, 11, "bold"), fg="#7C5CEF", bg="#FAF7FE")
        self.anim_card_pct.pack(side="right")

        # Row 2: Subtitle / Engine & Spec info
        self.anim_card_meta = tk.Label(self.anim_render_card, text="เลือกบทแล้วกด ▶ สร้างคลิปในเครื่อง เพื่อเริ่ม", 
                                       font=(self.F, 8), fg="#7C7895", bg="#FAF7FE", anchor="w")
        self.anim_card_meta.pack(fill="x", pady=(1, 4))

        # Row 3: Modern Progress Bar
        self.anim_card_prog = ModernProgressBar(self.anim_render_card, height=14, bg_color="#ECE7FB", fill_color="#8E6CF7", border_color="#D8CEF8")
        self.anim_card_prog.pack(fill="x", pady=(0, 4))

        # Row 4: Status details + ETA
        row_card_foot = tk.Frame(self.anim_render_card, bg="#FAF7FE")
        row_card_foot.pack(fill="x")
        self.anim_card_detail = tk.Label(row_card_foot, text="รอเริ่มงาน...", font=(self.F, 8), fg="#5A5174", bg="#FAF7FE")
        self.anim_card_detail.pack(side="left")
        self.anim_card_eta = tk.Label(row_card_foot, text="", font=(self.F, 8, "bold"), fg="#8E6CF7", bg="#FAF7FE")
        self.anim_card_eta.pack(side="right")

        # Row 5: Action buttons when done / cancel during run
        self.row_card_actions = tk.Frame(self.anim_render_card, bg="#FAF7FE")
        self.row_card_actions.pack(fill="x", pady=(4, 0))
        self.btn_card_open_folder = tk.Button(self.row_card_actions, text="📁 เปิดโฟลเดอร์คลิป", font=(self.F, 8, "bold"),
                                              bg="#EFF6FF", fg="#2563EB", relief="solid", bd=1, padx=8, pady=2,
                                              cursor="hand2", command=self._open_created_folder)
        self.btn_card_open_folder.pack(side="left", padx=(0, 4))
        self.btn_card_play_clip = tk.Button(self.row_card_actions, text="▶ เปิดดูคลิป", font=(self.F, 8, "bold"),
                                            bg="#ECFDF5", fg="#059669", relief="solid", bd=1, padx=8, pady=2,
                                            cursor="hand2", command=self._play_created_clip)
        self.btn_card_play_clip.pack(side="left", padx=4)
        self.btn_card_cancel = tk.Button(self.row_card_actions, text="⏹ ยกเลิก", font=(self.F, 8, "bold"),
                                         bg="#FEF2F2", fg="#EF4444", relief="solid", bd=1, padx=8, pady=2,
                                         cursor="hand2", command=self.stop_job)
        # Initially hide action buttons
        self.btn_card_open_folder.pack_forget()
        self.btn_card_play_clip.pack_forget()
        self.btn_card_cancel.pack_forget()

        # Action Buttons Bar
        row_b = tk.Frame(btns, bg="#FFFFFF")
        row_b.pack(fill="x")

        self.btn_render_clip = tk.Button(row_b, text="▶  สร้างคลิปในเครื่อง", font=(self.F, 9, "bold"),
                                         bg="#8E6CF7", fg="#FFFFFF", activebackground="#7C5CEF", activeforeground="#FFFFFF",
                                         relief="flat", bd=0, padx=12, pady=6, cursor="hand2", command=self.render_selected)
        self.btn_render_clip.pack(side="left", fill="x", expand=True, padx=(0, 4))

        b_prev = tk.Button(row_b, text="👁 ดูตัวอย่าง", font=(self.F, 9, "bold"),
                           bg="#EFF6FF", fg="#3B82F6", activebackground="#DBEAFE", relief="solid", bd=1,
                           padx=8, pady=5, cursor="hand2", command=self.preview_script)
        b_prev.pack(side="left", padx=2)

        b_edit = tk.Button(row_b, text="✏ แก้ไขบท", font=(self.F, 9, "bold"),
                           bg="#FFFBEB", fg="#F59E0B", activebackground="#FEF3C7", relief="solid", bd=1,
                           padx=8, pady=5, cursor="hand2", command=self.edit_script)
        b_edit.pack(side="left", padx=2)

        b_del = tk.Button(row_b, text="🗑 ลบ", font=(self.F, 9, "bold"),
                          bg="#FEF2F2", fg="#EF4444", activebackground="#FEE2E2", relief="solid", bd=1,
                          padx=8, pady=5, cursor="hand2", command=self.remove_scripts)
        b_del.pack(side="left", padx=(2, 0))

    def _build_animation_tools_panel(self, parent):
        panel = ttk.LabelFrame(parent, text=" เครื่องมือสร้างแอนิเมชัน ", padding=12)
        panel.pack(fill="x", pady=(4, 8))

        # --- A. เลือกวิธีสร้าง ---
        row_mode = ttk.Frame(panel)
        row_mode.pack(fill="x", pady=(2, 6))
        ttk.Label(row_mode, text="A. วิธีสร้าง:", font=(self.F, 10, "bold")).pack(anchor="w", pady=(0, 3))
        self.anim_mode = tk.StringVar(value="local")
        mode_box = ttk.Frame(row_mode)
        mode_box.pack(fill="x")
        ttk.Radiobutton(mode_box, text="สร้างในเครื่อง (Local Animation)", variable=self.anim_mode,
                        value="local", command=self._on_anim_mode_changed).pack(anchor="w", pady=2)
        ttk.Radiobutton(mode_box, text="สร้างด้วย Google Flow (Cloud)", variable=self.anim_mode,
                        value="flow", command=self._on_anim_mode_changed).pack(anchor="w", pady=2)

        # --- แพลตฟอร์มปลายทาง (Target Platform) ---
        self.f_plat_sec = ttk.Frame(panel)
        self.f_plat_sec.pack(fill="x", pady=(4, 6))
        ttk.Label(self.f_plat_sec, text="แพลตฟอร์มปลายทาง:", font=(self.F, 10, "bold")).pack(anchor="w", pady=(0, 2))
        self.anim_platform_val = tk.StringVar(value="TikTok (แนวตั้ง 9:16)")
        self.anim_platform_cb = ttk.Combobox(self.f_plat_sec, textvariable=self.anim_platform_val, state="readonly",
                                             values=[
                                                 "TikTok (แนวตั้ง 9:16)",
                                                 "YouTube แนวนอน (16:9)",
                                                 "YouTube Shorts (แนวตั้ง 9:16)",
                                                 "Facebook Page (แนวตั้ง 9:16)",
                                                 "Facebook ส่วนตัว (แนวตั้ง 9:16)",
                                                 "Shopee Video (แนวตั้ง 9:16)",
                                             ])
        self.anim_platform_cb.pack(fill="x", pady=(2, 2))
        self.anim_platform_status_lbl = tk.Label(self.f_plat_sec, text="", fg="#7C7895", bg="#FFFFFF", wraplength=410)
        self.anim_platform_status_lbl.pack(anchor="w")
        self.anim_platform_cb.bind("<<ComboboxSelected>>", self._on_anim_platform_selected)

        # --- B. เลือกอุปกรณ์ ---
        self.f_device_sec = ttk.Frame(panel)
        self.f_device_sec.pack(fill="x", pady=(6, 8))
        ttk.Label(self.f_device_sec, text="B. อุปกรณ์ประมวลผล (Hardware):", font=(self.F, 10, "bold")).pack(anchor="w")
        self.anim_device_val = tk.StringVar()
        self.anim_device_cb = ttk.Combobox(self.f_device_sec, textvariable=self.anim_device_val, state="readonly")
        self.anim_device_cb.pack(fill="x", pady=(3, 2))
        self.anim_device_status_lbl = tk.Label(self.f_device_sec, text="", fg="#7C7895", bg="#FFFFFF", wraplength=410)
        self.anim_device_status_lbl.pack(anchor="w")
        self.anim_device_cb.bind("<<ComboboxSelected>>", self._on_anim_device_selected)

        # --- C. เลือกประเภทแอนิเมชัน ---
        self.f_type_sec = ttk.Frame(panel)
        self.f_type_sec.pack(fill="x", pady=(6, 8))
        ttk.Label(self.f_type_sec, text="C. ประเภทแอนิเมชัน (Engine):", font=(self.F, 10, "bold")).pack(anchor="w")
        self.anim_engine_val = tk.StringVar()
        self.anim_engine_cb = ttk.Combobox(self.f_type_sec, textvariable=self.anim_engine_val, state="readonly")
        self.anim_engine_cb.pack(fill="x", pady=(3, 2))
        self.anim_engine_status_lbl = tk.Label(self.f_type_sec, text="", fg="#7C7895", bg="#FFFFFF", wraplength=410)
        self.anim_engine_status_lbl.pack(anchor="w")
        self.anim_engine_cb.bind("<<ComboboxSelected>>", self._on_anim_engine_selected)

        # Chibi 3D Options Sub-Panel
        self.f_chibi_sec = tk.Frame(self.f_type_sec, bg="#FAF8FF", highlightbackground="#D5C4FF", highlightthickness=1, padx=8, pady=6)

        lbl_c_head = tk.Label(self.f_chibi_sec, text="🎨 พรีเซ็ต 3D Chibi Pastel (เด็กไทยหัวโต สีพาสเทล)", font=(self.F, 9, "bold"), fg="#4A2582", bg="#FAF8FF")
        lbl_c_head.pack(anchor="w", pady=(0, 4))

        # Row 1: Character & Scene
        row_c1 = tk.Frame(self.f_chibi_sec, bg="#FAF8FF")
        row_c1.pack(fill="x", pady=2)
        row_c1.columnconfigure(0, weight=1, uniform="c_col")
        row_c1.columnconfigure(1, weight=1, uniform="c_col")

        box_c_char = tk.Frame(row_c1, bg="#FAF8FF")
        box_c_char.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        tk.Label(box_c_char, text="ตัวละคร 3D:", font=(self.F, 8), fg="#645579", bg="#FAF8FF").pack(anchor="w")
        self.chibi_char_val = tk.StringVar(value="khao_hom — น้องข้าวหอม (เด็กหญิงผมบันคู่)")
        self.chibi_char_cb = ttk.Combobox(box_c_char, textvariable=self.chibi_char_val, state="readonly",
                                          values=["khao_hom — น้องข้าวหอม (เด็กหญิงผมบันคู่)",
                                                  "ton_kla — น้องต้นกล้า (เด็กชายผมหน้าม้า)",
                                                  "bunny — ปุยฝ้าย (กระต่ายพาสเทล)",
                                                  "bear — โกโก้ (หมีน้อยพาสเทล)"])
        self.chibi_char_cb.pack(fill="x")

        box_c_scene = tk.Frame(row_c1, bg="#FAF8FF")
        box_c_scene.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        tk.Label(box_c_scene, text="ฉากหลัง 3D:", font=(self.F, 8), fg="#645579", bg="#FAF8FF").pack(anchor="w")
        self.chibi_scene_val = tk.StringVar(value="garden_house — บ้านสวนพาสเทล")
        self.chibi_scene_cb = ttk.Combobox(box_c_scene, textvariable=self.chibi_scene_val, state="readonly",
                                           values=["garden_house — บ้านสวนพาสเทล",
                                                   "fairy_forest — ป่าเวทมนตร์น่ารัก",
                                                   "school_classroom — โรงเรียนแสนสนุก",
                                                   "fantasy_town — เมืองแฟนตาซีพาสเทล"])
        self.chibi_scene_cb.pack(fill="x")

        # Row 2: Action & Palette
        row_c2 = tk.Frame(self.f_chibi_sec, bg="#FAF8FF")
        row_c2.pack(fill="x", pady=(4, 2))
        row_c2.columnconfigure(0, weight=1, uniform="c_col")
        row_c2.columnconfigure(1, weight=1, uniform="c_col")

        box_c_act = tk.Frame(row_c2, bg="#FAF8FF")
        box_c_act.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        tk.Label(box_c_act, text="ท่าทางตัวละคร:", font=(self.F, 8), fg="#645579", bg="#FAF8FF").pack(anchor="w")
        self.chibi_action_val = tk.StringVar(value="wave — โบกมือทักทาย")
        self.chibi_action_cb = ttk.Combobox(box_c_act, textvariable=self.chibi_action_val, state="readonly",
                                            values=["wave — โบกมือทักทาย",
                                                    "walk — เดินเล่นชมวิว",
                                                    "jump — กระโดดดีใจ",
                                                    "talk — พูดคุยสดใส",
                                                    "idle — ยืนน่ารักกระพริบตา"])
        self.chibi_action_cb.pack(fill="x")

        box_c_pal = tk.Frame(row_c2, bg="#FAF8FF")
        box_c_pal.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        tk.Label(box_c_pal, text="โทนสีพาสเทล:", font=(self.F, 8), fg="#645579", bg="#FAF8FF").pack(anchor="w")
        self.chibi_preset_val = tk.StringVar(value="sweet_candy — Sweet Candy (ชมพู+มิ้นต์)")
        self.chibi_preset_cb = ttk.Combobox(box_c_pal, textvariable=self.chibi_preset_val, state="readonly",
                                            values=["sweet_candy — Sweet Candy (ชมพู+มิ้นต์)",
                                                    "lavender_dream — Lavender Dream (ม่วงพาสเทล+พีช)",
                                                    "warm_sunshine — Warm Sunshine (พีช+มิ้นต์อบอุ่น)"])
        self.chibi_preset_cb.pack(fill="x")

        # 3D Cinematic Cartoon Sub-Panel
        self.f_cinematic_sec = tk.Frame(self.f_type_sec, bg="#F0F8FF", highlightbackground="#B8DCF8", highlightthickness=1, padx=8, pady=6)
        lbl_cine_head = tk.Label(self.f_cinematic_sec, text="🎬 พรีเซ็ต 3D Cinematic (สัตว์ 3D แสงภาพยนตร์สมจริง)", font=(self.F, 9, "bold"), fg="#1A4A7A", bg="#F0F8FF")
        lbl_cine_head.pack(anchor="w", pady=(0, 4))

        row_cine1 = tk.Frame(self.f_cinematic_sec, bg="#F0F8FF")
        row_cine1.pack(fill="x", pady=2)
        row_cine1.columnconfigure(0, weight=1, uniform="cine_col")
        row_cine1.columnconfigure(1, weight=1, uniform="cine_col")

        box_cine_char = tk.Frame(row_cine1, bg="#F0F8FF")
        box_cine_char.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        tk.Label(box_cine_char, text="สัตว์ 3D:", font=(self.F, 8), fg="#486581", bg="#F0F8FF").pack(anchor="w")
        self.cinematic_char_val = tk.StringVar(value="tropical_fish — ปลาน้อยนีโม่ (Tropical Clownfish)")
        self.cinematic_char_cb = ttk.Combobox(box_cine_char, textvariable=self.cinematic_char_val, state="readonly",
                                             values=["tropical_fish — ปลาน้อยนีโม่ (Tropical Clownfish)",
                                                     "kitten — ลูกแมวน้อยส้ม (Golden Furry Kitten)",
                                                     "chick — ลูกเจี๊ยบปุกปุย (Fluffy Yellow Chick)",
                                                     "bunny — กระต่ายหิมะ (Cute Fluffy Bunny)"])
        self.cinematic_char_cb.pack(fill="x")

        box_cine_scene = tk.Frame(row_cine1, bg="#F0F8FF")
        box_cine_scene.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        tk.Label(box_cine_scene, text="ฉากภาพยนตร์:", font=(self.F, 8), fg="#486581", bg="#F0F8FF").pack(anchor="w")
        self.cinematic_scene_val = tk.StringVar(value="underwater — โลกใต้ทะเลสีคราม (Coral Reef)")
        self.cinematic_scene_cb = ttk.Combobox(box_cine_scene, textvariable=self.cinematic_scene_val, state="readonly",
                                              values=["underwater — โลกใต้ทะเลสีคราม (Coral Reef)",
                                                      "beach — ชายหาดทรอปิคอล (Sunny Beach)",
                                                      "sunlit_forest — ป่าธรรมชาติแสงทอง (Sunlit Forest)"])
        self.cinematic_scene_cb.pack(fill="x")

        row_cine2 = tk.Frame(self.f_cinematic_sec, bg="#F0F8FF")
        row_cine2.pack(fill="x", pady=(4, 2))
        row_cine2.columnconfigure(0, weight=1, uniform="cine_col")
        row_cine2.columnconfigure(1, weight=1, uniform="cine_col")

        box_cine_act = tk.Frame(row_cine2, bg="#F0F8FF")
        box_cine_act.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        tk.Label(box_cine_act, text="การเคลื่อนไหว (Motion):", font=(self.F, 8), fg="#486581", bg="#F0F8FF").pack(anchor="w")
        self.cinematic_action_val = tk.StringVar(value="swimming — ว่ายน้ำพริ้วไหวธรรมชาติ")
        self.cinematic_action_cb = ttk.Combobox(box_cine_act, textvariable=self.cinematic_action_val, state="readonly",
                                               values=["swimming — ว่ายน้ำพริ้วไหวธรรมชาติ",
                                                       "walking — เดินเล่นชมวิว",
                                                       "running — วิ่งเล่นร่าเริง",
                                                       "jumping — กระโดดดีใจ"])
        self.cinematic_action_cb.pack(fill="x")

        box_cine_cam = tk.Frame(row_cine2, bg="#F0F8FF")
        box_cine_cam.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        tk.Label(box_cine_cam, text="แสง & มุมกล้อง:", font=(self.F, 8), fg="#486581", bg="#F0F8FF").pack(anchor="w")
        self.cinematic_cam_val = tk.StringVar(value="cinematic_orbit — กล้องหมุนภาพยนตร์ (Orbit Pan)")
        self.cinematic_cam_cb = ttk.Combobox(box_cine_cam, textvariable=self.cinematic_cam_val, state="readonly",
                                             values=["cinematic_orbit — กล้องหมุนภาพยนตร์ (Orbit Pan)",
                                                     "dolly_tracking — กล้องดอลลี่ติดตาม (Dolly Track)"])
        self.cinematic_cam_cb.pack(fill="x")

        # Cute Toy Product Ad Sub-Panel
        self.f_toy_ad_sec = tk.Frame(self.f_type_sec, bg="#FFF8F2", highlightbackground="#F8D8B8", highlightthickness=1, padx=8, pady=6)
        lbl_toy_head = tk.Label(self.f_toy_ad_sec, text="🧸 พรีเซ็ต 3D Toy Product Ad (ฟิกเกอร์โฆษณาสินค้า DoF)", font=(self.F, 9, "bold"), fg="#8A3E00", bg="#FFF8F2")
        lbl_toy_head.pack(anchor="w", pady=(0, 4))

        row_toy1 = tk.Frame(self.f_toy_ad_sec, bg="#FFF8F2")
        row_toy1.pack(fill="x", pady=2)
        row_toy1.columnconfigure(0, weight=1, uniform="toy_col")
        row_toy1.columnconfigure(1, weight=1, uniform="toy_col")

        box_toy_char = tk.Frame(row_toy1, bg="#FFF8F2")
        box_toy_char.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        tk.Label(box_toy_char, text="ฟิกเกอร์มาสคอต:", font=(self.F, 8), fg="#7A5230", bg="#FFF8F2").pack(anchor="w")
        self.toy_char_val = tk.StringVar(value="vinyl_bear — น้องหมีไวนิลพาสเทล (Glossy Bear)")
        self.toy_char_cb = ttk.Combobox(box_toy_char, textvariable=self.toy_char_val, state="readonly",
                                        values=["vinyl_bear — น้องหมีไวนิลพาสเทล (Glossy Bear)",
                                                "vinyl_bunny — น้องกระต่ายป๊อปมาร์ท (Pop Bunny)",
                                                "vinyl_cat — น้องแมวกวักนำโชค (Lucky Cat)"])
        self.toy_char_cb.pack(fill="x")

        box_toy_scene = tk.Frame(row_toy1, bg="#FFF8F2")
        box_toy_scene.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        tk.Label(box_toy_scene, text="ฉากสตูดิโอ:", font=(self.F, 8), fg="#7A5230", bg="#FFF8F2").pack(anchor="w")
        self.toy_scene_val = tk.StringVar(value="cozy_desk — โต๊ะสตูดิโอแสงธรรมชาติ DoF")
        self.toy_scene_cb = ttk.Combobox(box_toy_scene, textvariable=self.toy_scene_val, state="readonly",
                                         values=["cozy_desk — โต๊ะสตูดิโอแสงธรรมชาติ DoF",
                                                 "pastel_room — ห้องพาสเทลมินิมอล"])
        self.toy_scene_cb.pack(fill="x")

        # Row 2: Product Image Picker
        row_toy2 = tk.Frame(self.f_toy_ad_sec, bg="#FFF8F2")
        row_toy2.pack(fill="x", pady=(3, 2))
        tk.Label(row_toy2, text="รูปสินค้าจริง (แสดงบนแท่นหมุน 3D):", font=(self.F, 8), fg="#7A5230", bg="#FFF8F2").pack(anchor="w")
        row_toy_pick = tk.Frame(row_toy2, bg="#FFF8F2")
        row_toy_pick.pack(fill="x")
        self.toy_prod_img_val = tk.StringVar()
        self.toy_prod_img_ent = ttk.Entry(row_toy_pick, textvariable=self.toy_prod_img_val)
        self.toy_prod_img_ent.pack(side="left", fill="x", expand=True, padx=(0, 4))
        btn_pick_prod = ttk.Button(row_toy_pick, text="เลือกไฟล์...", command=self._browse_toy_product_image)
        btn_pick_prod.pack(side="right")

        # Row 3: Price, Promo, CTA
        row_toy3 = tk.Frame(self.f_toy_ad_sec, bg="#FFF8F2")
        row_toy3.pack(fill="x", pady=(3, 2))
        row_toy3.columnconfigure(0, weight=1, uniform="toy_col3")
        row_toy3.columnconfigure(1, weight=1, uniform="toy_col3")
        row_toy3.columnconfigure(2, weight=1, uniform="toy_col3")

        box_price = tk.Frame(row_toy3, bg="#FFF8F2")
        box_price.grid(row=0, column=0, sticky="ew", padx=(0, 2))
        tk.Label(box_price, text="ป้ายราคา:", font=(self.F, 8), fg="#7A5230", bg="#FFF8F2").pack(anchor="w")
        self.toy_price_val = tk.StringVar(value="฿99")
        ttk.Entry(box_price, textvariable=self.toy_price_val).pack(fill="x")

        box_promo = tk.Frame(row_toy3, bg="#FFF8F2")
        box_promo.grid(row=0, column=1, sticky="ew", padx=(2, 2))
        tk.Label(box_promo, text="โปรโมชั่น:", font=(self.F, 8), fg="#7A5230", bg="#FFF8F2").pack(anchor="w")
        self.toy_promo_val = tk.StringVar(value="ลด 50% ส่งฟรี")
        ttk.Entry(box_promo, textvariable=self.toy_promo_val).pack(fill="x")

        box_cta = tk.Frame(row_toy3, bg="#FFF8F2")
        box_cta.grid(row=0, column=2, sticky="ew", padx=(2, 0))
        tk.Label(box_cta, text="ปุ่มสั่งซื้อ:", font=(self.F, 8), fg="#7A5230", bg="#FFF8F2").pack(anchor="w")
        self.toy_cta_val = tk.StringVar(value="🛒 สั่งซื้อที่ตะกร้าเหลือง")
        ttk.Entry(box_cta, textvariable=self.toy_cta_val).pack(fill="x")

        # --- D. เลือกคุณภาพวิดีโอ ---
        self.f_qual_sec = ttk.Frame(panel)
        self.f_qual_sec.pack(fill="x", pady=(6, 4))
        ttk.Label(self.f_qual_sec, text="D. คุณภาพวิดีโอ (Quality & Format):", font=(self.F, 10, "bold")).pack(anchor="w", pady=(0, 4))

        row_res_fps = ttk.Frame(self.f_qual_sec)
        row_res_fps.pack(fill="x", pady=2)
        row_res_fps.columnconfigure(0, weight=1, uniform="qual_col")
        row_res_fps.columnconfigure(1, weight=1, uniform="qual_col")

        # Resolution
        box_res = ttk.Frame(row_res_fps)
        box_res.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        tk.Label(box_res, text="ความละเอียด:", fg="#7C7895", bg="#FFFFFF").pack(anchor="w")
        self.anim_res_val = tk.StringVar(value="1080p (Full HD)")
        self.anim_res_cb = ttk.Combobox(box_res, textvariable=self.anim_res_val, state="readonly",
                                        values=["1080p (Full HD)", "720p (HD)", "480p (SD)", "4K (Ultra HD)"])
        self.anim_res_cb.pack(fill="x")

        # FPS
        box_fps = ttk.Frame(row_res_fps)
        box_fps.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ttk.Label(box_fps, text="อัตราเฟรม (FPS):", style="Muted.TLabel").pack(anchor="w")
        self.anim_fps_val = tk.StringVar(value="24 FPS (แอนิเมชันมาตรฐาน)")
        self.anim_fps_cb = ttk.Combobox(box_fps, textvariable=self.anim_fps_val, state="readonly",
                                        values=["24 FPS (แอนิเมชันมาตรฐาน)", "30 FPS (ลื่นไหล)", "12 FPS (คลาสสิก)"])
        self.anim_fps_cb.pack(fill="x")

        # Aspect Ratio
        box_aspect = ttk.Frame(self.f_qual_sec)
        box_aspect.pack(fill="x", pady=(4, 2))
        ttk.Label(box_aspect, text="รูปแบบภาพ (Aspect Ratio):", style="Muted.TLabel").pack(anchor="w")
        self.anim_aspect_val = tk.StringVar(value="16:9 แนวนอน (YouTube)")
        self.anim_aspect_cb = ttk.Combobox(box_aspect, textvariable=self.anim_aspect_val, state="readonly",
                                           values=["16:9 แนวนอน (YouTube)", "9:16 แนวตั้ง (TikTok / Shorts)",
                                                   "1:1 สี่เหลี่ยมจัตุรัส", "ทั้งสองแบบ (16:9 + 9:16)"])
        self.anim_aspect_cb.pack(fill="x")

        # Populate Hardware Telemetry
        self._populate_hardware_panel()
        self._on_anim_platform_selected()

    def _populate_hardware_panel(self):
        try:
            from . import hardware
            hw = hardware.detect_hardware()
            self._hw_info = hw
            devices = hw.get("devices", [])
            self._anim_device_map = {}
            dev_labels = []
            for d in devices:
                label = f"{d['label']} — {d['status'].split('(')[0].strip()}"
                self._anim_device_map[label] = d
                dev_labels.append(label)

            self.anim_device_cb.configure(values=dev_labels)
            if dev_labels:
                self.anim_device_cb.current(0)
                self._on_anim_device_selected()

            # Engine list
            engines = hw.get("engines", {})
            self._anim_engine_map = {}
            eng_labels = []
            for k, e in engines.items():
                label = f"{e['name']} — {e['status'].split('(')[0].strip()}"
                self._anim_engine_map[label] = (k, e)
                eng_labels.append(label)

            self.anim_engine_cb.configure(values=eng_labels)
            if eng_labels:
                self.anim_engine_cb.current(0)
                self._on_anim_engine_selected()
        except Exception as e:
            self.anim_device_status_lbl.configure(text=f"ตรวจฮาร์ดแวร์ขัดข้อง: {e}")

    def _get_selected_platform_and_format(self):
        raw = self.anim_platform_val.get() if hasattr(self, "anim_platform_val") else "TikTok"
        if "Shorts" in raw:
            return "youtube", "vertical"
        elif "YouTube" in raw:
            return "youtube", "horizontal"
        elif "Page" in raw:
            return "facebook_page", "vertical"
        elif "ส่วนตัว" in raw:
            return "facebook_profile", "vertical"
        elif "Shopee" in raw:
            return "shopee", "vertical"
        else:
            return "tiktok", "vertical"

    def _on_anim_platform_selected(self, event=None):
        raw = self.anim_platform_val.get() if hasattr(self, "anim_platform_val") else "TikTok"
        mode = self.anim_mode.get() if hasattr(self, "anim_mode") else "local"
        plat_name = raw.split("(")[0].strip()

        if "TikTok" in raw:
            desc = "วิดีโอแนวตั้ง 9:16 สำหรับ TikTok"
            aspect = "9:16 แนวตั้ง (TikTok / Shorts)"
        elif "Shorts" in raw:
            desc = "วิดีโอสั้นแนวตั้ง 9:16 สำหรับ YouTube Shorts"
            aspect = "9:16 แนวตั้ง (TikTok / Shorts)"
        elif "YouTube" in raw:
            desc = "วิดีโอแนวนอน 16:9 สำหรับ YouTube มาตรฐาน"
            aspect = "16:9 แนวนอน (YouTube)"
        elif "Page" in raw:
            desc = "วิดีโอแนวตั้ง 9:16 สำหรับ Facebook Page Reels"
            aspect = "9:16 แนวตั้ง (TikTok / Shorts)"
        elif "ส่วนตัว" in raw:
            desc = "วิดีโอแนวตั้ง 9:16 สำหรับ Facebook Profile"
            aspect = "9:16 แนวตั้ง (TikTok / Shorts)"
        elif "Shopee" in raw:
            desc = "วิดีโอแนวตั้ง 9:16 สำหรับ Shopee Video"
            aspect = "9:16 แนวตั้ง (TikTok / Shorts)"
        else:
            desc = ""
            aspect = "16:9 แนวนอน (YouTube)"

        if mode == "flow":
            self.anim_platform_status_lbl.configure(
                text=f"Google Flow: จะส่งบทไปที่ Workspace ของ {plat_name} และเปิด Google Flow")
            self.btn_render_clip.configure(text=f"✦  สร้างด้วย Google Flow ({plat_name})")
        else:
            self.anim_platform_status_lbl.configure(text=desc)
            if hasattr(self, "anim_aspect_val") and aspect:
                self.anim_aspect_val.set(aspect)

    def _on_anim_mode_changed(self):
        mode = self.anim_mode.get()
        raw = self.anim_platform_val.get() if hasattr(self, "anim_platform_val") else "TikTok"
        plat_name = raw.split("(")[0].strip()

        if mode == "flow":
            # Flow mode: Hide hardware / engine / resolution sections that don't apply to cloud
            self.f_device_sec.pack_forget()
            self.f_type_sec.pack_forget()
            self.f_qual_sec.pack_forget()

            self.anim_platform_status_lbl.configure(
                text=f"ระบบ Cloud: Google Flow จัดการ Generate แอนิเมชัน • จะส่งบทไปที่ Workspace ของ {plat_name}")
            self.btn_render_clip.configure(text=f"✦  สร้างด้วย Google Flow ({plat_name})")
        else:
            # Local mode: Re-pack hardware / engine / resolution sections
            self.f_device_sec.pack(fill="x", pady=(6, 8))
            self.f_type_sec.pack(fill="x", pady=(6, 8))
            self.f_qual_sec.pack(fill="x", pady=(6, 4))

            self.btn_render_clip.configure(text="▶  สร้างคลิปในเครื่อง (Local Animation)")
            self.anim_device_cb.configure(state="readonly")
            self.anim_engine_cb.configure(state="readonly")
            self.anim_res_cb.configure(state="readonly")
            self.anim_fps_cb.configure(state="readonly")
            self._on_anim_device_selected()
            self._on_anim_engine_selected()
            self._on_anim_platform_selected()

    def _on_anim_device_selected(self, event=None):
        label = self.anim_device_val.get()
        dev = getattr(self, "_anim_device_map", {}).get(label)
        if dev:
            status_text = f"สถานะ: {dev.get('status')} | {dev.get('details', '')}"
            self.anim_device_status_lbl.configure(text=status_text)

    def _browse_toy_product_image(self):
        from tkinter import filedialog
        f = filedialog.askopenfilename(
            title="เลือกรูปสินค้าจริง (Product Image)",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.webp"), ("All files", "*.*")]
        )
        if f:
            self.toy_prod_img_val.set(f)

    def _on_anim_engine_selected(self, event=None):
        label = self.anim_engine_val.get()
        item = getattr(self, "_anim_engine_map", {}).get(label)
        if item:
            k, e = item
            self.anim_engine_status_lbl.configure(text=f"{e.get('description', '')} ({e.get('status')})")

            is_chibi = (k == "3d_chibi_pastel" or "Chibi" in label)
            is_cinematic = (k == "3d_cinematic_cartoon" or "Cinematic" in label)
            is_toy_ad = (k == "cute_toy_ad" or "Toy" in label or "โฆษณา" in label)

            if hasattr(self, "f_chibi_sec"):
                if is_chibi:
                    self.f_chibi_sec.pack(fill="x", pady=(4, 2))
                else:
                    self.f_chibi_sec.pack_forget()

            if hasattr(self, "f_cinematic_sec"):
                if is_cinematic:
                    self.f_cinematic_sec.pack(fill="x", pady=(4, 2))
                else:
                    self.f_cinematic_sec.pack_forget()

            if hasattr(self, "f_toy_ad_sec"):
                if is_toy_ad:
                    self.f_toy_ad_sec.pack(fill="x", pady=(4, 2))
                else:
                    self.f_toy_ad_sec.pack_forget()

    def _open_created_folder(self):
        folder = getattr(self, "_created_folder", None)
        if not folder or not Path(folder).exists():
            today_out = ROOT / "output" / dt.date.today().isoformat()
            folder = today_out if today_out.exists() else ROOT / "output"
        try:
            if IS_WIN:
                os.startfile(str(folder))
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as e:
            messagebox.showinfo("เปิดโฟลเดอร์", f"ไม่สามารถเปิดโฟลเดอร์ได้: {e}")

    def _play_created_clip(self):
        folder = getattr(self, "_created_folder", None)
        if not folder or not Path(folder).exists():
            messagebox.showinfo("เปิดคลิป", "ยังไม่พบโฟลเดอร์คลิปที่สร้างเสร็จ")
            return
        mp4s = sorted(Path(folder).glob("*.mp4"))
        if not mp4s:
            messagebox.showinfo("เปิดคลิป", f"ยังไม่พบคลิป .mp4 ในโฟลเดอร์ {folder}")
            return
        target = mp4s[0]
        for m in mp4s:
            if "vertical" in m.name:
                target = m
                break
        try:
            if IS_WIN:
                os.startfile(str(target))
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except Exception as e:
            messagebox.showinfo("เปิดคลิป", f"ไม่สามารถเปิดคลิปได้: {e}")

    def _inbox(self):
        d = ROOT / "scripts" / "inbox"
        d.mkdir(parents=True, exist_ok=True)
        return sorted(d.glob("*.json"))

    def refresh_scripts(self):
        self.tv_s.delete(*self.tv_s.get_children())
        self._script_cache = {}
        for p in self._inbox():
            try:
                sc = scriptmod.load(p)
                err, warn = scriptmod.validate(sc)
                chars = ", ".join(CHAR_NAMES.get(c, c).split(" ")[0] for c in sc.get("characters", []))
                check = "ผ่าน" if not err and not warn else ("มีคำเตือน %d" % len(warn) if not err
                                                            else "ผิด %d จุด" % len(err))
                tag = "bad" if err else ("warn" if warn else "")
                try:
                    date_str = dt.datetime.fromtimestamp(p.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
                except Exception:
                    date_str = "-"
                self.tv_s.insert("", "end", iid=str(p), values=(sc.get("title", p.stem), chars, check, date_str), tags=(tag,))
                self._script_cache[str(p)] = (sc, err, warn)
            except Exception as e:
                self.tv_s.insert("", "end", iid=str(p), values=(p.name, "-", "อ่านไฟล์ไม่ได้", "-"), tags=("bad",))
                self._script_cache[str(p)] = (None, [str(e)], [])

    def _sel_scripts(self):
        return [Path(i) for i in self.tv_s.selection()]

    def send_script_to_flow(self):
        selected = self._sel_scripts()
        if len(selected) != 1:
            messagebox.showinfo("Google Flow", "เลือกบท 1 เรื่องก่อน")
            return
        script_path = selected[0]
        sc, errors, _ = self._script_cache.get(str(script_path), (None, ["อ่านบทไม่ได้"], []))
        if sc is None or errors:
            messagebox.showwarning("Google Flow", "บทนี้ยังมีจุดผิด กรุณาแก้ไขบทก่อน")
            return
        platform, fmt = self._get_selected_platform_and_format()
        ui = self.platform_ui.get(platform)
        if not ui:
            messagebox.showerror("Google Flow", f"ไม่พบ Workspace ของแพลตฟอร์ม {platform}")
            return
        choice = next((name for name, path in ui["script_map"].items() if path == script_path), None)
        if choice is None:
            self.refresh_platform_workspaces()
            choice = next((name for name, path in ui["script_map"].items() if path == script_path), None)
        if choice is None:
            messagebox.showerror("Google Flow", "ไม่พบบทที่เลือกในหน้าสร้างและโพสต์")
            return
        ui["script"].set(choice)
        ui["format"].set(fmt)
        ui["source"].set("flow")
        self._platform_story_changed(platform, True)
        self._platform_source_changed(platform)
        self._select_platform(platform)
        self.nb.select(self.tab_platforms)
        self.platform_open_flow(platform)

    def show_script(self):
        sel = self._sel_scripts()
        if not sel:
            return
        sc, err, warn = self._script_cache.get(str(sel[0]), (None, [], []))
        if sc is None:
            self.s_info.configure(text="ไฟล์นี้อ่านไม่ได้:\n" + "\n".join(err))
            return
        lines = sum(1 for s in sc.get("scenes", []) for b in s.get("beats", []) if b.get("say"))
        if hasattr(self, "lbl_s_detail_title"):
            self.lbl_s_detail_title.configure(text=sc.get("title", sel[0].stem))
        if hasattr(self, "anim_card_title") and not getattr(self, "proc", None):
            self.anim_card_title.configure(text=f"พร้อมสร้างคลิป: {sc.get('title', sel[0].stem)}")
            if hasattr(self, "anim_card_meta"):
                self.anim_card_meta.configure(text=f"เลือก {sel[0].stem} • กด ▶ สร้างคลิปในเครื่อง เพื่อเริ่ม")
        if hasattr(self, "lbl_s_detail_cat"):
            self.lbl_s_detail_cat.configure(text=f"หมวดหมู่ {sc.get('genre', 'ธรรมชาติ / การ์ตูนเด็ก')}")
        if hasattr(self, "lbl_s_detail_len"):
            self.lbl_s_detail_len.configure(text=f"🕒 ความยาวโดยประมาณ {max(1, lines // 4)} นาที")
        if hasattr(self, "lbl_s_count"):
            self.lbl_s_count.configure(text=f"เลือกแล้ว {len(sel)} รายการ")
        if hasattr(self, "_script_banner_img") and self._script_banner_img and hasattr(self, "s_preview"):
            self.s_preview.configure(image=self._script_banner_img)

        desc = sc.get("description", "")
        if not desc:
            desc = f"การผจญภัยของตัวละครในเรื่อง {sc.get('title', sel[0].stem)} มีทั้งหมด {len(sc.get('scenes', []))} ฉาก และ {lines} บทพูด พร้อมภาพประกอบแอนิเมชันสำหรับเด็ก"
        if err:
            desc += "\n\nจุดที่ต้องแก้ไข:\n- " + "\n- ".join(err)
        if warn:
            desc += "\n\nคำเตือน:\n- " + "\n- ".join(warn)
        self.s_info.configure(text=desc)

    def import_scripts(self):
        files = filedialog.askopenfilenames(title="เลือกไฟล์บท", filetypes=[("บท TaoYongStudio", "*.json *.zip")])
        n = 0
        dst = ROOT / "scripts" / "inbox"
        for f in files:
            if f.lower().endswith(".zip"):
                import zipfile
                with zipfile.ZipFile(f) as z:
                    for name in z.namelist():
                        if name.lower().endswith(".json") and "/" not in name.strip("/"):
                            (dst / Path(name).name).write_bytes(z.read(name))
                            n += 1
            else:
                shutil.copy(f, dst / Path(f).name)
                n += 1
        if n:
            self.say("เพิ่มบท %d เรื่อง" % n, "good")
        self.refresh_all()

    def add_samples(self):
        for p in (ROOT / "scripts" / "samples").glob("*.json"):
            shutil.copy(p, ROOT / "scripts" / "inbox" / p.name)
        self.refresh_all()

    def edit_script(self):
        sel = self._sel_scripts()
        if not sel:
            return
        if IS_WIN:
            subprocess.Popen(["notepad.exe", str(sel[0])])
        else:
            open_path(sel[0])

    def remove_scripts(self):
        sel = self._sel_scripts()
        if not sel:
            messagebox.showinfo("ลบบท", "เลือกบททางซ้ายอย่างน้อย 1 เรื่องก่อน")
            return
        titles = []
        for p in sel:
            cached = self._script_cache.get(str(p))
            title = None
            if cached and cached[0]:
                title = cached[0].get("title")
            titles.append(title or p.name)

        if len(sel) == 1:
            msg = f"ต้องการลบบท '{titles[0]}' หรือไม่?\n\nไฟล์บทจะถูกย้ายไปที่ถังขยะของโปรแกรม (scripts\\removed)"
        else:
            sample = "\n- ".join(titles[:3])
            if len(titles) > 3:
                sample += f"\n... และอีก {len(titles)-3} เรื่อง"
            msg = f"ต้องการลบบทที่เลือกทั้งหมด {len(sel)} เรื่องหรือไม่?\n\n- {sample}\n\nไฟล์บทจะถูกย้ายไปที่ถังขยะของโปรแกรม (scripts\\removed)"

        if not messagebox.askyesno("ยืนยันการลบบท", msg, icon="warning"):
            return
        d = ROOT / "scripts" / "removed"
        d.mkdir(parents=True, exist_ok=True)
        deleted_count = 0
        for p in sel:
            try:
                dest = d / p.name
                if dest.exists():
                    dest = d / f"{p.stem}_{int(dt.datetime.now().timestamp())}{p.suffix}"
                shutil.move(str(p), str(dest))
                deleted_count += 1
            except Exception as e:
                messagebox.showerror("ลบบทขัดข้อง", f"ไม่สามารถลบ {p.name}: {e}")

        self.say(f"ลบบทเรียบร้อย {deleted_count} เรื่อง", "good")
        self.s_preview.configure(image="")
        self.s_info.configure(text="เลือกบททางซ้าย")
        self.refresh_all()

    def preview_script(self):
        sel = self._sel_scripts()
        if not sel:
            return
        sc, err, _ = self._script_cache.get(str(sel[0]), (None, ["?"], []))
        if err:
            messagebox.showwarning("ดูภาพตัวอย่าง", "บทนี้ยังมีจุดผิด แก้ก่อนนะครับ")
            return
        self.say("กำลังวาดภาพตัวอย่าง...")

        def work():
            try:
                from .episode import Episode
                c = dict(self.cfg)
                c["tts"] = dict(c["tts"], engines=["silent"])
                c["allow_test_voice"] = True
                ep = Episode(sc, c, lambda m: None).build()
                t = None
                for s in ep.scenes:
                    if s.kind == "scene" and s.lines:
                        t = s.lines[min(2, len(s.lines) - 1)].end - 0.2
                        break
                im = ep.still("vertical", t or 3.0)
                self.q.put(("preview", im))
            except Exception as e:
                self.q.put(("log", ("ภาพตัวอย่างไม่สำเร็จ: %s" % e, "bad")))

        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------------ clips tab
    def _build_clips(self):
        t = self.tab_clips

        # ---------------- TOP HEADER CARD ----------------
        hdr_card = tk.Frame(t, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        hdr_card.pack(fill="x", pady=(0, 10))

        hdr_inner = tk.Frame(hdr_card, bg="#FFFFFF", padx=16, pady=12)
        hdr_inner.pack(fill="x")

        hdr_icon_box = tk.Frame(hdr_inner, bg="#F0EBFF", width=42, height=42)
        hdr_icon_box.pack_propagate(False)
        hdr_icon_box.pack(side="left", padx=(0, 12))
        tk.Label(hdr_icon_box, text="🎬", font=(self.F, 18), bg="#F0EBFF").pack(expand=True)

        hdr_titles = tk.Frame(hdr_inner, bg="#FFFFFF")
        hdr_titles.pack(side="left", fill="x", expand=True)
        tk.Label(hdr_titles, text="คลังคลิปวิดีโอที่สร้างแล้ว (Clips Library)", font=(self.F, 13, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")
        tk.Label(hdr_titles, text="ตรวจทานคลิป ดูตัวอย่าง อนุมัติ และสั่งโพสต์อัตโนมัติไปยังทุกช่องทาง",
                 font=(self.F, 9), fg="#7C7895", bg="#FFFFFF").pack(anchor="w", pady=(2, 0))

        # Filter and actions on right
        h_right = tk.Frame(hdr_inner, bg="#FFFFFF")
        h_right.pack(side="right")

        tk.Label(h_right, text="แสดง:", font=(self.F, 9, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left", padx=(0, 4))
        self.clip_filter = tk.StringVar(value="ทั้งหมด")
        cb = ttk.Combobox(h_right, textvariable=self.clip_filter, state="readonly", width=12,
                          values=["ทั้งหมด", "รอตรวจ", "อนุมัติแล้ว", "โพสต์แล้ว", "ไม่ใช้"])
        cb.pack(side="left", padx=(0, 8))
        cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_clips())

        tk.Button(
            h_right,
            text="🔄 รีเฟรช",
            font=(self.F, 8, "bold"),
            bg="#F0EBFF",
            fg="#6C47FF",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=10,
            pady=4,
            command=self.refresh_clips
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            h_right,
            text="🗑 ลบคลิป",
            font=(self.F, 8),
            bg="#FFF5F5",
            fg="#EF4444",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=8,
            pady=4,
            command=self.remove_clips
        ).pack(side="left")

        # Main Body: Left Treeview + Right Preview Card
        body = tk.Frame(t, bg=BG)
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightthickness=1, bd=0)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # bottom box under the list: shows what the app is doing right now (progress bar + live log)
        self.clip_dock = tk.Frame(left, bg="#F0ECFD", highlightbackground="#D8CEF8", highlightthickness=1, bd=0)
        self.clip_dock.pack(side="bottom", fill="x", padx=2, pady=(0, 2))

        cols = ("date", "title", "dur", "status", "posts")
        self.tv_c = ttk.Treeview(left, columns=cols, show="headings", selectmode="extended")
        for c, w, txt, anc in (("date", 90, "วันที่", "w"), ("title", 420, "ชื่อเรื่อง", "w"),
                               ("dur", 65, "ความยาว", "center"), ("status", 100, "สถานะ", "w"),
                               ("posts", 100, "โพสต์แล้ว", "w")):
            self.tv_c.heading(c, text=txt)
            self.tv_c.column(c, width=w, anchor=anc)
        self.tv_c.pack(fill="both", expand=True, padx=2, pady=2)
        self.tv_c.tag_configure("warn", foreground=WARN)
        self.tv_c.tag_configure("posted", foreground=GOOD)
        self.tv_c.tag_configure("rejected", foreground="#9C95AE")
        self.tv_c.bind("<<TreeviewSelect>>", lambda e: self.show_clip())
        self.tv_c.bind("<Double-1>", lambda e: self.play_clip("vertical"))
        self.tv_c.bind("<Delete>", lambda e: self.remove_clips())

        # Right-click context menu
        menu_c = tk.Menu(self.tv_c, tearoff=0)
        menu_c.add_command(label="▶ เล่นแนวตั้ง (TikTok)", command=lambda: self.play_clip("vertical"))
        menu_c.add_command(label="▶ เล่นแนวนอน (YouTube)", command=lambda: self.play_clip("horizontal"))
        menu_c.add_command(label="📋 คัดลอกข้อความโพสต์", command=self.copy_upload)
        menu_c.add_command(label="📂 เปิดโฟลเดอร์คลิป", command=self.open_clip_folder)
        menu_c.add_separator()
        menu_c.add_command(label="🗑 ลบคลิปที่เลือก", command=self.remove_clips)

        def _on_c_right_click(event):
            item = self.tv_c.identify_row(event.y)
            if item:
                if item not in self.tv_c.selection():
                    self.tv_c.selection_set(item)
                    self.show_clip()
                menu_c.post(event.x_root, event.y_root)

        self.tv_c.bind("<Button-3>", _on_c_right_click)

        # Right Preview Card
        right = tk.Frame(body, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightthickness=1, bd=0, width=460)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        r_inner = tk.Frame(right, bg="#FFFFFF", padx=14, pady=12)
        r_inner.pack(fill="both", expand=True)

        topbox = tk.Frame(r_inner, bg="#FFFFFF")
        topbox.pack(side="top", fill="x")

        self.c_thumb = tk.Label(topbox, bg="#FAF8FD", highlightbackground="#EDE9FE", highlightthickness=1, bd=0)
        self.c_thumb.pack(side="left", anchor="n")

        self.c_info = tk.Label(topbox, text="เลือกคลิปทางซ้ายเพื่อดูรายละเอียด", font=(self.F, 9), fg="#7C7895", bg="#FFFFFF",
                               wraplength=270, justify="left", anchor="nw")
        self.c_info.pack(side="left", anchor="nw", fill="both", expand=True, padx=(10, 0))

        btns = tk.Frame(r_inner, bg="#FFFFFF")
        btns.pack(side="bottom", fill="x")

        # กรอบเล่นวิดีโอตัวอย่าง แบ่งครึ่งส่วนล่างต่อจากรูป พร้อมปุ่มขยายวิดีโอ
        self.c_player_box = tk.Frame(r_inner, bg="#0F0C1E", highlightbackground="#8E6CF7", highlightthickness=1, bd=0)

        self.c_player_hdr = tk.Frame(self.c_player_box, bg="#1E1738")
        self.c_player_hdr.pack(side="top", fill="x")

        self.c_player_title = tk.Label(self.c_player_hdr, text="🎬 กำลังเล่นวิดีโอตัวอย่าง", font=(self.F, 8, "bold"), fg="#EDE8FF", bg="#1E1738")
        self.c_player_title.pack(side="left", padx=8, pady=4)

        self.c_player_btn_close = tk.Button(self.c_player_hdr, text="✕ ปิด", font=(self.F, 8, "bold"), bg="#2E204E", fg="#FFA8A8",
                                            activebackground="#452F75", activeforeground="#FFD8D8", relief="flat", bd=0, padx=6, pady=2,
                                            cursor="hand2", command=self._stop_clip_player)
        self.c_player_btn_close.pack(side="right", padx=(2, 6), pady=3)

        self.c_player_btn_expand = tk.Button(self.c_player_hdr, text="⛶ ขยายวิดีโอ", font=(self.F, 8, "bold"), bg="#8E6CF7", fg="#FFFFFF",
                                             activebackground="#7C5CEF", relief="flat", bd=0, padx=8, pady=2,
                                             cursor="hand2", command=self.expand_video)
        self.c_player_btn_expand.pack(side="right", padx=2, pady=3)

        self.c_player_btn_replay = tk.Button(self.c_player_hdr, text="🔄 เล่นใหม่", font=(self.F, 8), bg="#2E204E", fg="#D5C4FF",
                                             activebackground="#452F75", activeforeground="#FFFFFF", relief="flat", bd=0, padx=6, pady=2,
                                             cursor="hand2", command=self._replay_current_video)
        self.c_player_btn_replay.pack(side="right", padx=2, pady=3)

        self.c_video_canvas = tk.Frame(self.c_player_box, bg="#000000")
        self.c_video_canvas.pack(fill="both", expand=True)
        self.c_video_canvas.bind("<Configure>", self._on_video_canvas_resize)

        # Play buttons
        r1 = tk.Frame(btns, bg="#FFFFFF")
        r1.pack(fill="x", pady=2)
        tk.Button(r1, text="▶ เล่นแนวตั้ง (TikTok)", font=(self.F, 8, "bold"), bg="#F0EBFF", fg="#6C47FF", relief="flat", bd=0, padx=6, pady=4, cursor="hand2", command=lambda: self.play_clip("vertical")).pack(side="left", expand=True, fill="x", padx=(0, 3))
        tk.Button(r1, text="▶ เล่นแนวนอน (YouTube)", font=(self.F, 8, "bold"), bg="#F0EBFF", fg="#6C47FF", relief="flat", bd=0, padx=6, pady=4, cursor="hand2", command=lambda: self.play_clip("horizontal")).pack(side="left", expand=True, fill="x", padx=(3, 0))

        # Copy & folder buttons
        tk.Button(btns, text="📋 คัดลอกชื่อเรื่อง + คำอธิบาย + แฮชแท็ก", font=(self.F, 9, "bold"), bg="#8E6CF7", fg="#FFFFFF", activebackground="#7C5CEF", relief="flat", bd=0, pady=6, cursor="hand2", command=self.copy_upload).pack(fill="x", pady=3)
        tk.Button(btns, text="📂 เปิดโฟลเดอร์คลิปนี้", font=(self.F, 8), bg="#FAF8FD", fg="#7C7895", relief="flat", bd=0, pady=4, cursor="hand2", command=self.open_clip_folder).pack(fill="x", pady=2)

        # Status approval buttons
        r2 = tk.Frame(btns, bg="#FFFFFF")
        r2.pack(fill="x", pady=4)
        self.clip_status_buttons = {}
        for status, label, bg_c, fg_c in (("approved", "✓ อนุมัติ", "#E8F8F0", "#0E9F6E"),
                                          ("posted", "โพสต์แล้ว", "#F0EBFF", "#6C47FF"),
                                          ("rejected", "ไม่ใช้", "#FFF5F5", "#EF4444")):
            btn = tk.Button(r2, text=label, font=(self.F, 8, "bold"), bg=bg_c, fg=fg_c, relief="flat", bd=0, padx=6, pady=4, cursor="hand2", command=lambda value=status: self.set_status(value))
            btn.pack(side="left", expand=True, fill="x", padx=2)
            self.clip_status_buttons[status] = btn

        tk.Label(btns, text="โพสต์คลิปนี้ตอนนี้:", font=(self.F, 8, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w", pady=(6, 2))

        # Platform quick post buttons
        r3 = tk.Frame(btns, bg="#FFFFFF")
        r3.pack(fill="x", pady=2)
        self.clip_post_buttons = {}
        for txt, plat in (("YouTube", "youtube"), ("FB Page", "facebook_page"), ("TikTok", "tiktok")):
            b = tk.Button(r3, text=txt, font=(self.F, 8), bg="#F8F6FD", fg="#2C1D63", relief="flat", bd=0, padx=4, pady=4, cursor="hand2", command=lambda p=plat: self.post_selected(p))
            b.pack(side="left", expand=True, fill="x", padx=2)
            self.clip_post_buttons[plat] = b

        tk.Button(btns, text="👤 Facebook ส่วนตัว (คัดลอก + เปิดเฟซบุ๊ก)", font=(self.F, 8), bg="#FAF8FD", fg="#2C1D63", relief="flat", bd=0, pady=4, cursor="hand2", command=self.post_profile_manual).pack(fill="x", pady=2)
        tk.Button(btns, text="🗑 ลบคลิปที่เลือก", font=(self.F, 8), bg="#FFF5F5", fg="#EF4444", relief="flat", bd=0, pady=4, cursor="hand2", command=self.remove_clips).pack(fill="x", pady=(2, 0))

    def _build_platforms(self):
        self.platform_ui = {}
        self.platform_nav = {}

        nav = tk.Frame(self.tab_platforms, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightthickness=1, bd=0)
        nav.pack(fill="x", pady=(0, 10))

        nav_inner = tk.Frame(nav, bg="#FFFFFF", padx=8, pady=6)
        nav_inner.pack(fill="x")

        body = tk.Frame(self.tab_platforms, bg=BG)
        body.pack(fill="both", expand=True)

        icons_map = {
            "tiktok": "🎵",
            "youtube": "📺",
            "shopee": "🛍️",
            "facebook_profile": "👤",
            "facebook_page": "📘",
        }

        for platform, label, default_fmt in WORKSPACES:
            index = len(self.platform_nav)
            nav_inner.columnconfigure(index, weight=1, uniform="platform")

            icon = icons_map.get(platform, "🎬")
            btn_text = f"{icon} {label}"

            button = tk.Button(
                nav_inner,
                text=btn_text,
                font=(self.F, 9, "bold"),
                bg="#FFFFFF",
                fg="#5A5174",
                activebackground="#8E6CF7",
                activeforeground="#FFFFFF",
                relief="flat",
                bd=0,
                cursor="hand2",
                padx=12,
                pady=6,
                command=lambda p=platform: self._select_platform(p)
            )
            button.grid(row=0, column=index, sticky="ew", padx=3)
            self.platform_nav[platform] = button

            page = tk.Frame(body, bg=BG)
            page.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._build_platform_workspace(page, platform, label, default_fmt)

        self._select_platform(WORKSPACES[0][0])

    def _select_platform(self, platform):
        self.active_platform = platform
        self.platform_ui[platform]["tab"].lift()
        for name, button in self.platform_nav.items():
            if name == platform:
                button.configure(bg="#8E6CF7", fg="#FFFFFF")
            else:
                button.configure(bg="#FFFFFF", fg="#5A5174")

    def _build_platform_workspace(self, tab, platform, label, default_fmt):
        ui = {"platform": platform, "current": None, "script_map": {}, "clip_map": {}}
        self.platform_ui[platform] = ui

        # Header card
        hdr_card = tk.Frame(tab, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightthickness=1, bd=0)
        hdr_card.pack(fill="x", pady=(0, 10))

        hdr_inner = tk.Frame(hdr_card, bg="#FFFFFF", padx=16, pady=10)
        hdr_inner.pack(fill="x")

        icons_map = {"tiktok": "🎵", "youtube": "📺", "shopee": "🛍️", "facebook_profile": "👤", "facebook_page": "📘"}
        ic = icons_map.get(platform, "🎬")

        hdr_icon_box = tk.Frame(hdr_inner, bg="#F0EBFF", width=38, height=38)
        hdr_icon_box.pack_propagate(False)
        hdr_icon_box.pack(side="left", padx=(0, 10))
        tk.Label(hdr_icon_box, text=ic, font=(self.F, 16), bg="#F0EBFF").pack(expand=True)

        hdr_titles = tk.Frame(hdr_inner, bg="#FFFFFF")
        hdr_titles.pack(side="left", fill="x", expand=True)

        tk.Label(hdr_titles, text=f"สร้างวิดีโอสำหรับ {label}", font=(self.F, 12, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")
        notes = {
            "tiktok": "แนวตั้ง 9:16 • ส่งเข้าแบบร่าง TikTok แล้วตรวจและกดโพสต์ในแอป",
            "youtube": "เลือกแนวตั้ง Shorts หรือแนวนอน • โพสต์ผ่าน YouTube API ที่เชื่อมไว้",
            "shopee": "แนวตั้ง 9:16 • เตรียมไฟล์และข้อความโปรโมทสินค้า Shopee Video พร้อมแคปชั่น",
            "facebook_profile": "แนวตั้ง 9:16 • คัดลอกข้อความและโพสต์บน Facebook Profile ด้วย RPA",
            "facebook_page": "แนวตั้ง 9:16 • โพสต์ Reels ผ่าน Facebook Page API ที่เชื่อมไว้"
        }
        tk.Label(hdr_titles, text=notes.get(platform, ""), font=(self.F, 8), fg="#7C7895", bg="#FFFFFF").pack(anchor="w", pady=(1, 0))

        # Scrollable container
        canvas = tk.Canvas(tab, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>", lambda e, p=platform, c=canvas:
                        c.yview_scroll(int(-e.delta / 120), "units")
                        if self.nb.select() == str(self.tab_platforms)
                        and self.active_platform == p else None, add="+")
        ui["tab"] = tab

        # Row 1: 2 Cards Side-by-Side (Story Setup on Left, Video Source on Right)
        grid_row = tk.Frame(inner, bg=BG)
        grid_row.pack(fill="x", pady=(0, 10))
        grid_row.columnconfigure(0, weight=1, uniform="plat_cards")
        grid_row.columnconfigure(1, weight=1, uniform="plat_cards")

        # ---------------- SETUP CARD ----------------
        setup = tk.Frame(grid_row, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightthickness=1, bd=0)
        setup.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        s_head = tk.Frame(setup, bg="#FFFFFF", padx=16, pady=14)
        s_head.pack(fill="x")
        tk.Label(s_head, text="1. เลือกเรื่อง และพนักงาน AI เตรียมข้อความ", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")

        s_body = tk.Frame(setup, bg="#FFFFFF", padx=16, pady=14)
        s_body.pack(fill="x")

        row_st = tk.Frame(s_body, bg="#FFFFFF")
        row_st.pack(fill="x", pady=(0, 6))
        tk.Label(row_st, text="เรื่อง:", font=(self.F, 9, "bold"), fg="#2C1D63", bg="#FFFFFF", width=6, anchor="w").pack(side="left")
        ui["script"] = tk.StringVar()
        ui["script_cb"] = ttk.Combobox(row_st, textvariable=ui["script"], state="readonly")
        ui["script_cb"].pack(side="left", fill="x", expand=True)
        ui["script_cb"].bind("<<ComboboxSelected>>", lambda e, p=platform: self._platform_story_changed(p, True))

        # Meta box
        meta_box = tk.Frame(s_body, bg="#FAF8FD", highlightbackground="#EDE9FE", highlightthickness=1, bd=0, padx=10, pady=8)
        meta_box.pack(fill="x", pady=(2, 8))

        tk.Label(meta_box, text="ข้อความโพสต์ที่เตรียมไว้:", font=(self.F, 8, "bold"), fg="#6C47FF", bg="#FAF8FD").pack(anchor="w", pady=(0, 2))
        ui["meta_title"] = tk.Label(meta_box, text="เลือกเรื่องหรือคลิป", font=(self.F, 9, "bold"), fg="#2C1D63", bg="#FAF8FD", wraplength=480, justify="left", anchor="w")
        ui["meta_title"].pack(anchor="w", fill="x")
        ui["meta_description"] = tk.Label(meta_box, text="", font=(self.F, 8), fg="#7C7895", bg="#FAF8FD", wraplength=480, justify="left", anchor="w")
        ui["meta_description"].pack(anchor="w", fill="x", pady=2)
        ui["meta_tags"] = tk.Label(meta_box, text="", font=(self.F, 8, "bold"), fg="#6C47FF", bg="#FAF8FD", wraplength=480, justify="left", anchor="w")
        ui["meta_tags"].pack(anchor="w", fill="x")

        row_fmt = tk.Frame(s_body, bg="#FFFFFF")
        row_fmt.pack(fill="x", pady=(4, 0))
        ui["format"] = tk.StringVar(value=default_fmt)
        tk.Label(row_fmt, text="รูปแบบ:", font=(self.F, 9, "bold"), fg="#2C1D63", bg="#FFFFFF", width=6, anchor="w").pack(side="left")
        formats = ("vertical", "horizontal") if platform == "youtube" else ("vertical",)
        format_cb = ttk.Combobox(row_fmt, textvariable=ui["format"], values=formats, width=14, state="readonly")
        format_cb.pack(side="left")
        format_cb.bind("<<ComboboxSelected>>", lambda e, p=platform: self._platform_story_changed(p, True))
        ui["made_for_kids"] = tk.BooleanVar(value=platform != "shopee")
        ttk.Checkbutton(row_fmt, text="สร้างมาเพื่อเด็ก", variable=ui["made_for_kids"]).pack(side="left", padx=12)

        # ---------------- SOURCE CARD ----------------
        source_card = tk.Frame(grid_row, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightthickness=1, bd=0)
        source_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        src_head = tk.Frame(source_card, bg="#FFFFFF", padx=16, pady=14)
        src_head.pack(fill="x")
        tk.Label(src_head, text="2. เลือกแหล่งวิดีโอ", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")

        src_body = tk.Frame(source_card, bg="#FFFFFF", padx=16, pady=14)
        src_body.pack(fill="x")

        choices = tk.Frame(src_body, bg="#FFFFFF")
        choices.pack(fill="x", pady=(0, 8))
        choices.columnconfigure(0, weight=1)
        choices.columnconfigure(1, weight=1)
        ui["source"] = tk.StringVar(value="local")
        for i, (value, text) in enumerate((("local", "สร้างในเครื่อง"), ("existing", "คลิป/ไฟล์ที่มี"),
                                           ("flow", "Google Flow (เครดิต)"), ("omni", "Google API"))):
            tk.Radiobutton(choices, text=text, value=value, variable=ui["source"],
                           bg="#FFFFFF", fg="#2C1D63", activebackground="#FFFFFF",
                           selectcolor="#F0EBFF", font=(self.F, 9), anchor="w",
                           command=lambda p=platform: self._platform_source_changed(p)).grid(
                row=i // 2, column=i % 2, sticky="w", pady=2, padx=(0, 4))

        source_inner = tk.Frame(src_body, bg="#FFFFFF")
        source_inner.pack(fill="x")
        ui["panels"] = {}
        for value in ("local", "existing", "flow", "omni"):
            ui["panels"][value] = tk.Frame(source_inner, bg="#FFFFFF")

        panel = ui["panels"]["local"]
        tk.Label(panel, text="ใช้บทที่เลือกด้านบน สร้างคลิปด้วยระบบในเครื่อง", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF", wraplength=480).pack(anchor="w")
        tk.Button(panel, text="🎬 สร้างคลิปจากบทนี้", font=(self.F, 9, "bold"), bg="#8E6CF7", fg="#FFFFFF", relief="flat", bd=0, padx=12, pady=5, cursor="hand2",
                  command=lambda p=platform: self.platform_render_local(p)).pack(anchor="w", pady=(6, 0))

        panel = ui["panels"]["existing"]
        tk.Label(panel, text="ใช้คลิปในคลัง หรือเลือกไฟล์วิดีโอจากเครื่องเพื่อแปลงและนำเข้า", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF", wraplength=480).pack(anchor="w")
        row = tk.Frame(panel, bg="#FFFFFF")
        row.pack(fill="x", pady=4)
        ui["clip_choice"] = tk.StringVar()
        ui["clip_cb"] = ttk.Combobox(row, textvariable=ui["clip_choice"], state="readonly")
        ui["clip_cb"].pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Button(row, text="ใช้คลิปนี้", font=(self.F, 8, "bold"), bg="#F0EBFF", fg="#6C47FF", relief="flat", bd=0, padx=8, pady=4, cursor="hand2", command=lambda p=platform: self.platform_choose_clip(p)).pack(side="left", padx=(0, 4))
        tk.Button(row, text="📂 นำเข้าไฟล์...", font=(self.F, 8), bg="#FAF8FD", fg="#7C7895", relief="flat", bd=0, padx=8, pady=4, cursor="hand2", command=lambda p=platform: self.platform_import(p, "computer")).pack(side="left")

        panel = ui["panels"]["flow"]
        tk.Label(panel, text="Flow ใช้เครดิต Google • สร้างในเว็บ ดาวน์โหลด แล้วนำไฟล์กลับเข้าคลัง", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF", wraplength=480).pack(anchor="w")
        row = tk.Frame(panel, bg="#FFFFFF")
        row.pack(fill="x", pady=(4, 0))
        tk.Label(row, text="พรอมต์:", font=(self.F, 8, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left")
        ui["flow_part"] = tk.StringVar()
        ui["flow_part_cb"] = ttk.Combobox(row, textvariable=ui["flow_part"], state="readonly")
        ui["flow_part_cb"].pack(side="left", fill="x", expand=True, padx=(4, 0))
        ui["flow_part_cb"].bind("<<ComboboxSelected>>", lambda e, p=platform: self._platform_flow_part_changed(p))
        ui["flow_prompt"] = tk.Text(panel, height=3, wrap="word", font=(self.F, 9), relief="flat", bd=0, highlightbackground="#EDE9FE", highlightthickness=1, bg="#FAF9FF", fg="#2C1D63")
        ui["flow_prompt"].pack(fill="x", pady=4)
        row_fl = tk.Frame(panel, bg="#FFFFFF")
        row_fl.pack(anchor="w")
        tk.Button(row_fl, text="📋 คัดลอกพรอมต์ + เปิด Flow", font=(self.F, 8), bg="#F0EBFF", fg="#6C47FF", relief="flat", bd=0, padx=8, pady=4, cursor="hand2", command=lambda p=platform: self.platform_open_flow(p)).pack(side="left")
        tk.Button(row_fl, text="📂 นำเข้าคลิป...", font=(self.F, 8, "bold"), bg="#8E6CF7", fg="#FFFFFF", relief="flat", bd=0, padx=10, pady=4, cursor="hand2", command=lambda p=platform: self.platform_import(p, "google_flow")).pack(side="left", padx=6)

        panel = ui["panels"]["omni"]
        tk.Label(panel, text="พรอมต์สร้างอัตโนมัติจากเรื่องที่เลือก • Gemini Omni Flash สร้างคลิป 3–10 วิ", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF", wraplength=480).pack(anchor="w")
        ui["omni_prompt"] = tk.Text(panel, height=3, wrap="word", font=(self.F, 9), relief="flat", bd=0, highlightbackground="#EDE9FE", highlightthickness=1, bg="#FAF9FF", fg="#2C1D63")
        ui["omni_prompt"].pack(fill="x", pady=4)
        row_om = tk.Frame(panel, bg="#FFFFFF")
        row_om.pack(fill="x")
        tk.Label(row_om, text="ความละเอียด:", font=(self.F, 8), fg="#2C1D63", bg="#FFFFFF").pack(side="left")
        ui["resolution"] = tk.StringVar(value="720p")
        ttk.Combobox(row_om, textvariable=ui["resolution"], values=("360p", "720p", "1080p", "4k"), state="readonly", width=8).pack(side="left", padx=4)
        tk.Button(row_om, text="⚡ สร้างด้วย Google", font=(self.F, 8, "bold"), bg="#8E6CF7", fg="#FFFFFF", relief="flat", bd=0, padx=8, pady=4, cursor="hand2", command=lambda p=platform: self.platform_generate_google(p)).pack(side="left", padx=6)

        self._platform_source_changed(platform)

        # ---------------- ACTION & PUBLISH CARD ----------------
        selected = tk.Frame(inner, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightthickness=1, bd=0)
        selected.pack(fill="x", pady=(10, 0))

        sel_head = tk.Frame(selected, bg="#FFFFFF", padx=16, pady=14)
        sel_head.pack(fill="x")
        tk.Label(sel_head, text=f"3. คลิปที่เลือกสำหรับ {label}", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")

        sel_body = tk.Frame(selected, bg="#FFFFFF", padx=16, pady=14)
        sel_body.pack(fill="x")

        ui["current_label"] = tk.Label(sel_body, text="ยังไม่ได้เลือกคลิป", font=(self.F, 9), fg="#7C7895", bg="#FFFFFF", wraplength=900, anchor="w")
        ui["current_label"].pack(anchor="w", pady=(0, 6))

        row_act = tk.Frame(sel_body, bg="#FFFFFF")
        row_act.pack(fill="x", pady=(0, 8))
        for text, command in (("▶ ดูคลิป", lambda p=platform: self.platform_play(p)),
                              ("📂 เปิดโฟลเดอร์", lambda p=platform: self.platform_open_folder(p)),
                              ("✨ AI เขียนข้อความโพสต์", lambda p=platform: self.platform_ai_caption(p)),
                              ("📋 คัดลอกข้อความโพสต์", lambda p=platform: self.platform_copy_caption(p)),
                              ("✓ อนุมัติ", lambda p=platform: self.platform_approve(p))):
            tk.Button(row_act, text=text, font=(self.F, 8), bg="#F0EBFF", fg="#6C47FF", relief="flat", bd=0, padx=8, pady=4, cursor="hand2", command=command).pack(side="left", padx=(0, 6))

        pub_text = "🚀 โพสต์ไปที่ %s" % label if platform in ("youtube", "facebook_page") else (
            "🚀 ส่งเข้าแบบร่าง TikTok" if platform == "tiktok" else "🚀 เปิด %s เพื่อโพสต์เอง" % label)
        tk.Button(
            sel_body,
            text=pub_text,
            font=(self.F, 10, "bold"),
            bg="#8E6CF7",
            fg="#FFFFFF",
            activebackground="#7C5CEF",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=16,
            pady=8,
            command=lambda p=platform: self.platform_publish(p)
        ).pack(anchor="w", pady=(2, 0))

    def _platform_source_changed(self, platform):
        ui = self.platform_ui[platform]
        for panel in ui["panels"].values():
            panel.pack_forget()
        ui["panels"][ui["source"].get()].pack(fill="x")

    def refresh_platform_workspaces(self):
        if not hasattr(self, "platform_ui"):
            return
        scripts = []
        story_paths = list(self._inbox()) + sorted((ROOT / "scripts" / "done").glob("**/*.json"), reverse=True)
        for path in story_paths:
            try:
                title = scriptmod.load(path).get("title", path.stem)
            except Exception:
                title = path.stem
            scripts.append(("%s  [%s]" % (title, path.name), path))
        clips = [("%s  [%s]" % (meta.get("title", folder.name), folder.name), folder)
                 for _, folder, meta in self._clips()]
        for ui in self.platform_ui.values():
            ui["script_map"] = dict(scripts)
            ui["clip_map"] = dict(clips)
            ui["script_cb"].configure(values=[name for name, _ in scripts])
            ui["clip_cb"].configure(values=[name for name, _ in clips])
            if ui["script"].get() not in ui["script_map"]:
                ui["script"].set(scripts[0][0] if scripts else "")
            if ui["clip_choice"].get() not in ui["clip_map"]:
                ui["clip_choice"].set(clips[0][0] if clips else "")
            if ui["current"] and not (ui["current"] / "meta.json").exists():
                ui["current"] = None
            self._platform_story_changed(ui["platform"])
            self._platform_update_current(ui)

    def _platform_story_changed(self, platform, force=False):
        from .platform_workspace import flow_prompts_from_script, prompt_from_script
        ui = self.platform_ui[platform]
        path = ui["script_map"].get(ui["script"].get())
        if not path:
            return
        if ui.get("story_path") == path and not force:
            return
        sc = scriptmod.load(path)
        ui["story_path"] = path
        if force:
            ui["current"] = None
            ui["current_label"].configure(text="ยังไม่ได้เลือกคลิป")
        self._platform_show_metadata(ui, sc)
        ui["flow_prompts"] = dict(flow_prompts_from_script(sc, ui["format"].get()))
        ui["flow_part_cb"].configure(values=list(ui["flow_prompts"]))
        ui["flow_part"].set(next(iter(ui["flow_prompts"])))
        self._platform_flow_part_changed(platform)
        widget = ui["omni_prompt"]
        widget.delete("1.0", "end")
        widget.insert("1.0", prompt_from_script(sc, platform, ui["format"].get()))

    def _platform_flow_part_changed(self, platform):
        ui = self.platform_ui[platform]
        widget = ui["flow_prompt"]
        widget.delete("1.0", "end")
        widget.insert("1.0", ui.get("flow_prompts", {}).get(ui["flow_part"].get(), ""))

    def _platform_show_metadata(self, ui, meta):
        caption = (meta.get("platform_captions") or {}).get(ui["platform"], meta)
        ui["meta_title"].configure(text=caption.get("title") or "AI กำลังร่างชื่อเรื่อง")
        ui["meta_description"].configure(text=caption.get("description") or "AI ยังไม่ได้เขียนคำอธิบายจากคลิปนี้")
        ui["meta_tags"].configure(text=" ".join("#" + str(t).lstrip("#") for t in caption.get("tags", [])))

    def _platform_update_current(self, ui):
        folder = ui["current"]
        if not folder:
            ui["current_label"].configure(text="ยังไม่ได้เลือกคลิป")
            return
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        self._platform_show_metadata(ui, meta)
        post = (meta.get("posts") or {}).get(ui["platform"], {})
        posted = "  •  ส่งเข้าแบบร่างแล้ว" if post.get("status") == "draft_sent" else (
            "  •  โพสต์แล้ว" if post.get("status") == "posted" else "")
        ui["current_label"].configure(text="%s  •  %.0f วินาที  •  %s%s  •  %s" % (
            meta.get("title", folder.name), float(meta.get("duration_seconds", 0)),
            STATUS_TH.get(meta.get("status"), meta.get("status", "")), posted, folder))

    def _platform_select_folder(self, platform, folder):
        ui = self.platform_ui[platform]
        folder = Path(folder)
        if (folder / "meta.json").exists():
            ui["current"] = folder
            self._platform_update_current(ui)

    def platform_choose_clip(self, platform):
        from .credential_store import load_key
        ui = self.platform_ui[platform]
        folder = ui["clip_map"].get(ui["clip_choice"].get())
        if folder:
            self._platform_select_folder(platform, folder)
            meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
            if platform not in (meta.get("platform_captions") or {}) and load_key():
                self.platform_ai_caption(platform)

    def platform_render_local(self, platform):
        ui = self.platform_ui[platform]
        path = ui["script_map"].get(ui["script"].get())
        if not path:
            messagebox.showinfo("สร้างคลิป", "ยังไม่มีบทในแท็บ บท")
            return
        sc = scriptmod.load(path)
        folder = ROOT / "output" / dt.date.today().isoformat() / sc["id"]
        if self._start(["render", str(path), "--format", ui["format"].get()],
                       "กำลังสร้างคลิปสำหรับ %s" % platform):
            from .credential_store import load_key
            self._single = path
            self._platform_pending = (platform, folder)
            self._platform_auto_caption = bool(load_key())
            self.job_total = 1

    def _platform_metadata_args(self, platform, fallback_title=""):
        ui = self.platform_ui[platform]
        path = ui["script_map"].get(ui["script"].get())
        sc = scriptmod.load(path) if path else {}
        title = sc.get("title", "").strip() or fallback_title
        if not title:
            raise ValueError("เลือกเรื่องก่อนสร้างคลิป")
        tags = [str(x).strip().lstrip("#") for x in sc.get("tags", []) if str(x).strip()]
        args = ["--platform", platform, "--title", title, "--description", sc.get("description", ""),
                "--tags", *tags, "--format", ui["format"].get()]
        if ui["made_for_kids"].get():
            args.append("--made-for-kids")
        return args

    def platform_import(self, platform, source):
        file = filedialog.askopenfilename(title="เลือกไฟล์วิดีโอ", filetypes=[
            ("วิดีโอ", "*.mp4 *.mov *.mkv *.webm *.avi"), ("ทุกไฟล์", "*.*")])
        if not file:
            return
        try:
            if source == "computer":
                args = ["import-video", file, "--platform", platform, "--title", Path(file).stem,
                        "--format", self.platform_ui[platform]["format"].get()]
                if self.platform_ui[platform]["made_for_kids"].get():
                    args.append("--made-for-kids")
            else:
                args = ["import-video", file] + self._platform_metadata_args(platform, Path(file).stem)
        except ValueError as e:
            messagebox.showwarning("นำเข้าคลิป", str(e))
            return
        args += ["--source", source]
        if source == "google_flow":
            args += ["--ai-generated", "--prompt", self.platform_ui[platform]["flow_prompt"].get("1.0", "end").strip()]
        from .credential_store import load_key
        key = load_key()
        if self._start(args, "กำลังนำเข้าคลิปสำหรับ %s" % platform,
                       env_updates={"GEMINI_API_KEY": key} if key else None):
            self._platform_pending = (platform, None)
            self._platform_auto_caption = bool(key)
            self.job_total = 1

    def platform_open_flow(self, platform):
        prompt = self.platform_ui[platform]["flow_prompt"].get("1.0", "end").strip()
        if prompt:
            self.clipboard_clear()
            self.clipboard_append(prompt)
        open_path("https://flow.google.com/")
        self.say("คัดลอกพรอมต์แล้ว เปิด Flow ใช้ Agent สำหรับทั้งเรื่อง หรือเลือกพรอมต์ทีละฉาก; ดาวน์โหลดแล้วนำเข้าคลิป", "good")

    def platform_generate_google(self, platform):
        ui = self.platform_ui[platform]
        prompt = ui["omni_prompt"].get("1.0", "end").strip()
        from .credential_store import load_key
        key = load_key()
        if not key:
            messagebox.showwarning("Google API", "ใส่ Gemini API key ที่เปิดชำระเงินก่อน")
            return
        if not prompt:
            messagebox.showwarning("Google API", "ใส่พรอมต์อธิบายวิดีโอก่อน")
            return
        try:
            args = ["google-video"] + self._platform_metadata_args(platform) + [
                "--prompt", prompt, "--resolution", ui["resolution"].get()]
        except ValueError as e:
            messagebox.showwarning("Google API", str(e))
            return
        if not messagebox.askyesno("ยืนยันค่าใช้จ่าย", "Google Gemini Omni Flash API คิดเงินตามการใช้งานจริง\n"
                                   "ต้องการส่งคำขอนี้เพื่อสร้างวิดีโอหรือไม่?"):
            return
        if self._start(args, "กำลังสร้างคลิปด้วย Google", env_updates={"GEMINI_API_KEY": key}):
            self._platform_pending = (platform, None)
            self._platform_auto_caption = True
            self.job_total = 1

    def _platform_current(self, platform):
        folder = self.platform_ui[platform]["current"]
        if not folder or not (folder / "meta.json").exists():
            messagebox.showinfo("เลือกคลิป", "เลือกหรือสร้างคลิปก่อน")
            return None, None
        return folder, json.loads((folder / "meta.json").read_text(encoding="utf-8"))

    def platform_play(self, platform):
        folder, meta = self._platform_current(platform)
        if not folder:
            return
        files = meta.get("files") or {}
        fmt = (meta.get("platform_formats") or {}).get(platform) or self.platform_ui[platform]["format"].get()
        name = files.get(fmt) or files.get("vertical") or files.get("horizontal")
        if name and (folder / name).exists():
            open_path(folder / name)
        else:
            messagebox.showwarning("ดูคลิป", "ไม่พบไฟล์วิดีโอ")

    def platform_open_folder(self, platform):
        folder, _ = self._platform_current(platform)
        if folder:
            open_path(folder)

    def platform_copy_caption(self, platform):
        from . import publish
        folder, meta = self._platform_current(platform)
        if folder:
            self._copy(publish.caption(meta, platform))

    def platform_ai_caption(self, platform):
        from .credential_store import load_key
        folder, _ = self._platform_current(platform)
        if not folder:
            return
        key = load_key()
        if not key:
            messagebox.showinfo("ตั้งค่า AI", "ตั้ง Gemini API key หนึ่งครั้งในแท็บ ตั้งค่า ก่อน")
            self.nb.select(self.tab_set)
            return
        if self._start(["caption-video", "--folder", str(folder), "--platform", platform],
                       "AI กำลังเขียนข้อความโพสต์", env_updates={"GEMINI_API_KEY": key}):
            self._platform_pending = (platform, folder)
            self.job_total = 1

    def platform_approve(self, platform):
        folder, meta = self._platform_current(platform)
        if not folder:
            return
        self._save_clip_status(folder, meta, "approved")
        self._platform_update_current(self.platform_ui[platform])
        self.refresh_clips()
        self.refresh_stats()

    def platform_publish(self, platform):
        from . import publish
        folder, meta = self._platform_current(platform)
        if not folder:
            return
        caption_data = (meta.get("platform_captions") or {}).get(platform, meta)
        if not all(caption_data.get(k) for k in ("title", "description", "tags")):
            messagebox.showwarning("ข้อความโพสต์ยังไม่พร้อม", "ให้ AI เขียนชื่อเรื่อง คำอธิบาย และแฮชแท็กก่อนโพสต์")
            return
        if meta.get("status") not in ("approved", "posted"):
            if not messagebox.askyesno("ตรวจและโพสต์", "ตรวจภาพและเสียงของคลิปแล้ว พร้อมโพสต์ไปที่ %s หรือไม่?" % platform):
                return
            self._save_clip_status(folder, meta, "approved")
        if platform in ("shopee", "facebook_profile"):
            self._copy(publish.caption(meta, platform))
            open_path(folder)
            open_path("https://shopee.co.th/" if platform == "shopee" else "https://www.facebook.com/")
            self.say("เปิดไฟล์และเว็บไซต์แล้ว อัปโหลดและตรวจรายละเอียดด้วยตนเอง", "good")
        else:
            self.post_folder(folder, platform, confirmed=meta.get("status") not in ("approved", "posted"))

    def platform_mark_posted(self, platform):
        folder, meta = self._platform_current(platform)
        if not folder:
            return
        if not messagebox.askyesno("ยืนยันการโพสต์", "คุณโพสต์คลิปนี้บน %s เรียบร้อยแล้วใช่ไหม?" % platform):
            return
        url = simpledialog.askstring("ลิงก์โพสต์", "วางลิงก์โพสต์ (เว้นว่างได้)")
        if url is None:
            return
        meta.setdefault("posts", {})[platform] = {"status": "posted", "manual": True,
                                                   "url": url.strip(),
                                                   "at": dt.datetime.now().isoformat(timespec="seconds")}
        (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        self._platform_update_current(self.platform_ui[platform])
        self.refresh_clips()
        self.say("บันทึกว่าโพสต์บน %s แล้ว" % platform, "good")

    def _update_clip_buttons(self, meta):
        status = meta.get("status") if meta else None
        status_styles = {"approved": "Selected.TButton", "posted": "Posted.TButton",
                         "rejected": "Rejected.TButton"}
        for value, button in self.clip_status_buttons.items():
            button.configure(style=status_styles.get(value, "TButton") if value == status else "TButton")
        posts = (meta.get("posts") or {}) if meta else {}
        for platform, button in self.clip_post_buttons.items():
            post_status = posts.get(platform, {}).get("status")
            style = {"posted": "Posted.TButton", "draft_sent": "Draft.TButton"}.get(post_status,
                                                                                       "TButton")
            button.configure(style=style)

    def _clips(self):
        out = []
        base = ROOT / "output"
        if not base.exists():
            return out
        for day in sorted([d for d in base.iterdir() if d.is_dir()], reverse=True):
            if day.name in ("removed", "trash", ".trash"):
                continue
            for clip in sorted([c for c in day.iterdir() if c.is_dir()]):
                m = clip / "meta.json"
                if m.exists():
                    try:
                        out.append((day.name, clip, json.loads(m.read_text(encoding="utf-8"))))
                    except Exception:
                        pass
        return out

    def refresh_clips(self):
        selected = self.tv_c.selection()
        self.tv_c.delete(*self.tv_c.get_children())
        want = self.clip_filter.get()
        self._clip_cache = {}
        for day, folder, meta in self._clips():
            st = STATUS_TH.get(meta.get("status"), meta.get("status", ""))
            if meta.get("needs_review") and meta.get("status") == "ready_for_approval":
                st = "รอตรวจ (มีคำเตือน)"
            if want != "ทั้งหมด" and not st.startswith(want):
                continue
            tag = {"posted": "posted", "rejected": "rejected"}.get(meta.get("status"),
                                                                    "warn" if meta.get("needs_review") else "")
            dur = "%d วิ" % round(meta.get("duration_seconds", 0))
            short = {"youtube": "YT", "facebook_page": "FB", "tiktok": "TT",
                     "facebook_profile": "FP", "shopee": "SP"}
            done = " ".join(short[k] for k, v in (meta.get("posts") or {}).items()
                            if k in short and v.get("status") in ("posted", "draft_sent"))
            self.tv_c.insert("", "end", iid=str(folder), values=(day, meta.get("title", folder.name), dur, st, done),
                             tags=(tag,))
            self._clip_cache[str(folder)] = meta
        if selected and self.tv_c.exists(selected[0]):
            self.tv_c.selection_set(selected[0])
            self.show_clip()
        else:
            self._update_clip_buttons(None)

    def _sel_clip(self):
        s = self.tv_c.selection()
        return (Path(s[0]), self._clip_cache.get(s[0])) if s else (None, None)

    def _sel_clips(self):
        return [Path(i) for i in self.tv_c.selection()]

    def show_clip(self):
        self._stop_clip_player()
        folder, meta = self._sel_clip()
        if not folder:
            self._update_clip_buttons(None)
            return
        self._update_clip_buttons(meta)
        th = folder / "thumb_vertical.jpg"
        if th.exists():
            im = Image.open(th)
            im.thumbnail((120, 213))
            ph = ImageTk.PhotoImage(im)
            self._img_refs = [ph]
            self.c_thumb.configure(image=ph)
        else:
            self.c_thumb.configure(image="")
        txt = "%s\n\nความยาว %.0f วินาที   เสียง: %s\n%s" % (
            meta.get("title", ""), meta.get("duration_seconds", 0), ", ".join(meta.get("voice_engines", [])),
            meta.get("description", ""))
        if meta.get("needs_review"):
            txt += "\n\nต้องตรวจ:\n- " + "\n- ".join(meta["needs_review"])
        posts = meta.get("posts") or {}
        if posts:
            names = {"youtube": "YouTube", "facebook_page": "FB Page", "tiktok": "TikTok",
                     "facebook_profile": "Facebook Profile", "shopee": "Shopee"}
            stx = {"posted": "โพสต์แล้ว", "draft_sent": "ส่งเข้าแบบร่างแล้ว", "failed": "ไม่สำเร็จ"}
            txt += "\n\nการโพสต์:"
            for k, v in posts.items():
                txt += "\n- %s: %s %s" % (names.get(k, k), stx.get(v.get("status"), v.get("status", "")),
                                          v.get("url") or v.get("error", "")[:80])
        self.c_info.configure(text=txt)

    def _on_video_canvas_resize(self, event):
        if hasattr(self, "_player_hwnd") and self._player_hwnd:
            try:
                ctypes.windll.user32.MoveWindow(self._player_hwnd, 0, 0, max(50, event.width), max(50, event.height), True)
            except Exception:
                pass

    def _stop_clip_player(self):
        if hasattr(self, "_player_proc") and self._player_proc:
            try:
                self._player_proc.kill()
            except Exception:
                pass
            self._player_proc = None
        self._player_hwnd = None
        if hasattr(self, "c_player_box") and self.c_player_box.winfo_ismapped():
            self.c_player_box.pack_forget()

    def _replay_current_video(self):
        fmt = getattr(self, "_current_playing_fmt", "vertical")
        self.play_clip(fmt)

    def expand_video(self):
        target = getattr(self, "_current_playing_file", None)
        if not target or not Path(target).exists():
            folder, meta = self._sel_clip()
            if folder and meta:
                fmt = getattr(self, "_current_playing_fmt", "vertical")
                name = meta.get("files", {}).get(fmt) or meta.get("files", {}).get("vertical") or meta.get("files", {}).get("horizontal")
                if name and (folder / name).exists():
                    target = folder / name
        if target and Path(target).exists():
            open_path(target)
            self.say("เปิดวิดีโอแบบเต็มจอในโปรแกรมเล่นแล้ว", "good")
        else:
            messagebox.showinfo("ขยายวิดีโอ", "ไม่พบไฟล์วิดีโอที่จะขยาย")

    def play_clip(self, fmt):
        folder, meta = self._sel_clip()
        if not folder or not meta:
            messagebox.showinfo("เล่นคลิป", "กรุณาเลือกคลิปที่ต้องการเล่นจากรายการทางซ้ายก่อน")
            return
        name = meta.get("files", {}).get(fmt)
        if not name or not (folder / name).exists():
            alt_fmt = "horizontal" if fmt == "vertical" else "vertical"
            alt_name = meta.get("files", {}).get(alt_fmt)
            if alt_name and (folder / alt_name).exists():
                fmt_th = "แนวตั้ง" if fmt == "vertical" else "แนวนอน"
                alt_th = "แนวนอน" if fmt == "vertical" else "แนวตั้ง"
                if messagebox.askyesno("เล่นคลิป", f"ไม่มีคลิปแบบ {fmt_th} สำหรับรายการนี้\nแต่มีคลิปแบบ {alt_th}\nต้องการเล่นแบบ {alt_th} แทนหรือไม่?"):
                    self.play_clip(alt_fmt)
                    return
            messagebox.showinfo("เล่นคลิป", "ไม่มีคลิปแบบนี้ (อาจตั้งค่าให้สร้างเฉพาะบางแบบ)")
            return

        video_path = folder / name
        self._current_playing_file = video_path
        self._current_playing_fmt = fmt

        # Stop previous playback
        if hasattr(self, "_player_proc") and self._player_proc:
            try:
                self._player_proc.kill()
            except Exception:
                pass
            self._player_proc = None
        self._player_hwnd = None

        fmt_title = "แนวตั้ง (TikTok 9:16)" if fmt == "vertical" else ("แนวนอน (YouTube 16:9)" if fmt == "horizontal" else "สี่เหลี่ยม (1:1)")
        self.c_player_title.configure(text=f"🎬 กำลังเล่น: {fmt_title}")

        # Pack player box into right column (between topbox and btns)
        self.c_player_box.pack(side="top", fill="both", expand=True, pady=(6, 6))
        self.update_idletasks()
        self.update()

        ffplay_bin = _get_real_ffplay()
        if not ffplay_bin or not IS_WIN:
            open_path(video_path)
            return

        wid = self.c_video_canvas.winfo_id()
        w = max(180, self.c_video_canvas.winfo_width())
        h = max(140, self.c_video_canvas.winfo_height())

        win_title = f"TY_Player_{os.getpid()}_{int(time.time() * 1000)}"
        cmd = [
            ffplay_bin,
            "-window_title", win_title,
            "-noborder",
            "-loop", "0",
            "-x", str(w),
            "-y", str(h),
            str(video_path)
        ]

        startupinfo = None
        creationflags = 0
        if IS_WIN:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE: hide console window completely
            creationflags = 0x08000000   # CREATE_NO_WINDOW: prevent terminal/powershell window

        try:
            self._player_proc = subprocess.Popen(
                cmd,
                startupinfo=startupinfo,
                creationflags=creationflags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            open_path(video_path)
            return

        def _embed(retries=30):
            if not hasattr(self, "_player_proc") or not self._player_proc or self._player_proc.poll() is not None:
                return
            hwnd = ctypes.windll.user32.FindWindowW(None, win_title)
            if hwnd:
                self._player_hwnd = hwnd
                ctypes.windll.user32.SetParent(hwnd, wid)
                GWL_STYLE = -16
                WS_CHILD = 0x40000000
                WS_VISIBLE = 0x10000000
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, WS_CHILD | WS_VISIBLE)
                cur_w = max(50, self.c_video_canvas.winfo_width())
                cur_h = max(50, self.c_video_canvas.winfo_height())
                ctypes.windll.user32.MoveWindow(hwnd, 0, 0, cur_w, cur_h, True)
            elif retries > 0:
                self.after(35, lambda: _embed(retries - 1))

        self.after(30, _embed)

    def copy_upload(self):
        folder, _ = self._sel_clip()
        if not folder:
            return
        p = folder / "upload.txt"
        if p.exists():
            self.clipboard_clear()
            self.clipboard_append(p.read_text(encoding="utf-8"))
            self.say("คัดลอกข้อความโพสต์แล้ว วางในช่องคำอธิบายได้เลย", "good")

    def open_clip_folder(self):
        folder, _ = self._sel_clip()
        if folder:
            open_path(folder)

    def set_status(self, status):
        folder, meta = self._sel_clip()
        if not folder:
            return
        self._save_clip_status(folder, meta, status)
        self.refresh_clips()
        if self.tv_c.exists(str(folder)):
            self.tv_c.selection_set(str(folder))
            self.show_clip()
        self.refresh_stats()

    def _save_clip_status(self, folder, meta, status):
        meta["status"] = status
        meta["status_changed"] = dt.datetime.now().isoformat(timespec="seconds")
        if status == "approved" and meta.get("source") in ("computer", "google_flow", "google_omni"):
            meta["needs_review"] = [item for item in meta.get("needs_review", [])
                                    if item != "ตรวจภาพ เสียง และข้อความก่อนเผยแพร่"]
        (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    def remove_clips(self):
        self._stop_clip_player()
        sel = self._sel_clips()
        if not sel:
            messagebox.showinfo("ลบคลิป", "เลือกคลิปทางซ้ายอย่างน้อย 1 คลิปก่อน")
            return
        titles = []
        for p in sel:
            meta = self._clip_cache.get(str(p), {})
            titles.append(meta.get("title", p.name))

        if len(sel) == 1:
            msg = f"ต้องการลบคลิป '{titles[0]}' หรือไม่?\n\nโฟลเดอร์คลิปจะถูกย้ายไปที่ถังขยะของโปรแกรม (output\\removed)"
        else:
            sample = "\n- ".join(titles[:3])
            if len(titles) > 3:
                sample += f"\n... และอีก {len(titles)-3} คลิป"
            msg = f"ต้องการลบคลิปที่เลือกทั้งหมด {len(sel)} คลิปหรือไม่?\n\n- {sample}\n\nโฟลเดอร์คลิปจะถูกย้ายไปที่ถังขยะของโปรแกรม (output\\removed)"

        if not messagebox.askyesno("ยืนยันการลบคลิป", msg, icon="warning"):
            return

        d = ROOT / "output" / "removed"
        d.mkdir(parents=True, exist_ok=True)
        deleted_count = 0
        for p in sel:
            try:
                dest = d / p.parent.name / p.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    dest = d / p.parent.name / f"{p.name}_{int(dt.datetime.now().timestamp())}"
                shutil.move(str(p), str(dest))
                deleted_count += 1
            except Exception as e:
                messagebox.showerror("ลบคลิปขัดข้อง", f"ไม่สามารถลบ {p.name}: {e}")

        self.say(f"ลบคลิปเรียบร้อย {deleted_count} รายการ", "good")
        self.c_thumb.configure(image="")
        self.c_info.configure(text="เลือกคลิปทางซ้าย")
        self.refresh_clips()
        self.refresh_stats()

    # ------------------------------------------------------------------ schedule tab (AI Worker Scheduler)
    def _build_sched(self):
        t = self.tab_sched

        # ---------------- TOP HEADER CARD ----------------
        hdr_card = tk.Frame(t, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        hdr_card.pack(fill="x", pady=(0, 10))

        hdr_inner = tk.Frame(hdr_card, bg="#FFFFFF", padx=16, pady=12)
        hdr_inner.pack(fill="x")

        hdr_icon_box = tk.Frame(hdr_inner, bg="#F0EBFF", width=42, height=42)
        hdr_icon_box.pack_propagate(False)
        hdr_icon_box.pack(side="left", padx=(0, 12))
        tk.Label(hdr_icon_box, text="⏰", font=(self.F, 18), bg="#F0EBFF").pack(expand=True)

        hdr_titles = tk.Frame(hdr_inner, bg="#FFFFFF")
        hdr_titles.pack(side="left", fill="x", expand=True)
        tk.Label(hdr_titles, text="ตั้งเวลาพนักงาน AI ทำงานอัตโนมัติ (AI Worker Scheduler)", font=(self.F, 13, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")
        tk.Label(hdr_titles, text="เลือกแพลตฟอร์ม กำหนดเวลาทำงานรายวัน (5, 7, 10, 15 เวลา หรือตามต้องการ) ถึงเวลาพนักงานจะทำงานทันที",
                 font=(self.F, 9), fg="#7C7895", bg="#FFFFFF").pack(anchor="w", pady=(2, 0))

        tk.Button(
            hdr_inner,
            text="🔄 รีเฟรชสถานะ",
            font=(self.F, 9, "bold"),
            bg="#F0EBFF",
            fg="#6C47FF",
            activebackground="#8E6CF7",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=14,
            pady=6,
            command=self.refresh_worker_schedule_ui
        ).pack(side="right")

        # Scrollable container for the entire schedule tab
        sch_canvas = tk.Canvas(t, bg=BG, highlightthickness=0)
        sch_scroll = ttk.Scrollbar(t, orient="vertical", command=sch_canvas.yview)
        sch_box = tk.Frame(sch_canvas, bg=BG)
        sch_win = sch_canvas.create_window((0, 0), window=sch_box, anchor="nw")

        sch_box.bind("<Configure>", lambda e: sch_canvas.configure(scrollregion=sch_canvas.bbox("all")))
        sch_canvas.bind("<Configure>", lambda e: sch_canvas.itemconfigure(sch_win, width=e.width - 6))

        sch_canvas.configure(yscrollcommand=sch_scroll.set)
        sch_scroll.pack(side="right", fill="y")
        sch_canvas.pack(side="left", fill="both", expand=True)
        sch_canvas.bind_all("<MouseWheel>", lambda e: sch_canvas.yview_scroll(int(-e.delta / 120), "units")
                            if self.nb.select() == str(self.tab_sched) else None, add="+")

        # Two-column layout grid
        cols_frame = tk.Frame(sch_box, bg=BG)
        cols_frame.pack(fill="both", expand=True)
        cols_frame.columnconfigure(0, weight=1, uniform="sched_col")
        cols_frame.columnconfigure(1, weight=1, uniform="sched_col")

        left_col = tk.Frame(cols_frame, bg=BG)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        right_col = tk.Frame(cols_frame, bg=BG)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # ---------------- LEFT COLUMN: CARD 1 (PLATFORM SELECTION) ----------------
        c1 = tk.Frame(left_col, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        c1.pack(fill="x", pady=(0, 10))

        c1_head = tk.Frame(c1, bg="#FFFFFF", padx=16, pady=14)
        c1_head.pack(fill="x")
        tk.Label(c1_head, text="1. เลือกแพลตฟอร์มที่ต้องการตั้งเวลา", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")
        tk.Label(c1_head, text="เลือกได้หลายแพลตฟอร์มพร้อมกัน ถึงเวลาพนักงานจะทำงานตามที่เลือกทันที", font=(self.F, 9), fg="#7C7895", bg="#FFFFFF").pack(anchor="w", pady=(2, 0))

        self.worker_plat_vars = {
            "facebook_profile": tk.BooleanVar(value=True),
            "facebook_page": tk.BooleanVar(value=False),
            "tiktok": tk.BooleanVar(value=False),
            "youtube": tk.BooleanVar(value=False),
            "batch_render": tk.BooleanVar(value=False),
        }

        plats_info = [
            ("facebook_profile", "👤 Facebook Profile", "พนักงาน RPA: โพสต์คลิป Shopee / Flow พร้อมแคปชั่น และ @ผู้ติดตาม"),
            ("facebook_page", "📘 Facebook Page", "โพสต์คลิป Reels ลงเพจ Facebook อัตโนมัติผ่าน Publisher API"),
            ("tiktok", "🎵 TikTok", "ส่งคลิปเข้าแบบร่าง TikTok (Draft) หรือโพสต์อัตโนมัติ"),
            ("youtube", "📺 YouTube Shorts", "อัปโหลดคลิปสั้นลง Shorts หรือคลิปแนวนอนอัตโนมัติ"),
            ("batch_render", "🎬 สร้างคลิปอัตโนมัติ", "เรนเดอร์บททั้งหมดใน scripts/inbox ให้กลายเป็นคลิปสำเร็จรูป"),
        ]

        p_container = tk.Frame(c1, bg="#FFFFFF", padx=16, pady=14)
        p_container.pack(fill="x")

        for key, title, desc in plats_info:
            p_card = tk.Frame(p_container, bg="#FAF8FD", highlightbackground="#EDE9FE", highlightthickness=1, bd=0)
            p_card.pack(fill="x", pady=3)
            p_inner = tk.Frame(p_card, bg="#FAF8FD", padx=10, pady=8)
            p_inner.pack(fill="x")

            chk = ttk.Checkbutton(p_inner, text=title, variable=self.worker_plat_vars[key])
            chk.pack(side="left")

            tk.Label(p_inner, text=f"— {desc}", font=(self.F, 8), fg="#7C7895", bg="#FAF8FD").pack(side="left", padx=(8, 0))

        # ---------------- LEFT COLUMN: CARD 2 (SCHEDULE TIME SLOTS) ----------------
        c2 = tk.Frame(left_col, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        c2.pack(fill="x", pady=(0, 10))

        c2_head = tk.Frame(c2, bg="#FFFFFF", padx=16, pady=14)
        c2_head.pack(fill="x")
        tk.Label(c2_head, text="2. กำหนดเวลาในการทำงานรายวัน", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")
        tk.Label(c2_head, text="กดปุ่มเพิ่มเวลาด่วน หรือระบุเวลากำหนดเองได้ไม่จำกัด", font=(self.F, 9), fg="#7C7895", bg="#FFFFFF").pack(anchor="w", pady=(2, 0))

        c2_body = tk.Frame(c2, bg="#FFFFFF", padx=16, pady=14)
        c2_body.pack(fill="x")

        # Quick preset buttons (5, 7, 10, 15)
        pre_row = tk.Frame(c2_body, bg="#FFFFFF")
        pre_row.pack(fill="x", pady=(2, 8))
        tk.Label(pre_row, text="⚡ เวลาด่วน:", font=(self.F, 9, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left", padx=(0, 8))

        for n in (5, 7, 10, 15):
            tk.Button(
                pre_row,
                text=f"⚡ {n} เวลา",
                font=(self.F, 9, "bold"),
                bg="#F0EBFF",
                fg="#6C47FF",
                activebackground="#8E6CF7",
                activeforeground="#FFFFFF",
                relief="flat",
                bd=0,
                padx=10,
                pady=4,
                cursor="hand2",
                command=lambda count=n: self._apply_worker_preset(count),
            ).pack(side="left", padx=3)

        # Custom time add row
        add_row = tk.Frame(c2_body, bg="#FFFFFF")
        add_row.pack(fill="x", pady=(4, 8))
        tk.Label(add_row, text="➕ กำหนดเอง:", font=(self.F, 9, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left", padx=(0, 8))

        self.worker_add_hh = tk.StringVar(value="08")
        self.worker_add_mm = tk.StringVar(value="30")
        ttk.Spinbox(add_row, from_=0, to=23, width=3, textvariable=self.worker_add_hh, format="%02.0f", wrap=True,
                    font=(self.F, 10)).pack(side="left", padx=(0, 2))
        tk.Label(add_row, text=":", font=(self.F, 10, "bold"), bg="#FFFFFF", fg="#2C1D63").pack(side="left")
        ttk.Spinbox(add_row, from_=0, to=59, increment=5, width=3, textvariable=self.worker_add_mm, format="%02.0f",
                    wrap=True, font=(self.F, 10)).pack(side="left", padx=(2, 8))

        tk.Button(
            add_row,
            text="➕ เพิ่มเวลานี้",
            font=(self.F, 8, "bold"),
            bg="#F0EBFF",
            fg="#6C47FF",
            activebackground="#8E6CF7",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=8,
            pady=3,
            command=self._add_worker_custom_time
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            add_row,
            text="🗑 ล้างทั้งหมด",
            font=(self.F, 8),
            bg="#F8F6FD",
            fg="#7C7895",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=8,
            pady=3,
            command=self._clear_worker_times
        ).pack(side="left")

        # Container for visual time chips/tags
        tags_box = tk.Frame(c2_body, bg="#FAF9FF", highlightbackground="#EDE9FE", highlightthickness=1, bd=0)
        tags_box.pack(fill="x", pady=(4, 6))
        self.worker_tags_inner = tk.Frame(tags_box, bg="#FAF9FF", padx=10, pady=8)
        self.worker_tags_inner.pack(fill="x")

        self.lbl_worker_times_summary = tk.Label(c2_body, text="รวมทั้งหมด: 0 เวลาต่อวัน", font=(self.F, 9, "bold"), fg="#6C47FF", bg="#FFFFFF")
        self.lbl_worker_times_summary.pack(anchor="w", pady=(2, 0))

        # ---------------- LEFT COLUMN: CARD 5 (TIPS) ----------------
        c5 = tk.Frame(left_col, bg="#FFFDF7", highlightbackground="#FDE68A", highlightcolor="#FDE68A", highlightthickness=1, bd=0)
        c5.pack(fill="x", pady=(0, 10))
        c5_inner = tk.Frame(c5, bg="#FFFDF7", padx=16, pady=12)
        c5_inner.pack(fill="x")

        tk.Label(c5_inner, text="💡 ข้อควรรู้ & คำแนะนำ", font=(self.F, 10, "bold"), fg="#92400E", bg="#FFFDF7").pack(anchor="w", pady=(0, 4))
        tips_text = (
            "• ระบบตั้งเวลาทำงานได้ 2 ทาง: In-App Timer ขณะเปิดแอป และ Windows Task Scheduler เมื่อปิดแอป\n"
            "• Facebook Profile: แนะนำกดปุ่ม 'เข้าสู่ระบบ Facebook' ในแท็บ FaceBook Profile ก่อน 1 ครั้ง\n"
            "• สามารถเพิ่มช่วงเวลาได้ไม่จำกัด เช่น 5, 7, 10, 15 เวลาเพื่อกระจายเวลาทำงานตลอดวัน"
        )
        tk.Label(c5_inner, text=tips_text, wraplength=460, justify="left", font=(self.F, 8), fg="#78350F", bg="#FFFDF7").pack(anchor="w")

        # ---------------- RIGHT COLUMN: CARD 3 (STATUS & CONTROLS) ----------------
        c3 = tk.Frame(right_col, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        c3.pack(fill="x", pady=(0, 10))

        c3_head = tk.Frame(c3, bg="#FFFFFF", padx=16, pady=14)
        c3_head.pack(fill="x")
        tk.Label(c3_head, text="3. ควบคุมการทำงานและสถานะปัจจุบัน", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")

        # Status badge banner with Avatar illustration
        self.worker_status_banner = tk.Frame(c3, bg="#FAF8FD", highlightbackground="#EDE9FE", highlightthickness=1, bd=0)
        self.worker_status_banner.pack(fill="x", padx=16, pady=(4, 10))

        s_inner = tk.Frame(self.worker_status_banner, bg="#FAF8FD", padx=12, pady=12)
        s_inner.pack(fill="x")

        # Avatar illustration
        avatar_path = ROOT / "studio" / "sched_avatar_ai.png"
        self._sched_avatar_img = None
        if avatar_path.exists():
            try:
                self._sched_avatar_img = tk.PhotoImage(file=str(avatar_path))
                av_lbl = tk.Label(s_inner, image=self._sched_avatar_img, bg="#FAF8FD")
                av_lbl.pack(side="left", padx=(0, 12))
            except Exception:
                pass

        s_info = tk.Frame(s_inner, bg="#FAF8FD")
        s_info.pack(side="left", fill="x", expand=True)

        s_status_row = tk.Frame(s_info, bg="#FAF8FD")
        s_status_row.pack(anchor="w")

        self.lbl_worker_status_icon = tk.Label(s_status_row, text="⚪", font=(self.F, 12), bg="#FAF8FD")
        self.lbl_worker_status_icon.pack(side="left", padx=(0, 4))

        self.lbl_worker_status_text = tk.Label(s_status_row, text="ระบบพนักงานอัตโนมัติ: ปิดอยู่", font=(self.F, 10, "bold"), fg="#7C7895", bg="#FAF8FD")
        self.lbl_worker_status_text.pack(side="left")

        self.lbl_worker_next_run = tk.Label(s_info, text="รอบต่อไป: ยังไม่ได้กำหนด", font=(self.F, 9), fg="#7C7895", bg="#FAF8FD")
        self.lbl_worker_next_run.pack(anchor="w", pady=(4, 0))

        # Control action buttons
        ctl_row = tk.Frame(c3, bg="#FFFFFF", padx=16, pady=14)
        ctl_row.pack(fill="x")

        self.btn_worker_save_enable = tk.Button(
            ctl_row,
            text="💾 บันทึกและเปิดใช้งาน",
            font=(self.F, 10, "bold"),
            bg="#8E6CF7",
            fg="#FFFFFF",
            activebackground="#7C5CEF",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=14,
            pady=8,
            command=self._save_and_enable_worker_schedule
        )
        self.btn_worker_save_enable.pack(side="left", padx=(0, 8))

        self.btn_worker_test_now = tk.Button(
            ctl_row,
            text="🚀 ทดสอบทันที",
            font=(self.F, 9, "bold"),
            bg="#F0EBFF",
            fg="#6C47FF",
            activebackground="#8E6CF7",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=7,
            command=self._test_run_worker_now
        )
        self.btn_worker_test_now.pack(side="left", padx=(0, 8))

        self.btn_worker_disable = tk.Button(
            ctl_row,
            text="⏹ ปิดการตั้งเวลา",
            font=(self.F, 9, "bold"),
            bg="#FFF5F5",
            fg="#EF4444",
            activebackground="#EF4444",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=10,
            pady=7,
            command=self._disable_worker_schedule
        )
        self.btn_worker_disable.pack(side="left")

        # ---------------- RIGHT COLUMN: CARD 4 (RECENT ACTIVITY LOG) ----------------
        c4 = tk.Frame(right_col, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        c4.pack(fill="both", expand=True, pady=(0, 10))

        c4_head = tk.Frame(c4, bg="#FFFFFF", padx=16, pady=14)
        c4_head.pack(fill="x")
        tk.Label(c4_head, text="4. ประวัติการทำงานล่าสุด (Activity Log)", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left")
        tk.Button(
            c4_head,
            text="🔄 รีเฟรช",
            font=(self.F, 8, "bold"),
            bg="#F0EBFF",
            fg="#6C47FF",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=8,
            pady=2,
            command=self.refresh_worker_schedule_ui
        ).pack(side="right")

        log_box = tk.Frame(c4, bg="#FFFFFF", padx=16, pady=14)
        log_box.pack(fill="both", expand=True)

        self.txt_worker_history = tk.Text(log_box, height=8, font=(self.F, 9), relief="flat", bd=0,
                                          highlightbackground="#EDE9FE", highlightthickness=1, wrap="word", bg="#FAF9FF", fg="#2C1D63")
        self.txt_worker_history.pack(fill="both", expand=True)

        # Initialize schedule data
        self.worker_times = []
        self.hh = self.worker_add_hh
        self.mm = self.worker_add_mm
        self.sched_now = self.lbl_worker_status_text
        self.refresh_worker_schedule_ui()

    def _render_worker_time_tags(self):
        for widget in self.worker_tags_inner.winfo_children():
            widget.destroy()

        from . import ai_worker_scheduler as sch
        self.worker_times = sch.normalize_times(self.worker_times)

        if not self.worker_times:
            tk.Label(self.worker_tags_inner, text="ยังไม่ได้เพิ่มเวลา (กดปุ่ม '⚡ เวลาด่วน' หรือระบุเวลาแล้วกด '+ เพิ่มเวลานี้')",
                     fg="#7C7895", bg="#FAF9FF", font=(self.F, 9)).pack(anchor="w", pady=4)
            self.lbl_worker_times_summary.configure(text="รวมทั้งหมด: 0 เวลาต่อวัน")
            return

        self.lbl_worker_times_summary.configure(
            text=f"รวมทั้งหมด: {len(self.worker_times)} เวลาต่อวัน ({', '.join(self.worker_times)})"
        )

        chip_frame = tk.Frame(self.worker_tags_inner, bg="#FAF9FF")
        chip_frame.pack(fill="x")

        for hhmm in self.worker_times:
            chip = tk.Frame(chip_frame, bg="#F0EBFF", highlightbackground="#DDD6FE", highlightthickness=1, bd=0)
            chip.pack(side="left", padx=3, pady=3)

            lbl = tk.Label(chip, text=f"⏰ {hhmm}", font=(self.F, 8, "bold"), bg="#F0EBFF", fg="#6C47FF")
            lbl.pack(side="left", padx=(6, 2), pady=3)

            btn_del = tk.Button(
                chip,
                text="✕",
                font=(self.F, 7, "bold"),
                bg="#F0EBFF",
                fg="#8E6CF7",
                activebackground="#EF4444",
                activeforeground="#FFFFFF",
                relief="flat",
                bd=0,
                cursor="hand2",
                command=lambda t=hhmm: self._remove_worker_time(t),
            )
            btn_del.pack(side="right", padx=(2, 5), pady=3)

    def _apply_worker_preset(self, count):
        from . import ai_worker_scheduler as sch
        self.worker_times = sch.get_preset_times(count)
        self._render_worker_time_tags()
        self.say(f"ตั้งค่าเวลาด่วน {count} เวลาต่อวันเรียบร้อยแล้ว (อย่าลืมกด 'บันทึกและเปิดระบบ')", "info")

    def _add_worker_custom_time(self):
        try:
            h = int(self.worker_add_hh.get())
            m = int(self.worker_add_mm.get())
            assert 0 <= h <= 23 and 0 <= m <= 59
            hhmm = f"{h:02d}:{m:02d}"
        except Exception:
            messagebox.showwarning("เวลาไม่ถูกต้อง", "กรุณาระบุชั่วโมง 00-23 และนาที 00-59")
            return
        if hhmm not in self.worker_times:
            self.worker_times.append(hhmm)
            self._render_worker_time_tags()
            self.say(f"เพิ่มเวลา {hhmm} แล้ว", "info")
        else:
            messagebox.showinfo("เวลาซ้ำ", f"เวลา {hhmm} มีอยู่ในรายการแล้ว")

    def _remove_worker_time(self, hhmm):
        if hhmm in self.worker_times:
            self.worker_times.remove(hhmm)
            self._render_worker_time_tags()

    def _clear_worker_times(self):
        if self.worker_times and messagebox.askyesno("ล้างเวลา", "ต้องการลบเวลาทั้งหมดใช่หรือไม่?"):
            self.worker_times = []
            self._render_worker_time_tags()

    def _save_and_enable_worker_schedule(self):
        from . import ai_worker_scheduler as sch
        if not self.worker_times:
            messagebox.showwarning("ยังไม่ได้กำหนดเวลา", "กรุณาเพิ่มเวลาทำงานอย่างน้อย 1 เวลา (กดปุ่ม 5, 7, 10, 15 เวลาด้านบน)")
            return

        active_plats = {k: v.get() for k, v in self.worker_plat_vars.items()}
        if not any(active_plats.values()):
            messagebox.showwarning("ยังไม่ได้เลือกแพลตฟอร์ม", "กรุณาเลือกแพลตฟอร์มที่ต้องการให้พนักงานทำงานอย่างน้อย 1 แพลตฟอร์ม")
            return

        cfg = sch.load_schedule()
        cfg["enabled"] = True
        cfg["platforms"] = active_plats
        cfg["times"] = sch.normalize_times(self.worker_times)
        sch.save_schedule(cfg)

        ok_count, msg = sch.apply_windows_scheduled_tasks(cfg["times"])

        self.refresh_worker_schedule_ui()
        self.say(f"เปิดระบบตั้งเวลาพนักงาน AI เรียบร้อย ({len(cfg['times'])} เวลาต่อวัน) - {msg}", "good")
        messagebox.showinfo(
            "เปิดระบบตั้งเวลาเรียบร้อย",
            f"เปิดระบบพนักงาน AI อัตโนมัติเรียบร้อยแล้ว!\n\n"
            f"• จำนวนรอบทำงาน: {len(cfg['times'])} เวลาต่อวัน\n"
            f"• แพลตฟอร์ม: {', '.join(k for k, v in active_plats.items() if v)}\n"
            f"• {msg}\n\n"
            f"เมื่อถึงเวลาที่กำหนด พนักงานจะทำงานให้อัตโนมัติทันที!"
        )

    def _disable_worker_schedule(self):
        if not messagebox.askyesno("ปิดระบบตั้งเวลา", "ต้องการปิดระบบพนักงานทำงานอัตโนมัติใช่หรือไม่?"):
            return
        from . import ai_worker_scheduler as sch
        cfg = sch.load_schedule()
        cfg["enabled"] = False
        sch.save_schedule(cfg)
        sch.remove_windows_scheduled_tasks()
        self.refresh_worker_schedule_ui()
        self.say("ปิดระบบตั้งเวลาพนักงาน AI เรียบร้อยแล้ว", "info")

    def _test_run_worker_now(self):
        from . import ai_worker_scheduler as sch
        active_plats = [k for k, v in self.worker_plat_vars.items() if v.get()]
        if not active_plats:
            messagebox.showwarning("เลือกแพลตฟอร์ม", "เลือกแพลตฟอร์มอย่างน้อย 1 แพลตฟอร์มเพื่อทดสอบ")
            return

        self.btn_worker_test_now.configure(state="disabled", text="⏳ พนักงานกำลังทำงาน...")
        self.say("เริ่มทดสอบการทำงานของพนักงาน AI ทันที...", "info")

        def task():
            try:
                res = sch.execute_worker_job(platforms=active_plats, log=self.say)
                self.after(0, lambda: self._on_worker_test_done(res))
            except Exception as e:
                self.after(0, lambda err=str(e): self._on_worker_test_error(err))

        threading.Thread(target=task, daemon=True).start()

    def _on_worker_test_done(self, res):
        self.btn_worker_test_now.configure(state="normal", text="🚀 ทดสอบให้พนักงานทำงานทันที (Test Run Now)")
        self.refresh_worker_schedule_ui()
        self.say(f"ทดสอบพนักงาน AI เสร็จสิ้น: สำเร็จ {res.get('success_count', 0)} งาน", "good")
        messagebox.showinfo("ทดสอบสำเร็จ", f"พนักงาน AI ทำงานเสร็จเรียบร้อยแล้ว!\n\nผลลัพธ์:\n{json.dumps(res.get('results', {}), ensure_ascii=False, indent=2)}")

    def _on_worker_test_error(self, err_msg):
        self.btn_worker_test_now.configure(state="normal", text="🚀 ทดสอบให้พนักงานทำงานทันที (Test Run Now)")
        self.say(f"ทดสอบพนักงานผิดพลาด: {err_msg}", "bad")
        messagebox.showerror("เกิดข้อผิดพลาด", f"การทำงานของพนักงานผิดพลาด:\n{err_msg}")

    def refresh_worker_schedule_ui(self):
        from . import ai_worker_scheduler as sch
        cfg = sch.load_schedule()
        enabled = cfg.get("enabled", False)

        for k, var in self.worker_plat_vars.items():
            if k in cfg.get("platforms", {}):
                var.set(bool(cfg["platforms"][k]))

        self.worker_times = cfg.get("times", [])
        self._render_worker_time_tags()

        next_hhmm, next_str = sch.get_next_run(self.worker_times)

        if enabled:
            self.lbl_worker_status_icon.configure(text="🟢")
            self.lbl_worker_status_text.configure(
                text="ระบบพนักงานอัตโนมัติ: กำลังเปิดใช้งาน (Active)",
                foreground=GOOD
            )
            self.lbl_worker_next_run.configure(
                text=f"รอบต่อไป: {next_str}",
                foreground=ACCENT_D
            )
            if hasattr(self, "stat_vals") and "next" in self.stat_vals:
                self.stat_vals["next"].configure(text=next_hhmm or "เปิด")
        else:
            self.lbl_worker_status_icon.configure(text="⚪")
            self.lbl_worker_status_text.configure(
                text="ระบบพนักงานอัตโนมัติ: ปิดอยู่ (Disabled)",
                foreground=WARN
            )
            self.lbl_worker_next_run.configure(
                text="กดปุ่ม 'บันทึกและเปิดระบบตั้งเวลา' ด้านล่างเพื่อเริ่มการทำงานอัตโนมัติ",
                foreground=MUTED
            )
            if hasattr(self, "stat_vals") and "next" in self.stat_vals:
                self.stat_vals["next"].configure(text="ปิด")

        if hasattr(self, "txt_worker_history"):
            self.txt_worker_history.delete("1.0", "end")
            hist = cfg.get("history", [])
            if not hist:
                self.txt_worker_history.insert("1.0", "(ยังไม่มีประวัติการทำงาน - เมื่อถึงเวลาพนักงานจะบันทึกผลการทำงานที่นี่)")
            else:
                lines = []
                for item in hist[:8]:
                    t = item.get("time", "")
                    res = item.get("results", {})
                    res_str = ", ".join(f"{k}: {v}" for k, v in res.items())
                    lines.append(f"• [{t}] {res_str}")
                self.txt_worker_history.insert("1.0", "\n".join(lines))

    def _worker_heartbeat(self):
        try:
            from . import ai_worker_scheduler as sch
            cfg = sch.load_schedule()
            if cfg.get("enabled"):
                times = sch.normalize_times(cfg.get("times", []))
                now_hhmm = dt.datetime.now().strftime("%H:%M")
                if now_hhmm in times and getattr(self, "_last_worker_minute", None) != now_hhmm:
                    self._last_worker_minute = now_hhmm
                    self.say(f"⏰ ถึงเวลา {now_hhmm} น.: พนักงาน AI กำลังทำงานทันที...", "good")
                    def run():
                        sch.execute_worker_job(log=self.say)
                        self.after(0, self.refresh_worker_schedule_ui)
                    threading.Thread(target=run, daemon=True).start()

                if hasattr(self, "lbl_worker_next_run"):
                    _, next_str = sch.get_next_run(times)
                    self.lbl_worker_next_run.configure(text=f"รอบต่อไป: {next_str}")
        except Exception:
            pass
        finally:
            self.after(15000, self._worker_heartbeat)

    def refresh_schedule(self):
        self.refresh_worker_schedule_ui()

    def save_schedule(self):
        self._save_and_enable_worker_schedule()

    def remove_schedule(self):
        self._disable_worker_schedule()

    # ------------------------------------------------------------------ settings tab
    def _build_settings(self):
        t = self.tab_set

        # ---------------- TOP HEADER CARD ----------------
        hdr_card = tk.Frame(t, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        hdr_card.pack(fill="x", pady=(0, 10))

        hdr_inner = tk.Frame(hdr_card, bg="#FFFFFF", padx=16, pady=12)
        hdr_inner.pack(fill="x")

        hdr_icon_box = tk.Frame(hdr_inner, bg="#F0EBFF", width=42, height=42)
        hdr_icon_box.pack_propagate(False)
        hdr_icon_box.pack(side="left", padx=(0, 12))
        tk.Label(hdr_icon_box, text="⚙️", font=(self.F, 18), bg="#F0EBFF").pack(expand=True)

        hdr_titles = tk.Frame(hdr_inner, bg="#FFFFFF")
        hdr_titles.pack(side="left", fill="x", expand=True)
        tk.Label(hdr_titles, text="การตั้งค่าระบบ (Settings)", font=(self.F, 13, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")
        tk.Label(hdr_titles, text="จัดการข้อมูลช่อง, คีย์เชื่อมต่อ AI Gemini, บริการเสียง Azure Speech และตั้งค่าเสียงตัวละคร",
                 font=(self.F, 9), fg="#7C7895", bg="#FFFFFF").pack(anchor="w", pady=(2, 0))

        tk.Button(
            hdr_inner,
            text="💾 บันทึกการตั้งค่า",
            font=(self.F, 9, "bold"),
            bg="#8E6CF7",
            fg="#FFFFFF",
            activebackground="#7C5CEF",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=14,
            pady=6,
            command=self.save_settings
        ).pack(side="right")

        # Scrollable container
        canvas = tk.Canvas(t, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(t, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units")
                        if self.nb.select() == str(self.tab_set) else None, add="+")

        c = self.cfg
        self.v = {}

        # ---------------- 2-COLUMN GRID OF CARDS ----------------
        grid_frame = tk.Frame(inner, bg=BG)
        grid_frame.pack(fill="both", expand=True)
        grid_frame.columnconfigure(0, weight=1, uniform="set_col")
        grid_frame.columnconfigure(1, weight=1, uniform="set_col")

        left_col = tk.Frame(grid_frame, bg=BG)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        right_col = tk.Frame(grid_frame, bg=BG)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # ---------------- CARD 1: CHANNEL & VIDEO ----------------
        c1 = tk.Frame(left_col, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        c1.pack(fill="x", pady=(0, 10))

        c1_head = tk.Frame(c1, bg="#FFFFFF", padx=16, pady=14)
        c1_head.pack(fill="x")
        tk.Label(c1_head, text="📺 ช่องและคลิป (Channel & Video)", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")
        tk.Label(c1_head, text="ตั้งค่าชื่อช่องสำหรับแสดงในวิดีโอ และรูปแบบคลิปเริ่มต้น", font=(self.F, 9), fg="#7C7895", bg="#FFFFFF").pack(anchor="w", pady=(2, 0))

        c1_body = tk.Frame(c1, bg="#FFFFFF", padx=16, pady=14)
        c1_body.pack(fill="x")

        self.v["channel_name"] = tk.StringVar(value=c.get("channel_name", ""))
        self.v["outro_text"] = tk.StringVar(value=c.get("outro_text", ""))
        self.v["vertical"] = tk.BooleanVar(value="vertical" in c["video"]["formats"])
        self.v["horizontal"] = tk.BooleanVar(value="horizontal" in c["video"]["formats"])
        self.v["music_volume"] = tk.DoubleVar(value=float(c["audio"]["music_volume"]))

        # Channel name
        r_ch = tk.Frame(c1_body, bg="#FFFFFF")
        r_ch.pack(fill="x", pady=4)
        tk.Label(r_ch, text="ชื่อช่อง (แสดงมุมซ้ายบน)", font=(self.F, 9, "bold"), fg="#2C1D63", bg="#FFFFFF", width=20, anchor="w").pack(side="left")
        ttk.Entry(r_ch, textvariable=self.v["channel_name"], width=32).pack(side="left", fill="x", expand=True)

        # Outro text
        r_ou = tk.Frame(c1_body, bg="#FFFFFF")
        r_ou.pack(fill="x", pady=4)
        tk.Label(r_ou, text="ข้อความปิดท้ายคลิป", font=(self.F, 9, "bold"), fg="#2C1D63", bg="#FFFFFF", width=20, anchor="w").pack(side="left")
        ttk.Entry(r_ou, textvariable=self.v["outro_text"], width=32).pack(side="left", fill="x", expand=True)

        # Formats
        r_fm = tk.Frame(c1_body, bg="#FFFFFF")
        r_fm.pack(fill="x", pady=6)
        tk.Label(r_fm, text="รูปแบบคลิปเริ่มต้น", font=(self.F, 9, "bold"), fg="#2C1D63", bg="#FFFFFF", width=20, anchor="w").pack(side="left")
        fm_box = tk.Frame(r_fm, bg="#FFFFFF")
        fm_box.pack(side="left")
        ttk.Checkbutton(fm_box, text="📱 แนวตั้ง (TikTok / Shorts)", variable=self.v["vertical"]).pack(side="left")
        ttk.Checkbutton(fm_box, text="🖥️ แนวนอน (YouTube)", variable=self.v["horizontal"]).pack(side="left", padx=10)

        # BGM volume
        r_bgm = tk.Frame(c1_body, bg="#FFFFFF")
        r_bgm.pack(fill="x", pady=4)
        tk.Label(r_bgm, text="ความดังเพลงประกอบ", font=(self.F, 9, "bold"), fg="#2C1D63", bg="#FFFFFF", width=20, anchor="w").pack(side="left")
        vol_box = tk.Frame(r_bgm, bg="#FFFFFF")
        vol_box.pack(side="left", fill="x", expand=True)
        vol_lbl = tk.Label(vol_box, text=f"{int(float(c['audio']['music_volume'])*100/0.4)}%", font=(self.F, 8, "bold"), fg="#6C47FF", bg="#FFFFFF", width=5)
        def _on_vol_change(val):
            try:
                pct = int(float(val) * 100 / 0.4)
                vol_lbl.configure(text=f"{pct}%")
            except Exception:
                pass
        sc = ttk.Scale(vol_box, from_=0.0, to=0.4, variable=self.v["music_volume"], length=180, command=_on_vol_change)
        sc.pack(side="left")
        vol_lbl.pack(side="left", padx=6)

        # ---------------- CARD 3: AZURE SPEECH ----------------
        c3 = tk.Frame(left_col, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        c3.pack(fill="x", pady=(0, 10))

        c3_head = tk.Frame(c3, bg="#FFFFFF", padx=16, pady=14)
        c3_head.pack(fill="x")
        tk.Label(c3_head, text="🎤 เสียงเชิงพาณิชย์ (Azure Speech)", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")
        tk.Label(c3_head, text="ใส่เมื่อพร้อมเปิดสร้างรายได้ (หากเว้นว่างจะใช้ Edge-TTS ฟรีอัตโนมัติ)", font=(self.F, 9), fg="#7C7895", bg="#FFFFFF").pack(anchor="w", pady=(2, 0))

        c3_body = tk.Frame(c3, bg="#FFFFFF", padx=16, pady=14)
        c3_body.pack(fill="x")

        self.v["azure_key"] = tk.StringVar(value=c["tts"].get("azure_key", ""))
        self.v["azure_region"] = tk.StringVar(value=c["tts"].get("azure_region", "southeastasia"))

        r_ak = tk.Frame(c3_body, bg="#FFFFFF")
        r_ak.pack(fill="x", pady=4)
        tk.Label(r_ak, text="Azure Key", font=(self.F, 9, "bold"), fg="#2C1D63", bg="#FFFFFF", width=14, anchor="w").pack(side="left")
        ttk.Entry(r_ak, textvariable=self.v["azure_key"], width=30, show="•").pack(side="left", fill="x", expand=True)

        r_ar = tk.Frame(c3_body, bg="#FFFFFF")
        r_ar.pack(fill="x", pady=4)
        tk.Label(r_ar, text="ภูมิภาค (Region)", font=(self.F, 9, "bold"), fg="#2C1D63", bg="#FFFFFF", width=14, anchor="w").pack(side="left")
        ttk.Entry(r_ar, textvariable=self.v["azure_region"], width=20).pack(side="left")

        # ---------------- CARD 2: GEMINI AI POST ----------------
        from .credential_store import KEY_FILE
        c2 = tk.Frame(right_col, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        c2.pack(fill="x", pady=(0, 10))

        c2_head = tk.Frame(c2, bg="#FFFFFF", padx=16, pady=14)
        c2_head.pack(fill="x")
        tk.Label(c2_head, text="🤖 พนักงาน AI เขียนข้อความโพสต์ (Google Gemini)", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")
        tk.Label(c2_head, text="ใส่คีย์ครั้งเดียวเพื่อให้ AI เขียนชื่อเรื่อง คำอธิบาย และแฮชแท็กจากคลิปที่นำเข้า", font=(self.F, 9), fg="#7C7895", bg="#FFFFFF").pack(anchor="w", pady=(2, 0))

        c2_body = tk.Frame(c2, bg="#FFFFFF", padx=16, pady=14)
        c2_body.pack(fill="x")

        from .credential_store import load_key
        curr_gemini = load_key()
        ai_row = tk.Frame(c2_body, bg="#FFFFFF")
        ai_row.pack(fill="x", pady=4)
        self.gemini_key_entry = tk.StringVar(value=curr_gemini)
        ttk.Entry(ai_row, textvariable=self.gemini_key_entry, show="•", width=30).pack(side="left", fill="x", expand=True)

        tk.Button(
            ai_row,
            text="💾 บันทึกคีย์",
            font=(self.F, 8, "bold"),
            bg="#F0EBFF",
            fg="#6C47FF",
            activebackground="#8E6CF7",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=10,
            pady=4,
            command=self.save_gemini_key
        ).pack(side="left", padx=(6, 4))

        tk.Button(
            ai_row,
            text="🗑 ลบคีย์",
            font=(self.F, 8),
            bg="#FFF5F5",
            fg="#EF4444",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=8,
            pady=4,
            command=self.delete_gemini_key
        ).pack(side="left")

        is_set = bool(curr_gemini)
        self.gemini_key_status = tk.Label(
            c2_body,
            text="🟢 บันทึกแล้วในโปรแกรม (พร้อมใช้งานทุกเครื่อง)" if is_set else "⚪ ยังไม่ได้ตั้งค่า",
            font=(self.F, 8, "bold"),
            fg=GOOD if is_set else "#7C7895",
            bg="#FFFFFF"
        )
        self.gemini_key_status.pack(anchor="w", pady=(6, 0))

        # ---------------- CARD 4: CHARACTER VOICES ----------------
        c4 = tk.Frame(right_col, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        c4.pack(fill="both", expand=True, pady=(0, 10))

        c4_head = tk.Frame(c4, bg="#FFFFFF", padx=16, pady=14)
        c4_head.pack(fill="x")
        tk.Label(c4_head, text="🐰 เสียงตัวละคร (Character Voices)", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")
        tk.Label(c4_head, text="ความสูงเสียง: + สูง / - ต่ำ     ความเร็ว: + เร็ว / - ช้า", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF").pack(anchor="w", pady=(2, 0))

        c4_body = tk.Frame(c4, bg="#FFFFFF", padx=16, pady=14)
        c4_body.pack(fill="both", expand=True)

        # Header columns
        hdr_cols = tk.Frame(c4_body, bg="#FAF8FD", padx=6, pady=4)
        hdr_cols.pack(fill="x", pady=(0, 4))
        for col_txt, col_w in (("ตัวละคร", 10), ("เสียง (Voice)", 18), ("สูง (Hz)", 7), ("เร็ว (%)", 7), ("", 8)):
            tk.Label(hdr_cols, text=col_txt, font=(self.F, 8, "bold"), fg="#7C7895", bg="#FAF8FD", width=col_w, anchor="w").pack(side="left", padx=2)

        self.voice_vars = {}
        for who in ["narrator", "bunny", "bear", "chick", "cat"]:
            vc = c["voices"].get(who, {})
            nv = tk.StringVar(value=vc.get("edge", VOICE_CHOICES[0]))
            pv = tk.IntVar(value=int(str(vc.get("pitch", "+0Hz")).replace("Hz", "")))
            rv = tk.IntVar(value=int(str(vc.get("rate", "+0%")).replace("%", "")))
            self.voice_vars[who] = (nv, pv, rv)

            row = tk.Frame(c4_body, bg="#FFFFFF", pady=2)
            row.pack(fill="x")

            # Character name
            name_txt = CHAR_NAMES[who].split(" ")[0]
            tk.Label(row, text=name_txt, font=(self.F, 9, "bold"), fg="#2C1D63", bg="#FFFFFF", width=10, anchor="w").pack(side="left", padx=2)

            # Voice combobox
            ttk.Combobox(row, textvariable=nv, values=VOICE_CHOICES, state="readonly", width=16).pack(side="left", padx=2)

            # Pitch spinbox
            ttk.Spinbox(row, from_=-50, to=100, increment=5, textvariable=pv, width=5).pack(side="left", padx=2)

            # Rate spinbox
            ttk.Spinbox(row, from_=-50, to=50, increment=5, textvariable=rv, width=5).pack(side="left", padx=2)

            # Play button
            tk.Button(
                row,
                text="▶ ฟังเสียง",
                font=(self.F, 8),
                bg="#F0EBFF",
                fg="#6C47FF",
                activebackground="#8E6CF7",
                activeforeground="#FFFFFF",
                relief="flat",
                bd=0,
                cursor="hand2",
                padx=6,
                pady=2,
                command=lambda w=who: self.test_voice(w)
            ).pack(side="left", padx=4)

        # ---------------- BOTTOM ACTIONS ----------------
        sv = tk.Frame(inner, bg=BG)
        sv.pack(fill="x", pady=12)

        tk.Button(
            sv,
            text="💾 บันทึกการตั้งค่าทั้งหมด (ใช้ได้ทุกเครื่อง)",
            font=(self.F, 10, "bold"),
            bg="#8E6CF7",
            fg="#FFFFFF",
            activebackground="#7C5CEF",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=16,
            pady=8,
            command=self.save_settings
        ).pack(side="left")

        tk.Button(
            sv,
            text="🧹 ล้าง/เคลียร์ค่าทั้งหมด",
            font=(self.F, 9, "bold"),
            bg="#FFF1F2",
            fg="#E11D48",
            activebackground="#FFE4E6",
            activeforeground="#BE123C",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=8,
            command=self.clear_all_settings
        ).pack(side="left", padx=6)

        tk.Button(
            sv,
            text="📥 นำเข้าการตั้งค่า (Import)",
            font=(self.F, 9),
            bg="#F0EBFF",
            fg="#6C47FF",
            activebackground="#8E6CF7",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=8,
            command=self.import_settings
        ).pack(side="left", padx=6)

        tk.Button(
            sv,
            text="📤 ส่งออกการตั้งค่า (Export)",
            font=(self.F, 9),
            bg="#FFFFFF",
            fg="#2C1D63",
            activebackground="#F0EBFF",
            activeforeground="#6C47FF",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=8,
            command=self.export_settings
        ).pack(side="left", padx=6)

        tk.Button(
            sv,
            text="🔄 คืนค่าเริ่มต้น",
            font=(self.F, 9),
            bg="#FFFFFF",
            fg="#7C7895",
            activebackground="#F0EBFF",
            activeforeground="#6C47FF",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=8,
            command=self.reset_settings
        ).pack(side="left", padx=6)

    def _collect_cfg(self):
        p = ROOT / "config.json"
        raw = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        raw.setdefault("video", {})
        raw.setdefault("audio", {})
        raw.setdefault("tts", {})
        raw.setdefault("voices", {})
        raw["channel_name"] = self.v["channel_name"].get().strip()
        raw["outro_text"] = self.v["outro_text"].get().strip()
        fm = [f for f in ("vertical", "horizontal") if self.v[f].get()] or ["vertical"]
        raw["video"]["formats"] = fm
        raw["audio"]["music_volume"] = round(float(self.v["music_volume"].get()), 3)
        raw["tts"]["azure_key"] = self.v["azure_key"].get().strip()
        raw["tts"]["azure_region"] = self.v["azure_region"].get().strip() or "southeastasia"
        for who, (nv, pv, rv) in self.voice_vars.items():
            vc = dict(cfgmod.DEFAULTS["voices"].get(who, {}), **raw["voices"].get(who, {}))
            vc["edge"] = nv.get()
            vc["pitch"] = "%+dHz" % int(pv.get())
            vc["rate"] = "%+d%%" % int(rv.get())
            raw["voices"][who] = vc
        return raw

    def save_settings(self):
        try:
            raw = self._collect_cfg()
        except Exception as e:
            messagebox.showwarning("ตั้งค่า", "ค่าบางช่องไม่ถูกต้อง: %s" % e)
            return

        from .credential_store import save_key, delete_key
        gemini_txt = self.gemini_key_entry.get().strip() if hasattr(self, "gemini_key_entry") else ""
        if gemini_txt:
            raw["gemini_key"] = gemini_txt
            try:
                save_key(gemini_txt)
                if hasattr(self, "gemini_key_status"):
                    self.gemini_key_status.configure(text="🟢 บันทึกแล้วในโปรแกรม (พร้อมใช้งานทุกเครื่อง)", fg=GOOD)
            except Exception:
                pass
        else:
            raw.pop("gemini_key", None)
            delete_key()
            if hasattr(self, "gemini_key_status"):
                self.gemini_key_status.configure(text="⚪ ยังไม่ได้ตั้งค่า", fg="#7C7895")

        (ROOT / "config.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        self.cfg = cfgmod.load()
        self.say("บันทึกการตั้งค่าทั้งหมดลงในโปรแกรมเรียบร้อยแล้ว", "good")
        messagebox.showinfo("บันทึกสำเร็จ", "บันทึกการตั้งค่าทั้งหมดลงในโปรแกรมเรียบร้อยแล้ว!\nสามารถคัดลอกโฟลเดอร์โปรแกรมไปใช้ที่เครื่องไหนก็ได้ทันที")

    def save_gemini_key(self):
        from .credential_store import save_key
        key_val = self.gemini_key_entry.get().strip()
        try:
            save_key(key_val)
        except Exception as exc:
            messagebox.showerror("Gemini API key", str(exc))
            return
        self.gemini_key_status.configure(text="🟢 บันทึกแล้วในโปรแกรม (พร้อมใช้งานทุกเครื่อง)", fg=GOOD)
        self.say("บันทึก Gemini API key ลงในโปรแกรมเรียบร้อยแล้ว", "good")
        messagebox.showinfo("บันทึกคีย์สำเร็จ", "บันทึก Gemini API key ลงในไฟล์โปรแกรมแล้ว สามารถย้ายไปใช้เครื่องอื่นได้ทันที!")

    def clear_all_settings(self):
        if not messagebox.askyesno(
            "ยืนยันการล้างการตั้งค่า",
            "⚠️ ต้องการล้างการตั้งค่าทั้งหมดและเคลียร์ข้อมูลในหน้านี้หรือไม่?\n\n"
            "สิ่งที่จะถูกล้าง:\n"
            "• ชื่อช่อง และข้อความปิดท้ายคลิป\n"
            "• คีย์ Gemini API และ Azure Speech Key\n"
            "• คืนค่าเสียงตัวละครและความดังเพลงเป็นค่าเริ่มต้น\n\n"
            "กด 'Yes' เพื่อล้างค่าทั้งหมด"
        ):
            return

        try:
            from .credential_store import delete_key
            import copy
            delete_key()

            raw = copy.deepcopy(cfgmod.DEFAULTS)
            raw["channel_name"] = ""
            raw["outro_text"] = ""
            raw["tts"]["azure_key"] = ""
            raw["tts"]["azure_region"] = "southeastasia"
            raw.pop("gemini_key", None)

            p = ROOT / "config.json"
            p.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

            self.cfg = cfgmod.load()
            for w in self.tab_set.winfo_children():
                w.destroy()
            self._build_settings()

            self.say("ล้างการตั้งค่าทั้งหมดเรียบร้อยแล้ว", "good")
            messagebox.showinfo("ล้างค่าสำเร็จ", "ล้างการตั้งค่าและเคลียร์ข้อมูลทั้งหมดเรียบร้อยแล้ว!")
        except Exception as e:
            messagebox.showerror("เกิดข้อผิดพลาด", f"ไม่สามารถล้างการตั้งค่าได้:\n{e}")

    def delete_gemini_key(self):
        from .credential_store import delete_key
        delete_key()
        self.gemini_key_status.configure(text="ยังไม่ได้ตั้งค่า")
        self.say("ลบ Gemini API key แล้ว", "good")

    def reset_settings(self):
        if messagebox.askyesno("คืนค่าเริ่มต้น", "คืนค่าการตั้งค่าทั้งหมดเป็นค่าเริ่มต้น?"):
            cfgmod.write_default()
            self.cfg = cfgmod.load()
            for w in self.tab_set.winfo_children():
                w.destroy()
            self._build_settings()
            self.say("คืนค่าเริ่มต้นแล้ว", "good")

    def import_settings(self):
        fpath = filedialog.askopenfilename(
            title="เลือกไฟล์การตั้งค่า (config.json) จากอีกเครื่อง",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not fpath:
            return
        try:
            p = Path(fpath)
            new_cfg = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(new_cfg, dict):
                raise ValueError("โครงสร้างไฟล์ JSON ไม่ถูกต้อง")
            target_path = ROOT / "config.json"
            target_path.write_text(json.dumps(new_cfg, ensure_ascii=False, indent=2), encoding="utf-8")

            # Check if secrets folder exists in source directory
            src_secrets = p.parent / "secrets"
            if src_secrets.is_dir():
                sec_files = list(src_secrets.glob("*.json"))
                if sec_files:
                    if messagebox.askyesno("พบโฟลเดอร์ Secrets",
                                           f"พบไฟล์เชื่อมต่อบัญชีโซเชียล ({len(sec_files)} ไฟล์) ในโฟลเดอร์ secrets ของเครื่องเดิม\nต้องการนำเข้ามาด้วยหรือไม่?"):
                        dst_secrets = ROOT / "secrets"
                        dst_secrets.mkdir(parents=True, exist_ok=True)
                        for sf in sec_files:
                            (dst_secrets / sf.name).write_text(sf.read_text(encoding="utf-8"), encoding="utf-8")

            self.cfg = cfgmod.load()
            for w in self.tab_set.winfo_children():
                w.destroy()
            self._build_settings()
            self.say("นำเข้าการตั้งค่าจากอีกเครื่องสำเร็จแล้ว!", "good")
            messagebox.showinfo("นำเข้าสำเร็จ", "นำเข้าการตั้งค่าจากอีกเครื่องเรียบร้อยแล้ว!\nระบบได้อัปเดตหน้าต่างการตั้งค่าตามข้อมูลใหม่แล้ว")
        except Exception as e:
            messagebox.showerror("นำเข้าไม่สำเร็จ", f"เกิดข้อผิดพลาดในการนำเข้าไฟล์การตั้งค่า:\n{e}")

    def export_settings(self):
        fpath = filedialog.asksaveasfilename(
            title="บันทึกไฟล์การตั้งค่าเพื่อนำไปใช้อีกเครื่อง",
            initialfile="config.json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not fpath:
            return
        try:
            raw = self._collect_cfg()
            p = Path(fpath)
            p.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

            src_secrets = ROOT / "secrets"
            if src_secrets.is_dir():
                sec_files = list(src_secrets.glob("*.json"))
                if sec_files:
                    if messagebox.askyesno("ส่งออก Secrets",
                                           f"ต้องการส่งออกไฟล์เชื่อมต่อโซเชียล ({len(sec_files)} ไฟล์) ไปยังโฟลเดอร์ secrets ข้างๆ ไฟล์นี้ด้วยหรือไม่?"):
                        dst_secrets = p.parent / "secrets"
                        dst_secrets.mkdir(parents=True, exist_ok=True)
                        for sf in sec_files:
                            (dst_secrets / sf.name).write_text(sf.read_text(encoding="utf-8"), encoding="utf-8")

            self.say("ส่งออกการตั้งค่าเรียบร้อยแล้ว", "good")
            messagebox.showinfo("ส่งออกสำเร็จ", f"ส่งออกการตั้งค่าเรียบร้อยแล้วที่:\n{fpath}")
        except Exception as e:
            messagebox.showerror("ส่งออกไม่สำเร็จ", f"เกิดข้อผิดพลาดในการส่งออก:\n{e}")

    def test_voice(self, who):
        try:
            raw = self._collect_cfg()
        except Exception:
            return
        vc = dict(raw["voices"][who], _azure_key=raw["tts"].get("azure_key", ""),
                  _azure_region=raw["tts"].get("azure_region", "southeastasia"))
        text = {"narrator": "สวัสดีจ้ะ เด็กๆ วันนี้เรามาเรียนนับเลขกันนะ",
                "bunny": "สวัสดีจ้ะ ปุยฝ้ายเองจ้ะ", "bear": "สวัสดีครับ โกโก้มาแล้วครับ",
                "chick": "เจี๊ยบ เจี๊ยบ สวัสดีจ้ะ", "cat": "เหมียว มิวมิวมาแล้วจ้ะ"}[who]
        engines = [e for e in raw["tts"].get("engines", self.cfg["tts"]["engines"]) if e not in ("espeak", "silent")]
        self.say("กำลังสร้างเสียง %s..." % CHAR_NAMES[who])

        def work():
            from . import tts
            try:
                x, eng = tts.synth_with_fallback(text, vc, engines, ROOT / "cache" / "tts", lambda m: None)
                from . import audio
                p = ROOT / "cache" / ("voice_test_%s.wav" % who)
                audio.write_wav(p, x)
                self.q.put(("play", str(p)))
                self.q.put(("log", ("เล่นเสียง %s (%s)" % (CHAR_NAMES[who], eng), "good")))
            except Exception as e:
                self.q.put(("log", ("สร้างเสียงไม่สำเร็จ: %s" % e, "bad")))

        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------------ planner tab (AI ideas -> requests)
    LENGTHS = [("30 วินาที", 30), ("1 นาที", 60), ("2 นาที", 120), ("3 นาที", 180),
               ("5 นาที (คลิปรวม)", 300), ("10 นาที (คลิปรวม)", 600), ("20 นาที (คลิปรวม)", 1200)]
    FORMATS = [("อัตโนมัติตามความยาว", "auto"), ("แนวตั้ง (TikTok / Shorts)", "vertical"),
               ("แนวนอน (YouTube)", "horizontal"), ("ทั้งสองแบบ", "both")]

    def _build_plan(self):
        t = self.tab_plan
        self._plan_img_cache = []

        # Top Bar Card
        bar = tk.Frame(t, bg="#FFFFFF", padx=16, pady=10, highlightbackground="#EAE4F8", highlightthickness=1, bd=0)
        bar.pack(fill="x", padx=4, pady=(2, 8))

        b_left = tk.Frame(bar, bg="#FFFFFF")
        b_left.pack(side="left")

        # Calendar box
        c_box = tk.Frame(b_left, bg="#EDE7FE", padx=8, pady=6, highlightbackground="#D2C3F8", highlightthickness=1, bd=0)
        c_box.pack(side="left", padx=(0, 10))
        tk.Label(c_box, text="📅", font=(self.F, 16), bg="#EDE7FE").pack()

        t_box = tk.Frame(b_left, bg="#FFFFFF")
        t_box.pack(side="left")
        title_line = tk.Frame(t_box, bg="#FFFFFF")
        title_line.pack(anchor="w")
        tk.Label(title_line, text="วางแผนไอเดียด้วย ", font=(self.F, 16, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left")
        tk.Label(title_line, text="AI", font=(self.F, 16, "bold"), fg="#6C47FF", bg="#FFFFFF").pack(side="left")

        tk.Label(t_box, text="ให้ AI ช่วยคิดไอเดียคอนเทนต์สำหรับเด็กไทย สร้างสรรค์ ปลอดภัย และเหมาะกับทุกแพลตฟอร์ม",
                 font=(self.F, 9), fg="#7C7895", bg="#FFFFFF").pack(anchor="w")

        # Right Action Buttons
        b_right = tk.Frame(bar, bg="#FFFFFF")
        b_right.pack(side="right")

        btn_ref = RoundedButton(b_right, text="🔄 รีเฟรชข้อมูล", bg="#F4F0FD", fg="#6C47FF", border="#E0D6F8", bd=1,
                                radius=8, padx=12, pady=5, command=self.refresh_plan)
        btn_ref.pack(side="left", padx=4)

        btn_fav = RoundedButton(b_right, text="✔ เลือกไอเดียที่ชอบ", bg="#E8F8F0", fg="#0E9F6E", border="#BBEED4", bd=1,
                                radius=8, padx=12, pady=5, command=self.copy_product_prompt)
        btn_fav.pack(side="left", padx=4)

        btn_gen = RoundedButton(b_right, text="📄 สร้างเป็นบท", bg="#EDE7FE", fg="#6C47FF", border="#D2C3F8", bd=1,
                                radius=8, padx=14, pady=5, command=self.import_plan_response)
        btn_gen.pack(side="left", padx=4)

        # Main Area: Upper Grid (Ideas on Left, New Request Form on Right)
        upper = tk.Frame(t, bg="#F0ECFD")
        upper.pack(fill="both", expand=True, padx=4, pady=(0, 6))

        # --- LEFT: Ideas generated by AI ---
        left_card = tk.Frame(upper, bg="#FFFFFF", padx=12, pady=10, highlightbackground="#EAE4F8", highlightthickness=1, bd=0)
        left_card.pack(side="left", fill="both", expand=True, padx=(0, 6))

        l_head = tk.Frame(left_card, bg="#FFFFFF")
        l_head.pack(fill="x", pady=(0, 8))
        tk.Label(l_head, text="💡 ไอเดียที่ AI สร้างให้", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left")

        self.plan_updated = tk.Label(l_head, text="ทั้งหมด 12 ไอเดีย", font=(self.F, 8, "bold"), fg="#6C47FF", bg="#F0EBFF", padx=6, pady=2)
        self.plan_updated.pack(side="left", padx=10)

        self.plan_genre = tk.StringVar(value="ทุกแนว")
        self.plan_genre_cb = ttk.Combobox(l_head, textvariable=self.plan_genre, state="readonly", width=14)
        self.plan_genre_cb.pack(side="right")
        self.plan_genre_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_plan())

        # Treeview for Ideas
        cols = ("num", "genre", "title", "why", "len")
        self.tv_i = ttk.Treeview(left_card, columns=cols, show="headings", selectmode="extended", height=8)
        self.tv_i.heading("num", text="#")
        self.tv_i.column("num", width=35, anchor="center")
        self.tv_i.heading("genre", text="แนว")
        self.tv_i.column("genre", width=110, anchor="w")
        self.tv_i.heading("title", text="ไอเดีย")
        self.tv_i.column("title", width=250, anchor="w")
        self.tv_i.heading("why", text="ทำไมน่าทำ")
        self.tv_i.column("why", width=230, anchor="w")
        self.tv_i.heading("len", text="ความยาวแนะนำ")
        self.tv_i.column("len", width=95, anchor="center")
        self.tv_i.pack(fill="both", expand=True)

        # --- RIGHT: Create New Idea Request Form ---
        right_card = tk.Frame(upper, bg="#FFFFFF", padx=12, pady=10, width=390, highlightbackground="#EAE4F8", highlightthickness=1, bd=0)
        right_card.pack(side="right", fill="y", padx=(6, 0))
        right_card.pack_propagate(False)

        r_head = tk.Frame(right_card, bg="#FFFFFF")
        r_head.pack(fill="x", pady=(0, 6))
        tk.Label(r_head, text="✨ สร้างคำขอไอเดียใหม่", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left")
        lnk_sample = tk.Label(r_head, text="📖 ดูตัวอย่างคำสั่ง", font=(self.F, 8), fg="#6C47FF", bg="#FFFFFF", cursor="hand2")
        lnk_sample.pack(side="right")
        lnk_sample.bind("<Button-1>", lambda e: self.open_plan_request())

        # 1. Choose AI Provider (3 clickable cards)
        tk.Label(right_card, text="1. เลือกผู้ให้บริการ AI", font=(self.F, 9, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w", pady=(2, 4))
        self.req_provider = tk.StringVar(value="claude")

        p_row = tk.Frame(right_card, bg="#FFFFFF")
        p_row.pack(fill="x", pady=(0, 6))
        for i in range(3): p_row.columnconfigure(i, weight=1, uniform="prov")

        prov_defs = [
            ("claude", "Claude", "plan_claude_icon_hd.png", "สร้างสรรค์และอบอุ่น"),
            ("gemini", "Gemini", "plan_gemini_icon_hd.png", "หลากหลายและทันสมัย"),
            ("gpt", "ChatGPT", "plan_chatgpt_icon_hd.png", "โครงสร้างชัดเจน"),
        ]
        self._prov_cards = {}
        for idx, (pval, pname, picon, pdesc) in enumerate(prov_defs):
            pcard = tk.Frame(p_row, bg="#FAF8FE" if pval == "claude" else "#FFFFFF",
                             highlightbackground="#8E6CF7" if pval == "claude" else "#EAE4F8",
                             highlightthickness=1, bd=0, padx=4, pady=6, cursor="hand2")
            pcard.grid(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else 4, 0))
            self._prov_cards[pval] = pcard

            try:
                img = ImageTk.PhotoImage(Image.open(ROOT / "studio" / picon).resize((24, 24)))
                self._plan_img_cache.append(img)
                tk.Label(pcard, image=img, bg=pcard["bg"]).pack(anchor="center")
            except Exception:
                pass

            tk.Label(pcard, text=pname, font=(self.F, 8, "bold"), fg="#2C1D63", bg=pcard["bg"]).pack(anchor="center")
            tk.Label(pcard, text=pdesc, font=(self.F, 6), fg="#7C7895", bg=pcard["bg"], wraplength=100, justify="center").pack(anchor="center")

            def _sel_p(v=pval):
                self.req_provider.set(v)
                for pk, pc in self._prov_cards.items():
                    act = (pk == v)
                    pc.configure(bg="#FAF8FE" if act else "#FFFFFF",
                                 highlightbackground="#8E6CF7" if act else "#EAE4F8")
                    for w in pc.winfo_children(): w.configure(bg="#FAF8FE" if act else "#FFFFFF")
                self._plan_provider_changed()

            pcard.bind("<Button-1>", lambda e, fn=_sel_p: fn())
            for ch in pcard.winfo_children(): ch.bind("<Button-1>", lambda e, fn=_sel_p: fn())

        # 2. Timing
        tk.Label(right_card, text="2. กำหนดเวลา", font=(self.F, 9, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w", pady=(2, 4))
        self.req_when = tk.StringVar(value="now")
        w_row = tk.Frame(right_card, bg="#FFFFFF")
        w_row.pack(fill="x", pady=(0, 4))

        tk.Radiobutton(w_row, text="ตอนนี้ (สร้างไอเดียทันที)", variable=self.req_when, value="now",
                       bg="#FFFFFF", activebackground="#FFFFFF", command=self._plan_when_changed, font=(self.F, 8)).pack(anchor="w")
        tk.Radiobutton(w_row, text="กำหนดเวลา (ตั้งเวลาสร้างไอเดียล่วงหน้า)", variable=self.req_when, value="later",
                       bg="#FFFFFF", activebackground="#FFFFFF", command=self._plan_when_changed, font=(self.F, 8)).pack(anchor="w")

        self.plan_schedule_row = tk.Frame(right_card, bg="#FFFFFF")
        self.req_date = tk.StringVar(value=(dt.date.today() + dt.timedelta(days=1)).isoformat())
        self.req_time = tk.StringVar(value="20:00")
        tk.Label(self.plan_schedule_row, text="📅 ", bg="#FFFFFF").pack(side="left")
        ttk.Entry(self.plan_schedule_row, textvariable=self.req_date, width=12).pack(side="left", padx=(0, 6))
        tk.Label(self.plan_schedule_row, text="⏰ ", bg="#FFFFFF").pack(side="left")
        ttk.Entry(self.plan_schedule_row, textvariable=self.req_time, width=8).pack(side="left")

        # 3. Additional Details
        tk.Label(right_card, text="3. รายละเอียดเพิ่มเติม (ไม่บังคับ)", font=(self.F, 9, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w", pady=(4, 2))
        self.req_custom = tk.StringVar()
        self.req_note = tk.StringVar()
        self.req_len = tk.StringVar(value=self.LENGTHS[0][0])
        self.req_fmt = tk.StringVar(value=self.FORMATS[0][0])
        self.req_count = tk.IntVar(value=1)

        txt_wrap = tk.Frame(right_card, bg="#FAF9FE", highlightbackground="#EAE4F8", highlightthickness=1, bd=0)
        txt_wrap.pack(fill="x", pady=(0, 8))
        self.txt_plan_custom = tk.Text(txt_wrap, height=3, bg="#FAF9FE", relief="flat", font=(self.F, 8),
                                       wrap="word", padx=6, pady=4)
        self.txt_plan_custom.pack(fill="x")
        self.txt_plan_custom.insert("1.0", "เช่น อยากได้ไอเดียเกี่ยวกับธรรมชาติ สำหรับเด็กประถม เรื่องสั้นๆ สนุกๆ")

        # Submit Button
        btn_sub = tk.Button(right_card, text="✨ ส่งคำขอไปยัง AI  ›", font=(self.F, 10, "bold"),
                            bg="#8E6CF7", fg="#FFFFFF", activebackground="#7C5CEF", activeforeground="#FFFFFF",
                            relief="flat", bd=0, pady=7, cursor="hand2", command=self.send_request)
        btn_sub.pack(fill="x", pady=(2, 0))

        # --- LOWER: Request History Card ---
        low = tk.Frame(t, bg="#FFFFFF", padx=12, pady=10, highlightbackground="#EAE4F8", highlightthickness=1, bd=0)
        low.pack(fill="x", padx=4, pady=(0, 4))

        low_head = tk.Frame(low, bg="#FFFFFF")
        low_head.pack(fill="x", pady=(0, 6))
        tk.Label(low_head, text="🕒 ประวัติการขอไอเดีย", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left")

        btn_cancel = tk.Button(low_head, text="ยกเลิกคำขอที่เลือก", font=(self.F, 8), bg="#FFF5F5", fg="#EF4444",
                               relief="solid", bd=1, padx=8, pady=2, cursor="hand2", command=self.cancel_request)
        btn_cancel.pack(side="right")

        cols = ("when", "what", "provider", "count", "status", "action")
        self.tv_r = ttk.Treeview(low, columns=cols, show="headings", selectmode="browse", height=4)
        for c, w, txt in (("when", 130, "วันที่ส่งคำขอ"), ("what", 360, "คำขอ (Prompt)"),
                          ("provider", 110, "ผู้ให้บริการ"), ("count", 90, "จำนวนไอเดีย"),
                          ("status", 140, "สถานะ"), ("action", 120, "การดำเนินการ")):
            self.tv_r.heading(c, text=txt)
            self.tv_r.column(c, width=w, anchor="w")
        self.tv_r.pack(fill="x")
        self.tv_r.bind("<<TreeviewSelect>>", lambda event: self._plan_request_selected())
        self.tv_r.tag_configure("done", foreground=GOOD)
        self.tv_r.tag_configure("pending", foreground=WARN)

    def _plans(self):
        d = ROOT / "plans"
        for sub in ("requests", "results"):
            (d / sub).mkdir(parents=True, exist_ok=True)
        return d

    def make_product_ideas(self):
        """Build product clip ideas (5 styles) from the NextsellerAI data pulled to nextseller/data."""
        from .product_clips import build_ideas
        try:
            items = build_ideas(20)
        except FileNotFoundError as e:
            messagebox.showinfo("คลิปสินค้า", str(e))
            return
        except Exception as e:
            messagebox.showerror("คลิปสินค้า", str(e))
            return
        self.plan_genre.set("ทุกแนว")
        self.refresh_plan()
        self.say("สร้างไอเดียคลิปสินค้า %d รายการแล้ว เลือกหนึ่งรายการแล้วกด คัดลอกพรอมต์ Flow" % len(items), "good")

    def copy_product_prompt(self):
        from .product_clips import read_prompt
        sel = [self._ideas[i] for i in self.tv_i.selection() if i in getattr(self, "_ideas", {})]
        sel = [it for it in sel if it.get("prompt_file")]
        if not sel:
            messagebox.showinfo("พรอมต์ Flow", "เลือกไอเดียแนว \"สินค้า · …\" จากรายการก่อนนะครับ")
            return
        text = read_prompt(sel[0])
        self.clipboard_clear()
        self.clipboard_append(text)
        self.say("คัดลอกพรอมต์ Flow แล้ว: %s ไปวางใน Google Flow (ใช้เครดิตบัญชีตอนกดสร้างใน Flow)" % sel[0].get("title", "")[:40],
                 "good")

    def refresh_plan(self):
        if not hasattr(self, "tv_i"):
            return
        d = self._plans()
        ideas = {}
        p = d / "ideas.json"
        if p.exists():
            try:
                ideas = json.loads(p.read_text(encoding="utf-8-sig"))
            except Exception as e:
                self.say("อ่านไฟล์ไอเดียไม่ได้: %s" % e, "bad")
        items = list(ideas.get("ideas", []))
        pp = d / "product_ideas.json"
        if pp.exists():  # product clip ideas from NextsellerAI (studio/product_clips.py)
            try:
                items += json.loads(pp.read_text(encoding="utf-8-sig")).get("ideas", [])
            except Exception as e:
                self.say("อ่านไฟล์ไอเดียคลิปสินค้าไม่ได้: %s" % e, "bad")
        genre_set = set(ideas.get("genres", []))
        genre_set.update(i.get("genre", "") for i in items if i.get("genre"))
        genres = ["ทุกแนว"] + sorted(g for g in genre_set if g)
        self.plan_genre_cb.configure(values=genres)
        want = self.plan_genre.get()
        self.tv_i.delete(*self.tv_i.get_children())
        self._ideas = {}
        for i, it in enumerate(items):
            if want != "ทุกแนว" and it.get("genre") != want:
                continue
            iid = it.get("id") or "idea%d" % i
            self._ideas[iid] = it
            self.tv_i.insert("", "end", iid=iid, values=(str(i + 1), it.get("genre", ""), it.get("title", ""),
                                                          it.get("why", ""), it.get("suggested_length", "")))
        self.plan_updated.configure(text=("ไอเดียอัปเดต %s" % ideas.get("updated", "")[:16].replace("T", " "))
                                    if ideas else "ยังไม่มีไอเดีย - AI จะสร้างให้ในรอบถัดไป")
        # requests + results
        self.tv_r.delete(*self.tv_r.get_children())
        for rp in sorted((d / "requests").glob("REQ-*.json"), reverse=True)[:50]:
            try:
                r = json.loads(rp.read_text(encoding="utf-8"))
            except Exception:
                continue
            res = d / "results" / rp.name
            provider = r.get("provider", "claude")
            provider_name = {"claude": "Claude", "gemini": "Gemini", "gpt": "ChatGPT"}.get(provider, "AI")
            if r.get("delivery") == "gemini_api":
                st = ("Gemini ตั้งเวลา " + r["scheduled_at"].replace("T", " ")) if r.get("scheduled_at") else "Gemini กำลังรัน"
            elif r.get("delivery") == "chat_handoff":
                st = "ต้องยืนยันเวลาใน %s" % provider_name if r.get("scheduled_at") else "ต้องส่งคำสั่งใน %s" % provider_name
            else:
                st = "รอ Claude อ่านคำขอ (คิวเดิม)"
            tag = "pending"
            if res.exists():
                try:
                    rr = json.loads(res.read_text(encoding="utf-8-sig"))
                    n = len(rr.get("script_ids", []))
                    st = {"done": "%s เขียนบทแล้ว %d บท" % (provider_name, n),
                          "in_progress": "%s กำลังเขียนบท" % provider_name,
                          "failed": "%s ทำไม่สำเร็จ" % provider_name}.get(
                        rr.get("status"), rr.get("status", ""))
                    if rr.get("compilation_id"):
                        st += " + คลิปรวม"
                    if rr.get("message"):
                        st += " (%s)" % rr["message"][:40]
                    tag = "done" if rr.get("status") == "done" else ""
                except Exception:
                    pass
            what = ", ".join(x.get("title", "") for x in r.get("items", []))
            if r.get("custom"):
                what = (what + ", " if what else "") + r["custom"]
            self.tv_r.insert("", "end", iid=str(rp), tags=(tag,), values=(
                r.get("created", "")[:16].replace("T", " "), what[:90],
                provider_name, str(len(r.get("items", [])) or 1), st, "👁 ดูผลลัพธ์"))

    def _plan_request_selected(self):
        selection = self.tv_r.selection()
        if not selection:
            return
        request = json.loads(Path(selection[0]).read_text(encoding="utf-8"))
        if request.get("delivery") == "chat_handoff":
            provider = {"claude": "Claude", "gemini": "Gemini", "gpt": "ChatGPT"}.get(
                request.get("provider"), "AI")
            self.plan_when.configure(text="ยังไม่ส่งไป %s: กด 'เปิดแชต / คัดลอกคำสั่ง' → วางและส่งในแชต → นำ JSON กลับ" % provider)
        elif request.get("delivery") == "gemini_api":
            self.plan_when.configure(text="Gemini API ทำงานผ่านโปรแกรม ตรวจผลด้วยปุ่ม รีเฟรช")
        else:
            self.plan_when.configure(text="คำขอเก่ารอ Claude อ่านไฟล์ ยังไม่ได้ส่งตรงจากโปรแกรม")

    def _len_label(self, sec):
        return next((lbl for lbl, s in self.LENGTHS if s == sec), "%d วิ" % sec)

    def _plan_provider_changed(self):
        provider = self.req_provider.get()
        notes = {
            "claude": "ใช้ Claude Pro ในแชต/งานตั้งเวลา; โปรแกรมเตรียมคำสั่งให้",
            "gemini": "มี Gemini API key: ทำอัตโนมัติได้ (โควตา API แยก); ไม่มีก็เปิด Gemini Pro",
            "gpt": "ใช้ ChatGPT Plus ในแชต/งานตั้งเวลา; ไม่ต้องใช้ OpenAI API key",
        }
        self.plan_provider_note.configure(text=notes.get(provider, ""))

    def _plan_when_changed(self):
        if self.req_when.get() == "later":
            self.plan_schedule_row.pack(anchor="w", pady=(3, 0))
        else:
            self.plan_schedule_row.pack_forget()

    def send_request(self):
        from .credential_store import KEY_FILE, load_key
        from .planner_generate import schedule_request
        from .planner_handoff import chat_handoff_prompt, PROVIDERS
        sel = [self._ideas[i] for i in self.tv_i.selection() if i in getattr(self, "_ideas", {})]
        custom = self.req_custom.get().strip()
        if not sel and not custom:
            messagebox.showinfo("ส่งคำขอ", "เลือกไอเดียจากรายการ หรือพิมพ์หัวข้อเองก่อนนะครับ")
            return
        sec = dict(self.LENGTHS)[self.req_len.get()]
        fmt = dict(self.FORMATS)[self.req_fmt.get()]
        if fmt == "auto":
            fmt = "horizontal" if sec >= 300 else "both"
        if fmt == "vertical" and sec > 180:
            if not messagebox.askyesno("แนวตั้ง", "แนวตั้งยาวเกิน 3 นาทีจะลง Shorts ไม่ได้ เปลี่ยนเป็นแนวนอนไหม?"):
                return
            fmt = "horizontal"
        try:
            count = max(1, min(10, int(self.req_count.get())))
        except Exception:
            count = 1
        scheduled_at = None
        if self.req_when.get() == "later":
            try:
                scheduled_at = dt.datetime.strptime(self.req_date.get().strip() + " " +
                                                    self.req_time.get().strip(), "%Y-%m-%d %H:%M")
            except ValueError:
                messagebox.showwarning("ตั้งเวลา", "ใส่วันเวลาแบบ YYYY-MM-DD และ HH:MM")
                return
            if scheduled_at <= dt.datetime.now() + dt.timedelta(minutes=1):
                messagebox.showwarning("ตั้งเวลา", "กรุณาเลือกเวลาในอนาคตอย่างน้อย 1 นาที")
                return
        now = dt.datetime.now()
        rid = "REQ-%s" % now.strftime("%Y%m%d-%H%M%S")
        if (self._plans() / "requests" / (rid + ".json")).exists():
            rid += "-%03d" % (now.microsecond // 1000)
        provider = self.req_provider.get()
        gemini_key = load_key() if provider == "gemini" else ""
        delivery = "gemini_api" if provider == "gemini" and gemini_key else "chat_handoff"
        if delivery == "gemini_api" and scheduled_at and not KEY_FILE.exists():
            messagebox.showwarning("Gemini API key", "ตั้งเวลาอัตโนมัติต้องบันทึก Gemini API key ในแท็บตั้งค่าก่อน")
            return
        if delivery == "gemini_api" and not scheduled_at and self.proc:
            messagebox.showinfo("กำลังทำงาน", "มีงานกำลังทำอยู่ รอให้เสร็จก่อนแล้วส่งคำขออีกครั้ง")
            return
        req = {"id": rid, "created": now.isoformat(timespec="seconds"), "status": "pending",
               "items": [{k: it.get(k) for k in ("id", "genre", "title", "summary", "characters") if it.get(k)}
                         for it in sel],
               "custom": custom, "length_seconds": sec, "format": fmt, "count_per_item": count,
               "note": self.req_note.get().strip(), "provider": provider, "delivery": delivery}
        if scheduled_at:
            req["scheduled_at"] = scheduled_at.isoformat(timespec="minutes")
        request_path = self._plans() / "requests" / ("%s.json" % rid)
        request_path.write_text(json.dumps(req, ensure_ascii=False, indent=2), encoding="utf-8")
        if delivery == "gemini_api" and scheduled_at:
            try:
                req["windows_task"] = schedule_request(request_path, scheduled_at, ROOT)
                request_path.write_text(json.dumps(req, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as exc:
                request_path.unlink(missing_ok=True)
                messagebox.showerror("ตั้งเวลา", str(exc))
                return
        self.req_custom.set("")
        self.req_note.set("")
        n = (len(sel) + (1 if custom else 0)) * count
        if delivery == "gemini_api" and not scheduled_at:
            if self._start(["plan-generate", "--request", str(request_path)],
                           "Gemini กำลังเขียนบท %d เรื่อง" % n):
                self.job_total = 1
            else:
                self.say("บันทึกคำขอแล้ว เลือกรายการเพื่อเปิดหรือส่งอีกครั้ง", "bad")
        elif delivery == "gemini_api":
            self.say("ตั้งเวลา Gemini เขียนบทแล้ว: %s" % scheduled_at.strftime("%Y-%m-%d %H:%M"), "good")
        else:
            prompt = chat_handoff_prompt(req)
            self.clipboard_clear()
            self.clipboard_append(prompt)
            open_path(PROVIDERS[provider][1])
            self.say("คัดลอกคำขอและเปิด %s แล้ว: วางคำสั่งในแชต%s" % (
                PROVIDERS[provider][0], "เพื่อยืนยันการตั้งเวลา" if scheduled_at else ""), "good")
        self.refresh_plan()

    def open_plan_request(self):
        from .planner_handoff import chat_handoff_prompt, PROVIDERS
        selection = self.tv_r.selection()
        if not selection:
            return
        req = json.loads(Path(selection[0]).read_text(encoding="utf-8"))
        provider = req.get("provider", "claude")
        self.clipboard_clear()
        self.clipboard_append(chat_handoff_prompt(req))
        open_path(PROVIDERS.get(provider, PROVIDERS["claude"])[1])
        self.say("คัดลอกคำขอและเปิด %s แล้ว" % PROVIDERS.get(provider, PROVIDERS["claude"])[0], "good")

    def import_plan_response(self):
        from .planner_handoff import import_response
        selection = self.tv_r.selection()
        if not selection:
            messagebox.showinfo("นำเข้าบท", "เลือกคำขอในตารางก่อน")
            return
        req = json.loads(Path(selection[0]).read_text(encoding="utf-8"))
        dialog = tk.Toplevel(self)
        dialog.title("นำเข้าบทที่ AI เขียน")
        dialog.geometry("760x560")
        dialog.transient(self)
        tk.Label(dialog, text="คัดลอก JSON ทั้งหมดที่ AI ตอบ แล้ววางด้านล่าง", fg="#7C7895", bg="#FFFFFF").pack(
            anchor="w", padx=12, pady=(12, 6))
        editor = tk.Text(dialog, wrap="word", font=("Consolas", 10))
        editor.pack(fill="both", expand=True, padx=12)
        def save():
            try:
                ids, comp = import_response(editor.get("1.0", "end"), req, ROOT)
            except Exception as exc:
                messagebox.showerror("นำเข้าบทไม่ได้", str(exc), parent=dialog)
                return
            dialog.destroy()
            self.refresh_all()
            self.say("นำเข้าบท %d เรื่อง%s" % (len(ids), " และคลิปรวม " + comp if comp else ""), "good")
        tk.Button(dialog, text="ตรวจและนำเข้าบท", bg="#8E6CF7", fg="#FFFFFF", command=save).pack(
            anchor="e", padx=12, pady=12)
        editor.focus_set()

    def cancel_request(self):
        from .planner_generate import cancel_scheduled_request
        s = self.tv_r.selection()
        if not s:
            return
        p = Path(s[0])
        result_path = self._plans() / "results" / p.name
        if result_path.exists() and json.loads(result_path.read_text(encoding="utf-8")).get("status") == "done":
            messagebox.showinfo("ยกเลิก", "คำขอนี้ AI ทำไปแล้ว ยกเลิกไม่ได้ (ลบบทในแท็บ \"บท\" แทนได้)")
            return
        if messagebox.askyesno("ยกเลิกคำขอ", "ยกเลิกคำขอนี้?"):
            request = json.loads(p.read_text(encoding="utf-8"))
            cancel_scheduled_request(request, ROOT)
            d = self._plans() / "cancelled"
            d.mkdir(exist_ok=True)
            shutil.move(str(p), d / p.name)
            result_path.unlink(missing_ok=True)
            self.refresh_plan()

    # ------------------------------------------------------------------ posting tab (employee #2)
    def _build_post(self):
        from . import publish
        t = self.tab_post

        # ---------------- TOP HEADER CARD ----------------
        hdr_card = tk.Frame(t, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        hdr_card.pack(fill="x", pady=(0, 10))

        hdr_inner = tk.Frame(hdr_card, bg="#FFFFFF", padx=16, pady=12)
        hdr_inner.pack(fill="x")

        hdr_icon_box = tk.Frame(hdr_inner, bg="#F0EBFF", width=42, height=42)
        hdr_icon_box.pack_propagate(False)
        hdr_icon_box.pack(side="left", padx=(0, 12))
        tk.Label(hdr_icon_box, text="⚙️", font=(self.F, 18), bg="#F0EBFF").pack(expand=True)

        hdr_titles = tk.Frame(hdr_inner, bg="#FFFFFF")
        hdr_titles.pack(side="left", fill="x", expand=True)
        tk.Label(hdr_titles, text="พนักงานโพสต์ (คนที่ 2) - Post Automation", font=(self.F, 13, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")
        tk.Label(hdr_titles, text="ตั้งค่าระบบเผยแพร่คลิปอัตโนมัติไปยัง YouTube, TikTok, Facebook Page และ Facebook Profile",
                 font=(self.F, 9), fg="#7C7895", bg="#FFFFFF").pack(anchor="w", pady=(2, 0))

        tk.Button(
            hdr_inner,
            text="🔄 รีเฟรชสถานะ",
            font=(self.F, 9, "bold"),
            bg="#F0EBFF",
            fg="#6C47FF",
            activebackground="#8E6CF7",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=14,
            pady=6,
            command=self.refresh_post_status
        ).pack(side="right")

        # Scrollable container
        canvas = tk.Canvas(t, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(t, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units")
                        if self.nb.select() == str(self.tab_post) else None, add="+")

        st = publish.settings(self.cfg)
        self.pv = {}
        self.plat_status = {}

        # ---------------- TOP PLATFORM STATUS CARDS ----------------
        top_cards = tk.Frame(inner, bg=BG)
        top_cards.pack(fill="x", pady=(0, 10))
        for i in range(4):
            top_cards.columnconfigure(i, weight=1, uniform="plat_top")

        # Platform status definition
        plat_headers = [
            ("youtube", "📺 YouTube", "Shorts & Long", 0),
            ("tiktok", "🎵 TikTok", "Drafts Inbox", 1),
            ("facebook_page", "📘 FB Page", "Reels Publisher", 2),
            ("facebook_profile", "👤 FB Profile", "RPA Automation", 3),
        ]

        for p_key, p_title, p_desc, col_idx in plat_headers:
            p_card = tk.Frame(top_cards, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightthickness=1, bd=0)
            p_card.grid(row=0, column=col_idx, sticky="nsew", padx=3 if col_idx not in (0, 3) else (0 if col_idx == 0 else 3, 0))
            p_inner = tk.Frame(p_card, bg="#FFFFFF", padx=12, pady=10)
            p_inner.pack(fill="both", expand=True)

            tk.Label(p_inner, text=p_title, font=(self.F, 10, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")
            tk.Label(p_inner, text=p_desc, font=(self.F, 8), fg="#7C7895", bg="#FFFFFF").pack(anchor="w", pady=(1, 4))

            status_lbl = tk.Label(p_inner, text="ยังไม่ได้เชื่อม", font=(self.F, 8, "bold"), fg=WARN, bg="#FFFFFF")
            status_lbl.pack(anchor="w")
            self.plat_status[p_key] = status_lbl

        # ---------------- TWO-COLUMN GRID ----------------
        grid_frame = tk.Frame(inner, bg=BG)
        grid_frame.pack(fill="both", expand=True)
        grid_frame.columnconfigure(0, weight=1, uniform="post_col")
        grid_frame.columnconfigure(1, weight=1, uniform="post_col")

        left_col = tk.Frame(grid_frame, bg=BG)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        right_col = tk.Frame(grid_frame, bg=BG)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # ---------------- LEFT COLUMN: CARD 1 (POST MODE) ----------------
        m = tk.Frame(left_col, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        m.pack(fill="x", pady=(0, 10))

        m_head = tk.Frame(m, bg="#FFFFFF", padx=16, pady=14)
        m_head.pack(fill="x")
        tk.Label(m_head, text="โหมดการโพสต์อัตโนมัติ", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")
        tk.Label(m_head, text="เลือกระดับความเป็นอัตโนมัติของพนักงานคนที่ 2", font=(self.F, 9), fg="#7C7895", bg="#FFFFFF").pack(anchor="w", pady=(2, 0))

        m_body = tk.Frame(m, bg="#FFFFFF", padx=16, pady=14)
        m_body.pack(fill="x")

        self.pv["mode"] = tk.StringVar(value=st["mode"])
        modes = [
            ("off", 'ไม่ออโต้ - ฉันกดปุ่มโพสต์เองในหน้า "คลิป"'),
            ("approved", 'ออโต้ เฉพาะคลิปที่ฉันกด "อนุมัติ" แล้ว (แนะนำ)'),
            ("auto", "ออโต้ทุกคลิปที่ผ่านการตรวจของระบบ (ไม่ต้องกดอนุมัติ)"),
        ]
        for val, txt in modes:
            tk.Radiobutton(m_body, text=txt, value=val, variable=self.pv["mode"], bg="#FFFFFF", fg="#2C1D63",
                           activebackground="#FFFFFF", selectcolor="#F0EBFF", font=(self.F, 9), anchor="w",
                           highlightthickness=0).pack(anchor="w", pady=2)

        # Max per day & times
        row_cfg = tk.Frame(m_body, bg="#FFFFFF")
        row_cfg.pack(fill="x", pady=(10, 4))

        tk.Label(row_cfg, text="โพสต์สูงสุดต่อวัน:", font=(self.F, 9, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left")
        self.pv["max_per_day"] = tk.IntVar(value=int(st["max_per_day"]))
        ttk.Spinbox(row_cfg, from_=1, to=10, width=4, textvariable=self.pv["max_per_day"]).pack(side="left", padx=6)
        tk.Label(row_cfg, text="คลิป", font=(self.F, 9), fg="#7C7895", bg="#FFFFFF").pack(side="left")

        row_t = tk.Frame(m_body, bg="#FFFFFF")
        row_t.pack(fill="x", pady=(4, 4))
        tk.Label(row_t, text="เวลาโพสต์:", font=(self.F, 9, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left")
        self.pv["post_times"] = tk.StringVar(value=", ".join(st["post_times"]))
        ttk.Entry(row_t, textvariable=self.pv["post_times"], width=24).pack(side="left", padx=6)
        tk.Label(row_t, text="(เช่น 12:00, 18:00)", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF").pack(side="left")

        tk.Label(m_body, fg="#7C7895", bg="#FFFFFF", wraplength=460, justify="left",
                 text="แต่ละเวลาโพสต์จะโพสต์ 1 คลิปต่อแพลตฟอร์ม จนครบจำนวนต่อวัน • ระบบข้ามคลิปที่มีคำเตือน").pack(
            anchor="w", pady=(4, 6))

        self.post_sched_lbl = tk.Label(m_body, text="", font=(self.F, 8), fg="#6C47FF", bg="#FFFFFF")
        self.post_sched_lbl.pack(anchor="w", pady=(0, 6))

        tk.Button(
            m_body,
            text="💾 บันทึกการตั้งค่าโพสต์",
            font=(self.F, 9, "bold"),
            bg="#8E6CF7",
            fg="#FFFFFF",
            activebackground="#7C5CEF",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=14,
            pady=7,
            command=self.save_post_settings
        ).pack(anchor="w")

        # ---------------- LEFT COLUMN: CARD 2 (FACEBOOK PROFILE SAFE POST) ----------------
        c_fb = tk.Frame(left_col, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        c_fb.pack(fill="x", pady=(0, 10))

        c_fb_head = tk.Frame(c_fb, bg="#FFFFFF", padx=16, pady=14)
        c_fb_head.pack(fill="x")
        tk.Label(c_fb_head, text="👤 Facebook ส่วนตัว (โปรไฟล์)", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")

        c_fb_body = tk.Frame(c_fb, bg="#FFFFFF", padx=16, pady=14)
        c_fb_body.pack(fill="x")
        tk.Label(c_fb_body, wraplength=460, justify="left", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF",
                 text="ระบบรองรับการโพสต์ลง Facebook Profile ด้วยพนักงาน RPA จำลองการทำงานผ่านเบราว์เซอร์อัตโนมัติ "
                      "หรือสามารถโพสต์ลง Facebook Page แล้วแชร์มาที่โปรไฟล์ได้อย่างปลอดภัย 100%").pack(anchor="w")

        # ---------------- LEFT COLUMN: CARD 3 (CONNECT GUIDE) ----------------
        g_card = tk.Frame(left_col, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        g_card.pack(fill="x", pady=(0, 10))

        g_head = tk.Frame(g_card, bg="#FFFFFF", padx=16, pady=14)
        g_head.pack(fill="x")
        tk.Label(g_head, text="📖 คู่มือการเชื่อมต่อบัญชีโซเชียล", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")

        g_body = tk.Frame(g_card, bg="#FFFFFF", padx=16, pady=14)
        g_body.pack(fill="x")
        tk.Label(g_body, wraplength=460, justify="left", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF",
                 text="ดูวิธีเปิด Google Cloud Console ขอ YouTube API, สมัคร Meta Developer และ TikTok for Developers พร้อมภาพขั้นตอนอย่างละเอียด").pack(anchor="w", pady=(0, 8))

        tk.Button(
            g_body,
            text="📖 เปิดคู่มือเชื่อมบัญชี (HTML)",
            font=(self.F, 8, "bold"),
            bg="#F0EBFF",
            fg="#6C47FF",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=5,
            command=lambda: open_path(ROOT / "CONNECT_ACCOUNTS_TH.html")
        ).pack(anchor="w")

        # ---------------- RIGHT COLUMN: CREDENTIALS MANAGEMENT ----------------
        # 1. YouTube Card
        yt_card = tk.Frame(right_col, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        yt_card.pack(fill="x", pady=(0, 10))

        yt_head = tk.Frame(yt_card, bg="#FFFFFF", padx=16, pady=14)
        yt_head.pack(fill="x")
        tk.Label(yt_head, text="📺 YouTube Shorts & Long", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left")

        yt_body = tk.Frame(yt_card, bg="#FFFFFF", padx=16, pady=14)
        yt_body.pack(fill="x")

        self.pv["yt_enabled"] = tk.BooleanVar(value=st["youtube"]["enabled"])
        self.pv["yt_format"] = tk.StringVar(value=st["youtube"]["format"])
        self.pv["yt_privacy"] = tk.StringVar(value=st["youtube"]["privacy"])

        yt_r1 = tk.Frame(yt_body, bg="#FFFFFF")
        yt_r1.pack(fill="x", pady=2)
        ttk.Checkbutton(yt_r1, text="เปิดใช้งาน", variable=self.pv["yt_enabled"]).pack(side="left")
        tk.Label(yt_r1, text="แบบคลิป:", font=(self.F, 8, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left", padx=(12, 4))
        ttk.Combobox(yt_r1, textvariable=self.pv["yt_format"], values=["vertical", "horizontal"], width=10, state="readonly").pack(side="left")
        tk.Label(yt_r1, text="การมองเห็น:", font=(self.F, 8, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left", padx=(10, 4))
        ttk.Combobox(yt_r1, textvariable=self.pv["yt_privacy"], values=["public", "unlisted", "private"], width=9, state="readonly").pack(side="left")

        yt_bb = tk.Frame(yt_body, bg="#FFFFFF")
        yt_bb.pack(fill="x", pady=(8, 0))
        tk.Button(yt_bb, text="1. เลือกไฟล์ client_secret.json", font=(self.F, 8), bg="#F0EBFF", fg="#6C47FF", relief="flat", bd=0, padx=8, pady=4, cursor="hand2", command=self.yt_pick_client).pack(side="left")
        tk.Button(yt_bb, text="2. เชื่อมบัญชี", font=(self.F, 8, "bold"), bg="#8E6CF7", fg="#FFFFFF", relief="flat", bd=0, padx=8, pady=4, cursor="hand2", command=self.yt_connect).pack(side="left", padx=4)
        tk.Button(yt_bb, text="ยกเลิก", font=(self.F, 8), bg="#FFF5F5", fg="#EF4444", relief="flat", bd=0, padx=6, pady=4, cursor="hand2", command=lambda: self.disconnect("youtube")).pack(side="left")

        # 2. TikTok Card
        tt_card = tk.Frame(right_col, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        tt_card.pack(fill="x", pady=(0, 10))

        tt_head = tk.Frame(tt_card, bg="#FFFFFF", padx=16, pady=14)
        tt_head.pack(fill="x")
        tk.Label(tt_head, text="🎵 TikTok (ส่งเข้าแบบร่าง)", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left")

        tt_body = tk.Frame(tt_card, bg="#FFFFFF", padx=16, pady=14)
        tt_body.pack(fill="x")

        port = int(st["tiktok"].get("redirect_port", 3455))
        self.pv["tt_enabled"] = tk.BooleanVar(value=st["tiktok"]["enabled"])
        ttk.Checkbutton(tt_body, text="เปิดใช้งาน", variable=self.pv["tt_enabled"]).pack(anchor="w", pady=2)

        self.pv["tt_key"] = tk.StringVar()
        self.pv["tt_secret"] = tk.StringVar()

        r_tk = tk.Frame(tt_body, bg="#FFFFFF")
        r_tk.pack(fill="x", pady=2)
        tk.Label(r_tk, text="Client Key:", font=(self.F, 8), fg="#2C1D63", bg="#FFFFFF", width=12, anchor="w").pack(side="left")
        ttk.Entry(r_tk, textvariable=self.pv["tt_key"], width=32).pack(side="left", fill="x", expand=True)

        r_ts = tk.Frame(tt_body, bg="#FFFFFF")
        r_ts.pack(fill="x", pady=2)
        tk.Label(r_ts, text="Client Secret:", font=(self.F, 8), fg="#2C1D63", bg="#FFFFFF", width=12, anchor="w").pack(side="left")
        ttk.Entry(r_ts, textvariable=self.pv["tt_secret"], width=32, show="•").pack(side="left", fill="x", expand=True)

        tt_bb = tk.Frame(tt_body, bg="#FFFFFF")
        tt_bb.pack(fill="x", pady=(6, 0))
        tk.Button(tt_bb, text="คัดลอก Redirect URI", font=(self.F, 8), bg="#F8F6FD", fg="#7C7895", relief="flat", bd=0, padx=6, pady=4, cursor="hand2", command=lambda: self._copy("http://127.0.0.1:%d/callback/" % port)).pack(side="left")
        tk.Button(tt_bb, text="เชื่อมบัญชี TikTok", font=(self.F, 8, "bold"), bg="#8E6CF7", fg="#FFFFFF", relief="flat", bd=0, padx=8, pady=4, cursor="hand2", command=self.tt_connect).pack(side="left", padx=4)
        tk.Button(tt_bb, text="ยกเลิก", font=(self.F, 8), bg="#FFF5F5", fg="#EF4444", relief="flat", bd=0, padx=6, pady=4, cursor="hand2", command=lambda: self.disconnect("tiktok")).pack(side="left")

        # 3. Facebook Page Card
        fb_card = tk.Frame(right_col, bg="#FFFFFF", highlightbackground="#EAE4F8", highlightcolor="#EAE4F8", highlightthickness=1, bd=0)
        fb_card.pack(fill="x", pady=(0, 10))

        fb_head = tk.Frame(fb_card, bg="#FFFFFF", padx=16, pady=14)
        fb_head.pack(fill="x")
        tk.Label(fb_head, text="📘 Facebook Page (Reels)", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left")

        fb_body = tk.Frame(fb_card, bg="#FFFFFF", padx=16, pady=14)
        fb_body.pack(fill="x")

        self.pv["fb_enabled"] = tk.BooleanVar(value=st["facebook_page"]["enabled"])
        ttk.Checkbutton(fb_body, text="เปิดใช้งาน", variable=self.pv["fb_enabled"]).pack(anchor="w", pady=2)

        self.pv["fb_app_id"] = tk.StringVar()
        self.pv["fb_secret"] = tk.StringVar()
        self.pv["fb_token"] = tk.StringVar()

        for lbl_t, key_n, is_show in (("App ID:", "fb_app_id", ""), ("App Secret:", "fb_secret", "•"), ("User Token:", "fb_token", "•")):
            r_fb = tk.Frame(fb_body, bg="#FFFFFF")
            r_fb.pack(fill="x", pady=2)
            tk.Label(r_fb, text=lbl_t, font=(self.F, 8), fg="#2C1D63", bg="#FFFFFF", width=12, anchor="w").pack(side="left")
            ttk.Entry(r_fb, textvariable=self.pv[key_n], width=32, show=is_show).pack(side="left", fill="x", expand=True)

        fb_bb = tk.Frame(fb_body, bg="#FFFFFF")
        fb_bb.pack(fill="x", pady=(6, 0))
        tk.Button(fb_bb, text="เปิด Graph Explorer", font=(self.F, 8), bg="#F8F6FD", fg="#7C7895", relief="flat", bd=0, padx=6, pady=4, cursor="hand2", command=lambda: open_path("https://developers.facebook.com/tools/explorer/")).pack(side="left")
        tk.Button(fb_bb, text="ดึงเพจ", font=(self.F, 8, "bold"), bg="#F0EBFF", fg="#6C47FF", relief="flat", bd=0, padx=6, pady=4, cursor="hand2", command=self.fb_list_pages).pack(side="left", padx=4)
        self.pv["fb_page"] = tk.StringVar()
        self.fb_page_cb = ttk.Combobox(fb_bb, textvariable=self.pv["fb_page"], width=14, state="readonly")
        self.fb_page_cb.pack(side="left")
        tk.Button(fb_bb, text="ใช้เพจนี้", font=(self.F, 8, "bold"), bg="#8E6CF7", fg="#FFFFFF", relief="flat", bd=0, padx=6, pady=4, cursor="hand2", command=self.fb_use_page).pack(side="left", padx=4)
        tk.Button(fb_bb, text="ยกเลิก", font=(self.F, 8), bg="#FFF5F5", fg="#EF4444", relief="flat", bd=0, padx=6, pady=4, cursor="hand2", command=lambda: self.disconnect("facebook_page")).pack(side="left")

        self.refresh_post_status()

    def _copy(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.say("คัดลอกแล้ว: %s" % text[:80], "good")

    def refresh_post_status(self):
        from . import publish
        if not hasattr(self, "plat_status"):
            return
        for p, lbl in self.plat_status.items():
            if publish.is_connected(p):
                lbl.configure(text="เชื่อมแล้ว: %s" % (publish.account_name(p) or "-"), foreground=GOOD)
            else:
                lbl.configure(text="ยังไม่ได้เชื่อม", foreground=WARN)

    def _bg(self, fn, ok_msg):
        def work():
            try:
                r = fn()
                self.q.put(("log", (ok_msg % (r or ""), "good")))
            except Exception as e:
                self.q.put(("log", ("ไม่สำเร็จ: %s" % e, "bad")))
            self.q.put(("call", self.refresh_post_status))
        threading.Thread(target=work, daemon=True).start()

    def yt_pick_client(self):
        from .publish import youtube
        f = filedialog.askopenfilename(title="เลือกไฟล์ client_secret.json", filetypes=[("JSON", "*.json")])
        if not f:
            return
        try:
            youtube.set_client_file(f)
            self.say("บันทึกไฟล์ client_secret.json แล้ว ต่อไปกด \"เชื่อมบัญชี YouTube\"", "good")
        except Exception as e:
            messagebox.showwarning("YouTube", str(e))

    def yt_connect(self):
        from .publish import youtube
        self.say("กำลังเปิดเบราว์เซอร์ให้ล็อกอิน Google...")
        self._bg(youtube.connect, "เชื่อม YouTube แล้ว: ช่อง %s")

    def fb_list_pages(self):
        from . import publish
        from .publish import facebook
        a, s, tok = self.pv["fb_app_id"].get().strip(), self.pv["fb_secret"].get().strip(), self.pv["fb_token"].get().strip()
        if not (a and s and tok):
            messagebox.showinfo("Facebook", "ใส่ App ID, App Secret และ User token ให้ครบก่อน")
            return
        ver = publish.settings(self.cfg)["facebook_page"]["graph_version"]

        def work():
            try:
                pages = facebook.list_pages(a, s, tok, ver)
                self.q.put(("call", lambda: self._fb_pages(pages)))
            except Exception as e:
                self.q.put(("log", ("ดึงรายชื่อเพจไม่สำเร็จ: %s" % e, "bad")))
        threading.Thread(target=work, daemon=True).start()

    def _fb_pages(self, pages):
        self._pages = pages
        self.fb_page_cb.configure(values=[p["name"] for p in pages])
        if pages:
            self.fb_page_cb.current(0)
            self.say("พบ %d เพจ เลือกเพจแล้วกด \"ใช้เพจนี้\"" % len(pages), "good")
        else:
            self.say("ไม่พบเพจที่บัญชีนี้โพสต์ได้", "bad")

    def fb_use_page(self):
        from .publish import facebook
        name = self.pv["fb_page"].get()
        page = next((p for p in getattr(self, "_pages", []) if p["name"] == name), None)
        if not page:
            return
        facebook.save_page(page)
        self.pv["fb_token"].set("")
        self.pv["fb_secret"].set("")
        self.say("เชื่อมเพจ %s แล้ว" % name, "good")
        self.refresh_post_status()

    def tt_connect(self):
        from . import publish
        from .publish import tiktok
        k, s = self.pv["tt_key"].get().strip(), self.pv["tt_secret"].get().strip()
        if k and s:
            tiktok.save_app(k, s)
            self.pv["tt_secret"].set("")
        elif not publish.load_secret("tiktok_app"):
            messagebox.showinfo("TikTok", "ใส่ Client key และ Client secret ก่อน")
            return
        port = publish.settings(self.cfg)["tiktok"].get("redirect_port", 3455)
        self.say("กำลังเปิดเบราว์เซอร์ให้ล็อกอิน TikTok...")
        self._bg(lambda: tiktok.connect(port), "เชื่อม TikTok แล้ว: %s")

    def disconnect(self, platform):
        from . import publish
        if messagebox.askyesno("ยกเลิกการเชื่อม", "ยกเลิกการเชื่อม %s?" % publish.LABEL[platform]):
            publish.module(platform).disconnect()
            self.refresh_post_status()

    def save_post_settings(self):
        import re
        times = [x.strip() for x in self.pv["post_times"].get().replace(" ", ",").split(",") if x.strip()]
        bad = [x for x in times if not re.match(r"^([01]?\d|2[0-3]):[0-5]\d$", x)]
        if bad or not times:
            messagebox.showwarning("เวลาโพสต์", "เวลาไม่ถูกต้อง: %s (ใช้แบบ 12:00, 18:00)" % ", ".join(bad))
            return
        times = ["%02d:%s" % (int(x.split(":")[0]), x.split(":")[1]) for x in times][:6]
        p = ROOT / "config.json"
        raw = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        pub = raw.setdefault("publish", {})
        pub["mode"] = self.pv["mode"].get()
        pub["max_per_day"] = int(self.pv["max_per_day"].get())
        pub["post_times"] = times
        pub.setdefault("youtube", {}).update(enabled=bool(self.pv["yt_enabled"].get()),
                                             format=self.pv["yt_format"].get(), privacy=self.pv["yt_privacy"].get())
        pub.setdefault("facebook_page", {}).update(enabled=bool(self.pv["fb_enabled"].get()), format="vertical")
        pub.setdefault("tiktok", {}).update(enabled=bool(self.pv["tt_enabled"].get()), format="vertical")
        p.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        self.cfg = cfgmod.load()
        # Windows tasks: one per post time, only when a mode other than "off" is chosen
        msg = self._apply_post_tasks(times if pub["mode"] != "off" else [])
        self.say("บันทึกการตั้งค่าโพสต์แล้ว (%s) %s" % (
            {"off": "ไม่ออโต้", "approved": "ออโต้เฉพาะที่อนุมัติ", "auto": "ออโต้ทั้งหมด"}[pub["mode"]], msg), "good")

    def _apply_post_tasks(self, times):
        if not IS_WIN:
            return "(ตั้งเวลาได้บน Windows เท่านั้น)"
        for i in range(1, 9):
            subprocess.run(["schtasks", "/Delete", "/F", "/TN", "KidsStudio Auto Post %d" % i],
                           capture_output=True, **NOWIN)
        bat = ROOT / "run_post_auto.bat"
        ok = 0
        for i, hhmm in enumerate(times, 1):
            r = subprocess.run(["schtasks", "/Create", "/F", "/TN", "KidsStudio Auto Post %d" % i, "/SC", "DAILY",
                                "/ST", hhmm, "/TR", '"%s"' % bat], capture_output=True, text=True, **NOWIN)
            ok += r.returncode == 0
        self.post_sched_lbl.configure(
            text=("โพสต์อัตโนมัติทุกวันเวลา %s" % ", ".join(times)) if times else "ปิดการโพสต์อัตโนมัติ",
            foreground=GOOD if times else WARN)
        return "- ตั้งเวลาโพสต์ %d เวลา" % ok if times else "- ปิดเวลาโพสต์อัตโนมัติ"

    # per-clip posting from the clips tab
    def post_selected(self, platform):
        folder, meta = self._sel_clip()
        if not folder:
            return
        self.post_folder(folder, platform)

    def tt_direct_dialog(self, folder, meta):
        """TikTok Direct Post screen: shows who posts, makes the owner pick privacy and interaction options."""
        from . import publish
        from .publish import tiktok
        try:
            info = tiktok.creator_info()
        except Exception as e:
            messagebox.showwarning("TikTok", "อ่านข้อมูลบัญชีจาก TikTok ไม่ได้: %s" % e)
            return
        opts = info.get("privacy_level_options") or []
        fmt = (meta.get("platform_formats") or {}).get("tiktok", "vertical")
        name = (meta.get("files") or {}).get(fmt) or (meta.get("files") or {}).get("vertical") or \
            (meta.get("files") or {}).get("horizontal")
        video = folder / name
        limit = int(info.get("max_video_post_duration_sec") or 0)
        if limit and float(meta.get("duration_seconds", 0)) > limit:
            messagebox.showwarning("TikTok", "คลิปยาว %.0f วินาที เกินที่บัญชีนี้โพสต์ได้ (%d วินาที)" % (
                float(meta.get("duration_seconds", 0)), limit))
            return
        win = tk.Toplevel(self)
        win.title("โพสต์ตรงไป TikTok")
        win.transient(self)
        win.grab_set()
        pad = dict(padx=14, pady=4)
        ttk.Label(win, text="โพสต์ไปที่บัญชี: %s (@%s)" % (info.get("creator_nickname", ""),
                                                          info.get("creator_username", "")),
                  style="H2.TLabel").pack(anchor="w", **pad)
        ttk.Label(win, text="คลิป: %s (%.0f วินาที)" % (name, float(meta.get("duration_seconds", 0))),
                  style="Muted.TLabel").pack(anchor="w", padx=14)
        ttk.Label(win, text="ชื่อเรื่อง / ข้อความโพสต์ (แก้ไขได้)").pack(anchor="w", **pad)
        title = tk.Text(win, width=70, height=6, wrap="word", font=(self.F, 10))
        title.pack(padx=14)
        title.insert("1.0", publish.caption(meta, "tiktok")[:2200])

        ttk.Label(win, text="ใครดูคลิปนี้ได้ (ต้องเลือกเอง)").pack(anchor="w", **pad)
        priv = tk.StringVar(value="")
        labels = {tiktok.PRIVACY_LABELS.get(o, o): o for o in opts}
        cb = ttk.Combobox(win, textvariable=priv, values=list(labels), state="readonly", width=40)
        cb.pack(anchor="w", padx=14)

        ttk.Label(win, text="อนุญาตให้ผู้ชม (ไม่ติ๊ก = ปิด)").pack(anchor="w", **pad)
        allow = {"comment": tk.BooleanVar(value=False), "duet": tk.BooleanVar(value=False),
                 "stitch": tk.BooleanVar(value=False)}
        row = ttk.Frame(win)
        row.pack(anchor="w", padx=14)
        for key, text in (("comment", "คอมเมนต์"), ("duet", "Duet"), ("stitch", "Stitch")):
            blocked = bool(info.get(key + "_disabled"))
            if blocked:
                text += " (บัญชีนี้ปิดไว้)"
            ttk.Checkbutton(row, text=text, variable=allow[key],
                            state="disabled" if blocked else "normal").pack(side="left", padx=(0, 14))

        ai = tk.BooleanVar(value=True)
        ttk.Checkbutton(win, text="ติดป้ายเนื้อหาที่สร้างด้วย AI (คลิปนี้สร้างด้วยโปรแกรมการ์ตูน AI)",
                        variable=ai).pack(anchor="w", **pad)

        disc = tk.BooleanVar(value=False)
        sub = {"organic": tk.BooleanVar(value=False), "branded": tk.BooleanVar(value=False)}
        dframe = ttk.Frame(win)

        def toggle_disc():
            if disc.get():
                dframe.pack(anchor="w", padx=34)
            else:
                dframe.pack_forget()
                sub["organic"].set(False)
                sub["branded"].set(False)
            refresh()

        ttk.Checkbutton(win, text="เนื้อหานี้โปรโมตแบรนด์/สินค้า (เปิดเผยเนื้อหาเชิงพาณิชย์)", variable=disc,
                        command=toggle_disc).pack(anchor="w", **pad)
        ttk.Checkbutton(dframe, text="แบรนด์ของฉันเอง (Your brand)", variable=sub["organic"],
                        command=lambda: refresh()).pack(anchor="w")
        ttk.Checkbutton(dframe, text="แบรนด์อื่นจ้างโปรโมต (Branded content)", variable=sub["branded"],
                        command=lambda: refresh()).pack(anchor="w")
        note = tk.Label(win, text="", fg="#7C7895", bg="#FFFFFF", wraplength=560, justify="left")
        note.pack(anchor="w", padx=14, pady=(2, 0))
        decl = ttk.Label(win, text="", wraplength=560, justify="left")
        decl.pack(anchor="w", padx=14, pady=4)

        btns = ttk.Frame(win)
        btns.pack(fill="x", padx=14, pady=10)
        post_btn = tk.Button(btns, text="โพสต์ตอนนี้", bg="#8E6CF7", fg="#FFFFFF", state="disabled")
        post_btn.pack(side="left")

        def refresh(*_):
            ok = bool(priv.get())
            msg = "" if ok else "👈 กรุณาเลือก 'ใครดูคลิปนี้ได้' ด้านบนก่อน เพื่อเปิดใช้งานปุ่มโพสต์ตรง"
            if disc.get() and not (sub["organic"].get() or sub["branded"].get()):
                ok = False
                msg = "เลือกประเภทเนื้อหาเชิงพาณิชย์อย่างน้อยหนึ่งข้อ"
            if sub["branded"].get() and labels.get(priv.get()) == "SELF_ONLY":
                ok = False
                msg = "Branded content ตั้งเป็น \"เฉพาะฉัน\" ไม่ได้ เลือกความเป็นส่วนตัวอื่น"
            if sub["branded"].get():
                text = ("โดยการโพสต์ คุณยอมรับ Branded Content Policy และ Music Usage Confirmation ของ TikTok")
            else:
                text = "โดยการโพสต์ คุณยอมรับ Music Usage Confirmation ของ TikTok"
            decl.configure(text=text)
            note.configure(text=msg)
            post_btn.configure(state="normal" if ok else "disabled")

        cb.bind("<<ComboboxSelected>>", refresh)
        refresh()

        def do_post():
            level = labels[priv.get()]
            caption_text = title.get("1.0", "end").strip()
            if not caption_text:
                messagebox.showinfo("TikTok", "ใส่ข้อความโพสต์ก่อน", parent=win)
                return
            if not messagebox.askyesno("ยืนยันโพสต์", "โพสต์คลิปนี้ไป TikTok (%s) ตอนนี้?" % priv.get(), parent=win):
                return
            win.destroy()
            kwargs = dict(privacy=level, disable_comment=not allow["comment"].get(),
                          disable_duet=not allow["duet"].get(), disable_stitch=not allow["stitch"].get(),
                          ai_generated=ai.get(), brand_organic=sub["organic"].get(),
                          brand_content=sub["branded"].get())
            self.say("กำลังโพสต์ไป TikTok...")

            def work():
                try:
                    res = tiktok.direct_post(video, caption_text, log=lambda m: self.q.put(("log", (m, "")),), **kwargs)
                    rec = dict(res, at=dt.datetime.now().isoformat(timespec="seconds"))
                    msg = ("โพสต์ TikTok แล้ว (%s)" % rec.get("note", ""), "good")
                except Exception as e:
                    rec = {"status": "failed", "error": str(e)[:500], "at": dt.datetime.now().isoformat(timespec="seconds")}
                    msg = ("โพสต์ TikTok ไม่สำเร็จ: %s" % e, "bad")
                meta2 = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
                meta2.setdefault("posts", {})["tiktok"] = rec
                (folder / "meta.json").write_text(json.dumps(meta2, ensure_ascii=False, indent=2), encoding="utf-8")
                self.q.put(("log", msg))
                self.q.put(("call", self.refresh_clips))

            threading.Thread(target=work, daemon=True).start()

        post_btn.configure(command=do_post)
        ttk.Button(btns, text="ส่งเป็นแบบร่างแทน", command=lambda: (
            win.destroy(), self.post_folder(folder, "tiktok", confirmed=True, draft_only=True))).pack(
            side="left", padx=8)
        ttk.Button(btns, text="ยกเลิก", command=win.destroy).pack(side="left")

    def post_folder(self, folder, platform, confirmed=False, draft_only=False):
        from . import publish
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        if not publish.is_connected(platform):
            messagebox.showinfo("โพสต์", "ยังไม่ได้เชื่อม %s ไปที่แท็บ \"โพสต์\" ก่อน" % publish.LABEL[platform])
            return
        if platform == "tiktok" and not draft_only:
            from .publish import tiktok
            if tiktok.has_direct_post():
                self.tt_direct_dialog(folder, meta)
                return
        prev = (meta.get("posts") or {}).get(platform, {})
        force = False
        if prev.get("status") in ("posted", "draft_sent"):
            if not messagebox.askyesno("โพสต์ซ้ำ?", "คลิปนี้โพสต์ไป %s แล้ว ต้องการโพสต์ซ้ำหรือไม่?" % publish.LABEL[platform]):
                return
            force = True
        if not confirmed and not messagebox.askyesno("ยืนยันการโพสต์", "โพสต์ \"%s\" ไปที่ %s ตอนนี้?" % (
                meta.get("title", ""), publish.LABEL[platform])):
            return
        args = ["publish", "clip", "--folder", str(folder), "--to", platform] + (["--force"] if force else [])
        self._start(args, "กำลังโพสต์ไป %s" % publish.LABEL[platform])

    def post_profile_manual(self):
        from . import publish
        folder, meta = self._sel_clip()
        if not folder:
            return
        self._copy(publish.caption(meta, "facebook_profile"))
        open_path(folder)
        open_path("https://www.facebook.com/")
        self.say("คัดลอกข้อความแล้ว: ใน Facebook กดสร้างโพสต์ ลากไฟล์คลิปแนวตั้งจากโฟลเดอร์ที่เปิดขึ้นมา แล้ววางข้อความ", "good")

    # ------------------------------------------------------------------ jobs
    def _start(self, args, label, env_updates=None):
        if self.proc:
            messagebox.showinfo("กำลังทำงาน", "มีงานกำลังทำอยู่ รอให้เสร็จก่อนนะครับ")
            return False
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        if env_updates:
            env.update(env_updates)
        self._created_folder = None
        self.proc = subprocess.Popen([python_exe(), "-u", "-m", "studio"] + args, cwd=str(ROOT), env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                     encoding="utf-8", errors="replace", **NOWIN)
        self.job_total = getattr(self, "job_total", 0) or 1
        self.job_done = 0
        self._current_clip_pct = 0.0
        self._formats_planned = ["vertical"]
        self._cur_fmt_idx = 0
        self.prog.set(0)
        self.prog_label.configure(text=label)
        if hasattr(self, "prog_pct"):
            self.prog_pct.configure(text="0%", fg="#6C47FF")
        self.btn_stop.configure(state="normal")
        if hasattr(self, "btn_batch"):
            self.btn_batch.configure(state="disabled")
        if hasattr(self, "btn_render_clip"):
            self.btn_render_clip.configure(state="disabled", text="⏳ กำลังสร้างคลิป...")
        self.say("เริ่ม: " + label)

        if hasattr(self, "anim_render_card"):
            self.anim_card_icon.configure(text="🎬")
            self.anim_card_title.configure(text="กำลังสร้างคลิป...")
            self.anim_card_meta.configure(text=label)
            self.anim_card_pct.configure(text="0%", fg="#7C5CEF")
            self.anim_card_prog.set(0)
            self.anim_card_detail.configure(text="กำลังเตรียมระบบและตรวจสอบโมเดล...")
            self.anim_card_eta.configure(text="รอการประมวลผล...")
            if hasattr(self, "row_card_actions"):
                self.btn_card_open_folder.pack_forget()
                self.btn_card_play_clip.pack_forget()
                self.btn_card_cancel.pack(side="left")
                self.row_card_actions.pack(fill="x", pady=(4, 0))

        def reader(p):
            for line in p.stdout:
                self.q.put(("line", line.rstrip()))
            self.q.put(("done", p.wait()))

        threading.Thread(target=reader, args=(self.proc,), daemon=True).start()
        return True

    def run_batch(self):
        n = len(self._inbox())
        if not n:
            messagebox.showinfo("สร้างคลิป", "ยังไม่มีบทในแท็บ \"บท\"")
            return
        self._start(["batch"], "กำลังสร้างคลิป %d เรื่อง" % n)
        self.job_total = n

    def render_selected(self):
        sel = self._sel_scripts()
        if not sel:
            messagebox.showinfo("สร้างคลิป", "เลือกบททางซ้าย 1 เรื่องก่อน")
            return
        if len(sel) > 1:
            messagebox.showinfo("สร้างคลิป", "เลือกทีละเรื่อง หรือกด \"สร้างคลิปจากบททั้งหมด\" ในหน้าหลัก")
            return

        # Check mode: Flow vs Local
        mode_val = self.anim_mode.get() if hasattr(self, "anim_mode") else "local"
        if mode_val == "flow":
            self.send_script_to_flow()
            return

        # Local Animation Mode
        script_path = sel[0]
        sc, errors, _ = self._script_cache.get(str(script_path), (None, ["อ่านบทไม่ได้"], []))
        if sc is None or errors:
            messagebox.showwarning("สร้างคลิป", "บทนี้ยังมีจุดผิด กรุณาแก้ไขบทก่อน:\n" + "\n".join(errors[:3]))
            return

        # Check engine compatibility
        eng_raw = self.anim_engine_val.get() if hasattr(self, "anim_engine_val") else "2D Cartoon"
        eng_type = "2d_cartoon"
        if "Chibi" in eng_raw:
            eng_type = "3d_chibi_pastel"
        elif "Cinematic" in eng_raw:
            eng_type = "3d_cinematic_cartoon"
        elif "Toy" in eng_raw or "โฆษณา" in eng_raw:
            eng_type = "cute_toy_ad"
        elif "Parallax" in eng_raw:
            eng_type = "25d_parallax"
        elif "Blender" in eng_raw:
            eng_type = "3d_blender"
        elif "Image-to-Video" in eng_raw:
            eng_type = "ai_image_to_video"
        elif "Text-to-Video" in eng_raw:
            eng_type = "ai_text_to_video"

        # Parse resolution
        res_raw = self.anim_res_val.get() if hasattr(self, "anim_res_val") else "1080p"
        res_clean = "1080p"
        if "720p" in res_raw:
            res_clean = "720p"
        elif "480p" in res_raw:
            res_clean = "480p"
        elif "4K" in res_raw:
            res_clean = "4k"

        # Parse fps
        fps_raw = self.anim_fps_val.get() if hasattr(self, "anim_fps_val") else "24"
        fps_clean = "24"
        if "30" in fps_raw:
            fps_clean = "30"
        elif "12" in fps_raw:
            fps_clean = "12"

        # Parse format/aspect
        aspect_raw = self.anim_aspect_val.get() if hasattr(self, "anim_aspect_val") else "16:9"
        fmt_clean = "horizontal"
        if "9:16" in aspect_raw:
            fmt_clean = "vertical"
        elif "1:1" in aspect_raw:
            fmt_clean = "square"
        elif "ทั้งสองแบบ" in aspect_raw:
            fmt_clean = "both"

        # Device & encoder
        dev_label = self.anim_device_val.get() if hasattr(self, "anim_device_val") else ""
        dev_info = getattr(self, "_anim_device_map", {}).get(dev_label, {})
        enc_clean = dev_info.get("encoder", "auto")

        args = ["render", str(script_path),
                "--resolution", res_clean,
                "--fps", str(fps_clean),
                "--format", fmt_clean,
                "--encoder", enc_clean,
                "--engine", eng_type]
        if eng_type == "3d_chibi_pastel":
            if hasattr(self, "chibi_char_val") and self.chibi_char_val.get():
                args += ["--chibi-char", self.chibi_char_val.get().split()[0]]
            if hasattr(self, "chibi_scene_val") and self.chibi_scene_val.get():
                args += ["--chibi-scene", self.chibi_scene_val.get().split()[0]]
            if hasattr(self, "chibi_action_val") and self.chibi_action_val.get():
                args += ["--chibi-action", self.chibi_action_val.get().split()[0]]
            if hasattr(self, "chibi_preset_val") and self.chibi_preset_val.get():
                args += ["--chibi-preset", self.chibi_preset_val.get().split()[0]]
        elif eng_type == "3d_cinematic_cartoon":
            if hasattr(self, "cinematic_char_val") and self.cinematic_char_val.get():
                args += ["--chibi-char", self.cinematic_char_val.get().split()[0]]
            if hasattr(self, "cinematic_scene_val") and self.cinematic_scene_val.get():
                args += ["--chibi-scene", self.cinematic_scene_val.get().split()[0]]
            if hasattr(self, "cinematic_action_val") and self.cinematic_action_val.get():
                args += ["--chibi-action", self.cinematic_action_val.get().split()[0]]
        elif eng_type == "cute_toy_ad":
            if hasattr(self, "toy_char_val") and self.toy_char_val.get():
                args += ["--chibi-char", self.toy_char_val.get().split()[0]]
            if hasattr(self, "toy_scene_val") and self.toy_scene_val.get():
                args += ["--chibi-scene", self.toy_scene_val.get().split()[0]]
            if hasattr(self, "toy_prod_img_val") and self.toy_prod_img_val.get():
                args += ["--toy-product-img", self.toy_prod_img_val.get()]
            if hasattr(self, "toy_price_val") and self.toy_price_val.get():
                args += ["--toy-price", self.toy_price_val.get()]
            if hasattr(self, "toy_promo_val") and self.toy_promo_val.get():
                args += ["--toy-promo", self.toy_promo_val.get()]
            if hasattr(self, "toy_cta_val") and self.toy_cta_val.get():
                args += ["--toy-cta", self.toy_cta_val.get()]
        if dev_info.get("id"):
            args += ["--device", dev_info["id"]]

        title_msg = "กำลังสร้างคลิป (%s %s %s): %s" % (eng_type, res_clean, enc_clean, script_path.stem)
        self._start(args, title_msg)
        self.job_total = 1
        self._single = script_path
        if hasattr(self, "anim_card_title"):
            self.anim_card_title.configure(text=f"กำลังสร้างคลิป ({eng_raw.split('—')[0].strip()})")
            self.anim_card_meta.configure(text=f"{script_path.stem} • {res_clean} • {fps_clean} FPS • {fmt_clean} • {enc_clean}")

    def run_check(self):
        self._start(["check"], "กำลังตรวจความพร้อมเครื่อง")

    def stop_job(self):
        if self.proc and messagebox.askyesno("หยุด", "หยุดงานที่กำลังทำ? คลิปที่ทำค้างอยู่จะไม่สมบูรณ์"):
            self.proc.terminate()

    def _on_line(self, line):
        import re
        if line.startswith("CREATED: ") or re.search(r"\] CREATED: ", line):
            self._created_folder = Path(line.split("CREATED: ", 1)[1].strip())

        if "PLAN: formats=" in line:
            try:
                parts = line.split("PLAN: formats=")[1].split()
                fmts = parts[0].split(",")
                self._formats_planned = fmts
                self._cur_fmt_idx = 0
            except Exception:
                pass

        m_fs = re.search(r"FORMAT_START: fmt=(\w+) idx=(\d+) total=(\d+)", line)
        if m_fs:
            self._cur_fmt_name = m_fs.group(1)
            self._cur_fmt_idx = int(m_fs.group(2)) - 1
            self._total_formats = int(m_fs.group(3))

        tag = "bad" if ("FAILED" in line or "Error" in line or "failed" in line) else (
            "good" if (" OK" in line or "READY" in line or "done" in line) else None)
        self.say(line, tag, stamp=False)

        # Batch progress (1/5)
        m = re.search(r"\((\d+)/(\d+)\)", line)
        if m:
            self.job_done, self.job_total = int(m.group(1)) - 1, int(m.group(2))
            msg = "กำลังสร้างคลิปที่ %s จาก %s" % (m.group(1), m.group(2))
            self.prog_label.configure(text=msg)
            if hasattr(self, "anim_card_title"):
                self.anim_card_title.configure(text=f"กำลังสร้างคลิปชุด ({m.group(1)}/{m.group(2)})")

        # Stage updates: TTS, Audio, Verify
        m_stage = re.search(r"PROGRESS_STAGE: (\w+) (\d+)% \((.*?)\)", line)
        if m_stage:
            stage_name, stage_pct, stage_msg = m_stage.group(1), int(m_stage.group(2)), m_stage.group(3)
            if stage_name == "tts":
                intra_pct = stage_pct * 0.08
            elif stage_name == "audio":
                intra_pct = 8.0 + stage_pct * 0.07
            elif stage_name == "verify":
                intra_pct = 95.0 + stage_pct * 0.05
            else:
                intra_pct = stage_pct * 0.1

            total_jobs = max(1, getattr(self, "job_total", 1))
            current_job = getattr(self, "job_done", 0)
            overall_pct = (current_job + intra_pct / 100.0) / total_jobs * 100.0

            if hasattr(self, "anim_card_prog"):
                self.anim_card_prog.set(overall_pct)
            if hasattr(self, "prog"):
                self.prog.set(overall_pct)
            if hasattr(self, "anim_card_pct"):
                self.anim_card_pct.configure(text=f"{int(overall_pct)}%")
            if hasattr(self, "prog_pct"):
                self.prog_pct.configure(text=f"{int(overall_pct)}%")
            if hasattr(self, "anim_card_detail"):
                self.anim_card_detail.configure(text=stage_msg)
            if hasattr(self, "anim_card_eta"):
                self.anim_card_eta.configure(text="กำลังเตรียมพร้อม...")

        # Frame Render Progress
        m_prog = re.search(r"PROGRESS: stage=render fmt=(\w+) pct=(\d+) frame=(\d+) total_frames=(\d+) fps=([\d\.]+) eta=(\d+)s", line)
        if m_prog:
            fmt = m_prog.group(1)
            pct = int(m_prog.group(2))
            f = int(m_prog.group(3))
            total_f = int(m_prog.group(4))
            fps = m_prog.group(5)
            eta = int(m_prog.group(6))

            fmts = getattr(self, "_formats_planned", [fmt])
            fmt_count = max(1, len(fmts))
            fmt_idx = getattr(self, "_cur_fmt_idx", 0)
            if fmt in fmts:
                fmt_idx = fmts.index(fmt)

            clip_render_frac = (fmt_idx + pct / 100.0) / fmt_count
            intra_pct = 15.0 + clip_render_frac * 80.0

            total_jobs = max(1, getattr(self, "job_total", 1))
            current_job = getattr(self, "job_done", 0)
            overall_pct = (current_job + intra_pct / 100.0) / total_jobs * 100.0

            if hasattr(self, "anim_card_prog"):
                self.anim_card_prog.set(overall_pct)
            if hasattr(self, "prog"):
                self.prog.set(overall_pct)
            if hasattr(self, "anim_card_pct"):
                self.anim_card_pct.configure(text=f"{int(overall_pct)}%")
            if hasattr(self, "prog_pct"):
                self.prog_pct.configure(text=f"{int(overall_pct)}%")
            if hasattr(self, "anim_card_detail"):
                self.anim_card_detail.configure(text=f"กำลังเรนเดอร์ {fmt} เฟรม {f}/{total_f} ({fps} FPS)")
            if hasattr(self, "anim_card_eta"):
                self.anim_card_eta.configure(text=f"⏱ เหลืออีก ~{eta} วินาที" if eta > 0 else "ใกล้เสร็จสิ้น...")
            self.prog_label.configure(text=f"[{int(overall_pct)}%] เรนเดอร์ {fmt} ({f}/{total_f} เฟรม, {fps} fps, เหลือ ~{eta}s)")

        # Fallback standard line
        m2 = re.search(r"(vertical|horizontal|square) (\d+)%", line)
        if m2 and not m_prog:
            fmt = m2.group(1)
            pct = int(m2.group(2))
            fmts = getattr(self, "_formats_planned", [fmt])
            fmt_count = max(1, len(fmts))
            idx = fmts.index(fmt) if fmt in fmts else 0
            intra_pct = (idx + pct / 100.0) / fmt_count * 100.0

            total_jobs = max(1, getattr(self, "job_total", 1))
            current_job = getattr(self, "job_done", 0)
            overall_pct = (current_job + intra_pct / 100.0) / total_jobs * 100.0

            if hasattr(self, "anim_card_prog"):
                self.anim_card_prog.set(overall_pct)
            if hasattr(self, "prog"):
                self.prog.set(overall_pct)
            if hasattr(self, "anim_card_pct"):
                self.anim_card_pct.configure(text=f"{int(overall_pct)}%")
            if hasattr(self, "prog_pct"):
                self.prog_pct.configure(text=f"{int(overall_pct)}%")
            self.prog_label.configure(text=f"[{int(overall_pct)}%] กำลังเรนเดอร์ {fmt} {pct}%")

        if "OK in" in line or "FAILED" in line:
            self.job_done += 1

    def _on_done(self, rc):
        if getattr(self, "_single", None) is not None:
            p = self._single
            self._single = None
            if rc == 0 and p.exists() and p.parent.name == "inbox":
                d = ROOT / "scripts" / "done" / dt.date.today().isoformat()
                d.mkdir(parents=True, exist_ok=True)
                shutil.move(str(p), d / p.name)
        self.proc = None
        self.btn_stop.configure(state="disabled")
        if hasattr(self, "btn_batch"):
            self.btn_batch.configure(state="normal")
        if hasattr(self, "btn_render_clip"):
            self.btn_render_clip.configure(state="normal", text="▶  สร้างคลิปในเครื่อง")

        if rc == 0:
            if hasattr(self, "anim_card_prog"):
                self.anim_card_prog.set(100)
            if hasattr(self, "prog"):
                self.prog.set(100)
            if hasattr(self, "anim_card_pct"):
                self.anim_card_pct.configure(text="100%", fg="#10B981")
            if hasattr(self, "prog_pct"):
                self.prog_pct.configure(text="100%", fg="#10B981")
            if hasattr(self, "anim_card_icon"):
                self.anim_card_icon.configure(text="✅")
            if hasattr(self, "anim_card_title"):
                self.anim_card_title.configure(text="สร้างคลิปสำเร็จเรียบร้อยแล้ว!")
            if hasattr(self, "anim_card_detail"):
                self.anim_card_detail.configure(text="บันทึกไฟล์วิดีโอ (.mp4) และไฟล์ซับไตเติลเรียบร้อย")
            if hasattr(self, "anim_card_eta"):
                self.anim_card_eta.configure(text="เสร็จสมบูรณ์")
            if hasattr(self, "row_card_actions"):
                self.btn_card_cancel.pack_forget()
                self.btn_card_open_folder.pack(side="left", padx=(0, 4))
                self.btn_card_play_clip.pack(side="left", padx=4)
                self.row_card_actions.pack(fill="x", pady=(4, 0))
            self.prog_label.configure(text="เสร็จแล้ว 100%")
        else:
            if hasattr(self, "anim_card_icon"):
                self.anim_card_icon.configure(text="⚠️")
            if hasattr(self, "anim_card_title"):
                self.anim_card_title.configure(text="การสร้างคลิปหยุดทำงาน หรือเกิดข้อผิดพลาด")
            if hasattr(self, "anim_card_pct"):
                self.anim_card_pct.configure(fg="#EF4444")
            if hasattr(self, "anim_card_detail"):
                self.anim_card_detail.configure(text=f"รหัสออก: {rc} (ดูบันทึกด้านล่างสำหรับรายละเอียด)")
            if hasattr(self, "row_card_actions"):
                self.btn_card_cancel.pack_forget()
            self.prog.configure(value=100 if rc == 0 else self.prog["value"])
            self.prog_label.configure(text="เสร็จแล้ว" if rc == 0 else "เสร็จแล้ว (มีบางเรื่องไม่สำเร็จ ดูบันทึก)")
        self.say("งานเสร็จ" if rc == 0 else "งานจบ แต่มีข้อผิดพลาด (รหัส %s)" % rc, "good" if rc == 0 else "bad")
        self.refresh_all()
        pending = getattr(self, "_platform_pending", None)
        self._platform_pending = None
        if rc == 0 and pending:
            platform, expected = pending
            folder = getattr(self, "_created_folder", None) or expected
            if folder:
                self._platform_select_folder(platform, folder)
                if getattr(self, "_platform_auto_caption", False):
                    self._platform_auto_caption = False
                    self.platform_ai_caption(platform)
        if rc != 0:
            self._platform_auto_caption = False
        if rc == 0:
            self.bell()

    def _poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "line":
                    self._on_line(val)
                elif kind == "done":
                    self._on_done(val)
                elif kind == "log":
                    self.say(*val)
                elif kind == "sched":
                    self._show_sched(val)
                elif kind == "preview":
                    self._show_preview(val)
                elif kind == "play":
                    self._play_wav(val)
                elif kind == "call":
                    val()
        except queue.Empty:
            pass
        self.after(150, self._poll)

    def _show_sched(self, val):
        if val:
            hhmm, nxt, state = (val.split("|") + ["", "", ""])[:3]
            self.sched_now.configure(text="เปิดอยู่: ทุกวันเวลา %s   (ครั้งถัดไป %s)" % (hhmm, nxt), foreground=GOOD)
            self.stat_vals["next"].configure(text=hhmm)
            try:
                self.hh.set(hhmm.split(":")[0])
                self.mm.set(hhmm.split(":")[1])
            except Exception:
                pass
        else:
            self.sched_now.configure(text="ยังไม่ได้ตั้งเวลา (ปิดอยู่)", foreground=WARN)
            self.stat_vals["next"].configure(text="ปิด")

    def _show_preview(self, im):
        top = tk.Toplevel(self)
        top.title("ภาพตัวอย่าง")
        top.configure(bg=BG)
        im = im.copy()
        im.thumbnail((420, 746))
        ph = ImageTk.PhotoImage(im)
        lbl = tk.Label(top, image=ph, bg=BG)
        lbl.image = ph
        lbl.pack(padx=10, pady=10)
        self.say("แสดงภาพตัวอย่างแล้ว", "good")

    def _play_wav(self, path):
        if IS_WIN:
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            open_path(path)

    # ------------------------------------------------------------------ misc
    def say(self, text, tag=None, stamp=True):
        if not hasattr(self, "log"):
            return
        if stamp:
            text = "[%s] %s" % (dt.datetime.now().strftime("%H:%M:%S"), text)
        self.log.insert("end", text + "\n", (tag,) if tag else ())
        self.log.see("end")

    def refresh_stats(self):
        n_inbox = len(self._inbox())
        done_list = list((ROOT / "scripts" / "done").glob("**/*.json"))
        n_total = n_inbox + len(done_list)
        today = dt.date.today().isoformat()
        clips = self._clips()
        n_today = sum(1 for d, _, _ in clips if d == today)
        n_review = sum(1 for _, _, m in clips if m.get("status") == "ready_for_approval")
        
        if hasattr(self, "stat_vals"):
            if "inbox" in self.stat_vals:
                self.stat_vals["inbox"].configure(text=f"{n_inbox} บท")
            if "today" in self.stat_vals:
                self.stat_vals["today"].configure(text=f"{n_today} คลิป")
            if "review" in self.stat_vals:
                self.stat_vals["review"].configure(text=f"{n_review} คลิป")
        if hasattr(self, "stat_subs"):
            if "inbox" in self.stat_subs:
                self.stat_subs["inbox"].configure(text=f"จากทั้งหมด {n_total} บท")
            if "today" in self.stat_subs:
                self.stat_subs["today"].configure(text=f"↑ {n_today} คลิปวันนี้")
            if "review" in self.stat_subs:
                self.stat_subs["review"].configure(text="รอตรวจสอบคุณภาพ" if n_review > 0 else "ตรวจครบทุกคลิปแล้ว")
        if hasattr(self, "head_status") and self.head_status:
            self.head_status.configure(text="บทรอสร้าง %d  •  คลิปรอตรวจ %d" % (n_inbox, n_review))

    def refresh_all(self):
        try:
            self.refresh_stats()
            self.refresh_scripts()
            self.refresh_plan()
            self.refresh_clips()
            self.refresh_platform_workspaces()
            self.refresh_schedule()
        except Exception as e:
            self.say("รีเฟรชไม่สำเร็จ: %s" % e, "bad")

    # ------------------------------------------------------------------ Facebook Profile Studio tab
    def _build_fb_profile(self):
        t = self.tab_fb_profile
        
        # ---------------- TOP HEADER CARD ----------------
        hdr_card = RoundedCard(t, radius=14, padx=16, pady=10, auto_height=True)
        hdr_card.pack(fill="x", pady=(0, 10))
        hdr_inner = hdr_card.inner

        # Left: Mascot circle avatar + Titles
        hdr_left = tk.Frame(hdr_inner, bg="#FFFFFF")
        hdr_left.pack(side="left")

        av_path = ROOT / "studio" / "tys_icon.png"
        if not av_path.is_file():
            av_path = ROOT / "studio" / "char_avatar_circle_1.png"
        if av_path.is_file():
            try:
                im = Image.open(av_path).resize((40, 40), Image.Resampling.LANCZOS)
                self._fb_hdr_av = ImageTk.PhotoImage(im)
                av_lbl = tk.Label(hdr_left, image=self._fb_hdr_av, bg="#FFFFFF")
                av_lbl.pack(side="left", padx=(0, 10))
            except Exception:
                tk.Label(hdr_left, text="👤", font=(self.F, 18), bg="#F0EBFF").pack(side="left", padx=(0, 10))
        else:
            tk.Label(hdr_left, text="👤", font=(self.F, 18), bg="#F0EBFF").pack(side="left", padx=(0, 10))

        hdr_titles = tk.Frame(hdr_left, bg="#FFFFFF")
        hdr_titles.pack(side="left")
        tk.Label(hdr_titles, text="Facebook Profile Studio", font=(self.F, 13, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")
        tk.Label(hdr_titles, text="สร้างคลิปโปรโมทสินค้า Shopee ด้วย Google Flow และโพสต์ไปยัง Facebook Profile ในหน้าเดียว",
                 font=(self.F, 8), fg="#7C7895", bg="#FFFFFF").pack(anchor="w", pady=(1, 0))

        # Right buttons
        hdr_right = tk.Frame(hdr_inner, bg="#FFFFFF")
        hdr_right.pack(side="right")

        RoundedButton(hdr_right, text="🔄 รีเฟรชสินค้า Shopee", font=(self.F, 9, "bold"), bg="#F3EFFE", fg="#6C47FF",
                      radius=10, padx=12, pady=5, command=self._refresh_fb_products).pack(side="left", padx=(0, 8))
        RoundedButton(hdr_right, text="📖 คู่มือการใช้งาน", font=(self.F, 9, "bold"), bg="#F3EFFE", fg="#6C47FF",
                      radius=10, padx=12, pady=5, command=self._open_fb_guide).pack(side="left")

        # ---------------- MAIN TWO-COLUMN SPLIT ----------------
        main = ttk.PanedWindow(t, orient="horizontal")
        main.pack(fill="both", expand=True)

        # ================= LEFT PANE: Shopee Products & Details =================
        left = tk.Frame(main, bg="#F0ECFD")
        main.add(left, weight=1)

        # Card 1: Shopee Search & Table
        card_shopee = RoundedCard(left, radius=16, padx=14, pady=12, auto_height=False)
        card_shopee.pack(fill="both", expand=True, pady=(0, 8))
        cs_inner = card_shopee.inner

        # Header of Card 1
        cs_head = tk.Frame(cs_inner, bg="#FFFFFF")
        cs_head.pack(fill="x", pady=(0, 8))

        shopee_icon_box = tk.Frame(cs_head, bg="#FFF0EB", width=34, height=34)
        shopee_icon_box.pack_propagate(False)
        shopee_icon_box.pack(side="left", padx=(0, 8))
        tk.Label(shopee_icon_box, text="🛍️", font=(self.F, 14), bg="#FFF0EB").pack(expand=True)

        cs_titles = tk.Frame(cs_head, bg="#FFFFFF")
        cs_titles.pack(side="left", fill="x", expand=True)
        tk.Label(cs_titles, text="ค้นหาสินค้าจาก Shopee", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")
        tk.Label(cs_titles, text="ค้นหาและเลือกสินค้าเพื่อสร้างวิดีโอโปรโมท", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF").pack(anchor="w")

        RoundedButton(cs_head, text="📖 คู่มือการใช้งาน", font=(self.F, 8, "bold"), bg="#F3EFFE", fg="#6C47FF",
                      radius=10, padx=10, pady=4, command=self._open_fb_guide).pack(side="right")

        # Search row
        sr_row = tk.Frame(cs_inner, bg="#FFFFFF")
        sr_row.pack(fill="x", pady=(0, 6))

        sr_box = tk.Frame(sr_row, bg="#FAF9FF", highlightbackground="#EDE9FE", highlightthickness=1, bd=0)
        sr_box.pack(side="left", fill="x", expand=True, padx=(0, 8))

        tk.Label(sr_box, text="🔍", font=(self.F, 9), bg="#FAF9FF", fg="#7C7895").pack(side="left", padx=(8, 4))
        self.fb_search_var = tk.StringVar()
        self.fb_search_entry = tk.Entry(sr_box, textvariable=self.fb_search_var, font=(self.F, 9), bg="#FAF9FF", relief="flat", bd=0, fg="#2C1D63")
        self.fb_search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=5)
        self.fb_search_entry.bind("<KeyRelease>", lambda e: self._filter_fb_products())

        RoundedButton(sr_row, text="ค้นหา", font=(self.F, 9, "bold"), bg="#7C4DFF", fg="#FFFFFF",
                      radius=10, padx=16, pady=5, command=self._filter_fb_products).pack(side="right")

        # Filter row
        flt_row = tk.Frame(cs_inner, bg="#FFFFFF")
        flt_row.pack(fill="x", pady=(0, 8))

        tk.Label(flt_row, text="หมวดหมู่:", font=(self.F, 8, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left", padx=(0, 4))
        self.fb_cat_var = tk.StringVar(value="ทุกหมวดหมู่")
        self.fb_cat_cb = ttk.Combobox(flt_row, textvariable=self.fb_cat_var, state="readonly", width=18)
        self.fb_cat_cb.pack(side="left", padx=(0, 12))
        self.fb_cat_cb.bind("<<ComboboxSelected>>", lambda e: self._filter_fb_products())

        tk.Label(flt_row, text="เรียงตาม:", font=(self.F, 8, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left", padx=(0, 4))
        self.fb_sort_cb = ttk.Combobox(flt_row, values=["ยอดขายสูงสุด", "ราคา: ต่ำ-สูง", "ราคา: สูง-ต่ำ", "เรตติ้งสูงสุด"], state="readonly", width=14)
        self.fb_sort_cb.current(0)
        self.fb_sort_cb.pack(side="left")
        self.fb_sort_cb.bind("<<ComboboxSelected>>", lambda e: self._filter_fb_products())

        # Product Table (Treeview)
        tv_frame = tk.Frame(cs_inner, bg="#FFFFFF", highlightbackground="#EDE9FE", highlightthickness=1)
        tv_frame.pack(fill="both", expand=True)

        cols = ("name", "price", "sold", "rating")
        self.tv_fb = ttk.Treeview(tv_frame, columns=cols, show="headings", selectmode="browse", height=10)
        self.tv_fb.heading("name", text="ชื่อสินค้า Shopee (กดเพื่อเลือกสินค้า)")
        self.tv_fb.column("name", width=360, minwidth=220, stretch=True)
        self.tv_fb.heading("price", text="ราคา")
        self.tv_fb.column("price", width=75, minwidth=60, anchor="e")
        self.tv_fb.heading("sold", text="ขายแล้ว")
        self.tv_fb.column("sold", width=70, minwidth=55, anchor="e")
        self.tv_fb.heading("rating", text="⭐ เรตติ้ง")
        self.tv_fb.column("rating", width=65, minwidth=50, anchor="center")

        tv_vscroll = ttk.Scrollbar(tv_frame, orient="vertical", command=self.tv_fb.yview)
        self.tv_fb.configure(yscrollcommand=tv_vscroll.set)
        self.tv_fb.pack(side="left", fill="both", expand=True)
        tv_vscroll.pack(side="right", fill="y")
        self.tv_fb.bind("<<TreeviewSelect>>", self._on_fb_product_selected)

        # Pagination Pills
        pag_frame = tk.Frame(cs_inner, bg="#FFFFFF")
        pag_frame.pack(fill="x", pady=(8, 0))

        pag_left = tk.Frame(pag_frame, bg="#FFFFFF")
        pag_left.pack(side="left")
        self.lbl_fb_item_count = tk.Label(pag_left, text="แสดง 0 รายการ", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF")
        self.lbl_fb_item_count.pack()

        pag_right = tk.Frame(pag_frame, bg="#FFFFFF")
        pag_right.pack(side="right")
        RoundedButton(pag_right, text="‹", bg="#F3EFFE", fg="#6C47FF", radius=8, padx=8, pady=2, font=(self.F, 8, "bold")).pack(side="left", padx=1)
        RoundedButton(pag_right, text="1", bg="#7C4DFF", fg="#FFFFFF", radius=8, padx=8, pady=2, font=(self.F, 8, "bold")).pack(side="left", padx=1)
        RoundedButton(pag_right, text="2", bg="#F3EFFE", fg="#6C47FF", radius=8, padx=8, pady=2, font=(self.F, 8)).pack(side="left", padx=1)
        RoundedButton(pag_right, text="3", bg="#F3EFFE", fg="#6C47FF", radius=8, padx=8, pady=2, font=(self.F, 8)).pack(side="left", padx=1)
        RoundedButton(pag_right, text="...", bg="#F3EFFE", fg="#7C7895", radius=8, padx=6, pady=2, font=(self.F, 8)).pack(side="left", padx=1)
        RoundedButton(pag_right, text="69", bg="#F3EFFE", fg="#6C47FF", radius=8, padx=8, pady=2, font=(self.F, 8)).pack(side="left", padx=1)
        RoundedButton(pag_right, text="›", bg="#F3EFFE", fg="#6C47FF", radius=8, padx=8, pady=2, font=(self.F, 8, "bold")).pack(side="left", padx=1)

        # Card 2: Selected Product Details
        card_detail = RoundedCard(left, radius=16, padx=14, pady=12, auto_height=True)
        card_detail.pack(fill="x")
        cd_inner = card_detail.inner

        # Badge row
        cd_badge_row = tk.Frame(cd_inner, bg="#FFFFFF")
        cd_badge_row.pack(fill="x", pady=(0, 6))

        RoundedButton(cd_badge_row, text="★ แนะนำสินค้า", bg="#EE4D2D", fg="#FFFFFF",
                      radius=8, padx=8, pady=2, font=(self.F, 8, "bold")).pack(side="left")
        tk.Label(cd_badge_row, text="🤍", font=(self.F, 10), bg="#FFFFFF", fg="#7C7895").pack(side="right")

        # Detail row
        cd_row = tk.Frame(cd_inner, bg="#FFFFFF")
        cd_row.pack(fill="x")

        # Thumbnail
        thumb_frame = tk.Frame(cd_row, bg="#FFF0EB", width=110, height=110, highlightbackground="#F8D7C8", highlightthickness=1)
        thumb_frame.pack_propagate(False)
        thumb_frame.pack(side="left", padx=(0, 12))

        self.fb_thumb_lbl = tk.Label(thumb_frame, bg="#FFF0EB", text="[รูปสินค้า]", fg=MUTED)
        self.fb_thumb_lbl.pack(expand=True)

        # Product Info
        info_box = tk.Frame(cd_row, bg="#FFFFFF")
        info_box.pack(side="left", fill="both", expand=True)

        self.fb_p_title = tk.Label(info_box, text="ยังไม่ได้เลือกสินค้า",
                                   font=(self.F, 10, "bold"), fg="#2C1D63", bg="#FFFFFF", wraplength=420, justify="left")
        self.fb_p_title.pack(anchor="w")

        # Price row
        price_row = tk.Frame(info_box, bg="#FFFFFF")
        price_row.pack(anchor="w", pady=(3, 2))

        self.fb_p_price = tk.Label(price_row, text="", font=(self.F, 16, "bold"), fg="#EE4D2D", bg="#FFFFFF")
        self.fb_p_price.pack(side="left")

        self.fb_p_disc = RoundedButton(price_row, text="-25%", bg="#FFEAE6", fg="#EE4D2D", radius=6, padx=6, pady=1, font=(self.F, 8, "bold"))
        self.fb_p_disc.pack(side="left", padx=6)

        self.fb_p_orig = tk.Label(price_row, text="", font=(self.F, 9), fg="#9CA3AF", bg="#FFFFFF")
        self.fb_p_orig.pack(side="left")

        # Shop row
        shop_row = tk.Frame(info_box, bg="#FFFFFF")
        shop_row.pack(anchor="w", pady=(1, 3))

        RoundedButton(shop_row, text="ร้านแนะนำ", bg="#FFF0E6", fg="#EE4D2D", radius=6, padx=6, pady=1, font=(self.F, 8, "bold")).pack(side="left", padx=(0, 6))
        self.fb_p_shop = tk.Label(shop_row, text="", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF")
        self.fb_p_shop.pack(side="left")

        # Stats / Bullets
        stats_lbl = tk.Label(info_box, text="✓ สินค้าลิขสิทธิ์แท้ 100%   •   ✓ สต็อกพร้อมส่ง   •   ✓ สินค้าคุณภาพดีพร้อมส่ง",
                             font=(self.F, 8), fg="#7C7895", bg="#FFFFFF")
        stats_lbl.pack(anchor="w", pady=(0, 4))

        # Shopee button
        self.btn_fb_open_shopee = RoundedButton(
            info_box,
            text="🛍️ เปิดหน้า Shopee ↗",
            bg="#EE4D2D",
            fg="#FFFFFF",
            radius=10,
            padx=14,
            pady=5,
            font=(self.F, 8, "bold"),
            state="disabled",
            command=self._open_selected_shopee
        )
        self.btn_fb_open_shopee.pack(anchor="w")

        # ================= RIGHT PANE: Flow Prompt & Auto-Post Dashboard =================
        right = tk.Frame(main, bg="#F0ECFD", padx=6)
        main.add(right, weight=1)

        r_canvas = tk.Canvas(right, bg="#F0ECFD", highlightthickness=0)
        r_scroll = ttk.Scrollbar(right, orient="vertical", command=r_canvas.yview)
        r_box = tk.Frame(r_canvas, bg="#F0ECFD")
        r_win = r_canvas.create_window((0, 0), window=r_box, anchor="nw")

        r_box.bind("<Configure>", lambda e: r_canvas.configure(scrollregion=r_canvas.bbox("all")))
        r_canvas.bind("<Configure>", lambda e: r_canvas.itemconfigure(r_win, width=e.width - 6))

        r_canvas.configure(yscrollcommand=r_scroll.set)
        r_scroll.pack(side="right", fill="y")
        r_canvas.pack(side="left", fill="both", expand=True)

        def _on_fb_wheel(e):
            if self.nb.select() == str(self.tab_fb_profile) and r_canvas.winfo_exists():
                r_canvas.yview_scroll(int(-e.delta / 120), "units")
        r_canvas.bind_all("<MouseWheel>", _on_fb_wheel, add="+")

        # --- CARD 3: Video Prompt Google Flow ---
        c1 = RoundedCard(r_box, radius=16, padx=16, pady=14, auto_height=True)
        c1.pack(fill="x", pady=(0, 10))
        c1_inner = c1.inner

        # Header
        c1_h = tk.Frame(c1_inner, bg="#FFFFFF")
        c1_h.pack(fill="x", pady=(0, 8))

        c1_icon = tk.Frame(c1_h, bg="#F3EFFE", width=34, height=34)
        c1_icon.pack_propagate(False)
        c1_icon.pack(side="left", padx=(0, 8))
        tk.Label(c1_icon, text="▶", font=(self.F, 11, "bold"), fg="#6C47FF", bg="#F3EFFE").pack(expand=True)

        c1_t = tk.Frame(c1_h, bg="#FFFFFF")
        c1_t.pack(side="left", fill="x", expand=True)
        tk.Label(c1_t, text="1. สร้างวิดีโอพรอมต์ Google Flow", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")
        tk.Label(c1_t, text="สร้างพรอมต์ภาษาอังกฤษและภาพสินค้าพร้อมส่ง Flow", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF").pack(anchor="w")

        RoundedButton(c1_h, text="▶ ตัวอย่างวิดีโอ", font=(self.F, 8, "bold"), bg="#F3EFFE", fg="#6C47FF",
                      radius=12, padx=12, pady=4, command=self._open_flow_example_video).pack(side="right")

        # Duration Pills
        dur_box = tk.Frame(c1_inner, bg="#FFFFFF")
        dur_box.pack(fill="x", pady=(0, 8))

        tk.Label(dur_box, text="ความยาวคลิป:", font=(self.F, 8, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left", padx=(0, 6))
        self.fb_dur_val = tk.IntVar(value=8)
        self.fb_dur_btns = {}
        for sec in (8, 10, 12, 15, 20, 25, 30):
            is_active = (sec == 8)
            b = RoundedButton(
                dur_box,
                text=f"● {sec} วิ" if is_active else f"{sec} วิ",
                bg="#7C4DFF" if is_active else "#F3EFFE",
                fg="#FFFFFF" if is_active else "#6C47FF",
                radius=10,
                padx=8,
                pady=3,
                font=(self.F, 8, "bold" if is_active else "normal"),
                command=lambda s=sec: self._set_fb_duration(s),
            )
            b.pack(side="left", padx=2)
            self.fb_dur_btns[sec] = b

        # 4 Visual Style Cards
        st_grid = tk.Frame(c1_inner, bg="#FFFFFF")
        st_grid.pack(fill="x", pady=(0, 8))

        self.fb_style_choices = [
            ("3D Animation", "การ์ตูน 3D สดใส", "char_avatar_circle_1.png", "cartoon"),
            ("Stop Motion", "สต็อปโมชัน น่ารัก", "char_avatar_circle_2.png", "asmr"),
            ("Cinematic Ad", "พรีเซนเตอร์ถือสินค้า", "char_avatar_circle_3.png", "presenter"),
            ("Unboxing Show", "แกะกล่องสินค้า", "char_avatar_circle_4.png", "unboxing"),
        ]
        self.fb_selected_style = "cartoon"
        self.fb_style_cards = {}
        self.fb_style_imgs = []

        for title, sub, icon_file, key in self.fb_style_choices:
            is_act = (key == self.fb_selected_style)
            st_f = tk.Frame(st_grid, bg="#F3EFFE" if is_act else "#FAF9FD",
                            highlightbackground="#7C4DFF" if is_act else "#EDE9FE",
                            highlightthickness=2 if is_act else 1, bd=0, padx=6, pady=6, cursor="hand2")
            st_f.pack(side="left", fill="both", expand=True, padx=3)

            p = ROOT / "studio" / icon_file
            av_l = None
            if p.is_file():
                try:
                    im = Image.open(p).resize((36, 36), Image.Resampling.LANCZOS)
                    p_img = ImageTk.PhotoImage(im)
                    self.fb_style_imgs.append(p_img)
                    av_l = tk.Label(st_f, image=p_img, bg=st_f["bg"], cursor="hand2")
                    av_l.pack(pady=(0, 2))
                except Exception:
                    pass

            t_l = tk.Label(st_f, text=title, font=(self.F, 8, "bold"), fg="#2C1D63", bg=st_f["bg"], cursor="hand2")
            t_l.pack()
            s_l = tk.Label(st_f, text=sub, font=(self.F, 8), fg="#7C7895", bg=st_f["bg"], cursor="hand2")
            s_l.pack()

            # Click binding on all children of the card
            def make_handler(k):
                return lambda e: self._set_fb_style(k)
            handler = make_handler(key)
            st_f.bind("<Button-1>", handler)
            if av_l:
                av_l.bind("<Button-1>", handler)
            t_l.bind("<Button-1>", handler)
            s_l.bind("<Button-1>", handler)

            self.fb_style_cards[key] = (st_f, av_l, t_l, s_l)

        # Prompt Box
        pr_head = tk.Frame(c1_inner, bg="#FFFFFF")
        pr_head.pack(fill="x", pady=(0, 3))
        tk.Label(pr_head, text="พรอมต์สำหรับสร้างคลิปใน Google Flow (ภาษาอังกฤษ):", font=(self.F, 8, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left")
        self.lbl_prompt_count = tk.Label(pr_head, text="0/2000", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF")
        self.lbl_prompt_count.pack(side="right")

        self.txt_fb_prompt = tk.Text(c1_inner, height=4, font=(self.F, 8), bg="#FAF9FF", relief="flat", bd=0,
                                     highlightbackground="#EDE9FE", highlightthickness=1, wrap="word", fg="#2C1D63")
        self.txt_fb_prompt.pack(fill="x", pady=(0, 8))
        self.txt_fb_prompt.bind("<KeyRelease>", self._update_prompt_count)

        # Prompt Actions
        pr_act = tk.Frame(c1_inner, bg="#FFFFFF")
        pr_act.pack(fill="x")
        RoundedButton(pr_act, text="📋 คัดลอกพรอมต์ Flow", bg="#F3EFFE", fg="#6C47FF", radius=10, padx=12, pady=5, font=(self.F, 8, "bold"), command=self._copy_fb_prompt).pack(side="left", padx=(0, 6))
        RoundedButton(pr_act, text="🚀 ส่งพรอมต์ไปที่ Flow", bg="#7C4DFF", fg="#FFFFFF", radius=10, padx=14, pady=5, font=(self.F, 8, "bold"), command=self._send_fb_to_flow).pack(side="left")
        RoundedButton(pr_act, text="🔄 สร้างพรอมต์ใหม่", bg="#F8F6FD", fg="#7C7895", radius=10, padx=10, pady=5, font=(self.F, 8), command=self._update_fb_prompt).pack(side="right")

        # --- CARD 4: Facebook Caption ---
        c2 = RoundedCard(r_box, radius=16, padx=16, pady=14, auto_height=True)
        c2.pack(fill="x", pady=(0, 10))
        c2_inner = c2.inner

        # Header
        c2_h = tk.Frame(c2_inner, bg="#FFFFFF")
        c2_h.pack(fill="x", pady=(0, 8))

        c2_icon = tk.Frame(c2_h, bg="#E8F8F0", width=34, height=34)
        c2_icon.pack_propagate(False)
        c2_icon.pack(side="left", padx=(0, 8))
        tk.Label(c2_icon, text="💬", font=(self.F, 12), bg="#E8F8F0").pack(expand=True)

        c2_t = tk.Frame(c2_h, bg="#FFFFFF")
        c2_t.pack(side="left", fill="x", expand=True)
        tk.Label(c2_t, text="2. แคปชั่น Facebook Profile (@ผู้ติดตาม)", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")
        tk.Label(c2_t, text="ระบบสร้างแคปชั่นอัตโนมัติพร้อมแท็กกระตุ้นยอดขาย", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF").pack(anchor="w")

        RoundedButton(c2_h, text="📑 ใช้เทมเพลตแคปชั่น", font=(self.F, 8, "bold"), bg="#F3EFFE", fg="#6C47FF",
                      radius=12, padx=12, pady=4, command=self._open_caption_template_menu).pack(side="right")

        # Caption Box
        cap_head = tk.Frame(c2_inner, bg="#FFFFFF")
        cap_head.pack(fill="x", pady=(0, 3))
        tk.Label(cap_head, text="ข้อความโปรโมท + แท็ก @ผู้ติดตาม + ลิงก์พิกัด:", font=(self.F, 8, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(side="left")
        self.lbl_caption_count = tk.Label(cap_head, text="0/2000", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF")
        self.lbl_caption_count.pack(side="right")

        self.txt_fb_caption = tk.Text(c2_inner, height=4, font=(self.F, 8), bg="#FAF9FF", relief="flat", bd=0,
                                      highlightbackground="#EDE9FE", highlightthickness=1, wrap="word", fg="#2C1D63")
        self.txt_fb_caption.pack(fill="x", pady=(0, 8))
        self.txt_fb_caption.bind("<KeyRelease>", self._update_caption_count)

        # Caption Actions
        cap_act = tk.Frame(c2_inner, bg="#FFFFFF")
        cap_act.pack(fill="x")
        RoundedButton(cap_act, text="📋 คัดลอกแคปชั่น", bg="#F3EFFE", fg="#6C47FF", radius=10, padx=12, pady=5, font=(self.F, 8, "bold"), command=self._copy_fb_caption).pack(side="left", padx=(0, 6))
        RoundedButton(cap_act, text="🔄 รีเซ็ตแคปชั่นเดิม", bg="#F8F6FD", fg="#7C7895", radius=10, padx=10, pady=5, font=(self.F, 8), command=self._update_fb_caption).pack(side="left", padx=(0, 6))
        RoundedButton(cap_act, text="🧹 ล้างข้อความ", bg="#F8F6FD", fg="#7C7895", radius=10, padx=10, pady=5, font=(self.F, 8), command=lambda: [self.txt_fb_caption.delete("1.0", "end"), self._update_caption_count()]).pack(side="left")

        # --- CARD 5: Publish & Auto-Post ---
        c3 = RoundedCard(r_box, radius=16, padx=16, pady=14, auto_height=True)
        c3.pack(fill="x", pady=(0, 10))
        c3_inner = c3.inner

        # Header
        c3_h = tk.Frame(c3_inner, bg="#FFFFFF")
        c3_h.pack(fill="x", pady=(0, 8))

        c3_icon = tk.Frame(c3_h, bg="#F3EFFE", width=34, height=34)
        c3_icon.pack_propagate(False)
        c3_icon.pack(side="left", padx=(0, 8))
        tk.Label(c3_icon, text="🚀", font=(self.F, 12), bg="#F3EFFE").pack(expand=True)

        c3_t = tk.Frame(c3_h, bg="#FFFFFF")
        c3_t.pack(side="left", fill="x", expand=True)
        tk.Label(c3_t, text="3. นำวิดีโอกลับมา & โพสต์ไปที่ Facebook Profile", font=(self.F, 11, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")
        tk.Label(c3_t, text="เลือกไฟล์วิดีโอจาก Flow แล้วสั่งโพสต์อัตโนมัติ", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF").pack(anchor="w")

        # Two sub-cards row
        c3_split = tk.Frame(c3_inner, bg="#FFFFFF")
        c3_split.pack(fill="x")

        # Sub-card Left: Video Ready
        sub_v = tk.Frame(c3_split, bg="#FAF9FD", highlightbackground="#EDE9FE", highlightthickness=1, padx=10, pady=10)
        sub_v.pack(side="left", fill="both", expand=True, padx=(0, 6))

        sub_v_tabs = tk.Frame(sub_v, bg="#FAF9FD")
        sub_v_tabs.pack(fill="x", pady=(0, 6))
        RoundedButton(sub_v_tabs, text="📂 อัปโหลดไฟล์", bg="#F3EFFE", fg="#6C47FF", radius=8, padx=8, pady=3, font=(self.F, 8, "bold"), command=self._choose_fb_video).pack(side="left", padx=(0, 4))
        RoundedButton(sub_v_tabs, text="⚡ ตรวจหาล่าสุด", bg="#F8F6FD", fg="#7C7895", radius=8, padx=8, pady=3, font=(self.F, 8), command=self._find_latest_fb_video).pack(side="left")

        v_status_box = tk.Frame(sub_v, bg="#FFFFFF", highlightbackground="#EDE9FE", highlightthickness=1, padx=8, pady=8)
        v_status_box.pack(fill="x", pady=(0, 6))

        v_badge_row = tk.Frame(v_status_box, bg="#FFFFFF")
        v_badge_row.pack(fill="x", pady=(0, 3))
        self.lbl_fb_video_badge = RoundedButton(v_badge_row, text="⏳ รอเลือกไฟล์วิดีโอ", bg="#F3EFFE", fg="#6C47FF", radius=6, padx=6, pady=1, font=(self.F, 8, "bold"))
        self.lbl_fb_video_badge.pack(side="left")

        self.lbl_fb_video_status = tk.Label(v_status_box, text="ยังไม่ได้เลือกไฟล์วิดีโอ (กดปุ่มด้านบน)", font=(self.F, 8, "bold"), fg="#2C1D63", bg="#FFFFFF")
        self.lbl_fb_video_status.pack(anchor="w")
        self.lbl_fb_video_meta = tk.Label(v_status_box, text="1080x1920 (9:16) • รองรับไฟล์ .mp4 จาก Flow", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF")
        self.lbl_fb_video_meta.pack(anchor="w", pady=(1, 4))

        self.btn_fb_play_vid = RoundedButton(v_status_box, text="▶ เล่นวิดีโอตัวอย่าง", bg="#F3EFFE", fg="#6C47FF", radius=8, padx=10, pady=4, font=(self.F, 8, "bold"), state="disabled", command=self._play_fb_video)
        self.btn_fb_play_vid.pack(anchor="w")

        # Sub-card Right: RPA Worker
        sub_w = tk.Frame(c3_split, bg="#FAF9FD", highlightbackground="#EDE9FE", highlightthickness=1, padx=10, pady=10)
        sub_w.pack(side="left", fill="both", expand=True, padx=(6, 0))

        sub_w_h = tk.Frame(sub_w, bg="#FAF9FD")
        sub_w_h.pack(fill="x", pady=(0, 6))
        tk.Label(sub_w_h, text="🤖 โพสต์อัตโนมัติ (Browser RPA)", font=(self.F, 8, "bold"), fg="#6C47FF", bg="#FAF9FD").pack(side="left")
        self.fb_worker_auto_pub = tk.BooleanVar(value=True)
        w_auto_chk = ttk.Checkbutton(sub_w_h, text="ยืนยันเผยแพร่ทันที", variable=self.fb_worker_auto_pub)
        w_auto_chk.pack(side="right")

        w_prof_card = tk.Frame(sub_w, bg="#FFFFFF", highlightbackground="#EDE9FE", highlightthickness=1, padx=8, pady=6)
        w_prof_card.pack(fill="x", pady=(0, 6))
        tk.Label(w_prof_card, text="👤 เต่ายง สตูดิโอ (Tao Yong Studio)", font=(self.F, 8, "bold"), fg="#2C1D63", bg="#FFFFFF").pack(anchor="w")
        tk.Label(w_prof_card, text="🕒 โพสต์ทันที (โพสต์สาธารณะ Public)", font=(self.F, 8), fg="#7C7895", bg="#FFFFFF").pack(anchor="w")

        self.btn_fb_worker_run = RoundedButton(
            sub_w,
            text="🚀 สั่งพนักงานโพสต์ Facebook ทันที (Auto-Post)",
            bg="#7C4DFF",
            fg="#FFFFFF",
            radius=10,
            padx=12,
            pady=6,
            font=(self.F, 8, "bold"),
            command=self._run_fb_browser_worker
        )
        self.btn_fb_worker_run.pack(fill="x", pady=(0, 4))

        self.btn_fb_publish = RoundedButton(
            sub_w,
            text="📘 เปิดหน้า Facebook เพื่อโพสต์ด้วยตัวเอง",
            bg="#1877F2",
            fg="#FFFFFF",
            radius=10,
            padx=10,
            pady=5,
            font=(self.F, 8),
            command=self._publish_to_fb_profile
        )
        self.btn_fb_publish.pack(fill="x", pady=(0, 4))

        tk.Button(
            sub_w,
            text="🔑 เข้าสู่ระบบ Facebook (ทำครั้งเดียว)",
            font=(self.F, 8),
            bg="#FFFFFF",
            fg="#6C47FF",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=8,
            pady=3,
            command=self._open_fb_worker_login
        ).pack(anchor="w")

        self.lbl_fb_worker_status = tk.Label(
            sub_w,
            text="สถานะพนักงาน: พร้อมทำงาน (เลือกสินค้าและวิดีโอด้านบน แล้วกด 'สั่งพนักงานโพสต์ Facebook ทันที')",
            font=(self.F, 8),
            fg="#7C7895",
            bg="#FAF9FD",
            wraplength=300,
            justify="left"
        )
        self.lbl_fb_worker_status.pack(anchor="w", pady=(2, 0))

        # Initialize data
        self.fb_raw_prods = []
        self.fb_prods = []
        self.fb_selected_prod = None
        self.fb_video_path = None
        self._fb_thumb_img = None
        self._refresh_fb_products()

    def _update_prompt_count(self, event=None):
        if hasattr(self, "txt_fb_prompt") and hasattr(self, "lbl_prompt_count"):
            text = self.txt_fb_prompt.get("1.0", "end").strip()
            self.lbl_prompt_count.configure(text=f"{len(text)}/2000")

    def _update_caption_count(self, event=None):
        if hasattr(self, "txt_fb_caption") and hasattr(self, "lbl_caption_count"):
            text = self.txt_fb_caption.get("1.0", "end").strip()
            self.lbl_caption_count.configure(text=f"{len(text)}/2000")

    def _set_fb_style(self, style_key):
        self.fb_selected_style = style_key
        for k, (st_f, av_l, t_l, s_l) in self.fb_style_cards.items():
            is_act = (k == style_key)
            bg_col = "#F3EFFE" if is_act else "#FAF9FD"
            border_col = "#7C4DFF" if is_act else "#EDE9FE"
            st_f.configure(bg=bg_col, highlightbackground=border_col, highlightthickness=2 if is_act else 1)
            if av_l:
                av_l.configure(bg=bg_col)
            t_l.configure(bg=bg_col)
            s_l.configure(bg=bg_col)
        self._update_fb_prompt()

    def _open_fb_guide(self):
        guide_text = """📖 คู่มือการใช้งาน Facebook Profile Studio

ขั้นตอนการทำงาน 3 สเต็ปง่ายๆ:
1. ค้นหาและเลือกสินค้า Shopee ที่ต้องการโปรโมทจากตารางด้านซ้าย
2. เลือกความยาวคลิป (8, 16, 30 วิ) และเลือกสไตล์ที่ชอบ (3D Animation, Stop Motion ฯลฯ)
   - กด '🚀 ส่งพรอมต์ไปที่ Flow' เพื่อเปิด Google Flow และส่งพรอมต์พร้อมรูปภาพสินค้าไปทำคลิป
3. เมื่อ Flow เจนคลิปเสร็จแล้ว ดาวน์โหลดไฟล์ .mp4 มาไว้ที่เครื่อง
   - กด '📂 อัปโหลดไฟล์' หรือ '⚡ ตรวจหาล่าสุด' เพื่อเลือกคลิป
   - กด '🚀 สั่งพนักงานโพสต์ Facebook ทันที (Auto-Post)' เพื่อให้ระบบโพสต์เข้า Profile ให้ทันที!
"""
        messagebox.showinfo("คู่มือการใช้งาน Facebook Profile Studio", guide_text)

    def _open_flow_example_video(self):
        messagebox.showinfo(
            "ตัวอย่างวิดีโอ Google Flow",
            """วิดีโอตัวอย่างที่สร้างด้วย Flow:

• รูปแบบ: แนวตั้ง 9:16 (เหมาะสำหรับ Reels / Facebook Post)
• เสียงพากย์: ภาษาไทยธรรมชาติ สอดคล้องกับจังหวะแอนิเมชัน
• สินค้า: ชูสินค้าเด่นชัดเจน พร้อมลูกศรชี้พิกัดคอมเมนต์"""
        )
    def _open_caption_template_menu(self):
        if not self.fb_selected_prod:
            messagebox.showinfo("เทมเพลตแคปชั่น", "กรุณาเลือกสินค้า Shopee ก่อน")
            return
        self._update_fb_caption()
        self.say("ปรับใช้เทมเพลตแคปชั่นสำเร็จ", "good")

    def _refresh_fb_products(self):
        from . import facebook_profile_flow as fb_flow
        self.say("กำลังโหลดสินค้า Shopee...")
        self.fb_raw_prods = fb_flow.load_shopee_products()
        cats = fb_flow.get_categories()
        if hasattr(self, "fb_cat_cb"):
            self.fb_cat_cb.configure(values=cats)
            if self.fb_cat_var.get() not in cats:
                self.fb_cat_var.set("ทุกหมวดหมู่")
        self._filter_fb_products()
        self.say(f"โหลดสินค้า Shopee {len(self.fb_raw_prods):,} รายการเรียบร้อย", "good")

    def _filter_fb_products(self):
        search = self.fb_search_var.get().strip().lower()
        cat = self.fb_cat_var.get()
        self.tv_fb.delete(*self.tv_fb.get_children())
        self.fb_prods = []

        for p in self.fb_raw_prods:
            if cat and cat != "ทุกหมวดหมู่" and p.get("category") != cat:
                continue
            if search and search not in p["name"].lower() and search not in p.get("seller_name", "").lower():
                continue
            self.fb_prods.append(p)
            price_txt = f"฿{p['effective_price']:,.2f}".rstrip("0").rstrip(".") if p['effective_price'] > 0 else "-"
            sold_txt = f"{p['sold_count']:,}" if p['sold_count'] > 0 else "-"
            rating_txt = f"{p['rating']:.1f}" if p['rating'] > 0 else "-"
            self.tv_fb.insert("", "end", iid=p["id"], values=(p["name"], price_txt, sold_txt, rating_txt))

        if hasattr(self, "lbl_fb_item_count"):
            self.lbl_fb_item_count.configure(text=f"แสดง 1-{min(len(self.fb_prods), 20)} จาก {len(self.fb_prods):,} รายการ")

        # Select first product if available
        if self.fb_prods:
            first_id = self.fb_prods[0]["id"]
            self.tv_fb.selection_set(first_id)
            self.tv_fb.see(first_id)
            self._select_fb_product(self.fb_prods[0])

    def _on_fb_product_selected(self, event=None):
        sel = self.tv_fb.selection()
        if not sel:
            return
        p_id = sel[0]
        prod = next((p for p in self.fb_prods if p["id"] == p_id), None)
        if prod:
            self._select_fb_product(prod)

    def _select_fb_product(self, prod):
        self.fb_selected_prod = prod
        self.fb_p_title.configure(text=prod["name"])
        price_txt = f"฿{prod['effective_price']:,.2f}".rstrip("0").rstrip(".")
        if prod.get("original_price") and prod["original_price"] > prod["effective_price"]:
            orig_txt = f"฿{prod['original_price']:,.2f}".rstrip("0").rstrip(".")
            self.fb_p_price.configure(text=price_txt)
            if hasattr(self, "fb_p_orig"):
                self.fb_p_orig.configure(text=orig_txt)
            if hasattr(self, "fb_p_disc"):
                try:
                    discount_pct = int(round((1 - (prod["effective_price"] / prod["original_price"])) * 100))
                    self.fb_p_disc.configure(text=f"-{discount_pct}%")
                except Exception:
                    self.fb_p_disc.configure(text="-25%")
        else:
            self.fb_p_price.configure(text=price_txt)
            if hasattr(self, "fb_p_orig"):
                self.fb_p_orig.configure(text="")
            if hasattr(self, "fb_p_disc"):
                self.fb_p_disc.configure(text="ราคาพิเศษ")

        shop_info = f"{prod.get('seller_name') or 'Shopee Official Store'}   ⭐ {prod['rating']:.1f}  (5.2k รีวิว)"
        self.fb_p_shop.configure(text=shop_info)
        self.btn_fb_open_shopee.configure(state="normal" if prod.get("product_url") else "disabled")

        # Load thumbnail in background thread
        self._load_fb_thumbnail(prod.get("image_url"), prod["id"])

        # Update prompt & caption
        self._update_fb_prompt()
        self._update_fb_caption()

    def _load_fb_thumbnail(self, image_url, product_id):
        from . import facebook_profile_flow as fb_flow
        self.fb_thumb_lbl.configure(image="", text="[กำลังโหลด...]", bg="#FFF0EB")

        def work():
            try:
                local_path = fb_flow.download_image_cache(image_url, product_id)
                if local_path and local_path.is_file():
                    try:
                        im = Image.open(local_path).convert("RGB")
                        im = im.resize((96, 96), Image.Resampling.LANCZOS)
                        tk_img = ImageTk.PhotoImage(im)
                        self.after(0, lambda: self._apply_fb_thumbnail(tk_img, product_id))
                        return
                    except Exception:
                        pass
                self.after(0, lambda: self.fb_thumb_lbl.configure(image="", text="[ไม่มีรูป]", bg="#FFF0EB"))
            except Exception:
                pass

        threading.Thread(target=work, daemon=True).start()

    def _apply_fb_thumbnail(self, tk_img, target_id):
        if self.fb_selected_prod and self.fb_selected_prod.get("id") == target_id:
            self._fb_thumb_img = tk_img
            self.fb_thumb_lbl.configure(image=self._fb_thumb_img, text="", bg="#FFF0EB")

    def _open_selected_shopee(self):
        if self.fb_selected_prod and self.fb_selected_prod.get("product_url"):
            open_path(self.fb_selected_prod["product_url"])

    def _set_fb_duration(self, seconds):
        self.fb_dur_val.set(seconds)
        for s, btn in self.fb_dur_btns.items():
            if s == seconds:
                btn.configure(bg="#7C4DFF", fg="#FFFFFF", text=f"● {s} วิ", font=(self.F, 8, "bold"))
            else:
                btn.configure(bg="#F3EFFE", fg="#6C47FF", text=f"{s} วิ", font=(self.F, 8, "normal"))
        self._update_fb_prompt()

    def _update_fb_prompt(self):
        if not self.fb_selected_prod:
            return
        from . import facebook_profile_flow as fb_flow
        dur = self.fb_dur_val.get()
        style_key = getattr(self, "fb_selected_style", "cartoon")
        prompt = fb_flow.generate_flow_prompt(self.fb_selected_prod, dur, style_key)
        self.txt_fb_prompt.delete("1.0", "end")
        self.txt_fb_prompt.insert("1.0", prompt)
        self._update_prompt_count()

    def _update_fb_caption(self):
        if not self.fb_selected_prod:
            return
        from . import facebook_profile_flow as fb_flow
        caption = fb_flow.generate_facebook_caption(self.fb_selected_prod)
        self.txt_fb_caption.delete("1.0", "end")
        self.txt_fb_caption.insert("1.0", caption)
        self._update_caption_count()
    def _copy_fb_prompt(self):
        text = self.txt_fb_prompt.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("พรอมต์ Flow", "กรุณาเลือกสินค้าเพื่อสร้างพรอมต์ก่อน")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.say("คัดลอกพรอมต์ Flow แล้ว พร้อมนำไปวางใน Google Flow", "good")

    def _send_fb_to_flow(self):
        if not self.fb_selected_prod:
            messagebox.showinfo("Google Flow", "กรุณาเลือกสินค้า Shopee ก่อน")
            return
        from . import facebook_profile_flow as fb_flow
        prompt = self.txt_fb_prompt.get("1.0", "end").strip()
        if not prompt:
            self._update_fb_prompt()
            prompt = self.txt_fb_prompt.get("1.0", "end").strip()

        assets = fb_flow.stage_product_assets_for_flow(self.fb_selected_prod, prompt)
        self.clipboard_clear()
        self.clipboard_append(prompt)

        # Open Google Flow
        open_path("https://flow.google.com/")

        # Open staging folder with the image
        if assets.get("image_file") and assets["image_file"].is_file():
            open_path(fb_flow.STAGING_DIR)

        self.say("คัดลอกพรอมต์แล้ว เปิด Google Flow และโฟลเดอร์รูปภาพสินค้าเรียบร้อย", "good")
        messagebox.showinfo(
            "ส่งไปยัง Google Flow",
            "เปิด Google Flow เรียบร้อยแล้ว!\n\n"
            "1. พรอมต์ถูกคัดลอกไปยังคลิปบอร์ดแล้ว (กด Ctrl+V เพื่อวางใน Flow)\n"
            "2. โฟลเดอร์รูปภาพสินค้าถูกเปิดขึ้นมาแล้ว (สามารถลากรูปสินค้าไปวางใน Flow ได้ทันที)\n"
            "3. เมื่อ Flow สร้างวิดีโอเสร็จแล้ว ให้ดาวน์โหลดไฟล์ .mp4 แล้วกลับมากด 'เลือกไฟล์วิดีโอจาก Flow' ในหน้านี้"
        )

    def _copy_fb_caption(self):
        caption = self.txt_fb_caption.get("1.0", "end").strip()
        if not caption:
            messagebox.showinfo("แคปชั่น", "กรุณาเลือกสินค้าเพื่อเตรียมแคปชั่นก่อน")
            return
        self.clipboard_clear()
        self.clipboard_append(caption)
        self.say("คัดลอกแคปชั่นสำหรับ Facebook Profile พร้อม @ผู้ติดตาม เรียบร้อยแล้ว", "good")

    def _choose_fb_video(self):
        filetypes = [("MP4 Video", "*.mp4"), ("All Files", "*.*")]
        init_dir = Path.home() / "Downloads"
        f = filedialog.askopenfilename(title="เลือกไฟล์วิดีโอที่สร้างจาก Flow",
                                       initialdir=str(init_dir) if init_dir.is_dir() else str(ROOT),
                                       filetypes=filetypes)
        if f:
            self._set_fb_video(Path(f))

    def _find_latest_fb_video(self):
        from . import facebook_profile_flow as fb_flow
        vids = fb_flow.find_recent_videos(5)
        if not vids:
            messagebox.showinfo("ตรวจหาวิดีโอ", "ไม่พบไฟล์วิดีโอ .mp4 ล่าสุดในโฟลเดอร์ Downloads หรือ output")
            return

        latest = vids[0]
        if messagebox.askyesno("พบวิดีโอล่าสุด",
                               f"พบวิดีโอ: {latest['filename']} ({latest['size_str']})\n"
                               f"ดาวน์โหลดเมื่อ: {latest['time_str']}\n\n"
                               "ต้องการใช้วิดีโอนี้เพื่อโพสต์ Facebook Profile หรือไม่?"):
            self._set_fb_video(latest["path"])

    def _set_fb_video(self, path):
        self.fb_video_path = Path(path)
        if self.fb_video_path.is_file():
            size_mb = self.fb_video_path.stat().st_size / (1024 * 1024)
            if hasattr(self, "lbl_fb_video_badge"):
                self.lbl_fb_video_badge.configure(text="● พร้อมโพสต์", bg="#E6F8F0", fg="#00A86B")
            self.lbl_fb_video_status.configure(
                text=f"📹 {self.fb_video_path.name}",
                fg="#2C1D63"
            )
            if hasattr(self, "lbl_fb_video_meta"):
                self.lbl_fb_video_meta.configure(text=f"1080x1920 (9:16) • {size_mb:.1f} MB • พร้อมโพสต์")
            self.btn_fb_play_vid.configure(state="normal")
            self.say(f"เลือกวิดีโอ: {self.fb_video_path.name}", "good")
        else:
            if hasattr(self, "lbl_fb_video_badge"):
                self.lbl_fb_video_badge.configure(text="❌ ไฟล์ไม่ถูกต้อง", bg="#FFF0F0", fg=BAD)
            self.lbl_fb_video_status.configure(text="ไฟล์ไม่ถูกต้องหรือไม่พบไฟล์", fg=BAD)
            self.btn_fb_play_vid.configure(state="disabled")
    def _play_fb_video(self):
        if self.fb_video_path and self.fb_video_path.is_file():
            open_path(self.fb_video_path)

    def _publish_to_fb_profile(self):
        self._copy_fb_caption()
        if self.fb_video_path and self.fb_video_path.is_file():
            try:
                subprocess.Popen(f'explorer /select,"{str(self.fb_video_path)}"')
            except Exception:
                open_path(self.fb_video_path.parent)
        else:
            messagebox.showwarning("ยังไม่ได้เลือกวิดีโอ", "แนะนำให้เลือกไฟล์วิดีโอจาก Flow ก่อน เพื่อให้ลากไปโพสต์ได้สะดวก")

        # Open Facebook
        open_path("https://www.facebook.com/")
        self.say("เปิด Facebook และคัดลอกแคปชั่นพร้อมแท็ก @ผู้ติดตาม แล้ว!", "good")

        messagebox.showinfo(
            "โพสต์ Facebook Profile",
            "เปิดหน้า Facebook และคัดลอกแคปชั่นเรียบร้อยแล้ว!\n\n"
            "วิธีโพสต์:\n"
            "1. บน Facebook ให้คลิกที่ 'คุณกำลังคิดอะไรอยู่' หรือสร้าง 'Reels'\n"
            "2. กด Ctrl+V เพื่อวางแคปชั่น (มีแท็ก @ผู้ติดตาม และลิงก์สินค้าครบถ้วน)\n"
            "3. ลากไฟล์วิดีโอจากโฟลเดอร์ที่เปิดขึ้นมาไปวางในโพสต์\n"
            "4. กด 'โพสต์' (Post)\n"
            "5. เมื่อโพสต์เสร็จแล้ว ให้กลับมากดปุ่ม '✅ บันทึกว่าโพสต์สำเร็จแล้ว' ที่หน้านี้"
        )

    def _mark_fb_posted(self):
        if not self.fb_selected_prod:
            messagebox.showinfo("บันทึกการโพสต์", "เลือกสินค้าก่อนบันทึก")
            return
        from . import facebook_profile_flow as fb_flow
        url = simpledialog.askstring("ลิงก์โพสต์ Facebook", "วาง URL โพสต์บน Facebook Profile (หรือกด OK เพื่อบันทึก)")
        if url is None:
            return

        caption = self.txt_fb_caption.get("1.0", "end").strip()
        vid = str(self.fb_video_path) if self.fb_video_path else ""
        fb_flow.record_facebook_post(self.fb_selected_prod, vid, caption, url)
        self.say(f"บันทึกการโพสต์สินค้า {self.fb_selected_prod['name'][:40]} บน Facebook Profile เรียบร้อยแล้ว", "good")
        messagebox.showinfo("สำเร็จ", "บันทึกประวัติการโพสต์ลงในระบบเรียบร้อยแล้ว!")

    def _open_fb_worker_login(self):
        from . import fb_browser_worker
        try:
            fb_browser_worker.open_login_window(log_callback=lambda msg: self.say(msg, "info"))
            self.lbl_fb_worker_status.configure(
                text="สถานะ: เปิดหน้าต่าง Facebook แล้ว กรุณาเข้าสู่ระบบในเบราว์เซอร์ (ระบบจะจำบัญชีไว้ถาวร)",
                foreground=ACCENT_D
            )
            messagebox.showinfo(
                "เข้าสู่ระบบ Facebook สำหรับพนักงาน",
                "เปิดเบราว์เซอร์สำหรับพนักงานเรียบร้อยแล้ว!\n\n"
                "1. ในหน้าต่างที่เปิดขึ้นมา ให้เข้าสู่ระบบ Facebook ของคุณตามปกติ\n"
                "2. เมื่อเข้าสู่ระบบสำเร็จแล้ว สามารถปล่อยหน้าต่างไว้หรือปิดได้เลย\n"
                "3. ระบบจะจำบัญชีนี้ไว้ถาวร ทำให้พนักงานโพสต์คลิปได้อัตโนมัติทันทีโดยไม่ต้องล็อกอินซ้ำ"
            )
        except Exception as e:
            self.say(f"เปิดเบราว์เซอร์ไม่สำเร็จ: {e}", "bad")
            messagebox.showerror("เกิดข้อผิดพลาด", f"ไม่สามารถเปิดเบราว์เซอร์ได้:\n{e}")

    def _run_fb_browser_worker(self):
        if not self.fb_selected_prod:
            messagebox.showinfo("พนักงานอัตโนมัติ", "กรุณาเลือกสินค้า Shopee ในตารางด้านซ้ายก่อน")
            return
        if not self.fb_video_path or not self.fb_video_path.is_file():
            messagebox.showwarning("พนักงานอัตโนมัติ", "ยังไม่ได้เลือกไฟล์วิดีโอจาก Flow (.mp4)\nกรุณากดเลือกไฟล์วิดีโอด้านบนก่อน")
            return

        caption = self.txt_fb_caption.get("1.0", "end").strip()
        if not caption:
            self._update_fb_caption()
            caption = self.txt_fb_caption.get("1.0", "end").strip()

        video_path = self.fb_video_path
        prod = self.fb_selected_prod
        auto_pub = self.fb_worker_auto_pub.get()

        self.btn_fb_worker_run.configure(state="disabled", text="⏳ พนักงานกำลังทำงาน...")
        self.lbl_fb_worker_status.configure(text="สถานะ: กำลังเริ่มต้นพนักงานเบราว์เซอร์...", foreground=ACCENT_D)
        self.say("พนักงานอัตโนมัติเริ่มทำงาน...", "info")

        def worker_task():
            from . import fb_browser_worker
            from . import facebook_profile_flow as fb_flow

            def update_log(msg):
                self.after(0, lambda m=msg: self._on_fb_worker_log(m))

            try:
                ok = fb_browser_worker.publish_facebook_reel(
                    video_path=video_path,
                    caption=caption,
                    auto_publish=auto_pub,
                    log_callback=update_log,
                )
                if ok:
                    fb_flow.record_facebook_post(prod, str(video_path), caption, "https://www.facebook.com/")
                    self.after(0, lambda: self._on_fb_worker_success(auto_pub))
                else:
                    self.after(0, lambda: self._on_fb_worker_success(False))
            except PermissionError as pe:
                self.after(0, lambda: self._on_fb_worker_error(str(pe), need_login=True))
            except Exception as ex:
                self.after(0, lambda: self._on_fb_worker_error(str(ex), need_login=False))

        threading.Thread(target=worker_task, daemon=True).start()

    def _on_fb_worker_log(self, msg):
        self.say(msg)
        self.lbl_fb_worker_status.configure(text=f"สถานะ: {msg}", foreground=ACCENT_D)

    def _on_fb_worker_success(self, auto_pub):
        self.btn_fb_worker_run.configure(state="normal", text="🚀 สั่งพนักงานโพสต์ Facebook ทันที (Auto-Post)")
        if auto_pub:
            msg = "🎉 พนักงานโพสต์คลิปลง Facebook Profile เรียบร้อยแล้ว!"
            self.lbl_fb_worker_status.configure(text=msg, foreground=GOOD)
            self.say(msg, "good")
            messagebox.showinfo("โพสต์สำเร็จ", "พนักงานได้อัปโหลดคลิป วางแคปชั่น และเผยแพร่ลง Facebook Profile เรียบร้อยแล้ว!")
        else:
            msg = "✨ พนักงานอัปโหลดและใส่แคปชั่นเรียบร้อยแล้ว! หน้าต่างเปิดค้างไว้ให้คุณตรวจทานก่อนกดเผยแพร่"
            self.lbl_fb_worker_status.configure(text=msg, foreground=ACCENT_D)
            self.say(msg, "good")

    def _on_fb_worker_error(self, err_msg, need_login=False):
        self.btn_fb_worker_run.configure(state="normal", text="🚀 สั่งพนักงานโพสต์ Facebook ทันที (Auto-Post)")
        self.lbl_fb_worker_status.configure(text=f"เกิดข้อผิดพลาด: {err_msg}", foreground=BAD)
        self.say(f"พนักงานทำงานผิดพลาด: {err_msg}", "bad")
        if need_login:
            if messagebox.askyesno("ต้องเข้าสู่ระบบ Facebook",
                                   f"{err_msg}\n\nต้องการเปิดหน้าต่างเข้าสู่ระบบ Facebook ตอนนี้หรือไม่?"):
                self._open_fb_worker_login()
        else:
            messagebox.showerror("พนักงานทำงานไม่สำเร็จ", f"เกิดข้อผิดพลาดในการทำงาน:\n{err_msg}")


def main():
    if IS_WIN:
        try:
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass
            app_id = "taoyongstudio.cartoon.app.v1"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass
    app = StudioApp()
    app.mainloop()


if __name__ == "__main__":
    main()
