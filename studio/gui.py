"""TaoYongStudio desktop window (Tkinter, ships with Python on Windows).

Start with:  TaoYongStudio.bat   (or: .venv\\Scripts\\pythonw -m studio.gui)
"""
import datetime as dt
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
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
              "chick": "เจี๊ยบ (ลูกไก่)", "cat": "มิวมิว (แมว)"}
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


class WebTabBar(tk.Frame):
    """Modern web-style navigation bar with anti-aliased pill tabs, smooth hover, and icons."""
    def __init__(self, parent, font_family="Leelawadee UI"):
        super().__init__(parent, bg="#FFFFFF", height=52)
        self.font_family = font_family
        self.notebook = None
        self.tabs = {}
        self._pill_cache = []

        # Subtle bottom divider line (1px web border)
        self.sep = tk.Frame(self, bg=LINE, height=1)
        self.sep.pack(side="bottom", fill="x")

        # Container for horizontal tab buttons with nice padding
        self.bar = tk.Frame(self, bg="#FFFFFF")
        self.bar.pack(side="left", padx=16, pady=6)

    def _make_pill(self, w, h, r, fill_color):
        scale = 2
        img = Image.new("RGBA", (w * scale, h * scale), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        rect = [0, 0, w * scale - 1, h * scale - 1]
        draw.rounded_rectangle(rect, radius=r * scale, fill=fill_color)
        img = img.resize((w, h), Image.Resampling.LANCZOS)
        tk_img = ImageTk.PhotoImage(img)
        self._pill_cache.append(tk_img)
        return tk_img

    def setup_tabs(self, notebook, tabs_def):
        self.notebook = notebook
        f_norm = tkfont.Font(family=self.font_family, size=10, weight="normal")
        f_bold = tkfont.Font(family=self.font_family, size=10, weight="bold")

        for frame, name, icon in tabs_def:
            full_text = f"{icon}  {name}" if icon else name
            tw = max(f_norm.measure(full_text), f_bold.measure(full_text))
            tab_w = max(76, tw + 28)
            tab_h = 36

            img_norm = self._make_pill(tab_w, tab_h, 8, "#FFFFFF")
            img_hover = self._make_pill(tab_w, tab_h, 8, "#F0EBFF")
            img_active = self._make_pill(tab_w, tab_h, 8, ACCENT)

            lbl = tk.Label(
                self.bar,
                text=full_text,
                image=img_norm,
                compound="center",
                font=(self.font_family, 10),
                fg="#5A5174",
                bg="#FFFFFF",
                cursor="hand2",
                bd=0,
                highlightthickness=0
            )
            lbl.pack(side="left", padx=3)

            info = {
                "frame": frame,
                "label": lbl,
                "name": name,
                "img_norm": img_norm,
                "img_hover": img_hover,
                "img_active": img_active,
                "is_active": False
            }

            lbl.bind("<Button-1>", lambda e, f=frame: self.notebook.select(f))
            lbl.bind("<Enter>", lambda e, i=info: self._on_enter(i))
            lbl.bind("<Leave>", lambda e, i=info: self._on_leave(i))

            self.tabs[str(frame)] = info

        self.sync_selection()

    def _on_enter(self, info):
        if not info["is_active"]:
            info["label"].configure(image=info["img_hover"], fg=ACCENT_D)

    def _on_leave(self, info):
        if not info["is_active"]:
            info["label"].configure(image=info["img_norm"], fg="#5A5174")

    def sync_selection(self):
        if not self.notebook:
            return
        current = self.notebook.select()
        for f_id, info in self.tabs.items():
            if f_id == current:
                info["is_active"] = True
                info["label"].configure(
                    image=info["img_active"],
                    fg="#FFFFFF",
                    font=(self.font_family, 10, "bold")
                )
            else:
                info["is_active"] = False
                info["label"].configure(
                    image=info["img_norm"],
                    fg="#5A5174",
                    font=(self.font_family, 10, "normal")
                )


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
        self.refresh_all()

    # ------------------------------------------------------------------ look
    def _set_icon(self):
        ico = ROOT / "studio" / "app.ico"
        png = ROOT / "studio" / "app.png"
        try:
            if IS_WIN and ico.exists():
                self.iconbitmap(default=str(ico))
            elif png.exists():
                self._icon = ImageTk.PhotoImage(Image.open(png).resize((64, 64)))
                self.iconphoto(True, self._icon)
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
        f = ttk.Frame(parent, style="Card.TFrame", padding=16)
        if pack:
            f.pack(**pack)
        return f

    # ------------------------------------------------------------------ layout
    def _build(self):
        head = tk.Frame(self, bg=INK, height=56)
        head.pack(fill="x")
        try:
            self._head_img = ImageTk.PhotoImage(Image.open(ROOT / "studio" / "app.png").resize((34, 34)))
            tk.Label(head, image=self._head_img, bg=INK).pack(side="left", padx=(16, 8), pady=10)
        except Exception:
            pass
        tk.Label(head, text="TaoYongStudio", bg=INK, fg="#FFFFFF", font=(self.F, 15, "bold")).pack(
            side="left", padx=(0, 14), pady=10)
        tk.Label(head, text="สตูดิโอสร้างคลิปการ์ตูนเด็กภาษาไทย", bg=INK, fg="#C9BEF7",
                 font=(self.F, 10)).pack(side="left", pady=10)

        # Web status badge on top right
        status_box = tk.Frame(head, bg="#3A2863", padx=12, pady=4)
        status_box.pack(side="right", padx=16, pady=12)
        self.head_status = tk.Label(status_box, text="", bg="#3A2863", fg="#E7E1FF", font=(self.F, 9, "bold"))
        self.head_status.pack()

        # Modern Web Tab Bar
        self.web_tab_bar = WebTabBar(self, font_family=self.F)
        self.web_tab_bar.pack(fill="x")

        # bottom bar is packed first so it always keeps its height
        bottom = ttk.Frame(self, padding=(14, 8, 14, 12))
        bottom.pack(side="bottom", fill="x")
        body = ttk.Frame(self, padding=(14, 12, 14, 0))
        body.pack(fill="both", expand=True)
        self.nb = ttk.Notebook(body, style="Hidden.TNotebook")
        self.nb.pack(fill="both", expand=True)
        self.tab_home = ttk.Frame(self.nb, padding=14)
        self.tab_plan = ttk.Frame(self.nb, padding=14)
        self.tab_scripts = ttk.Frame(self.nb, padding=14)
        self.tab_clips = ttk.Frame(self.nb, padding=14)
        self.tab_platforms = ttk.Frame(self.nb, padding=10)
        self.tab_post = ttk.Frame(self.nb, padding=14)
        self.tab_sched = ttk.Frame(self.nb, padding=14)
        self.tab_set = ttk.Frame(self.nb, padding=14)
        self.tab_fb_profile = ttk.Frame(self.nb, padding=14)
        tabs = ((self.tab_home, "หน้าแรก", "🏠"),
                (self.tab_plan, "วางแผน", "📋"),
                (self.tab_scripts, "บท", "📝"),
                (self.tab_clips, "คลิป", "🎬"),
                (self.tab_platforms, "สร้างและโพสต์", "🚀"),
                (self.tab_post, "ตั้งค่าโพสต์", "⚙️"),
                (self.tab_sched, "ตั้งเวลา", "⏰"),
                (self.tab_set, "ตั้งค่า", "🔧"),
                (self.tab_fb_profile, "FaceBook Profile", "👤"))
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

        # bottom: progress + log
        top = ttk.Frame(bottom)
        top.pack(fill="x")
        self.prog_label = ttk.Label(top, text="พร้อมทำงาน", font=(self.F, 10, "bold"))
        self.prog_label.pack(side="left")
        self.btn_stop = ttk.Button(top, text="หยุด", style="Danger.TButton", command=self.stop_job,
                                   state="disabled")
        self.btn_stop.pack(side="right")
        self.btn_log = ttk.Button(top, text="ซ่อนบันทึก", command=self._toggle_log)
        self.btn_log.pack(side="right", padx=6)
        self.prog = ttk.Progressbar(bottom, mode="determinate", maximum=100)
        self.prog.pack(fill="x", pady=(6, 6))
        self.log = tk.Text(bottom, height=5, bg="#1F1636", fg="#E8E2FF", insertbackground="#FFFFFF",
                           font=("Consolas" if IS_WIN else "DejaVu Sans Mono", 9), relief="flat",
                           padx=10, pady=6, wrap="word")
        self.log.pack(fill="x")
        self.log.tag_configure("bad", foreground="#FF9C9C")
        self.log.tag_configure("good", foreground="#9CF0B8")
        self._build_fb_profile()

    def _on_tab_changed(self, event=None):
        if hasattr(self, "web_tab_bar"):
            self.web_tab_bar.sync_selection()
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
        ttk.Label(t, text="สวัสดีครับ วันนี้จะทำคลิปอะไรดี", style="H1.TLabel").pack(anchor="w", pady=(0, 10))
        stats = ttk.Frame(t)
        stats.pack(fill="x")
        self.stat_vals = {}
        for i, (key, label) in enumerate((("inbox", "บทที่รอสร้าง"), ("today", "คลิปที่สร้างวันนี้"),
                                          ("review", "คลิปรอตรวจ"), ("next", "สร้างอัตโนมัติครั้งถัดไป"))):
            c = ttk.Frame(stats, style="Card.TFrame", padding=16)
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))
            stats.columnconfigure(i, weight=1)
            ttk.Label(c, text=label, style="Muted.TLabel").pack(anchor="w")
            v = ttk.Label(c, text="-", style="Big.TLabel")
            v.pack(anchor="w")
            self.stat_vals[key] = v

        act = self.card(t, fill="x", pady=(12, 0))
        ttk.Label(act, text="งานด่วน", style="H2.TLabel").pack(anchor="w", pady=(0, 10))
        row = ttk.Frame(act, style="Card.TFrame")
        row.pack(fill="x")
        self.btn_batch = ttk.Button(row, text="▶  สร้างคลิปจากบททั้งหมด", style="Accent.TButton",
                                    command=self.run_batch)
        self.btn_batch.pack(side="left")
        ttk.Button(row, text="ดูคลิปที่สร้างแล้ว", command=lambda: self.nb.select(self.tab_clips)).pack(
            side="left", padx=8)
        ttk.Button(row, text="เพิ่มบทจากไฟล์...", command=self.import_scripts).pack(side="left")
        ttk.Button(row, text="เปิดโฟลเดอร์ผลงาน", command=lambda: open_path(ROOT / "output")).pack(side="left",
                                                                                                   padx=8)
        ttk.Button(row, text="ตรวจความพร้อมเครื่อง", command=self.run_check).pack(side="right")

        tips = self.card(t, fill="both", expand=True, pady=(12, 0))
        ttk.Label(tips, text="ระบบทำงานอย่างไร", style="H2.TLabel").pack(anchor="w", pady=(0, 8))
        steps = [
            "1.  ในแท็บ \"วางแผน\" เลือก Claude, Gemini หรือ ChatGPT แล้วเลือกทำตอนนี้หรือกำหนดเวลา",
            "2.  เปิดแท็บ \"สร้างและโพสต์\" เลือกแพลตฟอร์มและเรื่อง แล้วกดสร้างคลิปจากเครื่องหรือ Google",
            "3.  พนักงาน AI เตรียมชื่อเรื่อง คำอธิบาย และแฮชแท็กให้ เปิดดูคลิป เลือก แล้วกดโพสต์",
            "4.  YouTube และ Facebook Page ต้องเชื่อมบัญชีในแท็บ \"ตั้งค่าโพสต์\" ก่อน; บางแพลตฟอร์มต้องกดเผยแพร่ต่อในเว็บหรือแอป",
            "5.  แนะนำโพสต์วันละ 2-3 คลิปที่ดีที่สุดต่อแพลตฟอร์ม เพื่อไม่ให้ถูกมองว่าเป็นคลิปผลิตจำนวนมาก",
        ]
        for s in steps:
            ttk.Label(tips, text=s, style="Card.TLabel", wraplength=1000, justify="left").pack(anchor="w", pady=3)

    # ------------------------------------------------------------------ scripts tab
    def _build_scripts(self):
        t = self.tab_scripts
        left = ttk.Frame(t)
        left.pack(side="left", fill="both", expand=True)
        bar = ttk.Frame(left)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="บทที่รอสร้างคลิป", style="H1.TLabel").pack(side="left")
        ttk.Button(bar, text="รีเฟรช", command=self.refresh_scripts).pack(side="right")
        ttk.Button(bar, text="เพิ่มบทจากไฟล์...", command=self.import_scripts).pack(side="right", padx=6)
        ttk.Button(bar, text="เพิ่มบทตัวอย่าง", command=self.add_samples).pack(side="right", padx=6)
        ttk.Button(bar, text="ลบบทที่เลือก", style="Danger.TButton", command=self.remove_scripts).pack(side="right")

        cols = ("title", "chars", "check")
        self.tv_s = ttk.Treeview(left, columns=cols, show="headings", selectmode="extended")
        for c, w, txt in (("title", 460, "ชื่อเรื่อง"), ("chars", 220, "ตัวละคร"), ("check", 160, "ผลตรวจบท")):
            self.tv_s.heading(c, text=txt)
            self.tv_s.column(c, width=w, anchor="w")
        self.tv_s.pack(fill="both", expand=True)
        self.tv_s.tag_configure("bad", foreground=BAD)
        self.tv_s.tag_configure("warn", foreground=WARN)
        self.tv_s.bind("<<TreeviewSelect>>", lambda e: self.show_script())
        self.tv_s.bind("<Double-1>", lambda e: self.edit_script())
        self.tv_s.bind("<Delete>", lambda e: self.remove_scripts())

        # Right-click context menu for scripts
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

        right = ttk.Frame(t, style="Card.TFrame", padding=14, width=480)
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)

        btns = ttk.Frame(right, style="Card.TFrame")
        btns.pack(side="bottom", fill="x")

        # Scrollable container for script preview and animation studio tools
        canvas = tk.Canvas(right, bg=CARD, highlightthickness=0)
        scroll = ttk.Scrollbar(right, orient="vertical", command=canvas.yview)
        scroll_content = ttk.Frame(canvas, style="Card.TFrame")
        win_id = canvas.create_window((0, 0), window=scroll_content, anchor="nw")

        scroll_content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win_id, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)

        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Mousewheel scroll support
        def _on_right_wheel(e):
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind("<MouseWheel>", _on_right_wheel)

        ttk.Label(scroll_content, text="รายละเอียดบท", style="H2.TLabel").pack(anchor="w")
        self.s_preview = tk.Label(scroll_content, bg=CARD)
        self.s_preview.pack(pady=6)
        self.s_info = ttk.Label(scroll_content, text="เลือกบททางซ้าย", style="Muted.TLabel", wraplength=420,
                                justify="left")
        self.s_info.pack(anchor="w", fill="x", pady=(0, 6))

        # ==============================================================
        # Panel: เครื่องมือสร้างแอนิเมชัน (Local GPU Animation Studio V1)
        # ==============================================================
        self._build_animation_tools_panel(scroll_content)

        # Action Buttons
        self.btn_render_clip = ttk.Button(btns, text="▶  สร้างคลิปในเครื่อง (Local Animation)", style="Accent.TButton",
                                          command=self.render_selected)
        self.btn_render_clip.pack(fill="x", pady=3)
        ttk.Button(btns, text="ดูภาพตัวอย่าง", command=self.preview_script).pack(fill="x", pady=3)
        ttk.Button(btns, text="แก้ไขบท (Notepad)", command=self.edit_script).pack(fill="x", pady=3)
        ttk.Button(btns, text="ลบบทที่เลือก", style="Danger.TButton", command=self.remove_scripts).pack(
            fill="x", pady=3)

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
        self.anim_platform_status_lbl = ttk.Label(self.f_plat_sec, text="", style="Muted.TLabel", wraplength=410)
        self.anim_platform_status_lbl.pack(anchor="w")
        self.anim_platform_cb.bind("<<ComboboxSelected>>", self._on_anim_platform_selected)

        # --- B. เลือกอุปกรณ์ ---
        self.f_device_sec = ttk.Frame(panel)
        self.f_device_sec.pack(fill="x", pady=(6, 8))
        ttk.Label(self.f_device_sec, text="B. อุปกรณ์ประมวลผล (Hardware):", font=(self.F, 10, "bold")).pack(anchor="w")
        self.anim_device_val = tk.StringVar()
        self.anim_device_cb = ttk.Combobox(self.f_device_sec, textvariable=self.anim_device_val, state="readonly")
        self.anim_device_cb.pack(fill="x", pady=(3, 2))
        self.anim_device_status_lbl = ttk.Label(self.f_device_sec, text="", style="Muted.TLabel", wraplength=410)
        self.anim_device_status_lbl.pack(anchor="w")
        self.anim_device_cb.bind("<<ComboboxSelected>>", self._on_anim_device_selected)

        # --- C. เลือกประเภทแอนิเมชัน ---
        self.f_type_sec = ttk.Frame(panel)
        self.f_type_sec.pack(fill="x", pady=(6, 8))
        ttk.Label(self.f_type_sec, text="C. ประเภทแอนิเมชัน (Engine):", font=(self.F, 10, "bold")).pack(anchor="w")
        self.anim_engine_val = tk.StringVar()
        self.anim_engine_cb = ttk.Combobox(self.f_type_sec, textvariable=self.anim_engine_val, state="readonly")
        self.anim_engine_cb.pack(fill="x", pady=(3, 2))
        self.anim_engine_status_lbl = ttk.Label(self.f_type_sec, text="", style="Muted.TLabel", wraplength=410)
        self.anim_engine_status_lbl.pack(anchor="w")
        self.anim_engine_cb.bind("<<ComboboxSelected>>", self._on_anim_engine_selected)

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
        ttk.Label(box_res, text="ความละเอียด:", style="Muted.TLabel").pack(anchor="w")
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

    def _on_anim_engine_selected(self, event=None):
        label = self.anim_engine_val.get()
        item = getattr(self, "_anim_engine_map", {}).get(label)
        if item:
            k, e = item
            self.anim_engine_status_lbl.configure(text=f"{e.get('description', '')} ({e.get('status')})")

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
                self.tv_s.insert("", "end", iid=str(p), values=(sc.get("title", p.stem), chars, check), tags=(tag,))
                self._script_cache[str(p)] = (sc, err, warn)
            except Exception as e:
                self.tv_s.insert("", "end", iid=str(p), values=(p.name, "-", "อ่านไฟล์ไม่ได้"), tags=("bad",))
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
        self.s_preview.configure(image="")
        if not sel:
            return
        sc, err, warn = self._script_cache.get(str(sel[0]), (None, [], []))
        if sc is None:
            self.s_info.configure(text="ไฟล์นี้อ่านไม่ได้:\n" + "\n".join(err))
            return
        lines = sum(1 for s in sc.get("scenes", []) for b in s.get("beats", []) if b.get("say"))
        txt = "%s\n\nไฟล์: %s\nฉาก: %d   บทพูด: %d บรรทัด\n\n%s" % (
            sc.get("title", ""), sel[0].name, len(sc.get("scenes", [])), lines, sc.get("description", ""))
        if err:
            txt += "\n\nต้องแก้:\n- " + "\n- ".join(err)
        if warn:
            txt += "\n\nคำเตือน:\n- " + "\n- ".join(warn)
        self.s_info.configure(text=txt)

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
        left = ttk.Frame(t)
        left.pack(side="left", fill="both", expand=True)
        bar = ttk.Frame(left)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="คลิปที่สร้างแล้ว", style="H1.TLabel").pack(side="left")
        ttk.Button(bar, text="รีเฟรช", command=self.refresh_clips).pack(side="right")
        ttk.Button(bar, text="ลบคลิปที่เลือก", style="Danger.TButton", command=self.remove_clips).pack(side="right", padx=6)
        self.clip_filter = tk.StringVar(value="ทั้งหมด")
        cb = ttk.Combobox(bar, textvariable=self.clip_filter, state="readonly", width=14,
                          values=["ทั้งหมด", "รอตรวจ", "อนุมัติแล้ว", "โพสต์แล้ว", "ไม่ใช้"])
        cb.pack(side="right", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_clips())
        ttk.Label(bar, text="แสดง:").pack(side="right")

        cols = ("date", "title", "dur", "status", "posts")
        self.tv_c = ttk.Treeview(left, columns=cols, show="headings", selectmode="extended")
        for c, w, txt, anc in (("date", 100, "วันที่", "w"), ("title", 400, "ชื่อเรื่อง", "w"),
                               ("dur", 70, "ความยาว", "center"), ("status", 120, "สถานะ", "w"),
                               ("posts", 110, "โพสต์แล้ว", "w")):
            self.tv_c.heading(c, text=txt)
            self.tv_c.column(c, width=w, anchor=anc)
        self.tv_c.pack(fill="both", expand=True)
        self.tv_c.tag_configure("warn", foreground=WARN)
        self.tv_c.tag_configure("posted", foreground=GOOD)
        self.tv_c.tag_configure("rejected", foreground="#9C95AE")
        self.tv_c.bind("<<TreeviewSelect>>", lambda e: self.show_clip())
        self.tv_c.bind("<Double-1>", lambda e: self.play_clip("vertical"))
        self.tv_c.bind("<Delete>", lambda e: self.remove_clips())

        # Right-click context menu for clips
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

        right = ttk.Frame(t, style="Card.TFrame", padding=14, width=480)
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)
        btns = ttk.Frame(right, style="Card.TFrame")
        btns.pack(side="bottom", fill="x")  # packed first so the buttons are always visible
        topbox = ttk.Frame(right, style="Card.TFrame")
        topbox.pack(fill="both", expand=True)
        self.c_thumb = tk.Label(topbox, bg=CARD)
        self.c_thumb.pack(side="left", anchor="n")
        self.c_info = ttk.Label(topbox, text="เลือกคลิปทางซ้าย", style="Muted.TLabel", wraplength=310,
                                justify="left")
        self.c_info.pack(side="left", anchor="nw", fill="both", expand=True, padx=(10, 0))
        r1 = ttk.Frame(btns, style="Card.TFrame")
        r1.pack(fill="x", pady=3)
        ttk.Button(r1, text="▶ แนวตั้ง (TikTok)", command=lambda: self.play_clip("vertical")).pack(
            side="left", expand=True, fill="x")
        ttk.Button(r1, text="▶ แนวนอน (YouTube)", command=lambda: self.play_clip("horizontal")).pack(
            side="left", expand=True, fill="x", padx=(6, 0))
        ttk.Button(btns, text="คัดลอกชื่อเรื่อง + คำอธิบาย + แฮชแท็ก", style="Accent.TButton",
                   command=self.copy_upload).pack(fill="x", pady=3)
        ttk.Button(btns, text="เปิดโฟลเดอร์คลิปนี้", command=self.open_clip_folder).pack(fill="x", pady=3)
        r2 = ttk.Frame(btns, style="Card.TFrame")
        r2.pack(fill="x", pady=3)
        self.clip_status_buttons = {}
        for status, label in (("approved", "✓ อนุมัติ"), ("posted", "โพสต์แล้ว"),
                              ("rejected", "ไม่ใช้")):
            button = ttk.Button(r2, text=label, command=lambda value=status: self.set_status(value))
            button.pack(side="left", expand=True, fill="x", padx=(0, 6) if status != "rejected" else 0)
            self.clip_status_buttons[status] = button
        ttk.Label(btns, text="โพสต์คลิปนี้ตอนนี้", style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
        r3 = ttk.Frame(btns, style="Card.TFrame")
        r3.pack(fill="x", pady=3)
        self.clip_post_buttons = {}
        for txt, plat in (("YouTube", "youtube"), ("FB Page", "facebook_page"), ("TikTok", "tiktok")):
            button = ttk.Button(r3, text=txt, command=lambda p=plat: self.post_selected(p))
            button.pack(side="left", expand=True, fill="x", padx=(0, 4))
            self.clip_post_buttons[plat] = button
        ttk.Button(btns, text="Facebook ส่วนตัว (คัดลอกข้อความ + เปิดเฟซบุ๊ก)",
                   command=self.post_profile_manual).pack(fill="x", pady=3)
        ttk.Button(btns, text="🗑  ลบคลิปที่เลือก", style="Danger.TButton",
                   command=self.remove_clips).pack(fill="x", pady=(6, 2))
        self._update_clip_buttons(None)

    # ------------------------------------------------------------------ platform workspaces
    def _build_platforms(self):
        self.platform_ui = {}
        self.platform_nav = {}
        nav = ttk.Frame(self.tab_platforms)
        nav.pack(fill="x", pady=(0, 8))
        body = ttk.Frame(self.tab_platforms)
        body.pack(fill="both", expand=True)
        for platform, label, default_fmt in WORKSPACES:
            index = len(self.platform_nav)
            nav.columnconfigure(index, weight=1, uniform="platform")
            button = ttk.Button(nav, text=label, style="PlatformNav.TButton",
                                command=lambda p=platform: self._select_platform(p))
            button.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 4, 0))
            self.platform_nav[platform] = button
            page = ttk.Frame(body)
            page.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._build_platform_workspace(page, platform, label, default_fmt)
        self._select_platform(WORKSPACES[0][0])

    def _select_platform(self, platform):
        self.active_platform = platform
        self.platform_ui[platform]["tab"].lift()
        for name, button in self.platform_nav.items():
            button.configure(style="PlatformNavSelected.TButton" if name == platform else "PlatformNav.TButton")

    def _build_platform_workspace(self, tab, platform, label, default_fmt):
        ui = {"platform": platform, "current": None, "script_map": {}, "clip_map": {}}
        self.platform_ui[platform] = ui
        canvas = tk.Canvas(tab, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
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

        ttk.Label(inner, text="สร้างวิดีโอสำหรับ %s" % label, style="H1.TLabel").pack(anchor="w", pady=(0, 8))
        notes = {"tiktok": "แนวตั้ง • ส่งเข้าแบบร่าง TikTok แล้วตรวจและกดโพสต์ในแอป",
                 "youtube": "เลือกแนวตั้ง Shorts หรือแนวนอน • โพสต์ผ่าน YouTube API ที่เชื่อมไว้",
                 "shopee": "แนวตั้ง • เตรียมไฟล์และข้อความเพื่ออัปโหลดเอง • ตรวจเงื่อนไขเนื้อหา AI ของ Shopee ก่อนโพสต์",
                 "facebook_profile": "แนวตั้ง • คัดลอกข้อความและโพสต์บนโปรไฟล์ด้วยตนเอง",
                 "facebook_page": "แนวตั้ง • โพสต์ Reels ผ่าน Facebook Page API ที่เชื่อมไว้"}
        ttk.Label(inner, text=notes[platform], wraplength=900).pack(anchor="w", pady=(0, 8))

        # Row 1: 2 Cards Side-by-Side (Story Setup on Left, Video Source on Right)
        grid_row = ttk.Frame(inner)
        grid_row.pack(fill="x", pady=(0, 10))
        grid_row.columnconfigure(0, weight=1, uniform="plat_cards")
        grid_row.columnconfigure(1, weight=1, uniform="plat_cards")

        setup = self.card(grid_row)
        setup.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ttk.Label(setup, text="เลือกเรื่อง แล้วให้พนักงาน AI เตรียมข้อความโพสต์", style="H2.TLabel").pack(
            anchor="w", pady=(0, 6))
        row = ttk.Frame(setup, style="Card.TFrame")
        row.pack(fill="x", pady=(0, 6))
        ttk.Label(row, text="เรื่อง", style="Card.TLabel", width=8).pack(side="left")
        ui["script"] = tk.StringVar()
        ui["script_cb"] = ttk.Combobox(row, textvariable=ui["script"], state="readonly")
        ui["script_cb"].pack(side="left", fill="x", expand=True)
        ui["script_cb"].bind("<<ComboboxSelected>>", lambda e, p=platform: self._platform_story_changed(p, True))
        ttk.Label(setup, text="ข้อความโพสต์ที่เตรียมไว้", style="H2.TLabel").pack(anchor="w", pady=(3, 2))
        ui["meta_title"] = ttk.Label(setup, text="เลือกเรื่องหรือคลิป", style="Card.TLabel",
                                      font=(self.F, 11, "bold"), wraplength=520)
        ui["meta_title"].pack(anchor="w", fill="x")
        ui["meta_description"] = ttk.Label(setup, text="", style="Muted.TLabel", wraplength=520)
        ui["meta_description"].pack(anchor="w", fill="x", pady=2)
        ui["meta_tags"] = ttk.Label(setup, text="", style="Card.TLabel", foreground=ACCENT_D, wraplength=520)
        ui["meta_tags"].pack(anchor="w", fill="x")
        row = ttk.Frame(setup, style="Card.TFrame")
        row.pack(fill="x", pady=(8, 0))
        ui["format"] = tk.StringVar(value=default_fmt)
        ttk.Label(row, text="รูปแบบ", style="Card.TLabel", width=8).pack(side="left")
        formats = ("vertical", "horizontal") if platform == "youtube" else ("vertical",)
        format_cb = ttk.Combobox(row, textvariable=ui["format"], values=formats, width=16,
                                 state="readonly")
        format_cb.pack(side="left")
        format_cb.bind("<<ComboboxSelected>>", lambda e, p=platform: self._platform_story_changed(p, True))
        ui["made_for_kids"] = tk.BooleanVar(value=platform != "shopee")
        ttk.Checkbutton(row, text="สร้างมาเพื่อเด็ก", variable=ui["made_for_kids"]).pack(side="left", padx=16)

        source_card = self.card(grid_row)
        source_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ttk.Label(source_card, text="เลือกแหล่งวิดีโอ", style="H2.TLabel").pack(anchor="w")
        choices = ttk.Frame(source_card, style="Card.TFrame")
        choices.pack(fill="x", pady=(5, 8))
        choices.columnconfigure(0, weight=1)
        choices.columnconfigure(1, weight=1)
        ui["source"] = tk.StringVar(value="local")
        for i, (value, text) in enumerate((("local", "สร้างในเครื่อง"), ("existing", "คลิป/ไฟล์ที่มี"),
                                           ("flow", "Google Flow (เครดิตบัญชี)"), ("omni", "Google API เสียเงิน"))):
            ttk.Radiobutton(choices, text=text, value=value, variable=ui["source"],
                            style="Card.TRadiobutton",
                            command=lambda p=platform: self._platform_source_changed(p)).grid(
                row=i // 2, column=i % 2, sticky="w", pady=3, padx=(0, 4))
        source_body = ttk.Frame(source_card, style="Card.TFrame")
        source_body.pack(fill="x")
        ui["panels"] = {}
        for value in ("local", "existing", "flow", "omni"):
            ui["panels"][value] = ttk.Frame(source_body, style="Card.TFrame")

        panel = ui["panels"]["local"]
        ttk.Label(panel, text="ใช้บทที่เลือกด้านบน สร้างคลิปด้วยระบบในเครื่อง", style="Muted.TLabel", wraplength=500).pack(
            anchor="w", padx=(0, 12))
        ttk.Button(panel, text="สร้างคลิปจากบทนี้", style="Accent.TButton",
                   command=lambda p=platform: self.platform_render_local(p)).pack(anchor="w", pady=(8, 0))

        panel = ui["panels"]["existing"]
        ttk.Label(panel, text="ใช้คลิปในคลัง หรือเลือกไฟล์วิดีโอจากเครื่องเพื่อแปลงและนำเข้า",
                  style="Muted.TLabel", wraplength=500).pack(anchor="w")
        row = ttk.Frame(panel, style="Card.TFrame")
        row.pack(fill="x", pady=5)
        ui["clip_choice"] = tk.StringVar()
        ui["clip_cb"] = ttk.Combobox(row, textvariable=ui["clip_choice"], state="readonly")
        ui["clip_cb"].pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(row, text="ใช้คลิปนี้", command=lambda p=platform: self.platform_choose_clip(p)).pack(
            side="left", padx=(0, 6))
        ttk.Button(row, text="นำเข้าไฟล์วิดีโอ...", command=lambda p=platform: self.platform_import(p, "computer")).pack(
            side="left")

        panel = ui["panels"]["flow"]
        ttk.Label(panel, text="Flow ใช้เครดิตของบัญชี Google • สร้างในเว็บ ดาวน์โหลด แล้วนำไฟล์กลับเข้าคลัง",
                  style="Muted.TLabel", wraplength=500).pack(anchor="w")
        row = ttk.Frame(panel, style="Card.TFrame")
        row.pack(fill="x", pady=(5, 0))
        ttk.Label(row, text="พรอมต์", style="Card.TLabel").pack(side="left")
        ui["flow_part"] = tk.StringVar()
        ui["flow_part_cb"] = ttk.Combobox(row, textvariable=ui["flow_part"], state="readonly")
        ui["flow_part_cb"].pack(side="left", fill="x", expand=True, padx=(6, 0))
        ui["flow_part_cb"].bind("<<ComboboxSelected>>", lambda e, p=platform: self._platform_flow_part_changed(p))
        ui["flow_prompt"] = tk.Text(panel, height=3, wrap="word", font=(self.F, 10))
        ui["flow_prompt"].pack(fill="x", pady=5)
        row = ttk.Frame(panel, style="Card.TFrame")
        row.pack(anchor="w")
        ttk.Button(row, text="คัดลอกพรอมต์ + เปิด Google Flow",
                   command=lambda p=platform: self.platform_open_flow(p)).pack(side="left")
        ttk.Button(row, text="นำเข้าคลิปที่ดาวน์โหลด...", style="Accent.TButton",
                   command=lambda p=platform: self.platform_import(p, "google_flow")).pack(side="left", padx=8)
        ttk.Label(panel, text="ใน Flow เลือก Agent สำหรับทั้งเรื่อง หรือ Video สำหรับฉากเดียว → Ctrl+V และสร้าง "
                              "→ รวมหลายช็อตใน Scenebuilder → ดาวน์โหลด MP4 → กลับมานำเข้า (ตรวจเครดิตก่อนสร้าง)",
                  style="Muted.TLabel", wraplength=500).pack(anchor="w", pady=(6, 0))

        panel = ui["panels"]["omni"]
        ttk.Label(panel, text="พรอมต์สร้างอัตโนมัติจากเรื่องที่เลือก • Gemini Omni Flash สร้างคลิป 3–10 วินาที",
                  style="Muted.TLabel", wraplength=500).pack(anchor="w")
        ui["omni_prompt"] = tk.Text(panel, height=3, wrap="word", font=(self.F, 10))
        ui["omni_prompt"].pack(fill="x", pady=5)
        row = ttk.Frame(panel, style="Card.TFrame")
        row.pack(fill="x")
        ttk.Label(row, text="ความละเอียด", style="Card.TLabel").pack(side="left")
        ui["resolution"] = tk.StringVar(value="720p")
        ttk.Combobox(row, textvariable=ui["resolution"], values=("360p", "720p", "1080p", "4k"),
                     state="readonly", width=8).pack(side="left", padx=6)
        ttk.Button(row, text="สร้างด้วย Google (มีค่าใช้จ่าย)", style="Accent.TButton",
                   command=lambda p=platform: self.platform_generate_google(p)).pack(side="left", padx=8)
        ttk.Button(row, text="ดูราคา Google",
                   command=lambda: open_path("https://ai.google.dev/gemini-api/docs/pricing")).pack(side="left")
        ttk.Button(row, text="ตั้งค่า Gemini key", command=lambda: self.nb.select(self.tab_set)).pack(side="left", padx=6)
        ttk.Label(panel, text="ตั้งค่า Gemini API key ครั้งเดียวในแท็บตั้งค่า; ตรวจราคาปัจจุบันก่อนกดสร้าง",
                  style="Muted.TLabel", wraplength=500).pack(anchor="w", pady=(5, 0))
        self._platform_source_changed(platform)

        # Row 2: Selected Clip Action Card
        selected = self.card(inner, fill="x", pady=(10, 0))
        ttk.Label(selected, text="คลิปที่เลือกสำหรับ %s" % label, style="H2.TLabel").pack(anchor="w")
        ui["current_label"] = ttk.Label(selected, text="ยังไม่ได้เลือกคลิป", style="Muted.TLabel", wraplength=900)
        ui["current_label"].pack(anchor="w", pady=(3, 6))
        row = ttk.Frame(selected, style="Card.TFrame")
        row.pack(fill="x")
        for text, command in (("▶ ดูคลิป", lambda p=platform: self.platform_play(p)),
                              ("เปิดโฟลเดอร์", lambda p=platform: self.platform_open_folder(p)),
                              ("AI เขียนข้อความโพสต์", lambda p=platform: self.platform_ai_caption(p)),
                              ("คัดลอกข้อความโพสต์", lambda p=platform: self.platform_copy_caption(p)),
                              ("✓ อนุมัติ", lambda p=platform: self.platform_approve(p))):
            ttk.Button(row, text=text, command=command).pack(side="left", padx=(0, 6))
        text = "โพสต์ไปที่ %s" % label if platform in ("youtube", "facebook_page") else (
            "ส่งเข้าแบบร่าง TikTok" if platform == "tiktok" else "เปิด %s เพื่อโพสต์เอง" % label)
        ttk.Button(selected, text=text, style="Accent.TButton",
                   command=lambda p=platform: self.platform_publish(p)).pack(anchor="w", pady=(8, 0))
        if platform in ("youtube", "facebook_page", "tiktok"):
            ttk.Button(selected, text="ตั้งค่าการเชื่อมบัญชี...",
                       command=lambda: self.nb.select(self.tab_post)).pack(anchor="w", pady=(6, 0))
        else:
            ttk.Button(selected, text="ยืนยันว่าโพสต์แล้ว",
                       command=lambda p=platform: self.platform_mark_posted(p)).pack(anchor="w", pady=(6, 0))

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

    def play_clip(self, fmt):
        folder, meta = self._sel_clip()
        if not folder:
            return
        name = meta.get("files", {}).get(fmt)
        if not name or not (folder / name).exists():
            messagebox.showinfo("เล่นคลิป", "ไม่มีคลิปแบบนี้ (อาจตั้งค่าให้สร้างเฉพาะบางแบบ)")
            return
        open_path(folder / name)

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

        # Header bar
        bar = ttk.Frame(t)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="ตั้งเวลาพนักงาน AI ทำงานอัตโนมัติ (AI Worker Scheduler)", style="H1.TLabel").pack(side="left")
        ttk.Label(bar, text="เลือกแพลตฟอร์ม กำหนดเวลาทำงานต่อวัน (5, 7, 10, 15 เวลา หรือตามต้องการ) ถึงเวลาพนักงานจะทำงานทันที",
                  foreground=MUTED, font=(self.F, 10)).pack(side="left", padx=12, pady=4)
        ttk.Button(bar, text="🔄 รีเฟรชสถานะ", command=self.refresh_worker_schedule_ui).pack(side="right")

        # Scrollable container for the entire schedule tab
        sch_canvas = tk.Canvas(t, bg=BG, highlightthickness=0)
        sch_scroll = ttk.Scrollbar(t, orient="vertical", command=sch_canvas.yview)
        sch_box = ttk.Frame(sch_canvas)
        sch_win = sch_canvas.create_window((0, 0), window=sch_box, anchor="nw")

        sch_box.bind("<Configure>", lambda e: sch_canvas.configure(scrollregion=sch_canvas.bbox("all")))
        sch_canvas.bind("<Configure>", lambda e: sch_canvas.itemconfigure(sch_win, width=e.width - 6))

        sch_canvas.configure(yscrollcommand=sch_scroll.set)
        sch_canvas.pack(side="left", fill="both", expand=True)
        sch_scroll.pack(side="right", fill="y")

        # ---------------- CARD 1: PLATFORM SELECTION ----------------
        c1 = ttk.Frame(sch_box, style="Card.TFrame", padding=14)
        c1.pack(fill="x", pady=(0, 10))

        c1_head = ttk.Frame(c1)
        c1_head.pack(fill="x", pady=(0, 6))
        ttk.Label(c1_head, text="1. เลือกแพลตฟอร์มที่ต้องการให้พนักงาน AI ทำงาน", font=(self.F, 12, "bold")).pack(side="left")
        ttk.Label(c1_head, text="(เลือกได้หลายแพลตฟอร์มพร้อมกัน เมื่อถึงเวลาพนักงานจะทำงานตามที่เลือกไว้ทันที)",
                  foreground=MUTED, font=(self.F, 10)).pack(side="left", padx=8)

        self.worker_plat_vars = {
            "facebook_profile": tk.BooleanVar(value=True),
            "facebook_page": tk.BooleanVar(value=False),
            "tiktok": tk.BooleanVar(value=False),
            "youtube": tk.BooleanVar(value=False),
            "batch_render": tk.BooleanVar(value=False),
        }

        plats_info = [
            ("facebook_profile", "👤 Facebook Profile", "พนักงานเบราว์เซอร์อัตโนมัติ (RPA): โพสต์คลิปสินค้า Shopee / Flow พร้อมแคปชั่น และ @ผู้ติดตาม"),
            ("facebook_page", "📘 Facebook Page", "โพสต์คลิป Reels ลงเพจ Facebook อัตโนมัติผ่าน Publisher API"),
            ("tiktok", "🎵 TikTok", "ส่งคลิปเข้าแบบร่าง TikTok (Draft) หรือโพสต์อัตโนมัติ"),
            ("youtube", "📺 YouTube Shorts", "อัปโหลดคลิปสั้นลง YouTube Shorts หรือคลิปแนวนอนอัตโนมัติ"),
            ("batch_render", "🎬 สร้างคลิปอัตโนมัติ (Batch Render)", "เรนเดอร์บททั้งหมดใน scripts/inbox ให้กลายเป็นคลิปวิดีโอสำเร็จรูป"),
        ]

        p_grid = ttk.Frame(c1)
        p_grid.pack(fill="x", pady=4)
        for key, title, desc in plats_info:
            row = ttk.Frame(p_grid)
            row.pack(fill="x", pady=3)
            chk = ttk.Checkbutton(row, text=title, variable=self.worker_plat_vars[key])
            chk.pack(side="left", padx=(0, 10))
            ttk.Label(row, text=f"— {desc}", foreground=MUTED, font=(self.F, 9)).pack(side="left")

        # ---------------- CARD 2: SCHEDULE TIME SLOTS (5, 7, 10, 15) ----------------
        c2 = ttk.Frame(sch_box, style="Card.TFrame", padding=14)
        c2.pack(fill="x", pady=(0, 10))

        c2_head = ttk.Frame(c2)
        c2_head.pack(fill="x", pady=(0, 6))
        ttk.Label(c2_head, text="2. กำหนดเวลาทำงานของพนักงาน (เลือกได้หลายเวลาต่อวัน)", font=(self.F, 12, "bold")).pack(side="left")
        ttk.Label(c2_head, text="กดปุ่มเพิ่มเวลาด่วน (5, 7, 10, 15 เวลา) หรือระบุเวลากำหนดเองได้ไม่จำกัด", foreground=MUTED,
                  font=(self.F, 10)).pack(side="left", padx=8)

        # Quick preset buttons (5, 7, 10, 15)
        pre_row = ttk.Frame(c2)
        pre_row.pack(fill="x", pady=(4, 8))
        ttk.Label(pre_row, text="⚡ ปุ่มเพิ่มเวลาด่วน:", font=(self.F, 10, "bold")).pack(side="left", padx=(0, 10))

        for n in (5, 7, 10, 15):
            tk.Button(
                pre_row,
                text=f"⚡ {n} เวลาต่อวัน",
                font=(self.F, 9, "bold"),
                bg="#F0EBFF",
                fg=ACCENT_D,
                activebackground=ACCENT,
                activeforeground="#FFFFFF",
                relief="flat",
                bd=1,
                padx=12,
                pady=4,
                cursor="hand2",
                command=lambda count=n: self._apply_worker_preset(count),
            ).pack(side="left", padx=4)

        # Custom time add row
        add_row = ttk.Frame(c2)
        add_row.pack(fill="x", pady=(4, 8))
        ttk.Label(add_row, text="➕ เพิ่มเวลากำหนดเอง:", font=(self.F, 10, "bold")).pack(side="left", padx=(0, 10))

        self.worker_add_hh = tk.StringVar(value="08")
        self.worker_add_mm = tk.StringVar(value="30")
        ttk.Spinbox(add_row, from_=0, to=23, width=3, textvariable=self.worker_add_hh, format="%02.0f", wrap=True,
                    font=(self.F, 11)).pack(side="left", padx=(0, 2))
        ttk.Label(add_row, text=":", font=(self.F, 11, "bold")).pack(side="left")
        ttk.Spinbox(add_row, from_=0, to=59, increment=5, width=3, textvariable=self.worker_add_mm, format="%02.0f",
                    wrap=True, font=(self.F, 11)).pack(side="left", padx=(2, 10))

        ttk.Button(add_row, text="➕ เพิ่มเวลานี้", command=self._add_worker_custom_time).pack(side="left", padx=(0, 10))
        ttk.Button(add_row, text="🗑 ล้างเวลาทั้งหมด", command=self._clear_worker_times).pack(side="left")

        # Container for visual time chips/tags
        tags_box = tk.Frame(c2, bg="#FAF9FF", bd=1, relief="solid")
        tags_box.pack(fill="x", pady=(6, 4))
        self.worker_tags_inner = ttk.Frame(tags_box, padding=10)
        self.worker_tags_inner.pack(fill="x")

        self.lbl_worker_times_summary = ttk.Label(c2, text="รวมทั้งหมด: 0 เวลาต่อวัน", font=(self.F, 9, "bold"), foreground=ACCENT_D)
        self.lbl_worker_times_summary.pack(anchor="w", pady=(2, 0))

        # ---------------- CARD 3: STATUS & CONTROLS ----------------
        c3 = ttk.Frame(sch_box, style="Card.TFrame", padding=14)
        c3.pack(fill="x", pady=(0, 10))

        c3_head = ttk.Frame(c3)
        c3_head.pack(fill="x", pady=(0, 6))
        ttk.Label(c3_head, text="3. ควบคุมระบบ & สถานะการทำงานทันที", font=(self.F, 12, "bold")).pack(side="left")

        # Status badge banner
        self.worker_status_banner = tk.Frame(c3, bg="#F5F3FA", bd=1, relief="solid")
        self.worker_status_banner.pack(fill="x", pady=(4, 10))
        s_inner = ttk.Frame(self.worker_status_banner, padding=10)
        s_inner.pack(fill="x")

        self.lbl_worker_status_icon = ttk.Label(s_inner, text="⚪", font=(self.F, 16))
        self.lbl_worker_status_icon.pack(side="left", padx=(0, 10))

        s_info = ttk.Frame(s_inner)
        s_info.pack(side="left", fill="x", expand=True)
        self.lbl_worker_status_text = ttk.Label(s_info, text="ระบบพนักงานอัตโนมัติ: ปิดอยู่", font=(self.F, 11, "bold"))
        self.lbl_worker_status_text.pack(anchor="w")
        self.lbl_worker_next_run = ttk.Label(s_info, text="รอบต่อไป: ยังไม่ได้กำหนด", foreground=MUTED, font=(self.F, 9))
        self.lbl_worker_next_run.pack(anchor="w", pady=(2, 0))

        # Control action buttons
        ctl_row = ttk.Frame(c3)
        ctl_row.pack(fill="x", pady=(4, 2))

        self.btn_worker_save_enable = ttk.Button(
            ctl_row,
            text="💾 บันทึกและเปิดระบบตั้งเวลา (Save & Enable)",
            style="Accent.TButton",
            command=self._save_and_enable_worker_schedule
        )
        self.btn_worker_save_enable.pack(side="left", padx=(0, 10))

        self.btn_worker_test_now = ttk.Button(
            ctl_row,
            text="🚀 ทดสอบให้พนักงานทำงานทันที (Test Run Now)",
            command=self._test_run_worker_now
        )
        self.btn_worker_test_now.pack(side="left", padx=(0, 10))

        self.btn_worker_disable = ttk.Button(
            ctl_row,
            text="⏹ ปิดระบบตั้งเวลา",
            style="Danger.TButton",
            command=self._disable_worker_schedule
        )
        self.btn_worker_disable.pack(side="left")

        # ---------------- CARD 4: RECENT ACTIVITY LOG ----------------
        c4 = ttk.Frame(sch_box, style="Card.TFrame", padding=14)
        c4.pack(fill="x", pady=(0, 10))

        c4_head = ttk.Frame(c4)
        c4_head.pack(fill="x", pady=(0, 6))
        ttk.Label(c4_head, text="4. ประวัติการทำงานของพนักงานล่าสุด (Activity Log)", font=(self.F, 12, "bold")).pack(side="left")
        ttk.Button(c4_head, text="🔄 รีเฟรช", command=self.refresh_worker_schedule_ui).pack(side="right")

        self.txt_worker_history = tk.Text(c4, height=5, font=(self.F, 9), relief="solid", bd=1,
                                          highlightthickness=0, wrap="word", bg="#FAF9FF")
        self.txt_worker_history.pack(fill="x", pady=(2, 4))

        # ---------------- CARD 5: TIPS & GUIDELINES ----------------
        c5 = ttk.Frame(sch_box, style="Card.TFrame", padding=14)
        c5.pack(fill="x", pady=(0, 10))
        ttk.Label(c5, text="💡 ข้อควรรู้ & คำแนะนำ", font=(self.F, 11, "bold")).pack(anchor="w", pady=(0, 4))
        tips_text = (
            "• ระบบตั้งเวลาทำงานได้ 2 ทางพร้อมกันแบบ Real-time:\n"
            "   1) เมื่อเปิดโปรแกรมไว้: มี In-App Timer คอยตรวจทุกนาที ถึงเวลาจะสั่งพนักงานทำงานทันที\n"
            "   2) เมื่อปิดโปรแกรมไว้: Windows Task Scheduler จะสั่งปลุกรันพนักงานอัตโนมัติผ่าน run_worker_auto.bat\n"
            "• สำหรับ Facebook Profile: กรุณากดปุ่ม 'เข้าสู่ระบบ Facebook (ทำครั้งเดียว)' ในแท็บ FaceBook Profile ก่อน เพื่อให้พนักงานมีสิทธิ์เข้าถึงบัญชี\n"
            "• สามารถเพิ่มช่วงเวลาได้ไม่จำกัด เช่น 5, 7, 10, 15 เวลา หรือกดปุ่มเพิ่มเวลาด่วนเพื่อกระจายเวลาทำงานตลอดวันได้ทันที"
        )
        ttk.Label(c5, text=tips_text, wraplength=980, justify="left", font=(self.F, 9), foreground=MUTED).pack(anchor="w")

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
            ttk.Label(self.worker_tags_inner, text="ยังไม่ได้เพิ่มเวลา (กดปุ่ม '⚡ ปุ่มเพิ่มเวลาด่วน' ด้านบน หรือระบุเวลาแล้วกด '+ เพิ่มเวลานี้')",
                      foreground=MUTED, font=(self.F, 9)).pack(anchor="w", pady=4)
            self.lbl_worker_times_summary.configure(text="รวมทั้งหมด: 0 เวลาต่อวัน")
            return

        self.lbl_worker_times_summary.configure(
            text=f"รวมทั้งหมด: {len(self.worker_times)} เวลาต่อวัน ({', '.join(self.worker_times)})"
        )

        chip_frame = ttk.Frame(self.worker_tags_inner)
        chip_frame.pack(fill="x")

        for hhmm in self.worker_times:
            chip = tk.Frame(chip_frame, bg="#EDE9FE", bd=1, relief="solid")
            chip.pack(side="left", padx=4, pady=4)

            lbl = tk.Label(chip, text=f"⏰ {hhmm}", font=(self.F, 9, "bold"), bg="#EDE9FE", fg=ACCENT_D)
            lbl.pack(side="left", padx=(6, 2), pady=3)

            btn_del = tk.Button(
                chip,
                text="✕",
                font=(self.F, 8, "bold"),
                bg="#EDE9FE",
                fg="#9333EA",
                activebackground=BAD,
                activeforeground="#FFFFFF",
                relief="flat",
                bd=0,
                cursor="hand2",
                command=lambda t=hhmm: self._remove_worker_time(t),
            )
            btn_del.pack(side="right", padx=(2, 6), pady=3)

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
        canvas = tk.Canvas(t, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(t, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
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

        # Row 1: 2 Cards (Channel & Video Settings on Left, Gemini AI Key on Right)
        row1 = ttk.Frame(inner)
        row1.pack(fill="x", pady=(0, 10))
        row1.columnconfigure(0, weight=1, uniform="set_col")
        row1.columnconfigure(1, weight=1, uniform="set_col")

        g = self.card(row1)
        g.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ttk.Label(g, text="ช่องและคลิป", style="H2.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.v["channel_name"] = tk.StringVar(value=c.get("channel_name", ""))
        self.v["outro_text"] = tk.StringVar(value=c.get("outro_text", ""))
        self.v["vertical"] = tk.BooleanVar(value="vertical" in c["video"]["formats"])
        self.v["horizontal"] = tk.BooleanVar(value="horizontal" in c["video"]["formats"])
        self.v["music_volume"] = tk.DoubleVar(value=float(c["audio"]["music_volume"]))
        rows = [("ชื่อช่อง (แสดงมุมซ้ายบน)", ttk.Entry(g, textvariable=self.v["channel_name"], width=36)),
                ("ข้อความปิดท้าย", ttk.Entry(g, textvariable=self.v["outro_text"], width=36))]
        for i, (lbl, w) in enumerate(rows, 1):
            ttk.Label(g, text=lbl, style="Card.TLabel").grid(row=i, column=0, sticky="w", pady=4)
            w.grid(row=i, column=1, sticky="w", padx=10)
        ttk.Label(g, text="สร้างแบบ", style="Card.TLabel").grid(row=3, column=0, sticky="w", pady=4)
        fr = ttk.Frame(g, style="Card.TFrame")
        fr.grid(row=3, column=1, sticky="w", padx=10)
        ttk.Checkbutton(fr, text="แนวตั้ง (TikTok / Shorts)", variable=self.v["vertical"]).pack(side="left")
        ttk.Checkbutton(fr, text="แนวนอน (YouTube)", variable=self.v["horizontal"]).pack(side="left", padx=12)
        ttk.Label(g, text="ความดังเพลงประกอบ", style="Card.TLabel").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Scale(g, from_=0.0, to=0.4, variable=self.v["music_volume"], length=220).grid(row=4, column=1,
                                                                                        sticky="w", padx=10)

        from .credential_store import KEY_FILE
        ai = self.card(row1)
        ai.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ttk.Label(ai, text="พนักงาน AI เขียนข้อความโพสต์ (Google Gemini)", style="H2.TLabel").pack(anchor="w")
        ttk.Label(ai, text="ใส่คีย์ครั้งเดียวเพื่อให้ AI เขียนชื่อเรื่อง คำอธิบาย และแฮชแท็กจากคลิปที่นำเข้า",
                  style="Muted.TLabel", wraplength=480).pack(anchor="w", pady=(4, 7))
        ai_row = ttk.Frame(ai, style="Card.TFrame")
        ai_row.pack(fill="x")
        self.gemini_key_entry = tk.StringVar()
        ttk.Entry(ai_row, textvariable=self.gemini_key_entry, show="•", width=36).pack(side="left", fill="x", expand=True)
        ttk.Button(ai_row, text="บันทึกคีย์", command=self.save_gemini_key).pack(side="left", padx=6)
        ttk.Button(ai_row, text="ลบคีย์", command=self.delete_gemini_key).pack(side="left")
        self.gemini_key_status = ttk.Label(ai, text="ตั้งค่าแล้วบนเครื่องนี้" if KEY_FILE.exists() else
                                           "ยังไม่ได้ตั้งค่า", style="Muted.TLabel")
        self.gemini_key_status.pack(anchor="w", pady=(5, 0))

        # Row 2: 2 Cards (Commercial Voice on Left, Character Voices on Right)
        row2 = ttk.Frame(inner)
        row2.pack(fill="x", pady=(0, 10))
        row2.columnconfigure(0, weight=1, uniform="set_col")
        row2.columnconfigure(1, weight=1, uniform="set_col")

        ab = self.card(row2)
        ab.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ttk.Label(ab, text="เสียงเชิงพาณิชย์ (Azure Speech)", style="H2.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        ttk.Label(ab, text="ใส่เมื่อพร้อมเปิดสร้างรายได้", style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self.v["azure_key"] = tk.StringVar(value=c["tts"].get("azure_key", ""))
        self.v["azure_region"] = tk.StringVar(value=c["tts"].get("azure_region", "southeastasia"))
        ttk.Label(ab, text="คีย์", style="Card.TLabel").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(ab, textvariable=self.v["azure_key"], width=32, show="•").grid(row=2, column=1, sticky="w", padx=10)
        ttk.Label(ab, text="ภูมิภาค", style="Card.TLabel").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(ab, textvariable=self.v["azure_region"], width=20).grid(row=3, column=1, sticky="w", padx=10)

        vb = self.card(row2)
        vb.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ttk.Label(vb, text="เสียงตัวละคร", style="H2.TLabel").grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 4))
        ttk.Label(vb, text="ความสูงเสียง: + สูง / - ต่ำ     ความเร็ว: + เร็ว / - ช้า",
                  style="Muted.TLabel").grid(row=1, column=0, columnspan=5, sticky="w", pady=(0, 8))
        for j, h in enumerate(("ตัวละคร", "เสียง", "สูง", "เร็ว", "")):
            ttk.Label(vb, text=h, style="Muted.TLabel").grid(row=2, column=j, sticky="w", padx=4)
        self.voice_vars = {}
        for i, who in enumerate(["narrator", "bunny", "bear", "chick", "cat"], 3):
            vc = c["voices"].get(who, {})
            nv = tk.StringVar(value=vc.get("edge", VOICE_CHOICES[0]))
            pv = tk.IntVar(value=int(str(vc.get("pitch", "+0Hz")).replace("Hz", "")))
            rv = tk.IntVar(value=int(str(vc.get("rate", "+0%")).replace("%", "")))
            self.voice_vars[who] = (nv, pv, rv)
            ttk.Label(vb, text=CHAR_NAMES[who].split(" ")[0], style="Card.TLabel").grid(row=i, column=0, sticky="w", padx=4, pady=3)
            ttk.Combobox(vb, textvariable=nv, values=VOICE_CHOICES, state="readonly", width=18).grid(
                row=i, column=1, padx=4)
            ttk.Spinbox(vb, from_=-50, to=100, increment=5, textvariable=pv, width=4).grid(row=i, column=2, padx=4)
            ttk.Spinbox(vb, from_=-50, to=50, increment=5, textvariable=rv, width=4).grid(row=i, column=3, padx=4)
            ttk.Button(vb, text="ฟังเสียง", command=lambda w=who: self.test_voice(w)).grid(row=i, column=4, padx=4)

        sv = ttk.Frame(inner)
        sv.pack(fill="x", pady=12)
        ttk.Button(sv, text="บันทึกการตั้งค่า", style="Accent.TButton", command=self.save_settings).pack(side="left")
        ttk.Button(sv, text="คืนค่าเริ่มต้น", command=self.reset_settings).pack(side="left", padx=8)

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
        (ROOT / "config.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        self.cfg = cfgmod.load()
        self.say("บันทึกการตั้งค่าแล้ว", "good")

    def save_gemini_key(self):
        from .credential_store import save_key
        try:
            save_key(self.gemini_key_entry.get())
        except Exception as exc:
            messagebox.showerror("Gemini API key", str(exc))
            return
        self.gemini_key_entry.set("")
        self.gemini_key_status.configure(text="ตั้งค่าแล้วบนเครื่องนี้")
        self.say("บันทึก Gemini API key สำหรับบัญชี Windows นี้แล้ว", "good")

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
        bar = ttk.Frame(t)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="วางแผนคลิปกับ AI", style="H1.TLabel").pack(side="left")
        self.plan_updated = ttk.Label(bar, text="", foreground=MUTED)
        self.plan_updated.pack(side="left", padx=12)
        ttk.Button(bar, text="รีเฟรช", command=self.refresh_plan).pack(side="right")
        ttk.Button(bar, text="คัดลอกพรอมต์ Flow (คลิปสินค้า)", command=self.copy_product_prompt).pack(side="right", padx=6)
        ttk.Button(bar, text="สร้างไอเดียคลิปสินค้า", command=self.make_product_ideas).pack(side="right")
        self.plan_genre = tk.StringVar(value="ทุกแนว")
        self.plan_genre_cb = ttk.Combobox(bar, textvariable=self.plan_genre, state="readonly", width=22)
        self.plan_genre_cb.pack(side="right", padx=6)
        self.plan_genre_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_plan())
        ttk.Label(bar, text="แนว:").pack(side="right")

        main = ttk.Frame(t)
        main.pack(fill="both", expand=True)
        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="ไอเดียที่ AI วิเคราะห์มาให้ (เลือกได้หลายอัน กด Ctrl ค้างแล้วคลิก)",
                  foreground=MUTED).pack(anchor="w")
        cols = ("genre", "title", "why", "len")
        self.tv_i = ttk.Treeview(left, columns=cols, show="headings", selectmode="extended", height=10)
        for c, w, txt in (("genre", 130, "แนว"), ("title", 330, "ไอเดีย"), ("why", 330, "ทำไมน่าทำ"),
                          ("len", 90, "ความยาวแนะนำ")):
            self.tv_i.heading(c, text=txt)
            self.tv_i.column(c, width=w, anchor="w")
        self.tv_i.pack(fill="both", expand=True, pady=(4, 0))

        right = ttk.Frame(main, style="Card.TFrame", padding=14, width=380)
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)
        ttk.Button(right, text="ส่งคำขอ", style="Accent.TButton", command=self.send_request).pack(
            side="bottom", fill="x", pady=(10, 0))
        form_canvas = tk.Canvas(right, bg=CARD, highlightthickness=0)
        form_scroll = ttk.Scrollbar(right, orient="vertical", command=form_canvas.yview)
        form = ttk.Frame(form_canvas, style="Card.TFrame")
        form_window = form_canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>", lambda e: form_canvas.configure(scrollregion=form_canvas.bbox("all")))
        form_canvas.bind("<Configure>", lambda e: form_canvas.itemconfigure(form_window, width=e.width))
        form_canvas.configure(yscrollcommand=form_scroll.set)
        form_canvas.pack(side="left", fill="both", expand=True)
        form_scroll.pack(side="right", fill="y")
        def scroll_plan_form(event):
            if self.nb.select() != str(self.tab_plan):
                return
            target = self.winfo_containing(self.winfo_pointerx(), self.winfo_pointery())
            if target is not None and str(target).startswith(str(right)):
                form_canvas.yview_scroll(int(-event.delta / 120), "units")
        self.bind_all("<MouseWheel>", scroll_plan_form, add="+")
        ttk.Label(form, text="สร้างคำขอ", style="H2.TLabel").pack(anchor="w")
        self.req_len = tk.StringVar(value=self.LENGTHS[0][0])
        self.req_fmt = tk.StringVar(value=self.FORMATS[0][0])
        self.req_count = tk.IntVar(value=1)
        self.req_custom = tk.StringVar()
        self.req_note = tk.StringVar()
        for lbl, w in (("ความยาวคลิป", ttk.Combobox(form, textvariable=self.req_len, state="readonly",
                                                    values=[x[0] for x in self.LENGTHS])),
                       ("แนวภาพ", ttk.Combobox(form, textvariable=self.req_fmt, state="readonly",
                                               values=[x[0] for x in self.FORMATS])),
                       ("จำนวนคลิป ต่อไอเดีย", ttk.Spinbox(form, from_=1, to=10, width=8, textvariable=self.req_count)),
                       ("หัวข้อที่อยากได้เพิ่ม (พิมพ์เองได้)", ttk.Entry(form, textvariable=self.req_custom)),
                       ("หมายเหตุถึง AI", ttk.Entry(form, textvariable=self.req_note))):
            ttk.Label(form, text=lbl, style="Card.TLabel").pack(anchor="w", pady=(8, 2))
            if isinstance(w, ttk.Spinbox):
                w.pack(anchor="w", pady=(0, 2))
            else:
                w.pack(fill="x", pady=(0, 2))
        ttk.Label(form, style="Muted.TLabel", wraplength=310, justify="left",
                  text="5-20 นาที = คลิปรวมหลายตอนแนวนอนสำหรับ YouTube (AI เขียนตอนใหม่ + ใช้ตอนเก่าที่แนวเดียวกัน) "
                       "• ไม่เลือกไอเดียก็ได้ ถ้าพิมพ์หัวข้อเอง").pack(anchor="w", pady=(8, 0))

        ttk.Label(form, text="ให้ AI ตัวไหนเขียนบท", style="H2.TLabel").pack(anchor="w", pady=(8, 2))
        self.req_provider = tk.StringVar(value="claude")
        provider_row = ttk.Frame(form, style="Card.TFrame")
        provider_row.pack(fill="x")
        for value, label in (("claude", "Claude Pro"), ("gemini", "Gemini Pro"),
                             ("gpt", "ChatGPT Plus")):
            ttk.Radiobutton(provider_row, text=label, value=value, variable=self.req_provider,
                            style="Card.TRadiobutton", command=self._plan_provider_changed).pack(side="left", padx=(0, 8))
        self.plan_provider_note = ttk.Label(form, text="", style="Muted.TLabel", wraplength=310)
        self.plan_provider_note.pack(anchor="w", pady=(3, 0))
        ttk.Label(form, text="เวลาที่ให้ทำ (ตามเวลาเครื่อง)", style="Card.TLabel").pack(anchor="w", pady=(7, 2))
        when_row = ttk.Frame(form, style="Card.TFrame")
        when_row.pack(fill="x")
        self.req_when = tk.StringVar(value="now")
        ttk.Radiobutton(when_row, text="ตอนนี้", value="now", variable=self.req_when,
                        style="Card.TRadiobutton", command=self._plan_when_changed).pack(side="left")
        ttk.Radiobutton(when_row, text="กำหนดเวลา", value="later", variable=self.req_when,
                        style="Card.TRadiobutton", command=self._plan_when_changed).pack(side="left", padx=(10, 0))
        self.req_date = tk.StringVar(value=(dt.date.today() + dt.timedelta(days=1)).isoformat())
        self.req_time = tk.StringVar(value="06:22")
        self.plan_schedule_row = ttk.Frame(form, style="Card.TFrame")
        ttk.Entry(self.plan_schedule_row, textvariable=self.req_date, width=13).pack(side="left")
        ttk.Label(self.plan_schedule_row, text=" เวลา ", style="Card.TLabel").pack(side="left")
        ttk.Entry(self.plan_schedule_row, textvariable=self.req_time, width=7).pack(side="left")
        self._plan_provider_changed()
        self._plan_when_changed()

        low = ttk.Frame(t)
        low.pack(fill="x", pady=(10, 0))
        top = ttk.Frame(low)
        top.pack(fill="x")
        ttk.Label(top, text="คำขอของฉัน", style="H2.TLabel", background=BG).pack(side="left")
        ttk.Button(top, text="ยกเลิกคำขอที่เลือก", command=self.cancel_request).pack(side="right")
        ttk.Button(top, text="นำเข้าบทจาก AI", command=self.import_plan_response).pack(side="right", padx=5)
        ttk.Button(top, text="เปิดแชต / คัดลอกคำสั่ง", command=self.open_plan_request).pack(side="right")
        self.plan_when = ttk.Label(top, text="แชต AI: วางคำสั่งในแชตและนำ JSON กลับ • Gemini API: โปรแกรมทำเอง", foreground=MUTED)
        self.plan_when.pack(side="left", padx=12)
        cols = ("when", "what", "len", "status")
        self.tv_r = ttk.Treeview(low, columns=cols, show="headings", selectmode="browse", height=5)
        for c, w, txt in (("when", 130, "ส่งเมื่อ"), ("what", 520, "เรื่อง"), ("len", 140, "ความยาว / แนว"),
                          ("status", 230, "สถานะ")):
            self.tv_r.heading(c, text=txt)
            self.tv_r.column(c, width=w, anchor="w")
        self.tv_r.pack(fill="x", pady=(4, 0))
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
            self.tv_i.insert("", "end", iid=iid, values=(it.get("genre", ""), it.get("title", ""),
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
            fmt_th = {k: v for v, k in self.FORMATS}.get(r.get("format"), r.get("format", ""))
            self.tv_r.insert("", "end", iid=str(rp), tags=(tag,), values=(
                r.get("created", "")[:16].replace("T", " "), what[:120],
                "%s / %s" % (self._len_label(r.get("length_seconds", 30)), fmt_th.split(" ")[0]), st))

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
        ttk.Label(dialog, text="คัดลอก JSON ทั้งหมดที่ AI ตอบ แล้ววางด้านล่าง", style="H2.TLabel").pack(
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
        ttk.Button(dialog, text="ตรวจและนำเข้าบท", style="Accent.TButton", command=save).pack(
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
        canvas = tk.Canvas(t, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(t, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
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
        ttk.Label(inner, text="พนักงานโพสต์ (คนที่ 2)", style="H1.TLabel").pack(anchor="w", pady=(0, 8))

        self.plat_status = {}

        def plat_card(parent, col, pad, key, title, note):
            c = self.card(parent)
            c.grid(row=0, column=col, sticky="nsew", padx=pad)
            top = ttk.Frame(c, style="Card.TFrame")
            top.pack(fill="x")
            ttk.Label(top, text=title, style="H2.TLabel").pack(side="left")
            lbl = ttk.Label(top, text="", style="Card.TLabel")
            lbl.pack(side="right")
            self.plat_status[key] = lbl
            if note:
                ttk.Label(c, text=note, style="Muted.TLabel", wraplength=480, justify="left").pack(anchor="w", pady=(4, 6))
            body = ttk.Frame(c, style="Card.TFrame")
            body.pack(fill="x")
            return body

        # Row 1: 2 Cards (Post Mode on Left, YouTube on Right)
        row1 = ttk.Frame(inner)
        row1.pack(fill="x", pady=(0, 10))
        row1.columnconfigure(0, weight=1, uniform="post_col")
        row1.columnconfigure(1, weight=1, uniform="post_col")

        m = self.card(row1)
        m.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ttk.Label(m, text="โหมดการโพสต์", style="H2.TLabel").pack(anchor="w")
        self.pv["mode"] = tk.StringVar(value=st["mode"])
        for val, txt in (("off", "ไม่ออโต้ - ฉันกดปุ่มโพสต์เองในหน้า \"คลิป\""),
                         ("approved", "ออโต้ เฉพาะคลิปที่ฉันกด \"อนุมัติ\" แล้ว (แนะนำ)"),
                         ("auto", "ออโต้ทุกคลิปที่ผ่านการตรวจของระบบ (ไม่ต้องกดอนุมัติ)")):
            tk.Radiobutton(m, text=txt, value=val, variable=self.pv["mode"], bg=CARD, fg=INK,
                           activebackground=CARD, selectcolor=CARD, font=(self.F, 11), anchor="w",
                           highlightthickness=0).pack(anchor="w", pady=2)
        row = ttk.Frame(m, style="Card.TFrame")
        row.pack(anchor="w", pady=(10, 0))
        ttk.Label(row, text="โพสต์สูงสุดต่อวัน ต่อแพลตฟอร์ม", style="Card.TLabel").pack(side="left")
        self.pv["max_per_day"] = tk.IntVar(value=int(st["max_per_day"]))
        ttk.Spinbox(row, from_=1, to=10, width=4, textvariable=self.pv["max_per_day"]).pack(side="left", padx=8)
        ttk.Label(row, text="คลิป     เวลาโพสต์", style="Card.TLabel").pack(side="left", padx=(12, 0))
        self.pv["post_times"] = tk.StringVar(value=", ".join(st["post_times"]))
        ttk.Entry(row, textvariable=self.pv["post_times"], width=20).pack(side="left", padx=8)
        ttk.Label(m, text="(คั่นด้วยจุลภาค เช่น 12:00, 18:00)", style="Muted.TLabel").pack(anchor="w", pady=(2, 0))
        ttk.Label(m, style="Muted.TLabel", wraplength=480, justify="left",
                  text="แต่ละเวลาโพสต์จะโพสต์ 1 คลิปต่อแพลตฟอร์ม จนครบจำนวนต่อวัน • ระบบข้ามคลิปที่มีคำเตือน").pack(
            anchor="w", pady=(6, 0))
        self.post_sched_lbl = ttk.Label(m, text="", style="Card.TLabel")
        self.post_sched_lbl.pack(anchor="w", pady=(4, 0))
        ttk.Button(m, text="บันทึกการตั้งค่าโพสต์", style="Accent.TButton", command=self.save_post_settings).pack(
            anchor="w", pady=(8, 0))

        # YouTube (Row 1, Column 1)
        b = plat_card(row1, 1, (6, 0), "youtube", "YouTube",
                      "โพสต์อัตโนมัติผ่าน API ทางการ ตั้ง \"สร้างมาเพื่อเด็ก\" และ \"เนื้อหาสังเคราะห์\" ให้ทุกคลิป "
                      "• ต้องมีไฟล์ client_secret.json (Desktop app) จาก Google Cloud ดูวิธีใน คู่มือเชื่อมบัญชี")
        self.pv["yt_enabled"] = tk.BooleanVar(value=st["youtube"]["enabled"])
        self.pv["yt_format"] = tk.StringVar(value=st["youtube"]["format"])
        self.pv["yt_privacy"] = tk.StringVar(value=st["youtube"]["privacy"])
        ttk.Checkbutton(b, text="ใช้งาน", variable=self.pv["yt_enabled"]).grid(row=0, column=0, sticky="w")
        ttk.Label(b, text="แบบคลิป", style="Card.TLabel").grid(row=0, column=1, padx=(12, 4))
        ttk.Combobox(b, textvariable=self.pv["yt_format"], values=["vertical", "horizontal"], width=11,
                     state="readonly").grid(row=0, column=2)
        ttk.Label(b, text="การมองเห็น", style="Card.TLabel").grid(row=0, column=3, padx=(12, 4))
        ttk.Combobox(b, textvariable=self.pv["yt_privacy"], values=["public", "unlisted", "private"], width=10,
                     state="readonly").grid(row=0, column=4)
        bb = ttk.Frame(b, style="Card.TFrame")
        bb.grid(row=1, column=0, columnspan=6, sticky="w", pady=(8, 0))
        ttk.Button(bb, text="1. เลือกไฟล์ client_secret.json", command=self.yt_pick_client).pack(side="left")
        ttk.Button(bb, text="2. เชื่อมบัญชี YouTube", command=self.yt_connect).pack(side="left", padx=6)
        ttk.Button(bb, text="ยกเลิกการเชื่อม", command=lambda: self.disconnect("youtube")).pack(side="left")

        # Row 2: 2 Cards (TikTok on Left, Facebook Page on Right)
        row2 = ttk.Frame(inner)
        row2.pack(fill="x", pady=(0, 10))
        row2.columnconfigure(0, weight=1, uniform="post_col")
        row2.columnconfigure(1, weight=1, uniform="post_col")

        # TikTok (Row 2, Column 0)
        port = int(st["tiktok"].get("redirect_port", 3455))
        b = plat_card(row2, 0, (0, 6), "tiktok", "TikTok (ส่งเข้าแบบร่าง)",
                      "กฎของ TikTok จะส่งคลิปเข้า \"กล่องข้อความ\" ในแอป TikTok แล้วคุณกดโพสต์เองในแอป "
                      "• Redirect URI: http://127.0.0.1:%d/callback/" % port)
        self.pv["tt_enabled"] = tk.BooleanVar(value=st["tiktok"]["enabled"])
        ttk.Checkbutton(b, text="ใช้งาน", variable=self.pv["tt_enabled"]).grid(row=0, column=0, sticky="w")
        self.pv["tt_key"] = tk.StringVar()
        self.pv["tt_secret"] = tk.StringVar()
        for i, (lbl, key, show) in enumerate((("Client key", "tt_key", ""), ("Client secret", "tt_secret", "•")), 1):
            ttk.Label(b, text=lbl, style="Card.TLabel").grid(row=i, column=0, sticky="w", pady=3)
            ttk.Entry(b, textvariable=self.pv[key], width=36, show=show).grid(row=i, column=1, columnspan=3,
                                                                            sticky="w", padx=8)
        bb = ttk.Frame(b, style="Card.TFrame")
        bb.grid(row=3, column=0, columnspan=6, sticky="w", pady=(8, 0))
        ttk.Button(bb, text="คัดลอก Redirect URI", command=lambda: self._copy(
            "http://127.0.0.1:%d/callback/" % port)).pack(side="left")
        ttk.Button(bb, text="เชื่อมบัญชี TikTok", command=self.tt_connect).pack(side="left", padx=6)
        ttk.Button(bb, text="ยกเลิกการเชื่อม", command=lambda: self.disconnect("tiktok")).pack(side="left")

        # Facebook Page (Row 2, Column 1)
        b = plat_card(row2, 1, (6, 0), "facebook_page", "Facebook Page",
                      "โพสต์อัตโนมัติเป็น Reels ผ่าน API ของ Meta (ติดป้าย AI ให้) • ใส่ App ID / App Secret "
                      "แล้ววาง token จาก Graph API Explorer จากนั้นเลือกเพจ")
        self.pv["fb_enabled"] = tk.BooleanVar(value=st["facebook_page"]["enabled"])
        ttk.Checkbutton(b, text="ใช้งาน", variable=self.pv["fb_enabled"]).grid(row=0, column=0, sticky="w")
        self.pv["fb_app_id"] = tk.StringVar()
        self.pv["fb_secret"] = tk.StringVar()
        self.pv["fb_token"] = tk.StringVar()
        for i, (lbl, key, show) in enumerate((("App ID", "fb_app_id", ""), ("App Secret", "fb_secret", "•"),
                                             ("User token", "fb_token", "•")), 1):
            ttk.Label(b, text=lbl, style="Card.TLabel").grid(row=i, column=0, sticky="w", pady=3)
            ttk.Entry(b, textvariable=self.pv[key], width=36, show=show).grid(row=i, column=1, columnspan=3,
                                                                            sticky="w", padx=8)
        bb = ttk.Frame(b, style="Card.TFrame")
        bb.grid(row=4, column=0, columnspan=6, sticky="w", pady=(8, 0))
        ttk.Button(bb, text="เปิด Graph Explorer", command=lambda: open_path(
            "https://developers.facebook.com/tools/explorer/")).pack(side="left")
        ttk.Button(bb, text="ดึงรายชื่อเพจ", command=self.fb_list_pages).pack(side="left", padx=4)
        self.pv["fb_page"] = tk.StringVar()
        self.fb_page_cb = ttk.Combobox(bb, textvariable=self.pv["fb_page"], width=20, state="readonly")
        self.fb_page_cb.pack(side="left")
        ttk.Button(bb, text="ใช้เพจนี้", command=self.fb_use_page).pack(side="left", padx=4)
        ttk.Button(bb, text="ยกเลิก", command=lambda: self.disconnect("facebook_page")).pack(side="left")

        # Row 3: 2 Cards (Facebook Profile on Left, Account Guide Card on Right)
        row3 = ttk.Frame(inner)
        row3.pack(fill="x", pady=(0, 10))
        row3.columnconfigure(0, weight=1, uniform="post_col")
        row3.columnconfigure(1, weight=1, uniform="post_col")

        # Facebook profile (Row 3, Column 0)
        c = self.card(row3)
        c.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ttk.Label(c, text="Facebook ส่วนตัว (โปรไฟล์)", style="H2.TLabel").pack(anchor="w")
        ttk.Label(c, style="Muted.TLabel", wraplength=480, justify="left",
                  text="Facebook ปิดการโพสต์ลงโปรไฟล์ส่วนตัวผ่านโปรแกรมตั้งแต่ปี 2018 และการใช้บอทคลิกแทนผิดกฎของ Meta "
                       "วิธีที่ปลอดภัย: ให้ระบบโพสต์ลงเพจ แล้วกด \"แชร์\" จากเพจไปที่โปรไฟล์ "
                       "หรือใช้ปุ่ม \"Facebook ส่วนตัว\" ในหน้าคลิป ซึ่งจะคัดลอกข้อความและเปิด Facebook ให้คุณโพสต์เอง").pack(
            anchor="w", pady=(4, 0))

        # Guide Card (Row 3, Column 1)
        g_card = self.card(row3)
        g_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ttk.Label(g_card, text="คู่มือการเชื่อมต่อบัญชีโซเชียล", style="H2.TLabel").pack(anchor="w")
        ttk.Label(g_card, style="Muted.TLabel", wraplength=480, justify="left",
                  text="ดูวิธีเปิด Google Cloud Console ขอ YouTube API, สมัคร Meta Developer, และเปิด TikTok for Developers "
                       "พร้อมภาพขั้นตอนและตัวอย่างการตั้งค่าอย่างละเอียด").pack(anchor="w", pady=(4, 10))
        ttk.Button(g_card, text="📖 เปิดคู่มือเชื่อมบัญชี (HTML)", style="Accent.TButton",
                   command=lambda: open_path(ROOT / "CONNECT_ACCOUNTS_TH.html")).pack(anchor="w")
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
        note = ttk.Label(win, text="", style="Muted.TLabel", wraplength=560, justify="left")
        note.pack(anchor="w", padx=14, pady=(2, 0))
        decl = ttk.Label(win, text="", wraplength=560, justify="left")
        decl.pack(anchor="w", padx=14, pady=4)

        btns = ttk.Frame(win)
        btns.pack(fill="x", padx=14, pady=10)
        post_btn = ttk.Button(btns, text="โพสต์ตอนนี้", style="Accent.TButton", state="disabled")
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
        self.job_total = 0
        self.job_done = 0
        self.prog.configure(value=0)
        self.prog_label.configure(text=label)
        self.btn_stop.configure(state="normal")
        self.btn_batch.configure(state="disabled")
        self.say("เริ่ม: " + label)

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
        if "Parallax" in eng_raw:
            eng_type = "25d_parallax"
        elif "Blender" in eng_raw:
            messagebox.showwarning(
                "เครื่องมือไม่พร้อม",
                "ยังไม่ได้ติดตั้ง Blender บนเครื่องนี้\nกรุณาเลือก '2D Cartoon Animation' หรือ '2.5D Parallax Animation' ซึ่งพร้อมใช้งานในเครื่องทันที"
            )
            return
        elif "AI" in eng_raw:
            messagebox.showwarning(
                "เครื่องมือไม่พร้อม",
                "ยังไม่ได้ติดตั้ง ComfyUI หรือ CUDA GPU บนเครื่องนี้\nกรุณาเลือก '2D Cartoon Animation' หรือ '2.5D Parallax Animation' ซึ่งพร้อมใช้งานในเครื่องทันที"
            )
            return

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
        if dev_info.get("id"):
            args += ["--device", dev_info["id"]]

        title_msg = "กำลังสร้างคลิป (%s %s %s): %s" % (eng_type, res_clean, enc_clean, script_path.stem)
        self._start(args, title_msg)
        self.job_total = 1
        self._single = script_path

    def run_check(self):
        self._start(["check"], "กำลังตรวจความพร้อมเครื่อง")

    def stop_job(self):
        if self.proc and messagebox.askyesno("หยุด", "หยุดงานที่กำลังทำ? คลิปที่ทำค้างอยู่จะไม่สมบูรณ์"):
            self.proc.terminate()

    def _on_line(self, line):
        import re
        if line.startswith("CREATED: ") or re.search(r"\] CREATED: ", line):
            self._created_folder = Path(line.split("CREATED: ", 1)[1].strip())
        tag = "bad" if ("FAILED" in line or "Error" in line or "failed" in line) else (
            "good" if (" OK" in line or "READY" in line or "done" in line) else None)
        self.say(line, tag, stamp=False)
        m = re.search(r"\((\d+)/(\d+)\)", line)
        if m:
            self.job_done, self.job_total = int(m.group(1)) - 1, int(m.group(2))
            self.prog_label.configure(text="กำลังสร้างคลิปที่ %s จาก %s" % (m.group(1), m.group(2)))
        m2 = re.search(r"(vertical|horizontal) (\d+)%", line)
        if self.job_total:
            frac = 0.0
            if m2:
                part = int(m2.group(2)) / 100.0
                nfmt = len(self.cfg["video"]["formats"])
                idx = self.cfg["video"]["formats"].index(m2.group(1)) if m2.group(1) in self.cfg["video"]["formats"] else 0
                frac = (idx + part) / max(1, nfmt)
            if "OK in" in line or "FAILED" in line:
                self.job_done += 1
                frac = 0
            self.prog.configure(value=100.0 * (self.job_done + frac) / self.job_total)

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
        self.btn_batch.configure(state="normal")
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
        today = dt.date.today().isoformat()
        clips = self._clips()
        n_today = sum(1 for d, _, _ in clips if d == today)
        n_review = sum(1 for _, _, m in clips if m.get("status") == "ready_for_approval")
        self.stat_vals["inbox"].configure(text=str(n_inbox))
        self.stat_vals["today"].configure(text=str(n_today))
        self.stat_vals["review"].configure(text=str(n_review))
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

        # Header bar
        bar = ttk.Frame(t)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Facebook Profile Studio", style="H1.TLabel").pack(side="left")
        ttk.Label(bar, text="สร้างคลิปโปรโมทสินค้า Shopee ด้วย Google Flow และโพสต์ไปยัง Facebook Profile ในหน้าเดียว",
                  foreground=MUTED, font=(self.F, 10)).pack(side="left", padx=14, pady=3)
        ttk.Button(bar, text="🔄 รีเฟรชสินค้า Shopee", command=self._refresh_fb_products).pack(side="right")

        # Main PanedWindow (Allows dragging divider to expand left or right freely!)
        main = ttk.PanedWindow(t, orient="horizontal")
        main.pack(fill="both", expand=True)

        # ---------------- LEFT PANE: Shopee Products (Dynamic expand) ----------------
        left = ttk.Frame(main, padding=(0, 0, 10, 0))
        main.add(left, weight=1)

        # Filter Card
        f_card = ttk.Frame(left, style="Card.TFrame", padding=10)
        f_card.pack(fill="x", pady=(0, 6))

        r1 = ttk.Frame(f_card)
        r1.pack(fill="x")
        ttk.Label(r1, text="🔍", font=(self.F, 10)).pack(side="left", padx=(0, 4))
        self.fb_search_var = tk.StringVar()
        self.fb_search_entry = ttk.Entry(r1, textvariable=self.fb_search_var)
        self.fb_search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.fb_search_entry.bind("<KeyRelease>", lambda e: self._filter_fb_products())

        ttk.Label(r1, text="หมวด:").pack(side="left", padx=(4, 4))
        self.fb_cat_var = tk.StringVar(value="ทุกหมวดหมู่")
        self.fb_cat_cb = ttk.Combobox(r1, textvariable=self.fb_cat_var, state="readonly", width=18)
        self.fb_cat_cb.pack(side="left")
        self.fb_cat_cb.bind("<<ComboboxSelected>>", lambda e: self._filter_fb_products())

        # Product Table Card (Expanded width with both V & H scrollbars)
        tv_frame = ttk.Frame(left, style="Card.TFrame", padding=2)
        tv_frame.pack(fill="both", expand=True)

        cols = ("name", "price", "sold", "rating")
        self.tv_fb = ttk.Treeview(tv_frame, columns=cols, show="headings", selectmode="browse", height=14)
        self.tv_fb.heading("name", text="ชื่อสินค้า Shopee (กดเพื่อเลือกสินค้า)")
        self.tv_fb.column("name", width=520, minwidth=280, stretch=True)
        self.tv_fb.heading("price", text="ราคา")
        self.tv_fb.column("price", width=90, minwidth=75, anchor="e")
        self.tv_fb.heading("sold", text="ขายแล้ว")
        self.tv_fb.column("sold", width=85, minwidth=70, anchor="e")
        self.tv_fb.heading("rating", text="⭐ เรตติ้ง")
        self.tv_fb.column("rating", width=65, minwidth=50, anchor="center")

        tv_vscroll = ttk.Scrollbar(tv_frame, orient="vertical", command=self.tv_fb.yview)
        tv_hscroll = ttk.Scrollbar(tv_frame, orient="horizontal", command=self.tv_fb.xview)
        self.tv_fb.configure(yscrollcommand=tv_vscroll.set, xscrollcommand=tv_hscroll.set)

        self.tv_fb.grid(row=0, column=0, sticky="nsew")
        tv_vscroll.grid(row=0, column=1, sticky="ns")
        tv_hscroll.grid(row=1, column=0, sticky="ew")
        tv_frame.columnconfigure(0, weight=1)
        tv_frame.rowconfigure(0, weight=1)
        self.tv_fb.bind("<<TreeviewSelect>>", self._on_fb_product_selected)

        # Product Detail Card (bottom of left pane, expanded width)
        p_card = ttk.Frame(left, style="Card.TFrame", padding=12)
        p_card.pack(fill="x", pady=(8, 0))

        p_row = ttk.Frame(p_card)
        p_row.pack(fill="x")
        self.fb_thumb_lbl = tk.Label(p_row, bg="#F0EBFF", width=14, height=7, text="[รูปสินค้า]", fg=MUTED)
        self.fb_thumb_lbl.pack(side="left", padx=(0, 12))

        p_info = ttk.Frame(p_row)
        p_info.pack(side="left", fill="both", expand=True)

        self.fb_p_title = ttk.Label(p_info, text="ยังไม่ได้เลือกสินค้า", font=(self.F, 11, "bold"),
                                    wraplength=580, justify="left")
        self.fb_p_title.pack(anchor="w", pady=(0, 3))

        self.fb_p_price = ttk.Label(p_info, text="", font=(self.F, 12, "bold"), foreground=BAD)
        self.fb_p_price.pack(anchor="w")

        self.fb_p_shop = ttk.Label(p_info, text="", foreground=MUTED, font=(self.F, 9))
        self.fb_p_shop.pack(anchor="w", pady=(2, 4))

        p_btns = ttk.Frame(p_info)
        p_btns.pack(fill="x", pady=(2, 0))
        self.btn_fb_open_shopee = ttk.Button(p_btns, text="🌐 เปิดหน้า Shopee", state="disabled",
                                             command=self._open_selected_shopee)
        self.btn_fb_open_shopee.pack(side="left")

        # ---------------- RIGHT PANE: Studio Dashboard (Scrollable & Expands) ----------------
        right = ttk.Frame(main, padding=(10, 0, 0, 0))
        main.add(right, weight=1)

        r_canvas = tk.Canvas(right, bg=BG, highlightthickness=0)
        r_scroll = ttk.Scrollbar(right, orient="vertical", command=r_canvas.yview)
        r_box = ttk.Frame(r_canvas)
        r_win = r_canvas.create_window((0, 0), window=r_box, anchor="nw")

        r_box.bind("<Configure>", lambda e: r_canvas.configure(scrollregion=r_canvas.bbox("all")))
        r_canvas.bind("<Configure>", lambda e: r_canvas.itemconfigure(r_win, width=e.width - 6))

        r_canvas.configure(yscrollcommand=r_scroll.set)
        r_canvas.pack(side="left", fill="both", expand=True)
        r_scroll.pack(side="right", fill="y")

        # --- SECTION 1: Flow Video Prompt Studio ---
        c1 = ttk.Frame(r_box, style="Card.TFrame", padding=14)
        c1.pack(fill="x", pady=(0, 10))

        c1_head = ttk.Frame(c1)
        c1_head.pack(fill="x", pady=(0, 6))
        ttk.Label(c1_head, text="1. สร้างวิดีโอพรอมต์ Google Flow", font=(self.F, 12, "bold")).pack(side="left")
        ttk.Label(c1_head, text="(เลือกความยาว 8 / 10 / 12 / 15 วินาที และสไตล์)", foreground=MUTED,
                  font=(self.F, 10)).pack(side="left", padx=8)

        # Duration Selector: 8s, 10s, 12s, 15s
        dur_row = ttk.Frame(c1)
        dur_row.pack(fill="x", pady=(2, 6))
        ttk.Label(dur_row, text="ความยาววิดีโอ:", font=(self.F, 10, "bold")).pack(side="left", padx=(0, 10))

        self.fb_dur_val = tk.IntVar(value=8)
        self.fb_dur_btns = {}
        for sec in (8, 10, 12, 15):
            b = tk.Button(
                dur_row,
                text=f"⚡ {sec} วินาที",
                font=(self.F, 9, "bold" if sec == 8 else "normal"),
                bg=ACCENT if sec == 8 else "#FFFFFF",
                fg="#FFFFFF" if sec == 8 else "#5A5174",
                activebackground=ACCENT_D,
                activeforeground="#FFFFFF",
                relief="flat",
                bd=1,
                padx=14,
                pady=5,
                cursor="hand2",
                command=lambda s=sec: self._set_fb_duration(s),
            )
            b.pack(side="left", padx=4)
            self.fb_dur_btns[sec] = b

        # Style Selector
        style_row = ttk.Frame(c1)
        style_row.pack(fill="x", pady=(4, 6))
        ttk.Label(style_row, text="สไตล์วิดีโอ:", font=(self.F, 10, "bold")).pack(side="left", padx=(0, 10))

        self.fb_style_choices = [
            ("พรีเซนเตอร์ถือสินค้า", "presenter"),
            ("ปัญหา → ทางออก", "problem"),
            ("แกะกล่องสินค้า", "unboxing"),
            ("เสียงและภาพใกล้ (ASMR)", "asmr"),
            ("การ์ตูน 3D สดใส", "cartoon"),
        ]
        self.fb_style_map = {lbl: key for lbl, key in self.fb_style_choices}
        self.fb_style_labels = [lbl for lbl, _ in self.fb_style_choices]
        self.fb_style_cb = ttk.Combobox(style_row, values=self.fb_style_labels, state="readonly", width=28)
        self.fb_style_cb.current(0)
        self.fb_style_cb.pack(side="left")
        self.fb_style_cb.bind("<<ComboboxSelected>>", lambda e: self._update_fb_prompt())

        # Prompt Box
        self.txt_fb_prompt = tk.Text(c1, height=7, font=(self.F, 10), relief="solid", bd=1,
                                     highlightthickness=0, wrap="word", bg="#FAF9FF")
        self.txt_fb_prompt.pack(fill="x", pady=(4, 8))

        # Explicitly Separated Action Buttons!
        p_actions = ttk.Frame(c1)
        p_actions.pack(fill="x")
        ttk.Button(p_actions, text="📋 คัดลอกพรอมต์ Flow", command=self._copy_fb_prompt).pack(side="left", padx=(0, 8))
        ttk.Button(p_actions, text="🚀 ส่งพรอมต์และรูปภาพไปที่ Flow", style="Accent.TButton",
                   command=self._send_fb_to_flow).pack(side="left")
        ttk.Button(p_actions, text="🔄 สร้างพรอมต์ใหม่", command=self._update_fb_prompt).pack(side="right")

        # --- SECTION 2: Facebook Caption & @ผู้ติดตาม ---
        c2 = ttk.Frame(r_box, style="Card.TFrame", padding=14)
        c2.pack(fill="x", pady=(0, 10))

        c2_head = ttk.Frame(c2)
        c2_head.pack(fill="x", pady=(0, 6))
        ttk.Label(c2_head, text="2. แคปชั่น Facebook Profile (@ผู้ติดตาม)", font=(self.F, 12, "bold")).pack(side="left")
        ttk.Label(c2_head, text="เตรียมข้อความโปรโมท + แท็ก @ผู้ติดตาม + แฮชแท็ก + ลิงก์", foreground=MUTED,
                  font=(self.F, 10)).pack(side="left", padx=8)

        self.txt_fb_caption = tk.Text(c2, height=8, font=(self.F, 10), relief="solid", bd=1,
                                      highlightthickness=0, wrap="word", bg="#FAF9FF")
        self.txt_fb_caption.pack(fill="x", pady=(2, 8))

        cap_actions = ttk.Frame(c2)
        cap_actions.pack(fill="x")
        ttk.Button(cap_actions, text="📋 คัดลอกแคปชั่น", command=self._copy_fb_caption).pack(side="left", padx=(0, 8))
        ttk.Button(cap_actions, text="🔄 รีเซ็ตแคปชั่นเดิม", command=self._update_fb_caption).pack(side="left")

        # --- SECTION 3: Video Import & Facebook Profile Publishing ---
        c3 = ttk.Frame(r_box, style="Card.TFrame", padding=14)
        c3.pack(fill="x", pady=(0, 10))

        c3_head = ttk.Frame(c3)
        c3_head.pack(fill="x", pady=(0, 6))
        ttk.Label(c3_head, text="3. นำวิดีโอกลับมา & โพสต์ไปที่ Facebook Profile", font=(self.F, 12, "bold")).pack(side="left")
        ttk.Label(c3_head, text="นำเข้าคลิปวิดีโอจาก Flow และโพสต์ไปที่ Facebook Profile", foreground=MUTED,
                  font=(self.F, 10)).pack(side="left", padx=8)

        v_actions = ttk.Frame(c3)
        v_actions.pack(fill="x", pady=(2, 8))
        ttk.Button(v_actions, text="📂 เลือกไฟล์วิดีโอจาก Flow (.mp4)", command=self._choose_fb_video).pack(side="left", padx=(0, 8))
        ttk.Button(v_actions, text="⚡ ค้นหาวิดีโอล่าสุดจาก Downloads", command=self._find_latest_fb_video).pack(side="left")

        # Video banner
        self.fb_vid_banner = tk.Frame(c3, bg="#F5F3FA", bd=1, relief="solid")
        self.fb_vid_banner.pack(fill="x", pady=(4, 10))
        v_inner = ttk.Frame(self.fb_vid_banner, padding=10)
        v_inner.pack(fill="x")
        self.lbl_fb_video_status = ttk.Label(v_inner, text="ยังไม่ได้เลือกไฟล์วิดีโอ (กดเลือกไฟล์ด้านบน)", font=(self.F, 10))
        self.lbl_fb_video_status.pack(side="left", fill="x", expand=True)
        self.btn_fb_play_vid = ttk.Button(v_inner, text="▶ เล่นวิดีโอ", state="disabled", command=self._play_fb_video)
        self.btn_fb_play_vid.pack(side="right")

        # Automation Worker Sub-card
        w_card = tk.Frame(c3, bg="#F0EBFF", bd=1, relief="solid")
        w_card.pack(fill="x", pady=(6, 10))
        w_inner = ttk.Frame(w_card, padding=12)
        w_inner.pack(fill="x")

        w_header = ttk.Frame(w_inner)
        w_header.pack(fill="x", pady=(0, 6))
        ttk.Label(w_header, text="🤖 พนักงานโพสต์ Facebook อัตโนมัติ (Browser RPA Worker)",
                  font=(self.F, 11, "bold"), foreground=ACCENT_D).pack(side="left")
        ttk.Label(w_header, text="ควบคุมเบราว์เซอร์ อัปโหลดคลิป พิมพ์แคปชั่น @ผู้ติดตาม และกดโพสต์ให้เอง 100%",
                  font=(self.F, 9), foreground=MUTED).pack(side="left", padx=8)

        # Worker controls row
        w_row = ttk.Frame(w_inner)
        w_row.pack(fill="x", pady=(4, 6))

        self.btn_fb_worker_run = tk.Button(
            w_row,
            text="🚀 สั่งพนักงานโพสต์ Facebook ทันที (Auto-Post)",
            font=(self.F, 10, "bold"),
            bg=ACCENT,
            fg="#FFFFFF",
            activebackground=ACCENT_D,
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self._run_fb_browser_worker
        )
        self.btn_fb_worker_run.pack(side="left", padx=(0, 10))

        self.fb_worker_auto_pub = tk.BooleanVar(value=True)
        ttk.Checkbutton(w_row, text="กดยืนยันเผยแพร่อัตโนมัติ (ถ้าไม่ติ๊ก จะเปิดค้างไว้ให้ตรวจทาน)",
                        variable=self.fb_worker_auto_pub).pack(side="left", padx=(0, 10))

        ttk.Button(w_row, text="🔑 เข้าสู่ระบบ Facebook (ทำครั้งเดียว)",
                   command=self._open_fb_worker_login).pack(side="right")

        # Worker status label
        self.lbl_fb_worker_status = ttk.Label(
            w_inner,
            text="สถานะพนักงาน: พร้อมทำงาน (เลือกสินค้าและวิดีโอด้านบน แล้วกด 'สั่งพนักงานโพสต์ Facebook ทันที')",
            font=(self.F, 9),
            foreground=MUTED
        )
        self.lbl_fb_worker_status.pack(anchor="w", pady=(2, 0))

        # Fallback manual actions
        pub_actions = ttk.Frame(c3)
        pub_actions.pack(fill="x", pady=(4, 0))
        ttk.Label(pub_actions, text="ทางเลือกอื่น:", foreground=MUTED, font=(self.F, 9)).pack(side="left", padx=(0, 6))
        self.btn_fb_publish = ttk.Button(pub_actions, text="📘 เปิด Facebook โพสต์ด้วยตนเอง",
                                         command=self._publish_to_fb_profile)
        self.btn_fb_publish.pack(side="left", padx=(0, 10))
        self.btn_fb_mark_posted = ttk.Button(pub_actions, text="✅ บันทึกว่าโพสต์สำเร็จแล้ว", command=self._mark_fb_posted)
        self.btn_fb_mark_posted.pack(side="left")

        # Initialize data
        self.fb_raw_prods = []
        self.fb_prods = []
        self.fb_selected_prod = None
        self.fb_video_path = None
        self._fb_thumb_img = None
        self._refresh_fb_products()

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
            self.fb_p_price.configure(text=f"{price_txt} (ปกติ {orig_txt})")
        else:
            self.fb_p_price.configure(text=price_txt)

        shop_info = f"🏪 ร้าน: {prod.get('seller_name') or 'Shopee Seller'}  |  ⭐ {prod['rating']:.1f}  |  ขายแล้ว {prod['sold_count']:,} ชิ้น"
        self.fb_p_shop.configure(text=shop_info)
        self.btn_fb_open_shopee.configure(state="normal" if prod.get("product_url") else "disabled")

        # Load thumbnail in background thread
        self._load_fb_thumbnail(prod.get("image_url"), prod["id"])

        # Update prompt & caption
        self._update_fb_prompt()
        self._update_fb_caption()

    def _load_fb_thumbnail(self, image_url, product_id):
        from . import facebook_profile_flow as fb_flow
        self.fb_thumb_lbl.configure(image="", text="[กำลังโหลด...]", bg="#F0EBFF")

        def work():
            local_path = fb_flow.download_image_cache(image_url, product_id)
            if local_path and local_path.is_file():
                try:
                    im = Image.open(local_path).convert("RGB")
                    im = im.resize((110, 110), Image.Resampling.LANCZOS)
                    tk_img = ImageTk.PhotoImage(im)
                    self.after(0, lambda: self._apply_fb_thumbnail(tk_img, product_id))
                    return
                except Exception:
                    pass
            self.after(0, lambda: self.fb_thumb_lbl.configure(image="", text="[ไม่มีรูป]", bg="#F0EBFF"))

        threading.Thread(target=work, daemon=True).start()

    def _apply_fb_thumbnail(self, tk_img, target_id):
        if self.fb_selected_prod and self.fb_selected_prod.get("id") == target_id:
            self._fb_thumb_img = tk_img
            self.fb_thumb_lbl.configure(image=self._fb_thumb_img, text="", bg="#FFFFFF")

    def _open_selected_shopee(self):
        if self.fb_selected_prod and self.fb_selected_prod.get("product_url"):
            open_path(self.fb_selected_prod["product_url"])

    def _set_fb_duration(self, seconds):
        self.fb_dur_val.set(seconds)
        for s, btn in self.fb_dur_btns.items():
            if s == seconds:
                btn.configure(bg=ACCENT, fg="#FFFFFF", font=(self.F, 9, "bold"))
            else:
                btn.configure(bg="#FFFFFF", fg="#5A5174", font=(self.F, 9, "normal"))
        self._update_fb_prompt()

    def _update_fb_prompt(self):
        if not self.fb_selected_prod:
            return
        from . import facebook_profile_flow as fb_flow
        dur = self.fb_dur_val.get()
        style_key = self.fb_style_map.get(self.fb_style_cb.get(), "presenter")
        prompt = fb_flow.generate_flow_prompt(self.fb_selected_prod, dur, style_key)
        self.txt_fb_prompt.delete("1.0", "end")
        self.txt_fb_prompt.insert("1.0", prompt)

    def _update_fb_caption(self):
        if not self.fb_selected_prod:
            return
        from . import facebook_profile_flow as fb_flow
        caption = fb_flow.generate_facebook_caption(self.fb_selected_prod)
        self.txt_fb_caption.delete("1.0", "end")
        self.txt_fb_caption.insert("1.0", caption)

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
            self.lbl_fb_video_status.configure(
                text=f"📹 ไฟล์: {self.fb_video_path.name}  |  ขนาด: {size_mb:.1f} MB  |  พร้อมโพสต์",
                foreground=GOOD
            )
            self.btn_fb_play_vid.configure(state="normal")
            self.say(f"เลือกวิดีโอ: {self.fb_video_path.name}", "good")
        else:
            self.lbl_fb_video_status.configure(text="ไฟล์ไม่ถูกต้องหรือไม่พบไฟล์", foreground=BAD)
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
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    app = StudioApp()
    app.mainloop()


if __name__ == "__main__":
    main()
