# ผลการส่งมอบ — TaoYongStudio Desktop V2

สร้างใหม่ทั้งหมดเป็น **Tauri 2 (Rust) + React 19 + TypeScript + Python**
โดยใช้ Python Engine ตัวเดิมที่ทำงานได้จริงเป็นฝั่งหลังบ้าน

---

## 1. สรุปผลตรวจ 11 หน้า

| # | หน้า | เส้นทาง | สถานะ | ข้อมูลจริงที่หน้าจอดึงมาใช้ |
|---|---|---|---|---|
| 1 | หน้าแรก (Dashboard) | `/` | ✅ ผ่าน | บทรอสร้าง 9 · คลิปวันนี้ 2 · คลิปทั้งหมด 2 · คลิปรอตรวจ 0 · สถานะระบบสด (GPU 4 ตัว, encoder 4 ตัว, TTS 4 เอนจิน) · เวลาโพสต์อัตโนมัติครั้งถัดไป · กิจกรรมล่าสุด 8 รายการ |
| 2 | วางแผน (AI Planner) | `/planner` | ✅ ผ่าน | ไอเดีย AI 42 อันจาก `plans/ideas.json` · ประวัติคำขอ 9 รายการ · สร้าง/ยกเลิก/นำเข้าผลลัพธ์ได้จริง |
| 3 | บท (Scripts) | `/scripts` | ✅ ผ่าน | บทจริง 52 ไฟล์ (inbox 9 / done 35 / samples 5) · ตรวจ GPU/CPU/encoder จริง · เรนเดอร์ผ่าน job พร้อม % และ log · ยกเลิกงานได้ |
| 4 | คลิป (Clips) | `/clips` | ✅ ผ่าน | คลิปจริงที่เรนเดอร์แล้ว 2 คลิป · เล่นไฟล์จริงในตัว player · ระยะเวลา/ความละเอียด/ช่องทางโพสต์จริง |
| 5 | สร้างและโพสต์ — TikTok | `/create/tiktok` | ✅ ผ่าน | 4 วิธีสร้างวิดีโอ · อัตราส่วน/ความยาว/สไตล์/ตัวละคร · ส่งเป็น **แบบร่าง** ผ่าน API จริง (ตามสเปก) |
| 6 | สร้างและโพสต์ — YouTube | `/create/youtube` | ✅ ผ่าน | Shorts/แนวนอน · Made for Kids · เลือกแหล่งวิดีโอ 4 แบบ + ลากวางไฟล์ · โพสต์จริงเมื่อเชื่อมต่อแล้ว ไม่งั้นปิดพร้อมเหตุผล |
| 7 | สร้างและโพสต์ — Shopee | `/create/shopee` | ✅ ผ่าน | 7 ขั้นตอน · เลือกสินค้าจริงจาก Shopee · ข้อความ/แท็ก/คลิปตัดต่อ/สรุปตรวจสอบ |
| 8 | ตั้งค่าโพสต์ | `/posting-settings` | ✅ ผ่าน | สถานะเชื่อมต่อจริง 4 แพลตฟอร์ม · จำนวนต่อวันแยกรายแพลตฟอร์ม (TikTok 3 / YouTube 2 / FB Page 2 / FB Profile 1) · เวลาโพสต์ |
| 9 | ตั้งเวลา | `/scheduler` | ✅ ผ่าน | ตั้งเวลาจริง + Windows Task Scheduler · เลือกแพลตฟอร์ม/เวลา · ทดสอบรอบทำงานจริง · ประวัติการทำงาน |
| 10 | ตั้งค่า | `/settings` | ✅ ผ่าน | Gemini / Azure Speech key (เข้ารหัส DPAPI) · เสียงตัวละครจริง 5 ตัว + ค่า pitch/rate · ทดสอบเสียงจริง |
| 11 | Facebook Profile | `/facebook-profile` | ✅ ผ่าน | สินค้า Shopee จริง 1,598 รายการ (ค้นหา/หมวด/เรียง/แบ่งหน้า) · พรอมต์ Google Flow · แคปชัน · ตั้งเวลาโพสต์อัตโนมัติ |

> หมายเหตุ: เส้นทาง `/create/facebook_page` เปิดใช้งานได้จริงเช่นกัน (แท็กแพลตฟอร์มในหน้าสร้างและโพสต์)

---

## 2. สิ่งที่สร้างใหม่

```
desktop/                      Tauri 2 + React 19 + TypeScript
├─ src/pages/                 11 หน้า (ไฟล์เดียวต่อ 1 หน้า)
├─ src/components/layout/     AppShell · Header · Sidebar (9 เมนู + ปุ่มปิดหน้าต่าง)
├─ src/components/common/     PastelCard · DataTable · Toast · ConfirmDialog · SearchInput …
├─ src/components/media/      VideoPlayer · VideoThumbnail · ClipStrip
├─ src/styles/tokens.css      ดีไซน์ท็อกเกน (สี รัศมี เงา ระยะ ฟอนต์)
├─ src/styles/global.css      คลาส CSS กลางกว่า 60 คลาส
├─ src/services/api.ts        ตัวเรียก Engine ผ่าน Tauri (มีโหมด browser สำหรับ dev)
└─ src-tauri/                 Rust: สะพาน invoke → Python, จัดการ asset protocol, ปุ่มหน้าต่าง

engine/taoyong/               Python Engine (ของเดิม) + ชั้น service ใหม่
├─ service.py                 HTTP JSON API แบบ loopback + token
├─ api.py                     52 เส้นทาง ครอบคลุมทุกหน้า
├─ credential_store.py        + เก็บ key แบบมีชื่อ (DPAPI)
├─ publish/__init__.py        + จำนวนคลิปต่อวันแยกรายแพลตฟอร์ม
└─ (โมดูลเดิมทั้งหมด)         compile · episode · tts · art · audio · scheduler · planner · publish …
```

### การเชื่อมต่อ

```
React  ──invoke()──►  Tauri (Rust)  ──HTTP 127.0.0.1 + token──►  Python Engine
                                                                   ├─ scripts/  (52 ไฟล์)
                                                                   ├─ plans/    (53 ไฟล์)
                                                                   ├─ output/   (คลิปจริง)
                                                                   └─ nextseller/data/ (1,598 สินค้า)
```

มาตรการป้องกัน: ผูก `127.0.0.1` เท่านั้น · token ใหม่ทุกครั้งที่เปิดโปรแกรม ·
ตรวจ Host header กัน DNS rebinding · ไม่มี CORS เว้นแต่เปิดด้วย `--dev-cors`

---

## 3. การแก้ไข Engine ที่จำเป็นระหว่างต่อ UI

| ปัญหา | การแก้ |
|---|---|
| คำขอไอเดียไม่ส่งไอเดียที่เลือกไปให้ Gemini | เขียน `items` ลงไฟล์คำขอ พร้อม `custom`/`count_per_item`/`length_seconds` |
| ตั้งเวลาไม่ได้จริง | `when:"scheduled"` เรียก `schedule_request()` ลง Windows Task Scheduler |
| นำเข้าผลลัพธ์ไม่คืนพาธไฟล์ | แก้ให้คืน `resultPath` + `scriptIds` จริง |
| บันทึก Azure Speech Key ไม่ได้จาก UI | เพิ่ม `/api/settings/azure-key` + `delete` (เข้ารหัส DPAPI) |
| จำนวนคลิปต่อวันไม่แยกแพลตฟอร์ม | เพิ่ม `max_per_day` ในแต่ละแพลตฟอร์ม และบังคับใช้ใน `run_auto()` |
| `platforms` ของตัวตั้งเวลาเป็น dict | ปรับเป็นรายการชื่อแพลตฟอร์มที่เปิดใช้ |
| โพสต์คลิปรายคลิปไม่มีเส้นทาง | เพิ่ม `POST /api/publish/clip` และ `/api/publish/caption` |
| หาโฟลเดอร์ workspace ผิดตอน build | แก้การ resolve root ให้แยกโฟลเดอร์ dev ออกจากโฟลเดอร์ bundle |

---

## 4. สิ่งที่ต้องแจ้งผู้ใช้

1. **พนักงาน AI ต้องเปิดเครื่องไว้** — ใช้ Windows Task Scheduler ไม่ใช่ service ที่ทำงานเบื้องหลัง
2. **TikTok ส่งเป็นแบบร่าง** เจ้าของบัญชีต้องกดโพสต์เองในแอป
3. **Shopee และ Facebook Profile ต้องโพสต์เอง** — โปรแกรมคัดลอกแคปชันและเปิดหน้าเว็บให้
4. **Gemini เป็น AI provider เดียวที่เรียกได้จริง** — Claude / ChatGPT ต้องคัดลอกพรอมต์ไปวางเอง (UI บอกชัดเจน)
5. **โหมด 3D ต้องมี Blender** และ encoder ที่ตรวจพบจริง (หน้าบทแสดงสถานะจริง)
6. **รูปแบบ 1:1 ยังใช้ไม่ได้** — Engine รองรับแค่ 9:16 / 16:9 (UI ปิดตัวเลือกนี้ไว้)
7. **คลิปจากเดิมเป็นแนวนอน 1920×1080** — ตัวอย่างที่เรนเดอร์แล้วในเครื่องนี้เป็นแนวนอน

---

## 5. วิธีใช้งาน

```bat
:: โหมดพัฒนา (React HMR + Tauri)
dev.bat

:: build โปรแกรม Windows
cd desktop
npm run tauri:build
```

ตัวติดตั้งที่ได้:

* `desktop\src-tauri\target\release\bundle\nsis\TaoYongStudio_2.0.0_x64-setup.exe` (58 MB)
* `desktop\src-tauri\target\release\bundle\msi\TaoYongStudio_2.0.0_x64_en-US.msi` (78.5 MB)

ติดตั้งแล้วได้โฟลเดอร์ที่มี `taoyongstudio.exe`, `engine\` (พร้อม sidecar `taoyong-engine.exe`),
`scripts\`, `plans\`, `output\`, `nextseller\`, `fonts\`, `assets\` — ใช้งานได้ทันทีโดยไม่ต้องติดตั้ง Python

## 6. ภาพหน้าจอจริง

`docs/screenshots/` มีภาพจากโปรแกรมจริงทั้ง 9 เมนู (ถ่ายจากหน้าต่าง Tauri ที่รันจริง)
