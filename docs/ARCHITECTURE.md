# โครงสร้างระบบ — TaoYongStudio Desktop V2

## ภาพรวม

```
┌──────────────────────────────────────────────────────────────────────┐
│  Tauri 2 (Rust)  desktop/src-tauri                                     │
│  • หน้าต่างไร้ขอบ (decorations: false) + custom window controls        │
│  • คำสั่ง: api_request / engine_status / engine_restart /             │
│            open_path / reveal_path                                     │
│  • จัดการ asset protocol เพื่อเล่นไฟล์วิดีโอจริงจากดิสก์              │
└───────────────┬──────────────────────────────────────────────────────┘
                │  invoke()
┌───────────────▼──────────────────────────────────────────────────────┐
│  React 19 + TypeScript   desktop/src                                  │
│  pages/ · components/{layout,common,media} · services/api.ts          │
│  design tokens: styles/tokens.css  +  styles/global.css                │
└───────────────┬──────────────────────────────────────────────────────┘
                │  HTTP 127.0.0.1 + bearer token
┌───────────────▼──────────────────────────────────────────────────────┐
│  Python Engine  engine/taoyong                                         │
│  service.py  →  ThreadingHTTPServer (loopback only, token auth)       │
│  api.py      →  ตัวจัดการเส้นทางทั้งหมด (34 route)                    │
│  ───────────────────────────────────────────────────────────────       │
│  compile.py · episode.py · art.py · audio.py · tts.py · textrender.py  │
│  hardware.py · credential_store.py · ai_worker_scheduler.py            │
│  planner_*.py · platform_workspace.py · product_clips.py               │
│  facebook_profile_flow.py · fb_browser_worker.py · publish/*           │
└───────────────┬──────────────────────────────────────────────────────┘
                │
   ┌────────────┴────────────┬──────────────┬─────────────┐
   ▼                         ▼              ▼             ▼
 scripts/                 output/        plans/      nextseller/data/
 (บทจริง)                (คลิปจริง)      (ไอเดีย)      (สินค้า Shopee)
```

## เหตุผลที่เลือกใช้ HTTP loopback แทน IPC อื่น

Python Engine เดิมเป็นโปรแกรม Python ล้วน (Tkinter + เรนเดอร์ + เสียงพากย์)
การห่อด้วย service แบบ loopback ทำให้:

* โค้ด Engine เดิมที่ทำงานได้จริง **ไม่ต้องแก้** เพียงเพิ่มชั้น `api.py`
* ตรวจสอบ API ได้ด้วย curl หรือ Python ธรรมดา ไม่ต้องเปิดหน้าต่าง
* ทำงานยังได้เมื่อปิดหน้าต่าง (แต่ต้องมี process ค้างไว้ — ดูข้อจำกัดด้านล่าง)

### มาตรการป้องกัน

| มาตรการ | รายละเอียด |
|---|---|
| ผูก address | `127.0.0.1` เท่านั้น — service ปฏิเสธที่จะ bind address อื่น |
| Token | สร้างใหม่ทุกครั้งที่เปิดโปรแกรม ส่งผ่าน stdout ของ process ไปยัง Rust |
| ตรวจ Host header | ปฏิเสธ request ที่ Host ไม่ใช่ loopback (กัน DNS rebinding) |
| ไม่มี CORS โดยค่าเริ่มต้น | มีเฉพาะเมื่อสั่ง `--dev-cors` (ใช้ตอนเปิดในเบราว์เซอร์เท่านั้น) |
| ไม่มี mock backend | ไม่มีโค้ดสำรองที่แอบทำงานแทน Engine |

## สัญญา API

ทุก response เป็น JSON และมี `"ok": true` เมื่อสำเร็จ
ถ้าผิดพลาดจะได้ HTTP 400 พร้อม `{ "error": "ข้อความภาษาไทย" }`

| กลุ่ม | Endpoint |
|---|---|
| ระบบ | `GET /api/health` · `GET /api/dashboard` · `GET /api/hardware` |
| บท | `GET /api/scripts` · `GET /api/scripts/detail` · `POST /api/scripts/import` · `POST /api/scripts/add-sample` · `POST /api/scripts/delete` · `POST /api/scripts/send-to-flow` |
| คลิป | `GET /api/clips` · `GET /api/clips/detail` · `POST /api/clips/delete` · `POST /api/clips/status` |
| เรนเดอร์ | `POST /api/render` · `GET /api/job` · `POST /api/job/cancel` |
| วางแผน | `GET /api/planner/ideas` · `GET /api/planner/requests` · `GET /api/planner/result` · `POST /api/planner/request` · `POST /api/planner/import-response` · `POST /api/planner/cancel` · `POST /api/planner/product-ideas` |
| แพลตฟอร์ม | `GET /api/platform/scripts` · `GET /api/platform/clips` · `POST /api/platform/import-video` · `POST /api/platform/google-video` · `POST /api/platform/analyze-prompt` |
| โพสต์ | `GET /api/posting/status` · `POST /api/posting/save` · `POST /api/posting/connect` · `POST /api/posting/disconnect` |
| ตั้งเวลา | `GET /api/scheduler` · `POST /api/scheduler/save` · `POST /api/scheduler/test` · `POST /api/scheduler/stop` |
| ตั้งค่า | `GET /api/settings` · `POST /api/settings/save` · `POST /api/settings/key` · `POST /api/settings/key/delete` · `POST /api/settings/test-voice` · `POST /api/settings/test-azure` |
| Shopee / Facebook | `GET /api/shopee/products` · `GET /api/shopee/categories` · `POST /api/facebook/prompt` · `POST /api/facebook/caption` · `GET /api/facebook/posts` |

## เส้นทางข้อมูลจริงในเครื่อง

```
scripts/inbox/*.json          บทที่รอสร้างคลิป        (9 ไฟล์)
scripts/done/<วันที่>/*.json   บทที่สร้างคลิปแล้ว       (35 ไฟล์)
scripts/samples/*.json        บทตัวอย่าง              (5 ไฟล์)
plans/ideas.json              ไอเดียที่ AI สร้าง
plans/requests/*.json         คำขอไปยัง AI
plans/results/*.json          ผลลัพธ์ที่นำเข้ากลับมา
plans/product_prompts/        พรอมต์สินค้า
output/<วันที่>/<คลิป>/      meta.json + ไฟล์วิดีโอ + ภาพปก
nextseller/data/products.csv  สินค้า Shopee จริง
config.json                   ค่าตั้งทั้งหมด (ไม่อยู่ใน git)
secrets/                      API key (DPAPI ของ Windows)
```

## ข้อจำกัดที่ต้องแจ้งผู้ใช้อยู่เสมอ

1. **พนักงาน AI ต้องเปิดเครื่องไว้** — ใช้ Windows Task Scheduler ไม่ใช่ service ที่ทำงานเบื้องหลัง
2. **TikTok ส่งเป็นแบบร่าง** เจ้าของบัญชีต้องกดโพสต์เองในแอป
3. **Shopee และ Facebook Profile โพสต์เอง** — โปรแกรมเปิดเว็บไซต์ + คัดลอกข้อความ
4. **โหมด 3D ต้องมี Blender** และ encoder ที่ตรวจพบได้จริง (หน้าบทแสดงสถานะ)
5. **Gemini เป็น AI provider เดียวที่เรียกได้จริง** Claude / ChatGPT ต้องคัดลอกพรอมต์ไปวางเอง

## การย้ายจากระบบเดิม (Tkinter) มาเป็นระบบใหม่

| เดิม | ใหม่ |
|---|---|
| `studio/gui.py` (Tkinter, 418 KB) | ถูกลบออกจากโปรเจกต์ — UI ใหม่อยู่ใน `desktop/src/pages/` |
| `studio/*.py` (Engine) | ย้ายไป `engine/taoyong/` โดยแก้เฉพาะ `config.py` (หา workspace root) |
| `studio/cli.py` | คงไว้ — ใช้เรียก `cli._render_one()` จาก service |
| `.bat` เก่า | เขียนใหม่เป็น `setup.bat` / `TaoYongStudio.bat` / `dev.bat` |
| `installer/` (ตัวติดตั้ง Tkinter) | ใช้ NSIS/MSI ของ Tauri แทน |
| `mockups/` | ย้ายไป `design-reference/` |

`config.py` เปลี่ยนเพียงส่วนที่หา root path — ตรรกะทั้งหมดของ Engine คงเดิม
