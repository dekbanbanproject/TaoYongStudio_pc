"""Prepare plan requests for subscription chat apps and import their script JSON."""
import json
import re
from pathlib import Path

from . import script as scriptmod
from .config import ROOT

PROVIDERS = {
    "claude": ("Claude Pro", "https://claude.ai/"),
    "gemini": ("Gemini Pro", "https://gemini.google.com/"),
    "gpt": ("ChatGPT Plus", "https://chatgpt.com/"),
}


def request_prompt(request):
    """A self-contained prompt that works in a normal Claude/Gemini/ChatGPT chat."""
    topics = [dict(title=item.get("title", ""), summary=item.get("summary", ""),
                   genre=item.get("genre", ""), characters=item.get("characters", []))
              for item in request.get("items", [])]
    if request.get("custom"):
        topics.append({"title": request["custom"]})
    count = max(1, int(request.get("count_per_item", 1)))
    seconds = int(request.get("length_seconds", 30))
    is_compilation = seconds >= 300
    example = {
        "scripts": [{"id": "ep-new-01", "title": "ชื่อคลิปภาษาไทย", "description": "คำอธิบายสั้น",
                     "tags": ["การ์ตูนเด็ก"], "genre": "แนว", "characters": ["bunny", "bear"],
                     "formats": ["horizontal"] if is_compilation else ["vertical", "horizontal"],
                     "scenes": [{"background": "meadow", "beats": [
                         {"who": "bunny", "say": "สวัสดีจ้ะ", "action": "wave"},
                         {"who": "bear", "say": "มาเรียนรู้กันนะ", "action": "point"}]}]}]}
    if is_compilation:
        example["compilation"] = {"id": "comp-new-01", "title": "ชื่อคลิปรวม",
                                  "description": "คำอธิบายคลิปรวม", "tags": ["การ์ตูนเด็ก", "รวมคลิป"],
                                  "target_minutes": max(5, seconds // 60), "format": "horizontal",
                                  "episodes": ["ep-new-01"]}
    return ("คุณเป็นพนักงาน AI ฝ่ายเขียนบทการ์ตูนเด็กภาษาไทยของ TaoYongStudio\n"
            "เขียนบทตามคำขอด้านล่าง และตอบเป็น JSON object อย่างเดียว ห้ามใส่ Markdown หรือคำอธิบายอื่น\n"
            f"รหัสคำขอ: {request['id']}\n"
            f"หัวข้อ: {json.dumps(topics, ensure_ascii=False)}\n"
            f"จำนวนบทต่อหัวข้อ: {count}\nความยาวเป้าหมาย: {seconds} วินาที\n"
            f"แนวภาพ: {request.get('format', 'both')}\nหมายเหตุ: {request.get('note', '')}\n"
            "รูปแบบผลลัพธ์ (เปลี่ยนข้อความและเพิ่มบทตามคำขอ):\n"
            f"{json.dumps(example, ensure_ascii=False, indent=2)}\n"
            "กฎ: แต่ละบทต้องมี id ไม่ซ้ำ ใช้ตัวอังกฤษเล็ก ตัวเลข และขีด; title, description, tags, "
            "characters และ scenes ต้องครบ; ตัวละครเลือก bunny, bear, chick, cat สูงสุด 4 ตัว; "
            "background เลือก meadow, beach, night, bedroom, classroom; beats แต่ละรายการมี say "
            "ภาษาไทยสั้น ๆ และ who เป็นตัวละครในฉากหรือ narrator; action ใช้ talk, wave, jump, "
            "cheer, point, happy, dance, none; ถ้าต้องการให้เด็กตอบ ให้ใส่ beat {\"pause\": 1.5}; "
            "เนื้อหาปลอดภัย เหมาะกับเด็ก ไม่มีแบรนด์หรือคำชวนซื้อ\n"
            + ("คลิป 5–20 นาทีให้เขียนหลายตอนสั้น ๆ แล้วใส่ compilation โดย episodes เป็น id ของตอนที่เขียน "
               "และ target_minutes ตามความยาวเป้าหมาย ห้ามเขียนบทเดียวยาว 20 นาที\n"
               if is_compilation else "")
            + "ตอบให้ JSON ถูกต้องและครบทุกบท")


def chat_handoff_prompt(request):
    prompt = request_prompt(request)
    when = request.get("scheduled_at")
    if when:
        return ("กรุณาตั้งงานแบบครั้งเดียวให้ทำในวันที่และเวลาต่อไปนี้ตามเขตเวลา Asia/Bangkok: "
                f"{when.replace('T', ' ')}\n"
                "ให้ยืนยันการตั้งเวลากับฉันในแชตนี้ แล้วเมื่อถึงเวลาจึงทำตามคำสั่งด้านล่าง "
                "และส่งผลเป็น JSON เพื่อให้ฉันนำเข้ากลับเข้า TaoYongStudio\n\n" + prompt)
    return prompt


def _decode_output(text):
    text = text.strip().lstrip("\ufeff")
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.I | re.S)
    if match:
        text = match.group(1)
    return json.loads(text)


def import_response(text, request, root=ROOT):
    """Validate the whole response before writing scripts and the request result."""
    data = _decode_output(text)
    if isinstance(data, list):
        scripts, compilation = data, None
    elif isinstance(data, dict):
        scripts = data.get("scripts") or ([data] if data.get("scenes") else [])
        compilation = data.get("compilation")
    else:
        raise ValueError("ผลจาก AI ต้องเป็น JSON ที่มี scripts")
    if not isinstance(scripts, list) or not scripts:
        raise ValueError("ไม่พบบทในช่อง scripts")
    root = Path(root)
    inbox = root / "scripts" / "inbox"
    done = root / "scripts" / "done"
    compdir = root / "scripts" / "compilations"
    ids = []
    for index, sc in enumerate(scripts, 1):
        if not isinstance(sc, dict):
            raise ValueError("บทที่ %d ไม่ใช่ JSON object" % index)
        ident = str(sc.get("id", ""))
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", ident):
            raise ValueError("บทที่ %d มี id ไม่ถูกต้อง" % index)
        if ident in ids or (inbox / (ident + ".json")).exists() or list(done.glob("**/" + ident + ".json")):
            raise ValueError("มี id บทซ้ำ: %s" % ident)
        if not str(sc.get("description", "")).strip():
            raise ValueError("บท %s ไม่มีคำอธิบายโพสต์" % ident)
        if not isinstance(sc.get("tags"), list) or not sc["tags"]:
            raise ValueError("บท %s ไม่มีแฮชแท็ก" % ident)
        errors, _ = scriptmod.validate(sc)
        if errors:
            raise ValueError("บท %s ไม่ผ่าน: %s" % (ident, "; ".join(errors[:4])))
        sc["request_id"] = request["id"]
        ids.append(ident)
    comp_id = None
    if compilation is not None:
        if not isinstance(compilation, dict):
            raise ValueError("compilation ต้องเป็น JSON object")
        comp_id = str(compilation.get("id", ""))
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", comp_id):
            raise ValueError("id คลิปรวมไม่ถูกต้อง")
        if (compdir / (comp_id + ".json")).exists() or list(done.glob("**/" + comp_id + ".json")):
            raise ValueError("มี id คลิปรวมซ้ำ: %s" % comp_id)
        episodes = compilation.get("episodes") or []
        if not isinstance(episodes, list) or not episodes or any(e not in ids for e in episodes):
            raise ValueError("compilation.episodes ต้องอ้างถึงบทที่ส่งมาครั้งนี้")
        if not str(compilation.get("title", "")).strip() or int(compilation.get("target_minutes", 0)) < 5:
            raise ValueError("คลิปรวมต้องมีชื่อและ target_minutes อย่างน้อย 5")
        compilation["request_id"] = request["id"]
    result_path = root / "plans" / "results" / (request["id"] + ".json")
    if result_path.exists():
        previous = json.loads(result_path.read_text(encoding="utf-8"))
        if previous.get("status") == "done":
            raise FileExistsError("คำขอนี้มีผลลัพธ์แล้ว")
    inbox.mkdir(parents=True, exist_ok=True)
    for sc in scripts:
        (inbox / (sc["id"] + ".json")).write_text(json.dumps(sc, ensure_ascii=False, indent=2), encoding="utf-8")
    if compilation is not None:
        compdir.mkdir(parents=True, exist_ok=True)
        (compdir / (comp_id + ".json")).write_text(json.dumps(compilation, ensure_ascii=False, indent=2), encoding="utf-8")
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps({"id": request["id"], "status": "done", "script_ids": ids,
                                       "compilation_id": comp_id, "message": "นำเข้าจาก %s" %
                                       PROVIDERS.get(request.get("provider"), ("AI", ""))[0]},
                                      ensure_ascii=False, indent=2), encoding="utf-8")
    return ids, comp_id
