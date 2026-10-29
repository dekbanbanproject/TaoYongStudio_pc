"""Product clip planner: turns NextsellerAI products into attention-grabbing clip ideas for affiliate baskets.

Reads nextseller/data/products.csv (+ product_scores.csv / angles.json) written by nextseller/*. Read-only.
Writes plans/product_ideas.json (shown in the planner tab) and one Flow prompt per idea in plans/product_prompts/.
Nothing is posted and no credits are spent here: the prompt is copied to Google Flow by the owner.
"""
import csv
import json
import re
from datetime import datetime
from pathlib import Path

from .config import ROOT

DATA = ROOT / "nextseller" / "data"
PLANS = ROOT / "plans"

# Content rules (same as the TaoYongStudio plan): never claim real use, no health/medical claims,
# fictional adult presenter, fully clothed, product must look like the listed product.
RULES_EN = ("The presenter is a fictional AI character, not a real person or celebrity; adult, tasteful, fully "
            "clothed, non-suggestive. Do not claim the product was personally tested. No medical or health claims. "
            "Show the product accurately as described. No text artifacts, no watermarks.")

PRESENTER = ("a fictional Thai woman presenter in her mid-20s, glamorous and attractive, confident charming smile, "
             "sleek styled hair, natural glowing makeup, chic fashionable fully-clothed outfit")

# 5 starting styles. hook = what happens in the first 2 seconds; beats = the 8 second structure.
STYLES = {
    "presenter": {
        "genre": "สินค้า · พรีเซนเตอร์ถือสินค้า",
        "hook": "ยิ้มสบตาแล้วชูสินค้าใกล้กล้อง",
        "beats": "ทัก → ชูสินค้าให้เห็นชัด → ชี้ลงไปที่ลิงก์",
        "scene": "{presenter}, speaking directly to camera in a bright modern studio or cafe, holds {product} up close "
                 "to the camera, smiles, then points down toward the link below the post",
        "line": "ของดีต้องบอกต่อค่ะ {short} กดลิงก์ดูราคาได้เลยนะคะ",
        "camera": "smooth slow dolly-in, eye level",
    },
    "problem": {
        "genre": "สินค้า · ปัญหา→ทางออก",
        "hook": "ภาพปัญหาที่คนเห็นแล้วนึกถึงตัวเอง ใน 2 วินาที",
        "beats": "เจอปัญหา → สินค้าเข้ามาแก้ → ชี้ลิงก์",
        "scene": "{presenter}, in a home setting, first looks frustrated by a small everyday problem related to "
                 "{product} (clutter, mess, inconvenience; no health issues), then picks up {product}, smiles in relief, "
                 "and points down toward the link",
        "line": "เจอปัญหานี้บ่อยไหมคะ ลอง {short} ดูนะคะ กดลิงก์ได้เลย",
        "camera": "handheld feel, quick push-in on the problem then on the product",
    },
    "unboxing": {
        "genre": "สินค้า · แกะกล่อง",
        "hook": "มือแกะกล่อง เสียงกรอบแกรบ",
        "beats": "แกะกล่อง → โชว์ตัวสินค้า → ชี้ลิงก์ (ไม่อ้างว่าใช้จริง)",
        "scene": "close-up of {presenter}'s hands opening a parcel on a clean table, revealing {product}; then she "
                 "holds it up to the camera and smiles, pointing down toward the link; crisp unboxing sound",
        "line": "แกะกล่องมาให้ดูกันค่ะ นี่คือ {short} สนใจกดลิงก์เลยนะคะ",
        "camera": "top-down then eye-level, macro detail on the product",
    },
    "asmr": {
        "genre": "สินค้า · ASMR",
        "hook": "ภาพใกล้สินค้า + เสียงเฉพาะตัว",
        "beats": "ภาพใกล้ + เสียง → โชว์รายละเอียด → ลิงก์",
        "scene": "extreme close-up macro shots of {product}, soft satisfying sounds of the product (tapping, clicking, "
                 "opening), gentle lighting; at the end {presenter} appears briefly and points down toward the link",
        "line": "{short} ฟังเสียงแล้วชอบไหมคะ กดลิงก์ดูได้เลย",
        "camera": "slow macro slides, shallow depth of field",
    },
    "cartoon": {
        "genre": "สินค้า · การ์ตูน/3D",
        "hook": "ตัวละครการ์ตูนน่ารักทักก่อน",
        "beats": "ตัวละครทัก → ใช้/ชูสินค้า → ชี้ลิงก์",
        "scene": "stylized 3D animation, soft lighting, a Pixar-like cute animated character (not a real person) in a "
                 "bright room, waves, then holds {product} up and points down toward the link with an animated arrow",
        "speaker": "the animated character",
        "line": "ดูนี่สิ {short} น่ารักมากเลย กดลิงก์ดูได้เลยนะ",
        "camera": "gentle orbit around the character",
    },
}
STYLE_ORDER = list(STYLES)

EXCLUDE_CATEGORIES = {"Health"}
EXCLUDE_WORDS = ("ซิม", "เติมเงิน", "บัตรเติม", "อาหารเสริม", "ลดน้ำหนัก", "ยารักษา", "วิตามิน", "สมุนไพร",
                 "ผลิตภัณฑ์เสริมอาหาร", "คอลลาเจน", "ถุงยาง", "เจลหล่อลื่น", "น้องชาย", "จุดซ่อนเร้น", "ผู้ใหญ่",
                 # skin-treatment / body claims: the clip would have to promise results
                 "เซรั่ม", "สิว", "รูขุมขน", "ฝ้า", "กระ ", "ริ้วรอย", "ผิวกระจ่าง", "ไวท์เทนนิ่ง", "ระงับกลิ่น",
                 "Cica", "Serum", "Acne", "Whitening", "Deodorant", "barrier", "Barrier", "Derma", "ผิวแพ้ง่าย", "ผื่น", "รังแค")
# angles that promise a measurable result are never fed to the video prompt (illustration only)
RESULT_ANGLE_WORDS = ("ก่อน", "หลัง", "พิสูจน์", "ทดสอบ", "Before", "After", "หายไป", "ผลลัพธ์", "จริง", "ติดทน", "ทนนาน")


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _read(name):
    p = DATA / name
    if not p.is_file():
        raise FileNotFoundError("ไม่พบ %s — รัน nextseller\\pull_nextseller_products.ps1 ก่อน" % p)
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_products(min_price=50.0, min_score=0, limit=None):
    """NextsellerAI products that pass the content rules, best first (score, then price band)."""
    prods = _read("products.csv")
    scores = {r["product_id"]: r for r in _read("product_scores.csv")} if (DATA / "product_scores.csv").is_file() else {}
    out = []
    for p in prods:
        price = _num(p.get("sale_price")) or _num(p.get("original_price"))
        sc = scores.get(p["id"], {})
        if p.get("category") in EXCLUDE_CATEGORIES or (price or 0) < min_price:
            continue
        if any(w in p.get("name", "") for w in EXCLUDE_WORDS):
            continue
        if (sc.get("decision") or "").upper() == "SKIP":
            continue
        score = _num(sc.get("score"))
        if min_score and (score or 0) < min_score:
            continue
        try:
            angles = json.loads(sc.get("suggested_angles") or "[]")
            risks = json.loads(sc.get("risks") or "[]")
        except json.JSONDecodeError:
            angles, risks = [], []
        out.append({"id": p["id"], "name": p["name"], "category": p.get("category", ""), "price": price,
                    "score": score, "angles": angles, "risks": risks, "image_url": p.get("image_url", ""),
                    "external_id": p.get("external_id", "")})
    # scored products first, then a sweet spot price band (100-1500 baht sells and photographs well)
    out.sort(key=lambda x: (x["score"] is None, -(x["score"] or 0), abs((x["price"] or 0) - 400)))
    return out[:limit] if limit else out


def short_name(name, n=34):
    """Shorten a listing title without cutting a word in half (for spoken lines and titles)."""
    name = re.sub(r"[\[\]【】()（）*!]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    if len(name) <= n:
        return name
    cut = name[:n]
    if name[n] != " " and " " in cut:  # we are mid-word: back off to the previous space
        cut = cut[:cut.rindex(" ")]
    return cut.rstrip(" -–—:,.")


def assign_styles(products, styles=None):
    """Round-robin styles so no style repeats within 3 clips in a row."""
    styles = styles or STYLE_ORDER
    out, last = [], []
    for i, p in enumerate(products):
        for k in range(len(styles)):
            s = styles[(i + k) % len(styles)]
            if s not in last[-2:]:
                break
        last.append(s)
        out.append((p, s))
    return out


def flow_prompt(product, style):
    st = STYLES[style]
    prod = "the product (%s, listed on Shopee)" % short_name(product["name"], 60)
    scene = st["scene"].format(presenter=PRESENTER, product=prod)
    line = st["line"].format(short=short_name(product["name"], 22))
    safe = [a for a in product.get("angles", []) if not any(w in a for w in RESULT_ANGLE_WORDS)]
    angle = safe[0] if safe else ""
    extra = (" Idea from the product analysis (show it as an illustration, never as a real test result): %s." % angle
             ) if angle else ""
    cartoon = style == "cartoon"
    look = "stylized 3D animated" if cartoon else "photorealistic"
    rules = RULES_EN.replace("The presenter is a fictional AI character, not a real person or celebrity; adult, tasteful, "
                             "fully clothed, non-suggestive.", "The character is fictional and animated; family-friendly."
                             if cartoon else "The presenter is a fictional AI character, not a real person or celebrity; "
                             "adult, tasteful, fully clothed, non-suggestive.")
    return ("Vertical 9:16 video, 8 seconds, %s social-media product video. Scene: %s.%s "
            "Hook in the first 2 seconds: %s. Bright, friendly mood. %s "
            "Audio: %s speaks Thai with natural lip-sync, saying: \"%s\"; light upbeat background music. "
            "Camera: %s." % (look, scene, extra, st["hook"], rules, st.get("speaker", "the presenter"), line, st["camera"]))


def build_ideas(count=20, styles=None, min_price=50.0, min_score=0):
    prods = load_products(min_price=min_price, min_score=min_score, limit=count)
    items, pdir = [], PLANS / "product_prompts"
    pdir.mkdir(parents=True, exist_ok=True)
    for n, (p, style) in enumerate(assign_styles(prods, styles), 1):
        st = STYLES[style]
        iid = "p%03d-%s" % (n, style)
        risk = "; ".join(p["risks"][:2])
        items.append({"id": iid, "genre": st["genre"],
                      "title": "%s — %s" % (short_name(p["name"], 48), st["hook"]),
                      "why": "โครง 8 วินาที: %s%s" % (st["beats"], (" | ระวัง: " + risk) if risk else ""),
                      "suggested_length": "8 วินาที", "product": {k: p[k] for k in ("id", "name", "category", "price", "score", "image_url")},
                      "style": style, "prompt_file": "product_prompts/%s.txt" % iid})
        (pdir / (iid + ".txt")).write_text(flow_prompt(p, style), encoding="utf-8")
    doc = {"updated": datetime.now().isoformat(timespec="seconds"),
           "note": "ไอเดียคลิปสินค้าจาก NextsellerAI (ตัดหมวดสุขภาพ ราคาต่ำกว่า %d บาท และสินค้าที่ SKIP)" % min_price,
           "ideas": items}
    PLANS.mkdir(exist_ok=True)
    (PLANS / "product_ideas.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return items


def read_prompt(idea):
    rel = idea.get("prompt_file")
    p = PLANS / rel if rel else None
    return p.read_text(encoding="utf-8") if p and p.is_file() else ""
