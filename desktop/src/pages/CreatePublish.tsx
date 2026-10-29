import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Clock,
  Copy,
  ExternalLink,
  Facebook,
  FolderOpen,
  Image as ImageIcon,
  Music2,
  Play,
  RefreshCw,
  Send,
  ShoppingBag,
  Sparkles,
  Type,
  Upload,
  Video as VideoIcon,
  Wand2,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { openUrl } from "@tauri-apps/plugin-opener";
import { open as openFileDialog } from "@tauri-apps/plugin-dialog";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import {
  apiGet,
  apiPost,
  CHAR_LABEL,
  PLATFORM_META,
  STATUS_LABEL,
  type ClipEntry,
  type JobPayload,
  type ScriptSummary,
} from "../services/api";
import {
  Chip,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  PastelCard,
  StatusBadge,
  formatDuration,
} from "../components/common/ui";
import { Modal, useToast } from "../components/common/feedback";
import { useApiData } from "../hooks/useApiData";
import { ClipStrip, VideoPlayer } from "../components/media/VideoPlayer";

/* ------------------------------------------------------------------ types */

type PlatformKey = "tiktok" | "youtube" | "shopee" | "facebook_profile" | "facebook_page";
type Format = "vertical" | "horizontal";

interface ScriptsResp {
  ok: boolean;
  scripts: ScriptSummary[];
}
interface ClipsResp {
  ok: boolean;
  clips: ClipEntry[];
}
interface PostingPlatformState {
  label: string;
  connected: boolean;
  accountName: string;
  postedToday: number;
  settings: Record<string, any>;
}
interface PostingState {
  mode: string;
  maxPerDay: number;
  postTimes: string[];
  platforms: Record<string, PostingPlatformState>;
}
interface PostingResp {
  ok: boolean;
  posting?: PostingState;
  platforms?: Record<string, PostingPlatformState>;
  mode?: string;
  postTimes?: string[];
}

const PLATFORM_KEYS: PlatformKey[] = ["tiktok", "youtube", "shopee", "facebook_profile", "facebook_page"];

const TAB_ITEMS: { key: PlatformKey; to: string; icon: LucideIcon }[] = [
  { key: "tiktok", to: "/create/tiktok", icon: Music2 },
  { key: "youtube", to: "/create/youtube", icon: Play },
  { key: "shopee", to: "/create/shopee", icon: ShoppingBag },
  { key: "facebook_profile", to: "/facebook-profile", icon: Facebook },
  { key: "facebook_page", to: "/create/facebook_page", icon: Facebook },
];

const FLOW_URL = "https://flow.google.com/";
const TIKTOK_UPLOAD_URL = "https://www.tiktok.com/upload";
const YOUTUBE_UPLOAD_URL = "https://studio.youtube.com/";
const SHOPEE_SELLER_URL = "https://seller.shopee.co.th/";
const FACEBOOK_URL = "https://www.facebook.com/";

const RATIOS: { key: Format | "square"; label: string; sub: string }[] = [
  { key: "vertical", label: "9:16", sub: "แนวตั้ง (TikTok)" },
  { key: "square", label: "1:1", sub: "สี่เหลี่ยม" },
  { key: "horizontal", label: "16:9", sub: "แนวนอน" },
];

const DURATIONS = [15, 30, 60];

const STYLE_OPTIONS = [
  { key: "3d", label: "การ์ตูน 3D" },
  { key: "2d", label: "การ์ตูน 2D" },
  { key: "other", label: "สไตล์อื่นๆ" },
];

const MAX_TAGS = 8;

/* ---------------------------------------------------------------- helpers */

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

function errText(e: unknown): string {
  const m = (e as any)?.message;
  return typeof m === "string" && m ? m : "ทำรายการไม่สำเร็จ";
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch {
      return false;
    }
  }
}

function clipVideo(clip?: ClipEntry): string {
  if (!clip) return "";
  const files = clip.files || {};
  for (const k of ["vertical", "horizontal"]) {
    const v = files[k];
    if (typeof v === "string" && v) return v;
  }
  for (const v of Object.values(files)) {
    if (typeof v === "string" && v.toLowerCase().endsWith(".mp4")) return v;
  }
  return "";
}

function clipPoster(clip?: ClipEntry): string {
  if (!clip) return "";
  const files = clip.files || {};
  return files["thumb_vertical"] || files["thumb_horizontal"] || clip.thumb || "";
}

function scriptThumb(script: ScriptSummary, clips: ClipEntry[]): string {
  const title = (script.title || "").trim().toLowerCase();
  if (!title) return "";
  const byTitle =
    clips.find((c) => (c.title || "").trim().toLowerCase() === title) ||
    clips.find((c) => (c.title || "").trim().toLowerCase().includes(title));
  if (byTitle) return clipPoster(byTitle);
  const byId = clips.find((c) => (c.id || "").includes(script.id) || (c.folderName || "").includes(script.id));
  return byId ? clipPoster(byId) : "";
}

function normalizePosting(res: PostingResp | null): PostingState {
  const src = res?.posting ?? res;
  return {
    mode: (src as any)?.mode ?? "off",
    maxPerDay: (src as any)?.maxPerDay ?? 0,
    postTimes: (src as any)?.postTimes ?? [],
    platforms: (src as any)?.platforms ?? {},
  };
}

function buildPrompt(
  script?: ScriptSummary,
  clip?: ClipEntry,
  opts?: { style?: string; duration?: number; character?: string; madeForKids?: boolean },
): string {
  const style = opts?.style === "2d" ? "2D" : opts?.style === "other" ? "ไม่ระบุสไตล์" : "3D";
  const seconds = opts?.duration && opts.duration > 0 ? opts.duration : 30;
  const who = opts?.character ? CHAR_LABEL[opts.character] ?? opts.character : "";
  const kids = opts?.madeForKids ? "ตั้งค่าเหมาะสำหรับเด็ก (Made for Kids)" : "";
  if (script) {
    const chars = (script.characters || []).map((c) => CHAR_LABEL[c] ?? c).join(", ");
    return [
      `สร้างวิดีโอการ์ตูนสำหรับเด็กไทย สไตล์ ${style} น่ารัก`,
      `เรื่อง: ${script.title}`,
      script.description ? `เนื้อหา: ${script.description}` : "",
      script.genre ? `แนวเรื่อง: ${script.genre}` : "",
      chars ? `ตัวละครในเรื่อง: ${chars}` : "",
      who ? `ตัวละครหลักที่ใช้: ${who}` : "",
      (script.tags || []).length ? `แท็ก: ${(script.tags || []).join(", ")}` : "",
      `ความยาวประมาณ ${seconds} วินาที อัตราส่วน 9:16 แนวตั้ง เหมาะสำหรับเด็ก`,
      kids,
    ]
      .filter(Boolean)
      .join("\n");
  }
  if (clip) {
    return [
      `สร้างวิดีโอแนะนำสินค้า สไตล์ ${style} น่ารักสำหรับเด็กไทย`,
      `คลิปต้นทาง: ${clip.title}`,
      clip.description ? `รายละเอียด: ${clip.description}` : "",
      who ? `ตัวละครที่ใช้: ${who}` : "",
      `ความยาวประมาณ ${seconds} วินาที อัตราส่วน 9:16 แนวตั้ง`,
    ]
      .filter(Boolean)
      .join("\n");
  }
  return `สร้างวิดีโอการ์ตูนสำหรับเด็กไทย สไตล์ ${style} น่ารัก ความยาว ${seconds} วินาที อัตราส่วน 9:16`;
}

function statusTone(status: string): "success" | "warn" | "danger" | "info" | "muted" {
  if (status === "approved" || status === "posted" || status === "posted_manual") return "success";
  if (status === "ready_for_approval") return "warn";
  if (status === "rejected") return "danger";
  if (status === "draft_sent") return "info";
  return "muted";
}

/** Text the owner pastes on the platform: title + description + hashtags. */
function postCaption(title: string, description: string, tags: string[]): string {
  const hashtags = tags.map((t) => "#" + t.replace(/\s+/g, "")).join(" ");
  return [title.trim(), description.trim(), hashtags].filter(Boolean).join("\n\n");
}

/* ------------------------------------------------------------------- tabs */

function PlatformTabs({ active }: { active: PlatformKey }) {
  return (
    <div className="platform-tabs">
      {TAB_ITEMS.map((t) => {
        const meta = PLATFORM_META[t.key];
        const Icon = t.icon;
        const isActive = t.key === active;
        return (
          <Link
            key={t.key}
            to={t.to}
            className={`platform-tab ${isActive ? "platform-tab--active" : ""}`}
          >
            <span className="platform-tab__logo" style={{ background: meta.bg, color: meta.color }}>
              <Icon size={15} />
            </span>
            <span>{meta.label}</span>
          </Link>
        );
      })}
    </div>
  );
}

/* -------------------------------------------------------------- fragments */

function StepHead({
  n,
  title,
  text,
  tone = "primary",
  action,
}: {
  n: number;
  title: string;
  text?: string;
  tone?: "primary" | "pink" | "mint" | "blue" | "orange";
  action?: ReactNode;
}) {
  return (
    <div className="row row--between" style={{ alignItems: "flex-start", marginBottom: 14, gap: 12 }}>
      <div className="step">
        <div className={`step__num step__num--${tone}`}>{n}</div>
        <div style={{ minWidth: 0 }}>
          <h3 className="step__title">{title}</h3>
          {text && <p className="step__text">{text}</p>}
        </div>
      </div>
      {action && <div style={{ flexShrink: 0 }}>{action}</div>}
    </div>
  );
}

function Tile({
  active,
  onClick,
  icon: Icon,
  title,
  desc,
  badge,
  badgeTone = "primary",
  disabled,
  hint,
}: {
  active: boolean;
  onClick: () => void;
  icon: LucideIcon;
  title: string;
  desc?: string;
  badge?: string;
  badgeTone?: "primary" | "pink" | "mint" | "blue" | "orange" | "warn";
  disabled?: boolean;
  hint?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="card"
      style={{
        textAlign: "left",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.55 : 1,
        border: `1.5px solid ${active ? "var(--c-primary)" : "var(--c-line)"}`,
        background: active ? "var(--g-primary-soft)" : "#fff",
        padding: 13,
        display: "flex",
        gap: 12,
        alignItems: "flex-start",
        boxShadow: "none",
      }}
    >
      <span
        className="card__title-icon"
        style={{ background: active ? "var(--g-primary)" : "var(--g-primary-soft)", color: active ? "#fff" : "var(--c-primary)" }}
      >
        <Icon size={16} />
      </span>
      <span style={{ minWidth: 0, flex: 1 }}>
        <span className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontWeight: 700, fontSize: "var(--fs-md)" }}>{title}</span>
          {badge && <StatusBadge tone={badgeTone}>{badge}</StatusBadge>}
        </span>
        {desc && (
          <span className="small muted" style={{ display: "block", marginTop: 3, lineHeight: 1.5 }}>
            {desc}
          </span>
        )}
        {hint && (
          <span className="xsmall muted" style={{ display: "block", marginTop: 3 }}>
            {hint}
          </span>
        )}
      </span>
    </button>
  );
}

function RatioRow({
  value,
  onChange,
}: {
  value: Format;
  onChange: (v: Format) => void;
}) {
  return (
    <div className="grid" style={{ gridTemplateColumns: "repeat(3, minmax(0,1fr))", gap: 10 }}>
      {RATIOS.map((r) => {
        const disabled = r.key === "square";
        const active = r.key === value;
        return (
          <button
            key={r.key}
            type="button"
            disabled={disabled}
            onClick={() => onChange(r.key as Format)}
            className="card"
            style={{
              padding: 10,
              textAlign: "center",
              cursor: disabled ? "not-allowed" : "pointer",
              opacity: disabled ? 0.5 : 1,
              border: `1.5px solid ${active ? "var(--c-primary)" : "var(--c-line)"}`,
              background: active ? "var(--g-primary-soft)" : "#fff",
              boxShadow: "none",
            }}
          >
            <div
              style={{
                width: 34,
                height: 22,
                margin: "0 auto 6px",
                border: "2px solid var(--c-primary)",
                borderRadius: 4,
              }}
            />
            <div style={{ fontWeight: 700 }}>{r.label}</div>
            <div className="xsmall muted">{disabled ? "ยังไม่รองรับ" : r.sub}</div>
          </button>
        );
      })}
    </div>
  );
}

function DurationRow({
  value,
  onChange,
  unit = "วินาที",
  hint,
}: {
  value: number;
  onChange: (v: number) => void;
  unit?: string;
  hint?: string;
}) {
  return (
    <div className="col" style={{ gap: 8 }}>
      <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
        {DURATIONS.map((d) => (
          <button
            key={d}
            type="button"
            onClick={() => onChange(d)}
            className="btn btn--sm"
            style={{
              background: value === d ? "var(--g-primary)" : "#fff",
              color: value === d ? "#fff" : "var(--c-ink)",
              border: "1px solid var(--c-line-strong)",
            }}
          >
            {d} {unit}
          </button>
        ))}
      </div>
      {hint && <span className="xsmall muted">{hint}</span>}
    </div>
  );
}

function TagEditor({
  tags,
  onChange,
}: {
  tags: string[];
  onChange: (tags: string[]) => void;
}) {
  const [text, setText] = useState("");
  const add = () => {
    const clean = text.trim().replace(/^#/, "");
    if (!clean) return;
    if (tags.length >= MAX_TAGS) return;
    if (tags.some((t) => t.toLowerCase() === clean.toLowerCase())) {
      setText("");
      return;
    }
    onChange([...tags, clean]);
    setText("");
  };
  return (
    <div className="col" style={{ gap: 8 }}>
      <div className="row row--wrap" style={{ gap: 7 }}>
        {tags.length === 0 && <span className="small muted">ยังไม่มีแท็ก</span>}
        {tags.map((t) => (
          <span key={t} className="chip chip--static">
            #{t}
            <button
              type="button"
              className="btn btn--ghost btn--icon btn--sm"
              style={{ width: 20, height: 20, padding: 0 }}
              onClick={() => onChange(tags.filter((x) => x !== t))}
              aria-label={`ลบแท็ก ${t}`}
            >
              <X size={12} />
            </button>
          </span>
        ))}
      </div>
      <div className="row" style={{ gap: 8 }}>
        <input
          className="input input--pill"
          value={text}
          placeholder="เพิ่มแท็ก"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          disabled={tags.length >= MAX_TAGS}
        />
        <button className="btn btn--soft btn--sm" onClick={add} disabled={tags.length >= MAX_TAGS}>
          เพิ่มแท็ก
        </button>
      </div>
      <span className="xsmall muted">
        ใช้ได้สูงสุด {MAX_TAGS} แท็ก (ใช้ {tags.length})
      </span>
    </div>
  );
}

function StoryThumb({ src, label }: { src: string; label: string }) {
  if (!src) {
    return (
      <div className="thumb" style={{ width: 104, height: 78 }}>
        <ImageIcon size={20} color="#a48cf0" />
      </div>
    );
  }
  return (
    <div className="thumb" style={{ width: 104, height: 78 }}>
      <img src={src} alt={label} />
    </div>
  );
}

/* ----------------------------------------------------------------- modals */

function ScriptModal({
  open,
  scripts,
  clips,
  onPick,
  onClose,
}: {
  open: boolean;
  scripts: ScriptSummary[];
  clips: ClipEntry[];
  onPick: (s: ScriptSummary) => void;
  onClose: () => void;
}) {
  return (
    <Modal open={open} title="เลือกเรื่องราว" icon={BookOpen} onClose={onClose} width={640}>
      {scripts.length === 0 ? (
        <EmptyState title="ยังไม่มีบทในระบบ" text="เพิ่มบทในหน้าบทก่อนจึงจะเลือกมาสร้างวิดีโอได้" />
      ) : (
        <div className="col" style={{ gap: 10 }}>
          {scripts.map((s) => (
            <button
              key={s.id}
              type="button"
              className="card"
              style={{
                display: "flex",
                gap: 12,
                alignItems: "center",
                padding: 10,
                textAlign: "left",
                cursor: "pointer",
                boxShadow: "none",
              }}
              onClick={() => {
                onPick(s);
                onClose();
              }}
            >
              <StoryThumb src={scriptThumb(s, clips)} label={s.title} />
              <span style={{ minWidth: 0 }}>
                <span style={{ display: "block", fontWeight: 700 }}>{s.title}</span>
                <span className="small muted clamp-2">{s.description || "-"}</span>
                <span className="row row--wrap" style={{ gap: 6, marginTop: 4 }}>
                  {s.genre && <Chip tone="mint">{s.genre}</Chip>}
                  <Chip tone="blue">{s.sceneCount} ฉาก</Chip>
                </span>
              </span>
            </button>
          ))}
        </div>
      )}
    </Modal>
  );
}

function ClipModal({
  open,
  clips,
  onPick,
  onClose,
}: {
  open: boolean;
  clips: ClipEntry[];
  onPick: (c: ClipEntry) => void;
  onClose: () => void;
}) {
  return (
    <Modal open={open} title="เลือกคลิปที่มีอยู่" icon={VideoIcon} onClose={onClose} width={640}>
      {clips.length === 0 ? (
        <EmptyState title="ยังไม่มีคลิปในระบบ" text="สร้างวิดีโอหรือนำเข้าไฟล์ก่อนจึงจะเลือกได้" />
      ) : (
        <div className="col" style={{ gap: 8 }}>
          {clips.map((c) => (
            <button
              key={c.folder || c.id}
              type="button"
              className="card"
              style={{
                display: "flex",
                gap: 12,
                alignItems: "center",
                padding: 10,
                textAlign: "left",
                cursor: "pointer",
                boxShadow: "none",
              }}
              onClick={() => {
                onPick(c);
                onClose();
              }}
            >
              <StoryThumb src={clipPoster(c)} label={c.title} />
              <span style={{ minWidth: 0 }}>
                <span style={{ display: "block", fontWeight: 700 }}>{c.title || c.id}</span>
                <span className="small muted">
                  {formatDuration(c.durationSeconds)} • {c.resolution || "-"} •{" "}
                  {STATUS_LABEL[c.status] ?? c.status}
                </span>
              </span>
            </button>
          ))}
        </div>
      )}
    </Modal>
  );
}

function LogModal({
  log,
  onClose,
}: {
  log: string[] | null;
  onClose: () => void;
}) {
  return (
    <Modal
      open={!!log}
      title="บันทึกการทำงานของระบบผู้เผยแพร่"
      icon={CheckCircle2}
      onClose={onClose}
      width={680}
      footer={
        <button className="btn btn--primary" onClick={onClose}>
          ปิด
        </button>
      }
    >
      {log && log.length > 0 ? (
        <div className="log">{log.join("\n")}</div>
      ) : (
        <EmptyState title="ไม่มีบันทึก" text="ระบบไม่ได้ทำงานในรอบนี้" />
      )}
    </Modal>
  );
}

/* -------------------------------------------------------------- data hooks */

function useScripts() {
  return useApiData<ScriptsResp>(() => apiGet<ScriptsResp>("/api/platform/scripts"));
}

function useClips() {
  return useApiData<ClipsResp>(() => apiGet<ClipsResp>("/api/platform/clips"));
}

function usePosting() {
  return useApiData<PostingResp>(() => apiGet<PostingResp>("/api/posting/status"));
}

/* ------------------------------------------------------------- publishing */

interface PublishResult {
  tone: "success" | "error" | "warn" | "info";
  title: string;
  text?: string;
  log: string[];
}

/** Local "YYYY-MM-DDTHH:mm:ss" stamp, same shape the engine writes into meta.json. */
function localStamp(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(
    d.getMinutes(),
  )}:${p(d.getSeconds())}`;
}

/**
 * Publishes through the real engine publisher and reports what actually happened.
 *
 * When a clip is selected we call the per-clip route (POST /api/publish/clip) so
 * exactly that clip goes out to exactly that platform. Without a clip we fall back
 * to the worker round (POST /api/scheduler/test), which lets the engine pick the
 * next eligible clip itself.
 */
async function publishNow(platform: PlatformKey, clip?: ClipEntry): Promise<PublishResult> {
  const startedAt = localStamp(new Date());
  const res = clip?.folder
    ? await apiPost<{ ok: boolean; jobId: string }>("/api/publish/clip", {
        folder: clip.folder,
        platform,
      })
    : await apiPost<{ ok: boolean; jobId: string }>("/api/scheduler/test", {
        schedule: { platforms: [platform] },
      });
  const jobId = res.jobId;
  let job: JobPayload | null = null;
  for (let i = 0; i < 150; i++) {
    await sleep(1000);
    const j = await apiGet<{ ok: boolean; job: JobPayload }>("/api/job", { id: jobId });
    if (j?.job) {
      job = j.job;
      if (job.status !== "running") break;
    }
  }
  const log = job?.log ?? [];

  let record: any = null;
  if (clip?.folder) {
    try {
      const detail = await apiGet<{ ok: boolean; meta: any }>("/api/clips/detail", { folder: clip.folder });
      const rec = detail?.meta?.posts?.[platform] ?? null;
      // Only trust a record that was written during this run, never an older one.
      if (rec?.at && String(rec.at) >= startedAt) record = rec;
    } catch {
      record = null;
    }
  }

  if (record?.status === "posted") {
    return {
      tone: "success",
      title: "โพสต์แล้ว",
      text: `${clip?.title || "คลิปที่เลือก"} ถูกเผยแพร่เรียบร้อย${record.url ? " (" + record.url + ")" : ""}`,
      log,
    };
  }
  if (record?.status === "draft_sent") {
    return {
      tone: "info",
      title: "ส่งเป็นแบบร่างแล้ว",
      text: "เปิดแอป TikTok แล้วเข้าแถบกล่องข้อความ (Inbox) เพื่อตรวจสอบและกดโพสต์เอง",
      log,
    };
  }
  if (record?.status === "failed") {
    return { tone: "error", title: "โพสต์ไม่สำเร็จ", text: record.error || "ดูบันทึกการทำงาน", log };
  }

  const failed = log.find((l) => l.includes("FAILED"));
  if (failed) return { tone: "error", title: "โพสต์ไม่สำเร็จ", text: failed.trim(), log };
  if (log.some((l) => l.includes("auto post is OFF")))
    return {
      tone: "warn",
      title: "ระบบผู้เผยแพร่ยังไม่ทำงาน",
      text: "โหมดการโพสต์อัตโนมัติปิดอยู่ — เปิดใช้งานได้ที่หน้าตั้งค่าโพสต์",
      log,
    };
  if (log.some((l) => l.includes("not connected")))
    return {
      tone: "error",
      title: "ยังไม่ได้เชื่อมต่อบัญชี",
      text: "เชื่อมต่อบัญชีได้ที่หน้าตั้งค่าโพสต์",
      log,
    };
  if (log.some((l) => l.includes("daily limit reached")))
    return {
      tone: "warn",
      title: "ถึงลิดจำกัดต่อวันแล้ว",
      text: "ระบบจะไม่โพสต์เกินจำนวนต่อวันที่ตั้งไว้ในหน้าตั้งค่าโพสต์",
      log,
    };
  if (log.some((l) => l.includes("already posted")))
    return { tone: "info", title: "คลิปนี้ถูกโพสต์ไปแล้ว", text: "ระบบไม่โพสต์คลิปซ้ำ", log };

  return {
    tone: "warn",
    title: "ยังไม่มีการเผยแพร่",
    text: "คลิปที่เลือกยังไม่ถูกเผยแพร่ — ดูบันทึกการทำงานด้านล่าง",
    log,
  };
}

/* ------------------------------------------------------------ social flow */

const METHODS: {
  key: "script" | "existing" | "flow" | "google";
  icon: LucideIcon;
  title: string;
  desc: string;
  badge: string;
  badgeTone: "primary" | "mint" | "orange" | "blue";
}[] = [
  {
    key: "script",
    icon: BookOpen,
    title: "สร้างจากบทในระบบ",
    desc: "เลือกจากบทเรื่องที่มีอยู่ในระบบ ที่สร้างไว้แล้ว กดเพื่อเรนเดอร์",
    badge: "แนะนำ",
    badgeTone: "primary",
  },
  {
    key: "existing",
    icon: FolderOpen,
    title: "ใช้วิดีโอที่มีอยู่",
    desc: "เลือกไฟล์วิดีโอจากเครื่อง แล้วนำเข้ามาใช้งานได้ทันที",
    badge: "",
    badgeTone: "blue",
  },
  {
    key: "flow",
    icon: Wand2,
    title: "สร้างด้วย Google Flow",
    desc: "คัดลอกพรอมต์ไปสร้างต่อที่ Google Flow (คุณต้องกดสร้างเอง)",
    badge: "ฟรี",
    badgeTone: "mint",
  },
  {
    key: "google",
    icon: Sparkles,
    title: "สร้างด้วย Google Generation",
    desc: "ให้ Google สร้างวิดีโอจากพรอมต์ (มีค่าใช้จ่าย ต้องตั้งค่า Gemini API Key)",
    badge: "เสียเงิน",
    badgeTone: "orange",
  },
];

function SocialFlow({ platform }: { platform: "tiktok" | "facebook_page" }) {
  const toast = useToast();
  const scriptsQ = useScripts();
  const clipsQ = useClips();
  const postingQ = usePosting();

  const scripts = scriptsQ.data?.scripts ?? [];
  const clips = clipsQ.data?.clips ?? [];
  const posting = normalizePosting(postingQ.data);
  const plat = posting.platforms[platform];

  const [scriptId, setScriptId] = useState("");
  const [clipFolder, setClipFolder] = useState("");
  const [method, setMethod] = useState<"script" | "existing" | "flow" | "google">("script");
  const [format, setFormat] = useState<Format>("vertical");
  const [duration, setDuration] = useState(30);
  const [style, setStyle] = useState("3d");
  const [character, setCharacter] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [prompt, setPrompt] = useState("");
  const [scriptOpen, setScriptOpen] = useState(false);
  const [clipOpen, setClipOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string[] | null>(null);

  const script = useMemo(() => scripts.find((s) => s.id === scriptId), [scripts, scriptId]);
  const clip = useMemo(() => clips.find((c) => c.folder === clipFolder), [clips, clipFolder]);

  useEffect(() => {
    if (!scriptId && scripts.length) {
      const first = scripts[0];
      setScriptId(first.id);
      setTitle(first.title || "");
      setDescription(first.description || "");
      setTags((first.tags || []).slice(0, MAX_TAGS));
      setPrompt(buildPrompt(first));
    }
  }, [scripts, scriptId]);

  useEffect(() => {
    setPrompt(buildPrompt(script, clip, { style, duration, character }));
  }, [script, clip, style, duration, character]);

  const characters = useMemo(() => {
    const set = new Set<string>();
    (script?.characters || []).forEach((c) => set.add(c));
    (clip?.characters || []).forEach((c) => set.add(c));
    return Array.from(set);
  }, [script, clip]);

  const label = PLATFORM_META[platform].label;
  const isDraft = platform === "tiktok";

  const publishDisabledReason = useMemo(() => {
    if (!plat?.connected) return "ยังไม่ได้เชื่อมต่อบัญชี";
    if (posting.mode === "off") return "โหมดการโพสต์อัตโนมัติยังปิดอยู่";
    if (!clip) return "ยังไม่ได้เลือกคลิป";
    return "";
  }, [plat, posting.mode, clip]);

  const enabledPublish = useMemo(() => {
    const list = Object.entries(posting.platforms)
      .filter(([, v]) => (v.settings || {}).enabled)
      .map(([k]) => PLATFORM_META[k]?.label ?? k);
    return list;
  }, [posting.platforms]);

  /* ------------------------------------------------------------- actions */

  const pickScript = (s: ScriptSummary) => {
    setScriptId(s.id);
    setTitle(s.title || "");
    setDescription(s.description || "");
    setTags((s.tags || []).slice(0, MAX_TAGS));
    setPrompt(buildPrompt(s, undefined, { style, duration, character }));
  };

  const importVideo = async (path: string) => {
    setBusy(true);
    try {
      const res = await apiPost<{ ok: boolean; folder: string; meta: any }>("/api/platform/import-video", {
        platform,
        path,
        title: title || "คลิปใหม่",
        description,
        tags,
        format,
      });
      toast.success("นำเข้าคลิปแล้ว", res?.meta?.title || res?.folder || "");
      clipsQ.reload();
    } catch (e) {
      toast.error("นำเข้าคลิปไม่สำเร็จ", errText(e));
    } finally {
      setBusy(false);
    }
  };

  const pickFile = async () => {
    try {
      const picked = await openFileDialog({
        multiple: false,
        directory: false,
        title: "เลือกไฟล์วิดีโอ",
        filters: [{ name: "วิดีโอ", extensions: ["mp4", "mov", "avi", "mkv", "webm", "m4v"] }],
      });
      if (typeof picked === "string" && picked) await importVideo(picked);
    } catch (e) {
      toast.error("เลือกไฟล์ไม่สำเร็จ", errText(e));
    }
  };

  const renderScript = async () => {
    if (!script) {
      setScriptOpen(true);
      return;
    }
    setBusy(true);
    try {
      const res = await apiPost<{ ok: boolean; jobId: string }>("/api/render", {
        path: script.path,
        format,
      });
      toast.info("เริ่มเรนเดอร์วิดีโอ", script.title);
      for (let i = 0; i < 180; i++) {
        await sleep(1000);
        const j = await apiGet<{ ok: boolean; job: JobPayload }>("/api/job", { id: res.jobId });
        if (j?.job && j.job.status !== "running") {
          if (j.job.status === "done") {
            toast.success("เรนเดอร์เสร็จแล้ว", script.title);
            clipsQ.reload();
          } else {
            toast.error("เรนเดอร์ไม่สำเร็จ", j.job.error || "ดูบันทึกการทำงาน");
          }
          break;
        }
      }
    } catch (e) {
      toast.error("เริ่มเรนเดอร์ไม่สำเร็จ", errText(e));
    } finally {
      setBusy(false);
    }
  };

  const analyzePrompt = async () => {
    try {
      const res = await apiPost<{ ok: boolean; analysis: any }>("/api/platform/analyze-prompt", {
        prompt,
        context: "video",
        duration,
      });
      const text = typeof res.analysis === "string" ? res.analysis : JSON.stringify(res.analysis, null, 2);
      setPrompt(text);
      toast.success("วิเคราะห์พรอมต์แล้ว", "พรอมต์ถูกปรับให้เหมาะกับวิดีโอของคุณ");
    } catch (e) {
      toast.error("วิเคราะห์พรอมต์ไม่สำเร็จ", errText(e));
    }
  };

  const copyPrompt = async () => {
    const ok = await copyText(prompt);
    if (ok) toast.success("คัดลอกพรอมต์แล้ว", "วางใน Google Flow เพื่อสร้างวิดีโอต่อ");
    else toast.error("คัดลอกไม่สำเร็จ", "ลองอีกครั้งหรือเลือกข้อความแล้วกดคัดลอกด้วยตัวเอง");
  };

  const openFlow = async () => {
    await copyText(prompt);
    await openUrl(FLOW_URL);
    toast.info("เปิด Google Flow แล้ว", "พรอมต์ถูกคัดลอกไว้ในคลิปบอร์ดแล้ว");
  };

  const googleVideo = async () => {
    setBusy(true);
    try {
      const res = await apiPost<{ ok: boolean; meta: any }>("/api/platform/google-video", {
        platform,
        prompt,
        title: title || "คลิปใหม่",
        description,
        tags,
        format,
      });
      toast.success("สร้างวิดีโอจาก Google แล้ว", res?.meta?.title || "");
      clipsQ.reload();
    } catch (e) {
      toast.error("สร้างวิดีโอด้วย Google ไม่สำเร็จ", `${errText(e)} — ลองใช้วิธีคัดลอกพรอมต์ไปที่ Google Flow แทน`);
    } finally {
      setBusy(false);
    }
  };

  const doPublish = async () => {
    setBusy(true);
    try {
      const res = await publishNow(platform, clip);
      if (res.tone === "success") toast.success(res.title, res.text);
      else if (res.tone === "error") toast.error(res.title, res.text);
      else if (res.tone === "info") toast.info(res.title, res.text);
      else toast.warn(res.title, res.text);
      setLog(res.log);
      clipsQ.reload();
    } catch (e) {
      toast.error("เรียกระบบผู้เผยแพร่ไม่สำเร็จ", errText(e));
    } finally {
      setBusy(false);
    }
  };

  const fillCaptionFromScript = () => {
    if (!script) return;
    setTitle(script.title || "");
    setDescription(script.description || "");
    setTags((script.tags || []).slice(0, MAX_TAGS));
    toast.info("เติมข้อมูลจากบทเรื่องแล้ว", script.title);
  };

  const manualUpload = async () => {
    const text = postCaption(title, description, tags);
    await copyText(text);
    await openUrl(isDraft ? TIKTOK_UPLOAD_URL : FACEBOOK_URL);
    toast.info(
      "คัดลอกชื่อเรื่อง คำบรรยาย และแฮชแท็กแล้ว",
      `เปิดหน้าอัปโหลดของ ${label} — ให้ตรวจสอบและกดโพสต์เอง`,
    );
  };

  /* --------------------------------------------------------------- render */

  const left = (
    <div className="col" style={{ gap: 16 }}>
      {/* step 1 */}
      <PastelCard>
        <StepHead
          n={1}
          tone="pink"
          title="เลือกเรื่องราว"
          text={`เลือกนิทานหรือเรื่องราวที่จะนำมาสร้างเป็นวิดีโอสำหรับ ${label}`}
          action={
            <button className="btn btn--soft btn--sm" onClick={() => setScriptOpen(true)}>
              <RefreshCw size={14} /> เปลี่ยนเรื่อง
            </button>
          }
        />
        {!script ? (
          <EmptyState
            title="ยังไม่ได้เลือกเรื่องราว"
            text="เลือกบทเรื่องจากระบบเพื่อนำมาสร้างวิดีโอ"
            icon={BookOpen}
            action={
              <button className="btn btn--primary btn--sm" onClick={() => setScriptOpen(true)}>
                <BookOpen size={14} /> เลือกเรื่องราว
              </button>
            }
          />
        ) : (
          <div className="row" style={{ alignItems: "flex-start", gap: 14 }}>
            <StoryThumb src={scriptThumb(script, clips)} label={script.title} />
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: "var(--fs-md)" }}>{script.title}</div>
              <div className="small muted clamp-2" style={{ marginTop: 2 }}>
                {script.description || "-"}
              </div>
              <div className="row row--wrap" style={{ gap: 6, marginTop: 8 }}>
                {script.genre && <Chip tone="mint">{script.genre}</Chip>}
                {(script.tags || []).slice(0, 4).map((t) => (
                  <Chip key={t} tone="orange">
                    {t}
                  </Chip>
                ))}
                {(script.characters || []).slice(0, 3).map((c) => (
                  <Chip key={c} tone="blue">
                    {CHAR_LABEL[c] ?? c}
                  </Chip>
                ))}
              </div>
            </div>
          </div>
        )}
      </PastelCard>

      {/* step 2 */}
      <PastelCard>
        <StepHead n={2} tone="blue" title="เลือกวิธีสร้างวิดีโอ" text="เลือกแผนการผลิตวิดีโอที่ต้องการ" />
        <div className="grid" style={{ gridTemplateColumns: "repeat(2, minmax(0,1fr))", gap: 12 }}>
          {METHODS.map((m) => (
            <Tile
              key={m.key}
              active={method === m.key}
              icon={m.icon}
              title={m.title}
              desc={m.desc}
              badge={m.badge}
              badgeTone={m.badgeTone}
              onClick={() => {
                setMethod(m.key);
                if (m.key === "script") void renderScript();
                if (m.key === "existing") void pickFile();
                if (m.key === "flow") void openFlow();
                if (m.key === "google") void googleVideo();
              }}
            />
          ))}
        </div>

        {method === "flow" || method === "google" ? (
          <div className="col" style={{ gap: 8, marginTop: 14 }}>
            <div className="field">
              <label className="field__label" htmlFor="prompt-social">
                พรอมต์สำหรับสร้างวิดีโอ
              </label>
              <textarea
                id="prompt-social"
                className="textarea"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                style={{ minHeight: 120 }}
              />
              <span className="field__hint">{prompt.length} ตัวอักษร</span>
            </div>
            <div className="row row--wrap" style={{ gap: 8 }}>
              <button className="btn btn--outline btn--sm" onClick={() => void analyzePrompt()}>
                <Wand2 size={14} /> วิเคราะห์พรอมต์
              </button>
              <button className="btn btn--outline btn--sm" onClick={() => void copyPrompt()}>
                <Copy size={14} /> คัดลอกพรอมต์
              </button>
              <button className="btn btn--soft btn--sm" onClick={() => void openFlow()}>
                <ExternalLink size={14} /> เปิด Google Flow
              </button>
              <button className="btn btn--primary btn--sm" onClick={() => void googleVideo()} disabled={busy}>
                <Sparkles size={14} /> ให้ Google สร้างวิดีโอ
              </button>
            </div>
            <span className="xsmall muted">
              ถ้า Google API ยังไม่ได้ตั้งค่า ระบบจะแจ้งข้อผิดพลาด — ใช้วิธีคัดลอกพรอมต์ไปสร้างที่ Google Flow แทนได้
            </span>
          </div>
        ) : null}
      </PastelCard>

      {/* step 3 */}
      <PastelCard>
        <StepHead n={3} tone="orange" title="ตั้งค่ารูปแบบวิดีโอ" text={`ปรับแต่งความยาวและรูปแบบให้เหมาะกับ ${label}`} />
        <div className="grid" style={{ gridTemplateColumns: "repeat(2, minmax(0,1fr))", gap: 16 }}>
          <div className="col" style={{ gap: 8 }}>
            <span className="field__label">
              <Type size={13} style={{ verticalAlign: "-2px" }} /> สัดส่วนภาพ
            </span>
            <RatioRow value={format} onChange={setFormat} />
          </div>
          <div className="col" style={{ gap: 8 }}>
            <span className="field__label">
              <Clock size={13} style={{ verticalAlign: "-2px" }} /> ความยาววิดีโอ
            </span>
            <DurationRow value={duration} onChange={setDuration} hint="ความยาวที่ต้องการสร้าง" />
          </div>
          <div className="col" style={{ gap: 8 }}>
            <span className="field__label">สไตล์วิดีโอ</span>
            <div className="col" style={{ gap: 6 }}>
              {STYLE_OPTIONS.map((s) => (
                <label key={s.key} className="checkbox">
                  <input
                    type="radio"
                    name="style-social"
                    checked={style === s.key}
                    onChange={() => setStyle(s.key)}
                  />
                  <span>{s.label}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="col" style={{ gap: 8 }}>
            <label className="field__label" htmlFor="character-social">
              ตัวละครที่ใช้
            </label>
            <select
              id="character-social"
              className="select"
              value={character}
              onChange={(e) => setCharacter(e.target.value)}
            >
              <option value="">-- เลือกตัวละคร --</option>
              {characters.map((c) => (
                <option key={c} value={c}>
                  {CHAR_LABEL[c] ?? c}
                </option>
              ))}
            </select>
            <span className="field__hint">
              {characters.length ? "ตัวละครที่พบในเรื่องราวหรือคลิปที่เลือก" : "ไม่พบข้อมูลตัวละครในรายการที่เลือก"}
            </span>
          </div>
        </div>
      </PastelCard>
    </div>
  );

  const right = (
    <div className="col" style={{ gap: 16 }}>
      {/* step 4 */}
      <PastelCard>
        <StepHead
          n={4}
          tone="primary"
          title="คำบรรยายและข้อมูลโพสต์"
          text="AI ช่วยคำบรรยายให้คุณได้ คุณแก้ไขได้ตามต้องการ"
          action={
            <button className="btn btn--soft btn--sm" onClick={fillCaptionFromScript} disabled={!script}>
              <RefreshCw size={14} /> สร้างใหม่
            </button>
          }
        />
        <div className="col" style={{ gap: 14 }}>
          <div className="field">
            <label className="field__label" htmlFor="social-title">
              ชื่อเรื่อง (Title)
            </label>
            <input
              id="social-title"
              className="input"
              value={title}
              maxLength={100}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="ใส่ชื่อเรื่อง"
            />
            <span className="field__hint">{title.length}/100</span>
          </div>
          <div className="field">
            <label className="field__label" htmlFor="social-desc">
              คำอธิบาย (Description)
            </label>
            <textarea
              id="social-desc"
              className="textarea"
              value={description}
              maxLength={500}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="ใส่คำอธิบาย"
            />
            <span className="field__hint">{description.length}/500</span>
          </div>
          <div className="field">
            <span className="field__label">แท็ก (Tags)</span>
            <TagEditor tags={tags} onChange={setTags} />
          </div>
        </div>
      </PastelCard>

      {/* step 5 */}
      <PastelCard>
        <StepHead
          n={5}
          tone="mint"
          title="วิดีโอที่สร้างเสร็จ"
          text={`ตรวจสอบวิดีโอก่อนส่งไปยัง ${label}`}
          action={
            <button className="btn btn--soft btn--sm" onClick={() => setClipOpen(true)}>
              <FolderOpen size={14} /> เลือกคลิป
            </button>
          }
        />

        <div className="col" style={{ gap: 12 }}>
          {clips.length === 0 ? (
            <EmptyState title="ยังไม่มีคลิปในระบบ" text="สร้างวิดีโอหรือนำเข้าไฟล์ก่อนจึงจะเลือกมาส่งต่อได้" icon={VideoIcon} />
          ) : (
            <ClipStrip
              clips={clips.map((c) => ({
                thumb: clipPoster(c),
                durationSeconds: c.durationSeconds,
                title: c.title || c.id,
              }))}
              onPick={(i) => setClipFolder(clips[i]?.folder || "")}
            />
          )}

          <VideoPlayer
            src={clipVideo(clip)}
            poster={clipPoster(clip)}
            aspect={format === "horizontal" ? "16:9" : "9:16"}
          />

          {clip ? (
            <div className="card card--soft" style={{ padding: 14 }}>
              <div className="row row--between" style={{ marginBottom: 8 }}>
                <span style={{ fontWeight: 700 }}>{clip.title || clip.id}</span>
                <StatusBadge tone={statusTone(clip.status)}>
                  {STATUS_LABEL[clip.status] ?? clip.status ?? "-"}
                </StatusBadge>
              </div>
              <div className="col" style={{ gap: 6 }}>
                <div className="row row--between small">
                  <span className="muted">รูปแบบ</span>
                  <span>{format === "horizontal" ? "16:9" : "9:16"}</span>
                </div>
                <div className="row row--between small">
                  <span className="muted">ความยาว</span>
                  <span>{clip.durationSeconds ? `${clip.durationSeconds} วินาที` : "-"}</span>
                </div>
                <div className="row row--between small">
                  <span className="muted">ความละเอียด</span>
                  <span>{clip.resolution || "-"}</span>
                </div>
                <div className="row row--between small">
                  <span className="muted">ประเภทไฟล์</span>
                  <span>MP4</span>
                </div>
                {(clip.needsReview || []).length > 0 && (
                  <div className="row row--between small">
                    <span className="muted">ต้องตรวจสอบ</span>
                    <span>{(clip.needsReview || []).join(", ")}</span>
                  </div>
                )}
              </div>
            </div>
          ) : null}

          <div className="row" style={{ gap: 10 }}>
            <button
              className="btn btn--outline"
              onClick={() => setPreviewOpen(true)}
              disabled={!clip}
            >
              <Play size={15} /> ดูตัวอย่าง
            </button>
            <button
              className="btn btn--pink btn--lg"
              style={{ flex: 1 }}
              onClick={() => void doPublish()}
              disabled={busy || !!publishDisabledReason}
            >
              {isDraft ? <Music2 size={18} /> : <Send size={18} />}
              {busy
                ? "กำลังทำงาน..."
                : isDraft
                  ? `ส่งเป็นแบบร่างไปยัง ${label}`
                  : `โพสต์ไปยัง ${label}`}
            </button>
          </div>

          <button
            className="btn btn--outline btn--sm"
            style={{ alignSelf: "flex-start" }}
            onClick={() => void manualUpload()}
          >
            <ExternalLink size={14} /> เปิดหน้าอัปโหลดของ {label} แล้ววางข้อความเอง
          </button>

          {publishDisabledReason ? (
            <div className="row row--between" style={{ gap: 10, flexWrap: "wrap" }}>
              <span className="xsmall muted">
                <AlertTriangle size={12} style={{ verticalAlign: "-2px" }} /> {publishDisabledReason}
              </span>
              <Link className="btn btn--soft btn--sm" to="/posting-settings">
                ไปที่หน้าตั้งค่าโพสต์
              </Link>
            </div>
          ) : (
            <span className="xsmall muted">
              {isDraft
                ? "การส่งจะเป็นแบบร่างในแอป TikTok คุณต้องกดโพสต์เองในแอป (กติกาของ TikTok)"
                : `ระบบจะส่งคลิปที่พร้อมเผยแพร่ 1 คลิป ไปยังแพลตฟอร์มที่เปิดใช้งานไว้${
                    enabledPublish.length ? ": " + enabledPublish.join(", ") : ""
                  }`}
            </span>
          )}
        </div>
      </PastelCard>
    </div>
  );

  return (
    <div className="col" style={{ gap: 16 }}>
      <div
        className="grid"
        style={{ gridTemplateColumns: "minmax(0, 1.05fr) minmax(0, 0.95fr)", alignItems: "start", gap: 16 }}
      >
        {left}
        {right}
      </div>

      <ScriptModal
        open={scriptOpen}
        scripts={scripts}
        clips={clips}
        onPick={pickScript}
        onClose={() => setScriptOpen(false)}
      />
      <ClipModal
        open={clipOpen}
        clips={clips}
        onPick={(c) => setClipFolder(c.folder || "")}
        onClose={() => setClipOpen(false)}
      />
      <LogModal log={log} onClose={() => setLog(null)} />
      <Modal
        open={previewOpen}
        title={`ตัวอย่างวิดีโอ${clip ? " — " + clip.title : ""}`}
        icon={Play}
        onClose={() => setPreviewOpen(false)}
        width={640}
        footer={
          <button className="btn btn--primary" onClick={() => setPreviewOpen(false)}>
            ปิด
          </button>
        }
      >
        <VideoPlayer
          src={clipVideo(clip)}
          poster={clipPoster(clip)}
          aspect={format === "horizontal" ? "16:9" : "9:16"}
        />
      </Modal>
    </div>
  );
}

/* ------------------------------------------------------------ youtube flow */

function YouTubeFlow() {
  const toast = useToast();
  const scriptsQ = useScripts();
  const clipsQ = useClips();
  const postingQ = usePosting();

  const scripts = scriptsQ.data?.scripts ?? [];
  const clips = clipsQ.data?.clips ?? [];
  const posting = normalizePosting(postingQ.data);
  const yt = posting.platforms.youtube;

  const [scriptId, setScriptId] = useState("");
  const [clipFolder, setClipFolder] = useState("");
  const [format, setFormat] = useState<Format>("vertical");
  const [madeForKids, setMadeForKids] = useState(true);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [visibility, setVisibility] = useState("public");
  const [scriptOpen, setScriptOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string[] | null>(null);
  const [dropHint, setDropHint] = useState("");

  const script = useMemo(() => scripts.find((s) => s.id === scriptId), [scripts, scriptId]);
  const clip = useMemo(() => clips.find((c) => c.folder === clipFolder), [clips, clipFolder]);

  useEffect(() => {
    if (!scriptId && scripts.length) {
      const first = scripts[0];
      setScriptId(first.id);
      setTitle(first.title || "");
      setDescription(first.description || "");
      setTags((first.tags || []).slice(0, MAX_TAGS));
    }
  }, [scripts, scriptId]);

  const importRef = useRef<(path: string) => Promise<void>>(async () => {});

  const importVideo = async (path: string) => {
    setBusy(true);
    try {
      const res = await apiPost<{ ok: boolean; folder: string; meta: any }>("/api/platform/import-video", {
        platform: "youtube",
        path,
        title: title || "คลิปใหม่",
        description,
        tags,
        format,
      });
      toast.success("นำเข้าคลิปแล้ว", res?.meta?.title || res?.folder || "");
      clipsQ.reload();
    } catch (e) {
      toast.error("นำเข้าคลิปไม่สำเร็จ", errText(e));
    } finally {
      setBusy(false);
    }
  };
  importRef.current = importVideo;

  useEffect(() => {
    // Drag & drop is a desktop-shell feature; skip it outside Tauri.
    if (typeof window === "undefined" || !("__TAURI_INTERNALS__" in window)) return;
    let alive = true;
    let unlisten: (() => void) | undefined;
    getCurrentWebview()
      .onDragDropEvent((event) => {
        const p = event.payload;
        if (p.type === "drop") {
          const path = p.paths?.[0];
          if (path) void importRef.current(path);
        } else if (p.type === "enter" || p.type === "over") {
          setDropHint("ปล่อยไฟล์เพื่อนำเข้า");
        } else {
          setDropHint("");
        }
      })
      .then((un) => {
        if (alive) unlisten = un;
        else un();
      })
      .catch(() => {});
    return () => {
      alive = false;
      unlisten?.();
    };
  }, []);

  const pickFile = async () => {
    try {
      const picked = await openFileDialog({
        multiple: false,
        directory: false,
        title: "เลือกไฟล์วิดีโอ",
        filters: [{ name: "วิดีโอ", extensions: ["mp4", "mov", "avi", "mkv", "webm", "m4v"] }],
      });
      if (typeof picked === "string" && picked) await importVideo(picked);
    } catch (e) {
      toast.error("เลือกไฟล์ไม่สำเร็จ", errText(e));
    }
  };

  const doPublish = async () => {
    setBusy(true);
    try {
      const res = await publishNow("youtube", clip);
      if (res.tone === "success") toast.success(res.title, res.text);
      else if (res.tone === "error") toast.error(res.title, res.text);
      else if (res.tone === "info") toast.info(res.title, res.text);
      else toast.warn(res.title, res.text);
      setLog(res.log);
      clipsQ.reload();
    } catch (e) {
      toast.error("เรียกระบบผู้เผยแพร่ไม่สำเร็จ", errText(e));
    } finally {
      setBusy(false);
    }
  };

  const blockedReason = !yt?.connected
    ? "ยังไม่ได้เชื่อมต่อบัญชี"
    : posting.mode === "off"
      ? "โหมดการโพสต์อัตโนมัติยังปิดอยู่"
      : !clip
        ? "ยังไม่ได้เลือกคลิป"
        : "";

  const manualUpload = async () => {
    await copyText(postCaption(title, description, tags));
    await openUrl(YOUTUBE_UPLOAD_URL);
    toast.info("คัดลอกชื่อเรื่อง คำบรรยาย และแฮชแท็กแล้ว", "เปิด YouTube Studio ให้อัปโหลดและกดโพสต์เอง");
  };

  const sources: { key: string; icon: LucideIcon; title: string; desc: string; badge?: string }[] = [
    {
      key: "file",
      icon: FolderOpen,
      title: "ไฟล์ในเครื่อง",
      desc: "อัปโหลดไฟล์วิดีโอที่มีอยู่ (MP4, MOV, AVI)",
    },
    {
      key: "library",
      icon: VideoIcon,
      title: "นำเข้าจากคลังคลิป",
      desc: "เลือกคลิปที่สร้างไว้แล้วในระบบมาใช้งาน",
    },
    {
      key: "flow",
      icon: Wand2,
      title: "Google Flow",
      desc: "คัดลอกพรอมต์ไปสร้างต่อที่ Google Flow",
      badge: "ใหม่",
    },
    {
      key: "google",
      icon: Sparkles,
      title: "Google สร้างวิดีโอ API",
      desc: "สร้างวิดีโอด้วย AI อัตโนมัติในโปรแกรม (มีค่าใช้จ่าย)",
    },
  ];

  return (
    <div
      className="grid"
      style={{ gridTemplateColumns: "minmax(0, 1.1fr) minmax(0, 0.9fr)", alignItems: "start", gap: 16 }}
    >
      <div className="col" style={{ gap: 16 }}>
        <PastelCard>
          <StepHead
            n={1}
            tone="pink"
            title="เลือกเรื่องที่จะสร้าง"
            text="เลือกจากบทที่เตรียมไว้ หรือสร้างบทใหม่ที่หน้าแผนงาน"
            action={
              <button className="btn btn--soft btn--sm" onClick={() => setScriptOpen(true)}>
                <Sparkles size={14} /> สร้างบทใหม่
              </button>
            }
          />
          {scripts.length === 0 ? (
            <EmptyState
              title="ยังไม่มีบทในระบบ"
              text="สร้างบทที่หน้าแผนงานหรือหน้าบทก่อน"
              icon={BookOpen}
              action={
                <button className="btn btn--primary btn--sm" onClick={() => setScriptOpen(true)}>
                  เลือกบท
                </button>
              }
            />
          ) : (
            <div className="grid" style={{ gridTemplateColumns: "repeat(4, minmax(0,1fr))", gap: 12 }}>
              {scripts.slice(0, 4).map((s) => (
                <Tile
                  key={s.id}
                  active={s.id === scriptId}
                  icon={BookOpen}
                  title={s.title}
                  desc={s.description}
                  onClick={() => {
                    setScriptId(s.id);
                    setTitle(s.title || "");
                    setDescription(s.description || "");
                    setTags((s.tags || []).slice(0, MAX_TAGS));
                  }}
                />
              ))}
            </div>
          )}
        </PastelCard>

        <PastelCard>
          <StepHead n={2} tone="blue" title="รูปแบบวิดีโอ" text="เลือกคัดส่วนวิดีโอให้เหมาะกับ YouTube" />
          <div className="grid" style={{ gridTemplateColumns: "repeat(2, minmax(0,1fr))", gap: 12 }}>
            <Tile
              active={format === "vertical"}
              icon={VideoIcon}
              title="YouTube Shorts"
              desc="แนวตั้ง 9:16 เหมาะกับคลิปสั้น ความยาว 15-60 วินาที"
              onClick={() => setFormat("vertical")}
            />
            <Tile
              active={format === "horizontal"}
              icon={VideoIcon}
              title="YouTube แนวนอน"
              desc="แนวนอน 16:9 เหมาะกับวิดีโอความยาว 1-10 นาที"
              onClick={() => setFormat("horizontal")}
            />
          </div>
          <label className="checkbox" style={{ marginTop: 12 }}>
            <input
              type="checkbox"
              checked={madeForKids}
              onChange={(e) => setMadeForKids(e.target.checked)}
            />
            <span>เหมาะสำหรับเด็ก (Made for Kids)</span>
          </label>
          <span className="field__hint" style={{ marginTop: 4 }}>
            ตัวเลือกนี้จะถูกใส่ในพรอมต์ตอนสร้างวิดีโอใหม่ (คลิปที่นำเข้าจะใช้ค่าเริ่มต้นของระบบ)
          </span>
        </PastelCard>

        <PastelCard>
          <StepHead n={3} tone="orange" title="เลือกแหล่งวิดีโอ" text="อัปโหลดคลิปเพื่อทำงานต่อ หรือเชื่อมต่อกับ Google Flow" />
          <div className="grid" style={{ gridTemplateColumns: "repeat(2, minmax(0,1fr))", gap: 12 }}>
            {sources.map((s) => (
              <Tile
                key={s.key}
                active={false}
                icon={s.icon}
                title={s.title}
                desc={s.desc}
                badge={s.badge}
                badgeTone="pink"
                onClick={() => {
                  if (s.key === "file") void pickFile();
                  if (s.key === "library") {
                    const first = clips[0];
                    if (!first) {
                      toast.warn("ยังไม่มีคลิปในคลัง", "สร้างคลิปก่อน หรือเลือกไฟล์ในเครื่อง");
                      return;
                    }
                    setClipFolder(first.folder || "");
                  }
                  if (s.key === "flow") {
                    void copyText(buildPrompt(script, clip, { madeForKids }));
                    void openUrl(FLOW_URL);
                    toast.info("เปิด Google Flow แล้ว", "พรอมต์ถูกคัดลอกไว้แล้ว");
                  }
                  if (s.key === "google") {
                    void (async () => {
                      setBusy(true);
                      try {
                        const res = await apiPost<{ ok: boolean; meta: any }>("/api/platform/google-video", {
                          platform: "youtube",
                          prompt: buildPrompt(script, clip, { madeForKids }),
                          title: title || "คลิปใหม่",
                          description,
                          tags,
                          format,
                        });
                        toast.success("สร้างวิดีโอแล้ว", res?.meta?.title || "");
                        clipsQ.reload();
                      } catch (e) {
                        toast.error("สร้างวิดีโอไม่สำเร็จ", `${errText(e)} — ลองใช้ Google Flow แทน`);
                      } finally {
                        setBusy(false);
                      }
                    })();
                  }
                }}
              />
            ))}
          </div>

          <div
            className="card card--soft"
            style={{
              marginTop: 14,
              border: "1.5px dashed var(--c-line-strong)",
              textAlign: "center",
              padding: 18,
            }}
          >
            <Upload size={20} color="var(--c-primary)" />
            <div style={{ fontWeight: 700, marginTop: 6 }}>
              ลากไฟล์วิดีโอมาวางที่นี่ หรือกดเลือกไฟล์ในเครื่อง
            </div>
            <div className="xsmall muted" style={{ marginTop: 2 }}>
              {dropHint || "รองรับไฟล์ MP4, MOV, AVI (ขนาดไม่เกิน 2 GB)"}
            </div>
            <button className="btn btn--soft btn--sm" style={{ marginTop: 10 }} onClick={() => void pickFile()}>
              <FolderOpen size={14} /> เลือกไฟล์ในเครื่อง
            </button>
          </div>
        </PastelCard>
      </div>

      <div className="col" style={{ gap: 16 }}>
        <PastelCard>
          <StepHead
            n={4}
            tone="mint"
            title="ตัวอย่างคลิปที่เลือก"
            text="ตรวจสอบวิดีโอก่อนโพสต์ลง YouTube"
            action={
              clips.length ? (
                <select
                  className="select"
                  style={{ width: 220 }}
                  value={clipFolder}
                  onChange={(e) => setClipFolder(e.target.value)}
                >
                  <option value="">-- เลือกคลิป --</option>
                  {clips.map((c) => (
                    <option key={c.folder} value={c.folder}>
                      {c.title || c.id}
                    </option>
                  ))}
                </select>
              ) : undefined
            }
          />
          <VideoPlayer
            src={clipVideo(clip)}
            poster={clipPoster(clip)}
            aspect={format === "horizontal" ? "16:9" : "9:16"}
          />
          {clip ? (
            <div className="row row--between small" style={{ marginTop: 8 }}>
              <span className="muted">ความยาว</span>
              <span>{clip.durationSeconds ? `${clip.durationSeconds} วินาที` : "-"}</span>
            </div>
          ) : null}
        </PastelCard>

        <PastelCard>
          <StepHead
            n={5}
            tone="primary"
            title="ข้อมูลสำหรับ YouTube"
            text="กรอกข้อมูลให้ครบก่อนโพสต์"
            action={
              <Link className="btn btn--soft btn--sm" to="/posting-settings">
                ใช้ข้อมูลอุปกรณ์
              </Link>
            }
          />
          <div className="col" style={{ gap: 14 }}>
            <div className="field">
              <label className="field__label" htmlFor="yt-title">
                ชื่อเรื่อง (Title) *
              </label>
              <input
                id="yt-title"
                className="input"
                value={title}
                maxLength={100}
                onChange={(e) => setTitle(e.target.value)}
              />
              <span className="field__hint">{title.length}/100</span>
            </div>
            <div className="field">
              <label className="field__label" htmlFor="yt-desc">
                คำอธิบาย (Description)
              </label>
              <textarea
                id="yt-desc"
                className="textarea"
                value={description}
                maxLength={5000}
                onChange={(e) => setDescription(e.target.value)}
                style={{ minHeight: 140 }}
              />
              <span className="field__hint">{description.length}/5000</span>
            </div>
            <div className="field">
              <span className="field__label">แท็ก (Tags)</span>
              <TagEditor tags={tags} onChange={setTags} />
            </div>
            <div className="field">
              <span className="field__label">การมองเห็น (Visibility)</span>
              <div className="row row--wrap" style={{ gap: 14 }}>
                {[
                  { key: "public", label: "สาธารณะ" },
                  { key: "unlisted", label: "ไม่สาธารณะ" },
                  { key: "private", label: "ส่วนตัว" },
                ].map((v) => (
                  <label key={v.key} className="checkbox">
                    <input
                      type="radio"
                      name="visibility"
                      checked={visibility === v.key}
                      onChange={() => setVisibility(v.key)}
                    />
                    <span>{v.label}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="row" style={{ gap: 10 }}>
              <button className="btn btn--outline" onClick={() => void manualUpload()}>
                <ExternalLink size={15} /> เปิด YouTube Studio
              </button>
              <Link className="btn btn--outline" to="/scheduler">
                <Clock size={15} /> ตั้งเวลาโพสต์
              </Link>
              <button
                className="btn btn--lg"
                style={{
                  flex: 1,
                  background: "linear-gradient(135deg, #ff5a5a 0%, #e02d2d 100%)",
                  color: "#fff",
                  boxShadow: "0 4px 12px rgba(224, 45, 45, 0.28)",
                }}
                onClick={() => void doPublish()}
                disabled={busy || !!blockedReason}
              >
                <Send size={18} />
                {busy ? "กำลังทำงาน..." : "โพสต์ไปยัง YouTube"}
              </button>
            </div>
            {blockedReason ? (
              <div className="row row--between" style={{ gap: 10, flexWrap: "wrap" }}>
                <span className="xsmall muted">
                  <AlertTriangle size={12} style={{ verticalAlign: "-2px" }} /> {blockedReason}
                </span>
                <Link className="btn btn--soft btn--sm" to="/posting-settings">
                  ไปที่หน้าตั้งค่าโพสต์
                </Link>
              </div>
            ) : (
              <span className="xsmall muted">
                ระบบจะโพสต์คลิปที่พร้อมเผยแพร่ 1 คลิปไปยัง YouTube
                {yt?.accountName ? ` (บัญชี ${yt.accountName})` : ""}
              </span>
            )}
          </div>
        </PastelCard>
      </div>

      <ScriptModal
        open={scriptOpen}
        scripts={scripts}
        clips={clips}
        onPick={(s) => {
          setScriptId(s.id);
          setTitle(s.title || "");
          setDescription(s.description || "");
          setTags((s.tags || []).slice(0, MAX_TAGS));
        }}
        onClose={() => setScriptOpen(false)}
      />
      <LogModal log={log} onClose={() => setLog(null)} />
    </div>
  );
}

/* -------------------------------------------------------------- shopee flow */

const SHOPEE_STORIES = [
  { key: "review", title: "รีวิวสินค้า", desc: "แนะนำสินค้าคุ้มค่า", icon: Sparkles },
  { key: "howto", title: "how to ใช้สินค้า", desc: "สอนใช้สินค้า", icon: BookOpen },
  { key: "compare", title: "เปรียบเทียบสินค้า", desc: "เทียบรุ่นก่อนซื้อ", icon: CheckCircle2 },
  { key: "unbox", title: "แกะกล่อง", desc: "ดีไซน์ มีของแถม", icon: Type },
];

const SHOPEE_SOURCES = [
  { key: "script", title: "คลิปจากบทเรื่อง", desc: "เรนเดอร์จากบทเรื่องในระบบ (ฟรี/ใช้เครื่อง)", badge: "แนะนำ", badgeTone: "primary" as const, icon: BookOpen },
  { key: "import", title: "นำเข้าคลิปที่มีอยู่", desc: "เลือกไฟล์วิดีโอจากเครื่อง", badge: "", badgeTone: "blue" as const, icon: Upload },
  { key: "flow", title: "สร้างจากคำสั่งซื้อ Google Flow", desc: "คัดลอกพรอมต์แล้วไปสร้างต่อที่ Google Flow", badge: "ฟรี", badgeTone: "mint" as const, icon: Wand2 },
  { key: "google", title: "สร้างวิดีโอด้วย AI Google Flow", desc: "สร้างวิดีโออัตโนมัติในโปรแกรม (มีค่าใช้จ่าย)", badge: "เสียเงิน", badgeTone: "orange" as const, icon: Sparkles },
];

function ShopeeFlow() {
  const toast = useToast();
  const scriptsQ = useScripts();
  const clipsQ = useClips();
  const productsQ = useApiData<{ ok: boolean; products: any[]; total: number }>(() =>
    apiGet("/api/shopee/products", { perPage: 12 }),
  );

  const scripts = scriptsQ.data?.scripts ?? [];
  const clips = clipsQ.data?.clips ?? [];
  const products = productsQ.data?.products ?? [];

  const [story, setStory] = useState("review");
  const [product, setProduct] = useState<any>(null);
  const [productOpen, setProductOpen] = useState(false);
  const [caption, setCaption] = useState("");
  const [clipFolder, setClipFolder] = useState("");
  const [format, setFormat] = useState<Format>("vertical");
  const [duration, setDuration] = useState(30);
  const [character, setCharacter] = useState("");
  const [music, setMusic] = useState(true);
  const [overlay, setOverlay] = useState(true);
  const [sticker, setSticker] = useState(true);
  const [busy, setBusy] = useState(false);
  const [title, setTitle] = useState("");

  const clip = useMemo(() => clips.find((c) => c.folder === clipFolder), [clips, clipFolder]);

  const characters = useMemo(() => {
    const set = new Set<string>();
    (clip?.characters || []).forEach((c) => set.add(c));
    scripts.forEach((s) => (s.characters || []).forEach((c) => set.add(c)));
    return Array.from(set);
  }, [clip, scripts]);

  const hashtags = useMemo(() => {
    const base = ["#ช้อปปี้Shopee", "#รีวิวสินค้า", "#ของมันต้องมี", "#TaoYongStudio"];
    if (product?.category) base.unshift("#" + String(product.category).replace(/\s+/g, ""));
    return base;
  }, [product]);

  const extraOptions = useMemo(
    () =>
      [music ? "เพิ่มเพลงพื้นหลัง" : "", overlay ? "เพิ่มข้อความบนวิดีโอ" : "", sticker ? "เพิ่มสติกเกอร์" : ""]
        .filter(Boolean)
        .join(", "),
    [music, overlay, sticker],
  );

  const shopeePrompt = useMemo(() => {
    const base = buildPrompt(scripts[0], clip, { duration, character });
    return extraOptions ? `${base}\nตัวเลือกเพิ่มเติม: ${extraOptions}` : base;
  }, [scripts, clip, duration, character, extraOptions]);

  const checklist = useMemo(() => {
    return [
      { ok: !!product, text: "มีข้อมูลสินค้าที่จะโปรโมต" },
      { ok: caption.trim().length > 0, text: "มีข้อความสำหรับโพสต์" },
      { ok: caption.length <= 500, text: "ข้อความไม่เกิน 500 ตัวอักษร" },
      { ok: !!clip, text: "มีคลิปวิดีโอพร้อมโพสต์" },
      { ok: hashtags.length > 0, text: "มีแฮชแท็กแนะนำ" },
    ];
  }, [product, caption, clip, hashtags]);

  const selectProduct = (p: any) => {
    setProduct(p);
    const price = p?.sale_price ?? p?.price ?? 0;
    const discount =
      p?.original_price && price && Number(p.original_price) > Number(price)
        ? ` ลด ${Math.round((1 - Number(price) / Number(p.original_price)) * 100)}%`
        : "";
    setCaption(
      [
        `💧 กระตุ้นน้ำพร้อม ลากาสักห้าทห้าม ${p?.name || ""}`,
        price ? `ราคา ฿${Number(price).toLocaleString("th-TH")}${discount}` : "",
        p?.rating ? `⭐ คะแนน ${Number(p.rating).toFixed(1)}/5` : "",
        p?.sold_count ? `ยอดสั่งซื้อแล้ว ${Number(p.sold_count).toLocaleString("th-TH")} ชิ้น` : "",
        p?.seller_name ? `ร้านค้า: ${p.seller_name}` : "",
        "",
        "สั่งซื้อ Shopee ที่ลิงก์ด้านล่างได้เลยค่ะ 👇",
        p?.product_url ? `👉 ${p.product_url}` : "",
      ]
        .filter(Boolean)
        .join("\n")
    );
    setTitle(p?.name ? `กระตุ้นน้ำพร้อม ลากาสักห้าทห้าม ${p.name}` : "");
  };

  const importVideo = async (path: string) => {
    setBusy(true);
    try {
      const res = await apiPost<{ ok: boolean; folder: string; meta: any }>("/api/platform/import-video", {
        platform: "shopee",
        path,
        title: title || product?.name || "คลิป Shopee",
        description: caption,
        tags: hashtags.map((h) => h.replace("#", "")),
        format,
      });
      toast.success("นำเข้าคลิปแล้ว", res?.meta?.title || res?.folder || "");
      clipsQ.reload();
    } catch (e) {
      toast.error("นำเข้าคลิปไม่สำเร็จ", errText(e));
    } finally {
      setBusy(false);
    }
  };

  const pickFile = async () => {
    try {
      const picked = await openFileDialog({
        multiple: false,
        directory: false,
        title: "เลือกไฟล์วิดีโอ",
        filters: [{ name: "วิดีโอ", extensions: ["mp4", "mov", "avi", "mkv", "webm", "m4v"] }],
      });
      if (typeof picked === "string" && picked) await importVideo(picked);
    } catch (e) {
      toast.error("เลือกไฟล์ไม่สำเร็จ", errText(e));
    }
  };

  const renderScript = async () => {
    const s = scripts[0];
    if (!s) {
      toast.warn("ยังไม่มีบทเรื่องในระบบ", "สร้างบทที่หน้าบทก่อน");
      return;
    }
    setBusy(true);
    try {
      const res = await apiPost<{ ok: boolean; jobId: string }>("/api/render", { path: s.path, format });
      toast.info("เริ่มเรนเดอร์วิดีโอ", s.title);
      for (let i = 0; i < 180; i++) {
        await sleep(1000);
        const j = await apiGet<{ ok: boolean; job: JobPayload }>("/api/job", { id: res.jobId });
        if (j?.job && j.job.status !== "running") {
          if (j.job.status === "done") {
            toast.success("เรนเดอร์เสร็จแล้ว", s.title);
            clipsQ.reload();
          } else {
            toast.error("เรนเดอร์ไม่สำเร็จ", j.job.error || "ดูบันทึกการทำงาน");
          }
          break;
        }
      }
    } catch (e) {
      toast.error("เรนเดอร์ไม่สำเร็จ", errText(e));
    } finally {
      setBusy(false);
    }
  };

  const openFlow = async () => {
    await copyText(shopeePrompt);
    await openUrl(FLOW_URL);
    toast.info("เปิด Google Flow แล้ว", "พรอมต์ถูกคัดลอกไว้แล้ว");
  };

  const googleVideo = async () => {
    setBusy(true);
    try {
      const res = await apiPost<{ ok: boolean; meta: any }>("/api/platform/google-video", {
        platform: "shopee",
        prompt: shopeePrompt,
        title: title || product?.name || "คลิป Shopee",
        description: caption,
        tags: hashtags.map((h) => h.replace("#", "")),
        format,
      });
      toast.success("สร้างวิดีโอแล้ว", res?.meta?.title || "");
      clipsQ.reload();
    } catch (e) {
      toast.error("สร้างวิดีโอด้วย Google ไม่สำเร็จ", `${errText(e)} — ลองใช้วิธีคัดลอกพรอมต์ไปที่ Google Flow แทน`);
    } finally {
      setBusy(false);
    }
  };

  const manualPost = async () => {
    if (!caption.trim()) {
      toast.warn("ยังไม่มีข้อความสำหรับโพสต์", "เขียนข้อความในขั้นตอนที่ 3 ก่อน");
      return;
    }
    const ok = await copyText(caption);
    await openUrl(SHOPEE_SELLER_URL);
    toast.info(
      ok ? "คัดลอกข้อความแล้ว เปิด Shopee Seller Centre" : "เปิด Shopee Seller Centre แล้ว",
      "Shopee Video ไม่มีช่องทาง API — ต้องอัปโหลดวิดีโอและวางข้อความเอง",
    );
  };

  return (
    <div className="grid" style={{ gridTemplateColumns: "repeat(3, minmax(0,1fr))", alignItems: "start", gap: 16 }}>
      {/* column 1 */}
      <div className="col" style={{ gap: 16 }}>
        <PastelCard>
          <StepHead n={1} tone="orange" title="เลือกสตอรี่ / แนวเรื่อง" text="เลือกแนวคลิปที่จะทำ" />
          <div className="grid" style={{ gridTemplateColumns: "repeat(2, minmax(0,1fr))", gap: 10 }}>
            {SHOPEE_STORIES.map((s) => (
              <Tile
                key={s.key}
                active={story === s.key}
                icon={s.icon}
                title={s.title}
                desc={s.desc}
                onClick={() => setStory(s.key)}
              />
            ))}
          </div>
        </PastelCard>

        <PastelCard>
          <StepHead
            n={2}
            tone="primary"
            title="ข้อมูลสินค้าและข้อความโปรโมต"
            text="เลือกสินค้าจาก Shopee ที่จะโปรโมต"
            action={
              <button className="btn btn--soft btn--sm" onClick={() => setProductOpen(true)}>
                <RefreshCw size={14} /> เปลี่ยนสินค้า
              </button>
            }
          />
          {!product ? (
            <EmptyState
              title="ยังไม่ได้เลือกสินค้า"
              text="เลือกสินค้าจากรายการสินค้า Shopee ที่ระบบดึงมาให้"
              icon={ShoppingBag}
              action={
                <button className="btn btn--primary btn--sm" onClick={() => setProductOpen(true)}>
                  เลือกสินค้า
                </button>
              }
            />
          ) : (
            <div className="row" style={{ alignItems: "flex-start", gap: 12 }}>
              {product.image_url ? (
                <div className="thumb" style={{ width: 96, height: 96 }}>
                  <img src={product.image_url} alt={product.name || "สินค้า"} />
                </div>
              ) : (
                <div className="thumb" style={{ width: 96, height: 96 }}>
                  <ShoppingBag size={20} color="#a48cf0" />
                </div>
              )}
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontWeight: 700 }}>{product.name}</div>
                <div className="row" style={{ gap: 8, marginTop: 4 }}>
                  <span className="strong" style={{ color: "var(--c-pink-strong)" }}>
                    ฿{Number(product.sale_price ?? product.price ?? 0).toLocaleString("th-TH")}
                  </span>
                  {product.original_price && Number(product.original_price) > Number(product.sale_price ?? product.price ?? 0) ? (
                    <>
                      <span className="small muted" style={{ textDecoration: "line-through" }}>
                        ฿{Number(product.original_price).toLocaleString("th-TH")}
                      </span>
                      <StatusBadge tone="danger">
                        ลด {Math.round((1 - Number(product.sale_price) / Number(product.original_price)) * 100)}%
                      </StatusBadge>
                    </>
                  ) : null}
                </div>
                {product.seller_name ? (
                  <div className="small muted" style={{ marginTop: 4 }}>
                    ร้านค้า: {product.seller_name}
                  </div>
                ) : null}
                {product.rating ? (
                  <div className="small muted">คะแนน {Number(product.rating).toFixed(1)}/5</div>
                ) : null}
                {product.sold_count ? (
                  <div className="small muted">ยอดขาย {Number(product.sold_count).toLocaleString("th-TH")} ชิ้น</div>
                ) : null}
                {product.product_url ? (
                  <button
                    className="btn btn--outline btn--sm"
                    style={{ marginTop: 8 }}
                    onClick={() => {
                      void copyText(product.product_url);
                      void openUrl(product.product_url);
                    }}
                  >
                    <ExternalLink size={14} /> เปิดหน้าสินค้า
                  </button>
                ) : null}
              </div>
            </div>
          )}
        </PastelCard>

        <PastelCard>
          <StepHead n={3} tone="mint" title="ข้อความสำหรับโพสต์" text="เขียนข้อความและเช็คความครบถ้วนก่อนโพสต์" />
          <div className="field">
            <label className="field__label" htmlFor="shopee-caption">
              ข้อความ
            </label>
            <textarea
              id="shopee-caption"
              className="textarea"
              value={caption}
              maxLength={500}
              onChange={(e) => setCaption(e.target.value)}
              style={{ minHeight: 120 }}
            />
            <span className="field__hint">{caption.length}/500</span>
          </div>
          <div className="col" style={{ gap: 5, marginTop: 10 }}>
            {checklist.map((c) => (
              <div key={c.text} className="row" style={{ gap: 7 }}>
                <CheckCircle2 size={14} color={c.ok ? "var(--c-success)" : "var(--c-muted)"} />
                <span className="small" style={{ color: c.ok ? "var(--c-ink)" : "var(--c-muted)" }}>
                  {c.text}
                </span>
              </div>
            ))}
          </div>
          <div className="row row--wrap" style={{ gap: 7, marginTop: 10 }}>
            {hashtags.map((h) => (
              <Chip key={h} tone="pink">
                {h}
              </Chip>
            ))}
          </div>
        </PastelCard>
      </div>

      {/* column 2 */}
      <div className="col" style={{ gap: 16 }}>
        <PastelCard>
          <StepHead n={4} tone="blue" title="เลือกคลิปและตัดต่อ" text="เลือกคลิปที่จะใช้และดูลำดับการตัดต่อ" />
          <VideoPlayer
            src={clipVideo(clip)}
            poster={clipPoster(clip)}
            aspect={format === "horizontal" ? "16:9" : "9:16"}
          />
          <div style={{ marginTop: 10 }}>
            {clips.length === 0 ? (
              <EmptyState title="ยังไม่มีคลิปในระบบ" text="สร้างหรือนำเข้าคลิปก่อน" icon={VideoIcon} />
            ) : (
              <ClipStrip
                clips={clips.map((c) => ({
                  thumb: clipPoster(c),
                  durationSeconds: c.durationSeconds,
                  title: c.title || c.id,
                }))}
                onPick={(i) => setClipFolder(clips[i]?.folder || "")}
              />
            )}
          </div>
        </PastelCard>

        <PastelCard>
          <StepHead n={6} tone="blue" title="สร้างวิดีโอตามสั่งซื้อ" text="เลือกวิธีสร้างคลิปของคุณ" />
          <div className="grid" style={{ gridTemplateColumns: "repeat(2, minmax(0,1fr))", gap: 10 }}>
            {SHOPEE_SOURCES.map((s) => (
              <Tile
                key={s.key}
                active={false}
                disabled={busy}
                icon={s.icon}
                title={s.title}
                desc={s.desc}
                badge={s.badge}
                badgeTone={s.badgeTone}
                onClick={() => {
                  if (s.key === "script") void renderScript();
                  if (s.key === "import") void pickFile();
                  if (s.key === "flow") void openFlow();
                  if (s.key === "google") void googleVideo();
                }}
              />
            ))}
          </div>
        </PastelCard>
      </div>

      {/* column 3 */}
      <div className="col" style={{ gap: 16 }}>
        <PastelCard>
          <StepHead n={5} tone="orange" title="ตั้งค่ารูปแบบวิดีโอ" text="ปรับให้เข้ากับ Shopee Video" />
          <div className="col" style={{ gap: 14 }}>
            <div className="col" style={{ gap: 8 }}>
              <span className="field__label">สัดส่วนภาพ</span>
              <RatioRow value={format} onChange={setFormat} />
            </div>
            <div className="col" style={{ gap: 8 }}>
              <span className="field__label">ความยาววิดีโอ</span>
              <DurationRow value={duration} onChange={setDuration} hint="แนะนำ 15-30 วินาที" />
            </div>
            <div className="col" style={{ gap: 8 }}>
              <label className="field__label" htmlFor="shopee-character">
                สไตล์ตัวละครที่ใช้
              </label>
              <select
                id="shopee-character"
                className="select"
                value={character}
                onChange={(e) => setCharacter(e.target.value)}
              >
                <option value="">-- เลือกตัวละคร --</option>
                {characters.map((c) => (
                  <option key={c} value={c}>
                    {CHAR_LABEL[c] ?? c}
                  </option>
                ))}
              </select>
            </div>
            <div className="col" style={{ gap: 10 }}>
              {[
                { key: "music", label: "เพิ่มเพลงพื้นหลัง", value: music, set: setMusic },
                { key: "overlay", label: "เพิ่มข้อความบนวิดีโอ", value: overlay, set: setOverlay },
                { key: "sticker", label: "เพิ่มสติกเกอร์", value: sticker, set: setSticker },
              ].map((row) => (
                <div key={row.key} className="row row--between">
                  <span className="small">{row.label}</span>
                  <label className="switch">
                    <input type="checkbox" checked={row.value} onChange={(e) => row.set(e.target.checked)} />
                    <span className="switch__track" />
                  </label>
                </div>
              ))}
              <span className="xsmall muted">
                ตัวเลือกเหล่านี้จะถูกใส่ในพรอมต์ตอนสร้างวิดีโอใหม่
              </span>
            </div>
          </div>
        </PastelCard>

        <PastelCard>
          <StepHead
            n={7}
            tone="mint"
            title="สรุปคอนเทนต์และตรวจสอบ"
            text="ตรวจสอบให้ครบก่อนนำไปลง Shopee Video"
            action={<StatusBadge tone="success">พร้อมลง</StatusBadge>}
          />
          <div className="col" style={{ gap: 10 }}>
            {product ? (
              <div className="row" style={{ gap: 10 }}>
                {product.image_url ? (
                  <div className="thumb" style={{ width: 64, height: 64 }}>
                    <img src={product.image_url} alt={product.name || "สินค้า"} />
                  </div>
                ) : null}
                <div style={{ minWidth: 0 }}>
                  <div className="small strong truncate">{product.name}</div>
                  <div className="xsmall muted">
                    ฿{Number(product.sale_price ?? product.price ?? 0).toLocaleString("th-TH")}
                  </div>
                </div>
              </div>
            ) : null}
            <div className="col" style={{ gap: 5 }}>
              {checklist.map((c) => (
                <div key={c.text} className="row" style={{ gap: 7 }}>
                  <CheckCircle2 size={14} color={c.ok ? "var(--c-success)" : "var(--c-muted)"} />
                  <span className="small" style={{ color: c.ok ? "var(--c-ink)" : "var(--c-muted)" }}>
                    {c.text}
                  </span>
                </div>
              ))}
            </div>
            <button className="btn btn--orange btn--lg btn--block" onClick={() => void manualPost()}>
              <Send size={18} /> โพสต์ไปยัง Shopee Video
            </button>
            <span className="xsmall muted">
              Shopee Video ไม่มีช่องทาง API — ปุ่มนี้จะคัดลอกข้อความและเปิด Shopee Seller Centre ให้อัปโหลดและกดโพสต์เอง
            </span>
          </div>
        </PastelCard>
      </div>

      <Modal
        open={productOpen}
        title="เลือกสินค้าจาก Shopee"
        icon={ShoppingBag}
        onClose={() => setProductOpen(false)}
        width={720}
      >
        {productsQ.loading ? (
          <LoadingState />
        ) : productsQ.error ? (
          <ErrorState message={productsQ.error} onRetry={() => productsQ.reload()} />
        ) : products.length === 0 ? (
          <EmptyState
            title="ยังไม่มีข้อมูลสินค้า"
            text="ระบบยังไม่มีรายการสินค้าจาก Shopee — ลองอัปเดตข้อมูลสินค้าที่หน้า Facebook Profile"
            icon={ShoppingBag}
          />
        ) : (
          <div className="grid" style={{ gridTemplateColumns: "repeat(3, minmax(0,1fr))", gap: 12 }}>
            {products.map((p: any) => (
              <button
                key={p.id || p.product_id || p.name}
                type="button"
                className="card"
                style={{ padding: 10, textAlign: "left", cursor: "pointer", boxShadow: "none" }}
                onClick={() => {
                  selectProduct(p);
                  setProductOpen(false);
                }}
              >
                {p.image_url ? (
                  <div className="thumb" style={{ width: "100%", height: 110, marginBottom: 8 }}>
                    <img src={p.image_url} alt={p.name || "สินค้า"} />
                  </div>
                ) : null}
                <div className="small strong clamp-2">{p.name}</div>
                <div className="xsmall muted">฿{Number(p.sale_price ?? p.price ?? 0).toLocaleString("th-TH")}</div>
              </button>
            ))}
          </div>
        )}
      </Modal>
    </div>
  );
}

/* ------------------------------------------------------------------- page */

export default function CreatePublish() {
  const { platform } = useParams();
  const key: PlatformKey = PLATFORM_KEYS.includes(platform as PlatformKey)
    ? (platform as PlatformKey)
    : "tiktok";

  const meta = PLATFORM_META[key];

  return (
    <div className="stack">
      <PageHeader
        title={`สร้างวิดีโอสำหรับ ${meta.label}`}
        subtitle={
          key === "tiktok"
            ? "เปลี่ยนเรื่องราวให้เป็นวิดีโอสำหรับ TikTok พร้อมคำบรรยายและแถวโพสต์ ตรวจสอบการโพสต์ได้ที่หน้าคลังคลิป"
            : key === "youtube"
              ? "เลือกเรื่อง สร้างวิดีโอด้วย AI และโพสต์เป็น YouTube ได้ในคลิกเดียว"
              : key === "shopee"
                ? "สร้างคลิปแทนคิวดิโอไว้โมงลีค้า สำหรับ Shopee Video ให้ดักจู สูญ ดูเพลิน และช่วยเพิ่มยอดขาย"
                : "สร้างและโพสต์ Reel ให้เพจของคุณผ่าน API ของ Meta"
        }
        icon={key === "tiktok" ? Music2 : key === "youtube" ? Play : key === "shopee" ? ShoppingBag : Facebook}
        tone={key === "tiktok" ? "pink" : key === "youtube" ? "orange" : key === "shopee" ? "orange" : "blue"}
        extra={<PlatformTabs active={key} />}
      />

      {key === "facebook_profile" ? (
        <Navigate to="/facebook-profile" replace />
      ) : key === "tiktok" || key === "facebook_page" ? (
        <SocialFlow platform={key} />
      ) : key === "youtube" ? (
        <YouTubeFlow />
      ) : (
        <ShopeeFlow />
      )}
    </div>
  );
}
