# TaoYongStudio Desktop V2

โปรแกรม Windows Desktop สำหรับสร้างคลิปการ์ตูนเด็กภาษาไทยด้วย AI
แล้วเผยแพร่ไปยัง TikTok, YouTube, Shopee, Facebook Page และ Facebook Profile

**สถาปัตยกรรม:** Tauri 2 (Rust shell) + React 19 + TypeScript (UI) + Python (Engine)

---

## โครงสร้างโปรเจกต์

```
F:\DverClips\
├─ desktop\                     # Tauri 2 + React + TypeScript (UI ทั้งหมด)
│  ├─ src\
│  │  ├─ components\layout\     # AppShell, Header, Sidebar
│  │  ├─ components\common\     # PastelCard, DataTable, Toast, ConfirmDialog, ...
│  │  ├─ components\media\      # VideoPlayer, VideoThumbnail
│  │  ├─ pages\                 # 11 หน้า
│  │  ├─ services\api.ts        # ตัวช่วยเรียก Python Engine ผ่าน Tauri
│  │  └─ styles\                # tokens.css (design tokens) + global.css
│  └─ src-tauri\                # Rust: สะพานเชื่อม UI -> Python Engine
├─ engine\taoyong\              # Python Engine (ของเดิมที่ทำงานได้จริง)
│  ├─ service.py                # HTTP JSON API แบบ loopback + token
│  ├─ api.py                    # ตัวจัดการเส้นทางทั้งหมด
│  ├─ compile.py / episode.py   # สายการเรนเดอร์วิดีโอ
│  ├─ tts.py / audio.py         # เสียงพากย์ + เพลง + เอฟเฟกต์
│  ├─ art.py / textrender.py    # วาดภาพการ์ตูน + ซับ
│  ├─ hardware.py               # ตรวจ GPU / CPU / encoder
│  ├─ credential_store.py       # เก็บ API key (DPAPI ของ Windows)
│  ├─ ai_worker_scheduler.py    # ตัวจัดตารางงาน + Windows Task Scheduler
│  └─ publish\                  # YouTube / Facebook Page / TikTok
├─ scripts\                     # บทจริง (inbox / done / samples)
├─ plans\                       # ไอเดีย + คำขอ + ผลลัพธ์จริง
├─ output\                      # คลิปที่เรนเดอร์แล้ว
├─ nextseller\data\             # ข้อมูลสินค้า Shopee จริง
├─ fonts\                       # Kanit (SIL OFL)
├─ assets\branding\             # ภาพประกอบการ์ตูนจริง
├─ design-reference\            # ภาพต้นแบบ 10 หน้า
└─ docs\                        # เอกสารรูปแบบบท + คู่มือเชื่อมต่อบัญชี
```

## การทำงานของระบบ

```
React UI  ──invoke()──►  Tauri Rust (src-tauri)
                              │
                              │ HTTP 127.0.0.1 + bearer token
                              ▼
                     Python Engine service
                              │
        ┌─────────────┬───────┴────────┬──────────────┐
        ▼             ▼                ▼              ▼
   scripts/       output/         plans/         config.json
```

* Python Engine ผูกกับ `127.0.0.1` เท่านั้น และต้องมี token ต่อครั้งที่เปิดโปรแกรม
* ทุกหน้าจอดึงข้อมูลจาก Engine จริง — ไม่มี Mock Data
* ถ้าแพลตฟอร์มใดยังไม่ได้เชื่อมต่อ หน้าจอจะแสดงสถานะจริงว่า "ยังไม่ได้เชื่อมต่อ"

## ติดตั้ง (สำหรับนักพัฒนา)

```bat
:: 1) ติดตั้ง Python Engine
cd engine
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

:: 2) ติดตั้ง frontend
cd ..\desktop
npm install

:: 3) รันแบบ dev (เปิด Tauri + React)
npm run tauri:dev
```

หรือเรียก Python Engine โดยตรง:

```bat
cd engine
.venv\Scripts\python -m taoyong.service --host 127.0.0.1 --port 8765 --token <token>
```

## คำสั่งที่ใช้บ่อย

| คำสั่ง | ทำอะไร |
|---|---|
| `npm run tauri:dev` | เปิดโปรแกรมในโหมดพัฒนา (React HMR + Tauri) |
| `npm run build` | build React เป็น `desktop/dist` |
| `npm run typecheck` | ตรวจ TypeScript |
| `npm run tauri:build` | build โปรแกรม Windows + Installer (NSIS/MSI) |
| `studio.bat check` | ตรวจความพร้อมของเครื่อง (จากระบบเดิม) |

## เสียงพากย์

โปรแกรมลองตามลำดับ `config.json` → `tts.engines`
(`azure` → `edge` → `sapi` → `espeak`)

* **azure** — เสียง Microsoft ใช้เชิงพาณิชย์ได้ ต้องมี Azure Speech key
* **edge** — เสียงเดียวกันฟรีผ่าน Edge read-aloud ต้องต่อเน็ต (เหมาะกับทดสอบ)
* **sapi** — เสียงไทยของ Windows ใช้ออฟไลน์ได้
* **espeak** — เสียงหุ่นยนต์ ใช้ทดสอบเท่านั้น

ถ้าคลิปใดใช้เสียงสำรอง `meta.json` จะมีคำเตือนอยู่ใน `needs_review`
ฝ่ายตรวจจะไม่ส่งคลิปนั้นไปโพสต์

## การเชื่อมต่อบัญชี

ดูรายละเอียดที่ `docs/CONNECT_ACCOUNTS_TH.md`

| แพลตฟอร์ม | วิธี |
|---|---|
| YouTube | OAuth ผ่าน API ต้องมี `secrets/youtube_client.json` |
| Facebook Page | OAuth ผ่าน Graph API |
| TikTok | OAuth ส่งคลิปเข้าเป็นแบบร่าง เจ้าของบัญชีกดโพสต์เองในแอป |
| Facebook Profile / Shopee | เปิดเว็บไซต์ + คัดลอกข้อความให้โพสต์เอง |

## ข้อมูลจริงที่ใช้อยู่ในเครื่องนี้

* `scripts/` — บท 52 ไฟล์ (inbox 9, done 35, samples 5)
* `plans/` — ไอเดีย คำขอ และผลลัพธ์ 53 ไฟล์
* `nextseller/data/` — สินค้า Shopee จริง (products, scores, angles)
* `output/` — คลิปตัวอย่างที่เรนเดอร์จริง

## ข้อจำกัดที่ต้องแจ้งผู้ใช้

* พนักงาน AI ใช้ **Windows Task Scheduler** — ต้องเปิดเครื่องไว้จึงจะทำงานต่อเนื่อง
* การโพสต์ TikTok / Shopee / Facebook Profile เป็นการส่งออกให้ผู้ใช้โพสต์เอง ไม่ใช่โพสต์อัตโนมัติ
* โหมด 3D ต้องมี Blender และ encoder ที่ใช้งานได้ (ตรวจสอบได้ที่หน้าตั้งค่า/หน้าบท)

## สัญลิขสิทธิ์

ฟอนต์ Kanit ใช้สัญญาอนุญาต SIL Open Font License (`fonts/OFL.txt`)
