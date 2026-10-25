"""Facebook Profile + Shopee Product Video Studio with Google Flow integration.

Allows selecting Shopee products, generating Flow video prompts for 8/10/12/15 seconds,
copying / sending prompts and images to Flow, importing generated videos, and publishing
to Facebook Profile with caption, hashtags, and @ผู้ติดตาม.
"""
import csv
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import threading
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from .config import ROOT

# Directories
DATA_DIR = ROOT / "nextseller" / "data"
PLANS_DIR = ROOT / "plans"
STAGING_DIR = ROOT / "plans" / "flow_staging"
POSTS_LOG_FILE = ROOT / "plans" / "facebook_profile_posts.json"
CACHE_DIR = ROOT / "cache" / "shopee_images"

# Ensure directories exist
STAGING_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Content and Presenter Rules
RULES_EN = (
    "The presenter is a fictional AI character, not a real person or celebrity; adult, tasteful, "
    "fully clothed, non-suggestive. Do not claim the product was personally tested. No medical or health claims. "
    "Show the product accurately as described. Crisp studio lighting, 4K resolution, 9:16 vertical ratio, "
    "no text artifacts, no watermarks."
)

PRESENTER = (
    "a charming, fashionable Thai female creator in her mid-20s, warm genuine smile, stylish hairstyle, "
    "natural makeup, chic tasteful outfit"
)

# 5 Video styles for Shopee products
STYLES = {
    "presenter": {
        "label": "พรีเซนเตอร์ถือสินค้า (Presenter)",
        "hook": "ยิ้มทักทายกล้องอย่างเป็นกันเอง พร้อมชูสินค้าให้เห็นโลโก้และแพ็กเกจชัดเจนใน 2 วินาทีแรก",
        "beats_8": "ทักทายสดใส (0-2s) → ชูสินค้าให้เห็นจุดเด่นชัดๆ (2-6s) → ยิ้มและชี้ลงด้านล่างไปที่ลิงก์พิกัด (6-8s)",
        "beats_10": "เปิดคลิปด้วยรอยยิ้มชวนคุย (0-2s) → ถือสินค้าหมุนโชว์และพูดถึงความคุ้มค่า (2-7s) → ชี้ลงไปที่ลิงก์พิกัดสั่งซื้อ (7-10s)",
        "beats_12": "ทักทายคนดูด้วยความตื่นเต้น (0-3s) → โชว์สินค้าและบอกเหตุผลที่ต้องมีติดตัว (3-9s) → เชิญชวนกดลิงก์สั่งซื้อด้านล่าง (9-12s)",
        "beats_15": "เปิดตัวอย่างน่าสนใจ (0-3s) → สาธิตการถือและจุดเด่นของสินค้าอย่างละเอียด (3-11s) → ตอกย้ำความคุ้มและชี้ไปที่ลิงก์ (11-15s)",
        "scene": "{presenter}, in a bright modern aesthetic studio, holds up {product} close to the lens, smiling enthusiastically, highlighting key details, then points down toward the purchase link below",
        "camera": "smooth slow dolly-in, crisp eye-level focus on presenter and product",
    },
    "problem": {
        "label": "ปัญหา → ทางออก (Problem-Solution)",
        "hook": "แสดงสีหน้าหงุดหงิดกับปัญหาในชีวิตประจำวันที่ทุกคนคุ้นเคย ก่อนพบทางออกใน 2 วินาที",
        "beats_8": "เจอปัญหา (0-2s) → หยิบสินค้าขึ้นมาแก้ปัญหาได้ทันที (2-6s) → ยิ้มโล่งใจและชี้ลิงก์ (6-8s)",
        "beats_10": "เผชิญปัญหาเดิมๆ (0-2s) → หยิบสินค้าขึ้นมาใช้งานได้สะดวกสบาย (2-7s) → แนะนำให้กดซื้อที่ลิงก์ (7-10s)",
        "beats_12": "จำลองสถานการณ์ที่สร้างความยุ่งยาก (0-3s) → สินค้าเข้ามาช่วยจัดการอย่างง่ายดาย (3-9s) → บอกพิกัดลิงก์สั่งซื้อ (9-12s)",
        "beats_15": "เริ่มจากปัญหาที่กวนใจ (0-3s) → แนะนำสินค้าเป็นตัวช่วยกู้วิกฤต (3-11s) → สรุปความประทับใจและชวนกดสั่งซื้อ (11-15s)",
        "scene": "{presenter}, in a realistic cozy setting, first looks relatable and troubled by a small everyday hassle, then introduces {product}, beaming with relief as it solves the difficulty, pointing toward the link below",
        "camera": "quick handheld dynamic punch-in on problem, transitioning into clean stable focus on the solution",
    },
    "unboxing": {
        "label": "แกะกล่องสินค้า (Unboxing)",
        "hook": "มือแกะกล่องพัสดุ เสียงเปิดกล่องชัดเจน โชว์ของใหม่แกะกล่องใน 2 วินาที",
        "beats_8": "แกะกล่องเปิดพัสดุ (0-2s) → หยิบสินค้าขึ้นมาโชว์สัมผัสแรก (2-6s) → ชี้ลิงก์พิกัดราคาดี (6-8s)",
        "beats_10": "เปิดกล่องลุ้นของด้านใน (0-2s) → สัมผัสและโชว์รายละเอียดสินค้าใหม่ (2-7s) → แนะนำให้กดดูราคาที่ลิงก์ (7-10s)",
        "beats_12": "แกะเทปเปิดกล่องพัสดุ (0-3s) → หยิบสินค้าออกมาตรวจเช็กความสวยงาม (3-9s) → ชี้ลงไปที่ลิงก์สั่งซื้อ (9-12s)",
        "beats_15": "แกะกล่องพร้อมเสียง ASMR (0-3s) → นำสินค้าออกมาโชว์ทุกมุมมองอย่างประณีต (3-11s) → ชวนกดสั่งพิกัดที่ลิงก์ด้านล่าง (11-15s)",
        "scene": "hands opening a neat Shopee delivery parcel on a pristine table, revealing {product}; then {presenter} lifts it toward the camera with an admiring smile, gesturing downward to the link",
        "camera": "overhead flat-lay view tilting down to a sharp macro close-up of the product",
    },
    "asmr": {
        "label": "เสียงและภาพใกล้ (ASMR Macro)",
        "hook": "ภาพโคลสอัปใกล้ชิด พร้อมเสียงสัมผัสพื้นผิวของสินค้าที่มีเอกลักษณ์ใน 2 วินาที",
        "beats_8": "โคลสอัปผิวสัมผัสและเสียง (0-2s) → หมุนโชว์ความประณีตของสินค้า (2-6s) → แนะนำลิงก์สั่งซื้อ (6-8s)",
        "beats_10": "ซูมใกล้โชว์วัสดุและเสียงกรุ๊งกริ๊ง (0-2s) → หมุนสินค้าสะท้อนแสงไฟสตูดิโอ (2-7s) → ชี้ลิงก์พิกัด (7-10s)",
        "beats_12": "ภาพมาโครเน้นดีเทลสุดพรีเมียม (0-3s) → แสดงฟังก์ชันและการใช้งานใกล้ๆ (3-9s) → บอกพิกัดลิงก์ด้านล่าง (9-12s)",
        "beats_15": "สัมผัสเสียงและภาพมาโครอย่างเพลิดเพลิน (0-3s) → โชว์ความคุ้มค่าและคุณภาพวัสดุ (3-11s) → ยิ้มและชี้ไปที่ลิงก์ (11-15s)",
        "scene": "ultra macro detailed shots of {product}, highlighting rich texture, sleek build, and satisfying tactile qualities; {presenter} appears gracefully at the finale pointing down to the link",
        "camera": "gentle slow-motion slider pan, cinematic shallow depth of field with soft bokeh",
    },
    "cartoon": {
        "label": "การ์ตูน 3D สดใส (3D Cartoon)",
        "hook": "ตัวการ์ตูน 3D แอนิเมชันน่ารักโบกมือทักทาย ดึงดูดสายตาทันทีใน 2 วินาทีแรก",
        "beats_8": "ตัวการ์ตูนกระโดดทักทาย (0-2s) → ชูสินค้าขึ้นมาพร้อมประกายวิ้งๆ (2-6s) → ชี้ลูกศรลงไปที่ลิงก์ (6-8s)",
        "beats_10": "ตัวการ์ตูน 3D โบกมือสดใส (0-2s) → อุ้มสินค้าและเต้นอย่างมีความสุข (2-7s) → ชี้ชวนกดลิงก์สั่งซื้อ (7-10s)",
        "beats_12": "ตัวการ์ตูนน่ารักวิ่งเข้ามาทัก (0-3s) → สาธิตการใช้สินค้าแบบการ์ตูนมีชีวิตชีวา (3-9s) → ชี้พิกัดโปรโมชั่น (9-12s)",
        "beats_15": "แอนิเมชัน 3D สุดน่ารักเปิดเรื่อง (0-3s) → โชว์ความเจ๋งของสินค้าพร้อมเอฟเฟกต์สดใส (3-11s) → ชวนกดลิงก์สั่งซื้อทันที (11-15s)",
        "scene": "high quality 3D stylized animated character in a vibrant Pixar-like pastel room, happily displaying {product} with magical sparkles, pointing down toward the link with an animated glowing arrow",
        "camera": "playful sweeping camera orbit around the 3D character and product",
    },
}

SPEECH_LINES = {
    8: {
        "presenter": "ของดีต้องบอกต่อค่ะ {short_name} จิ้มลิงก์ดูราคาได้เลยนะคะ",
        "problem": "เจอปัญหานี้บ่อยไหมคะ ลอง {short_name} ดูนะคะ กดลิงก์เลย",
        "unboxing": "แกะกล่องมาแล้วค่ะ {short_name} สวยคุ้มมาก กดลิงก์เลยนะคะ",
        "asmr": "{short_name} งานดีสัมผัสโดนใจ จิ้มลิงก์ดูได้เลยค่ะ",
        "cartoon": "ดูนี่สิคะ {short_name} น่ารักน่าใช้มาก กดลิงก์เลยน้า",
    },
    10: {
        "presenter": "ใครหาตัวนี้อยู่ แนะนำเลยค่ะ {short_name} คุ้มราคามาก จิ้มลิงก์ด้านล่างได้เลยนะคะ",
        "problem": "หมดกังวลเรื่องนี้ได้เลยค่ะ ใช้ {short_name} ชีวิตง่ายขึ้นเยอะ กดลิงก์พิกัดเลยค่ะ",
        "unboxing": "แกะกล่องของจริงให้ดู {short_name} ดีงามเกินราคา สนใจจิ้มลิงก์ด้านล่างได้เลยค่ะ",
        "asmr": "สัมผัสความฟินกับ {short_name} คุณภาพพรีเมียม กดดูรายละเอียดที่ลิงก์ได้เลยค่ะ",
        "cartoon": "ว้าวสุดๆ ไปเลย {short_name} ของแท้แน่นอน กดจิ้มลิงก์ดูราคาพิเศษได้เลยนะ",
    },
    12: {
        "presenter": "เจอของดีแบบนี้ต้องรีบบอกต่อค่ะ {short_name} คุณภาพดีมาก พิกัดอยู่ที่ลิงก์ด้านล่างนะคะ",
        "problem": "ถ้าคุณเจอปัญหานี้อยู่บ่อยๆ ต้องลอง {short_name} ช่วยได้จริง จิ้มลิงก์ด้านล่างดูโปรได้เลยค่ะ",
        "unboxing": "เปิดกล่องแกะให้ดูกันชัดๆ {short_name} สวยตรงปกมาก สนใจกดลิงก์ดูพิกัดได้เลยจ้า",
        "asmr": "ฟังเสียงแล้วชอบไหมคะ {short_name} วัสดุดีเนียนกริบ จิ้มลิงก์ด้านล่างไปช้อปกันได้เลยค่ะ",
        "cartoon": "เพื่อนๆ ดูนี่เร็ว {short_name} ใช้ง่ายและดีจริงๆ ไปกดดูราคาในลิงก์ด้านล่างได้เลยนะ",
    },
    15: {
        "presenter": "ไอเทมเด็ดที่ทุกคนต้องมีติดบ้าน {short_name} คุ้มค่าและตอบโจทย์สุดๆ กดสั่งซื้อที่ลิงก์ด้านล่างได้เลยนะคะ",
        "problem": "ไม่ต้องทนกับความยุ่งยากอีกต่อไปค่ะ แค่มี {short_name} จัดการได้ครบจบในตัว จิ้มลิงก์สั่งซื้อได้เลยค่ะ",
        "unboxing": "แกะกล่องพัสดุรีวิวกันแบบจัดเต็ม {short_name} ตัวจริงสวยถูกใจมาก พิกัดสั่งซื้ออยู่ในลิงก์ด้านล่างนะคะ",
        "asmr": "ความประณีตระดับพรีเมียมของ {short_name} ที่คุณต้องลองสัมผัส สนใจพิกัดช้อปปิ้งจิ้มลิงก์ด้านล่างได้เลยค่ะ",
        "cartoon": "ของดีและคุ้มค่าแบบนี้ {short_name} ต้องรีบมีกันแล้วนะ สั่งง่ายๆ แค่จิ้มลิงก์ด้านล่างเลยจ้า",
    },
}


def _short_title(name, max_len=36):
    """Clean and shorten product title without cutting mid-word."""
    name = re.sub(r"[\[\]【】()（）*!#]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    if len(name) <= max_len:
        return name
    cut = name[:max_len]
    if " " in cut:
        cut = cut[: cut.rindex(" ")]
    return cut.rstrip(" -–—:,.")


def load_shopee_products(min_price=0.0, search="", category=""):
    """Load products from nextseller/data/products.csv with optional filters."""
    csv_file = DATA_DIR / "products.csv"
    if not csv_file.is_file():
        # Fallback to NextsellerAI project location if KidsStudio has not pulled yet
        alt_file = Path(r"C:\Users\NBPK\Desktop\Work Speck\NextsellerAI\nextseller\data\products.csv")
        if alt_file.is_file():
            csv_file = alt_file

    if not csv_file.is_file():
        return []

    # Read scores if available
    scores_file = DATA_DIR / "product_scores.csv"
    scores = {}
    if scores_file.is_file():
        try:
            with scores_file.open(encoding="utf-8-sig", newline="") as f:
                for r in csv.DictReader(f):
                    scores[r["product_id"]] = r
        except Exception:
            scores = {}

    products = []
    search_lower = search.strip().lower()

    with csv_file.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("name", "").strip()
            cat = row.get("category", "").strip()
            if not name:
                continue

            # Price parsing
            try:
                sale_p = float(row.get("sale_price") or 0)
            except ValueError:
                sale_p = 0.0
            try:
                orig_p = float(row.get("original_price") or 0)
            except ValueError:
                orig_p = 0.0

            effective_price = sale_p if sale_p > 0 else orig_p
            if min_price > 0 and effective_price < min_price:
                continue

            if category and category != "ทุกหมวดหมู่" and cat != category:
                continue

            if search_lower and (search_lower not in name.lower() and search_lower not in cat.lower() and search_lower not in row.get("seller_name", "").lower()):
                continue

            sc = scores.get(row.get("id"), {})
            try:
                score_num = float(sc.get("score") or 0)
            except ValueError:
                score_num = 0.0

            try:
                sold = int(row.get("sold_count") or 0)
            except ValueError:
                sold = 0

            try:
                rating = float(row.get("rating") or 0.0)
            except ValueError:
                rating = 0.0

            products.append({
                "id": row.get("id", ""),
                "name": name,
                "short_name": _short_title(name),
                "category": cat,
                "seller_name": row.get("seller_name", ""),
                "sale_price": sale_p,
                "original_price": orig_p,
                "effective_price": effective_price,
                "rating": rating,
                "sold_count": sold,
                "product_url": row.get("product_url", ""),
                "affiliate_url": row.get("affiliate_url", "") or row.get("product_url", ""),
                "image_url": row.get("image_url", ""),
                "score": score_num,
                "decision": sc.get("decision", ""),
                "suggested_angles": sc.get("suggested_angles", ""),
            })

    # Sort: highest rating & sold first
    products.sort(key=lambda x: (x["rating"], x["sold_count"]), reverse=True)
    return products


def get_categories():
    """Extract unique categories from products.csv."""
    prods = load_shopee_products()
    cats = sorted({p["category"] for p in prods if p.get("category")})
    return ["ทุกหมวดหมู่"] + cats


def download_image_cache(image_url, product_id):
    """Download Shopee product image to local cache and return local Path or None."""
    if not image_url:
        return None
    ext = ".jpg"
    dest = CACHE_DIR / f"{product_id}{ext}"
    if dest.is_file() and dest.stat().st_size > 500:
        return dest

    try:
        req = urllib.request.Request(
            image_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://shopee.co.th/",
            },
        )
        with urllib.request.urlopen(req, timeout=12) as response, open(dest, "wb") as out_file:
            shutil.copyfileobj(response, out_file)
        return dest
    except Exception:
        return None


def generate_flow_prompt(product, duration_sec=8, style_key="presenter"):
    """Generate high-converting Flow video prompt for 8/10/12/15 seconds."""
    if duration_sec not in (8, 10, 12, 15):
        duration_sec = 8

    style = STYLES.get(style_key, STYLES["presenter"])
    short_title = _short_title(product.get("name", "สินค้า Shopee"), max_len=45)
    spoken_name = _short_title(product.get("name", "สินค้านี้"), max_len=24)

    prod_desc = f'"{short_title}" (Shopee product)'
    scene_text = style["scene"].format(presenter=PRESENTER, product=prod_desc)
    beats_text = style.get(f"beats_{duration_sec}", style["beats_8"])

    # Spoken Thai line
    speech_tpl = SPEECH_LINES.get(duration_sec, SPEECH_LINES[8]).get(style_key, SPEECH_LINES[8]["presenter"])
    spoken_line = speech_tpl.format(short_name=spoken_name)

    is_cartoon = style_key == "cartoon"
    visual_look = "vibrant 3D animation" if is_cartoon else "photorealistic cinematic commercial"
    rules_text = (
        RULES_EN.replace("The presenter is a fictional AI character, not a real person or celebrity; adult, tasteful, fully clothed, non-suggestive.",
                         "The character is a cute fictional 3D animated figure; wholesome and charming.")
        if is_cartoon else RULES_EN
    )

    prompt = (
        f"Vertical 9:16 video, exactly {duration_sec} seconds duration, {visual_look} for Shopee social affiliate.\n"
        f"Scene: {scene_text}.\n"
        f"Hook & Timeline ({duration_sec}s): {beats_text}.\n"
        f"Action & Energy: Bright, uplifting commercial atmosphere. Camera: {style['camera']}.\n"
        f"Audio: Presenter speaks Thai with natural fluid lip-sync: \"{spoken_line}\"; clean ambient acoustic music.\n"
        f"Compliance: {rules_text}"
    )
    return prompt.strip()


def generate_facebook_caption(product, style="reels"):
    """Prepare engaging Facebook Profile post caption with hook, @ผู้ติดตาม, and hashtags."""
    title = product.get("name", "").strip()
    sale_price = product.get("sale_price") or product.get("effective_price") or 0.0
    orig_price = product.get("original_price") or 0.0
    rating = product.get("rating") or 0.0
    sold = product.get("sold_count") or 0
    shop = product.get("seller_name") or ""
    affiliate_url = product.get("affiliate_url") or product.get("product_url") or "https://shopee.co.th"

    # Price string
    price_str = f"฿{sale_price:,.2f}".rstrip("0").rstrip(".") if sale_price > 0 else "ราคาพิเศษ"
    if orig_price > sale_price and sale_price > 0:
        orig_str = f" ฿{orig_price:,.2f}".rstrip("0").rstrip(".")
        discount_text = f"🔥 ลดพิเศษเหลือเพียง {price_str} (ปกติ {orig_str})"
    else:
        discount_text = f"🔥 ราคาเพียง {price_str}"

    rating_text = f"⭐ รีวิว {rating:.1f}/5.0 จากผู้ซื้อจริง" if rating > 0 else "⭐ สินค้าคุณภาพยอดนิยม"
    sold_text = f" | ยอดสั่งซื้อไปแล้วกว่า {sold:,} ชิ้น!" if sold > 0 else ""

    short_t = _short_title(title, max_len=60)

    caption = (
        f"✨ ป้ายยาของดีต้องมีติดตัว! {short_t}\n\n"
        f"{discount_text}\n"
        f"{rating_text}{sold_text}\n"
        f"{('🏪 ร้านค้า: ' + shop) if shop else ''}\n\n"
        f"ใครหาตัวนี้อยู่บอกเลยว่าคุ้มมากกก สวยตรงปก ใช้งานดีจริงค่ะ 🥰\n\n"
        f"👇 สนใจพิกัดสินค้าจิ้มลิงก์นี้ได้เลยนะคะ:\n"
        f"👉 {affiliate_url}\n\n"
        f"@ผู้ติดตาม ฝากกดไลก์ กดแชร์ เป็นกำลังใจให้ด้วยนะคะ ✨\n\n"
        f"#ช้อปปี้ #ShopeeTH #รีวิวช้อปปี้ #ของมันต้องมี #ใช้ดีบอกต่อ #ป้ายยาของใช้ #พิกัดในคอมเมนต์ #ShopeeAffiliate"
    )
    return caption.strip()


def stage_product_assets_for_flow(product, prompt_text):
    """Download image to staging directory and write prompt text file."""
    pid = product.get("id") or "prod_" + dt.datetime.now().strftime("%Y%m%d%H%M%S")
    img_dest = STAGING_DIR / f"{pid}.jpg"
    txt_dest = STAGING_DIR / f"{pid}_prompt.txt"

    # Write prompt
    txt_dest.write_text(prompt_text, encoding="utf-8")

    # Image
    img_url = product.get("image_url", "")
    if img_url:
        cached = download_image_cache(img_url, pid)
        if cached and cached.is_file():
            shutil.copy2(cached, img_dest)

    return {"prompt_file": txt_dest, "image_file": img_dest if img_dest.is_file() else None}


def find_recent_videos(limit=5):
    """Find recently created or downloaded MP4 videos in Downloads and output folder."""
    candidates = []
    search_dirs = [
        Path.home() / "Downloads",
        ROOT / "output",
    ]

    for s_dir in search_dirs:
        if not s_dir.is_dir():
            continue
        for p in s_dir.glob("**/*.mp4"):
            try:
                stat = p.stat()
                mtime = stat.st_mtime
                candidates.append((mtime, p, stat.st_size))
            except Exception:
                pass

    candidates.sort(key=lambda x: x[0], reverse=True)
    out = []
    for mtime, p, size in candidates[:limit]:
        time_str = dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        size_mb = size / (1024 * 1024)
        out.append({
            "path": p,
            "filename": p.name,
            "time_str": time_str,
            "size_str": f"{size_mb:.1f} MB",
            "mtime": mtime,
        })
    return out


def record_facebook_post(product, video_path, caption, post_url=""):
    """Save record of published Facebook Profile post into JSON log."""
    record = {
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "product_id": product.get("id", ""),
        "product_name": product.get("name", ""),
        "video_path": str(video_path),
        "post_url": post_url.strip(),
        "caption": caption[:300] + "...",
        "affiliate_url": product.get("affiliate_url", ""),
    }

    records = []
    if POSTS_LOG_FILE.is_file():
        try:
            records = json.loads(POSTS_LOG_FILE.read_text(encoding="utf-8"))
        except Exception:
            records = []

    records.insert(0, record)
    POSTS_LOG_FILE.write_text(json.dumps(records[:200], ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def load_facebook_posts_history(limit=50):
    """Load history of published Facebook Profile posts."""
    if not POSTS_LOG_FILE.is_file():
        return []
    try:
        data = json.loads(POSTS_LOG_FILE.read_text(encoding="utf-8"))
        return data[:limit] if isinstance(data, list) else []
    except Exception:
        return []
