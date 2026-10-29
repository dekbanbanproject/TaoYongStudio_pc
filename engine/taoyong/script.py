"""Load and validate episode scripts (JSON written by the analyst / script-writer)."""
import json
import re
from pathlib import Path

from .art import BACKGROUNDS, COLORS, ITEM_KINDS, SPECIES

ACTIONS = ["talk", "wave", "jump", "cheer", "point", "happy", "dance", "none", "swimming", "walk", "run"]
BG_ALIASES = {"park": "meadow", "ทุ่งหญ้า": "meadow", "ทะเล": "beach", "ชายหาด": "beach", "กลางคืน": "night",
              "room": "bedroom", "ห้องนอน": "bedroom", "school": "classroom", "ห้องเรียน": "classroom"}


def slugify(s):
    s = re.sub(r"[^0-9A-Za-z฀-๿_-]+", "-", str(s)).strip("-")
    return s[:60] or "episode"


def load(path):
    path = Path(path)
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    data.setdefault("id", slugify(path.stem))
    return data


def validate(sc):
    """Return (errors, warnings). Errors stop rendering; warnings do not."""
    err, warn = [], []
    if not isinstance(sc, dict):
        return ["script must be a JSON object"], []
    if not str(sc.get("title", "")).strip():
        err.append("missing 'title'")
    elif len(sc["title"]) > 95:
        warn.append("title longer than 95 characters (YouTube limit 100)")
    chars = sc.get("characters") or []
    if not chars:
        err.append("missing 'characters' (list, e.g. [\"bunny\", \"bear\"])")
    for c in chars:
        if c not in SPECIES:
            err.append("unknown character '%s' (choose from %s)" % (c, ", ".join(SPECIES)))
    if len(chars) > 4:
        err.append("at most 4 characters")
    scenes = sc.get("scenes") or []
    if not scenes:
        err.append("missing 'scenes'")
    total_chars = 0
    for i, s in enumerate(scenes, 1):
        where = "scene %d" % i
        bg = BG_ALIASES.get(s.get("background", "meadow"), s.get("background", "meadow"))
        if bg not in BACKGROUNDS:
            err.append("%s: unknown background '%s' (choose from %s)" % (where, bg, ", ".join(BACKGROUNDS)))
        cast = s.get("cast", chars)
        for c in cast:
            if c not in chars:
                err.append("%s: cast member '%s' is not in 'characters'" % (where, c))
        beats = s.get("beats") or []
        if not beats:
            err.append("%s: no 'beats'" % where)
        for j, b in enumerate(beats, 1):
            w = "%s beat %d" % (where, j)
            text = b.get("say", b.get("text", ""))
            if not text and "pause" not in b:
                err.append("%s: needs 'say' (text) or 'pause' (seconds)" % w)
            if text:
                total_chars += len(text)
                if len(text) > 120:
                    warn.append("%s: line is long (%d chars) - split it for kids" % (w, len(text)))
                who = b.get("who", "narrator")
                if who != "narrator" and who not in cast:
                    err.append("%s: speaker '%s' is not on stage in this scene" % (w, who))
            for key in ("action", "react"):
                if key in b and b[key] not in ACTIONS:
                    err.append("%s: unknown %s '%s' (choose from %s)" % (w, key, b[key], ", ".join(ACTIONS)))
            it = b.get("items")
            if it:
                if it.get("kind") not in ITEM_KINDS:
                    err.append("%s: unknown item kind '%s' (choose from %s)" % (w, it.get("kind"), ", ".join(ITEM_KINDS)))
                n = it.get("count", 1)
                if not isinstance(n, int) or n < 0 or n > 10:
                    err.append("%s: items.count must be 0-10" % w)
                c = it.get("color")
                if c and not (str(c).startswith("#") or str(c).lower() in COLORS or c in COLORS):
                    warn.append("%s: unknown colour '%s', default used" % (w, c))
            card = b.get("card")
            if card and len(str(card)) > 40:
                warn.append("%s: card text is long; keep it to a word or number" % w)
    fm = sc.get("formats")
    if fm is not None and (not isinstance(fm, list) or any(f not in ("vertical", "horizontal") for f in fm)):
        err.append("'formats' must be a list of 'vertical' / 'horizontal'")
    est = total_chars * 0.085 + 6
    if est > 11 * 60:
        err.append("estimated length %.0f min - too long for one episode (max ~11 min); use a compilation" % (est / 60))
    elif est > 180 and "horizontal" not in (fm or ["vertical", "horizontal"]):
        warn.append("estimated length %.0fs - vertical Shorts must be under 3 minutes" % est)
    return err, warn
