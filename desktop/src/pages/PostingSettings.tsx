import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  ExternalLink,
  FolderOpen,
  Link2,
  Loader2,
  Minus,
  Plus,
  RefreshCw,
  Save,
  Settings2,
  ShieldCheck,
  Sparkles,
  Trash2,
  Unplug,
} from "lucide-react";
import {
  apiGet,
  apiPost,
  engineStatus,
  revealPath,
  PLATFORM_META,
  type PostingPlatform,
  type PostingStatus,
} from "../services/api";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  PastelCard,
  StatusBadge,
} from "../components/common/ui";
import { useApiData } from "../hooks/useApiData";
import { Modal, useToast } from "../components/common/feedback";

/* ------------------------------------------------------------------ types */

type PlatformKey = "tiktok" | "youtube" | "facebook_page" | "facebook_profile";

type PostingStatusResponse = {
  ok: boolean;
  posting: PostingStatus;
};

type PlatformSettings = {
  enabled: boolean;
  format: string;
  max_per_day: number;
  privacy?: string;
  category_id?: string;
  graph_version?: string;
  redirect_port?: number;
};

type FormState = {
  mode: string;
  maxPerDay: number;
  postTimes: string[];
  platforms: Record<PlatformKey, PlatformSettings>;
};

const PLATFORM_KEYS: PlatformKey[] = ["tiktok", "youtube", "facebook_page", "facebook_profile"];

const PLATFORM_LABEL: Record<PlatformKey, string> = {
  tiktok: "TikTok",
  youtube: "YouTube",
  facebook_page: "Facebook Page",
  facebook_profile: "Facebook Profile",
};

const PLATFORM_DESC: Record<PlatformKey, string> = {
  tiktok: "โพสต์คลิปลง TikTok (บัญชีธุรกิจ)",
  youtube: "โพสต์คลิปขึ้น YouTube",
  facebook_page: "โพสต์ลงเพจ Facebook ของสตูดิโอ",
  facebook_profile: "โพสต์ลงโปรไฟล์ส่วนตัวผ่านพนักงาน AI (เบราว์เซอร์)",
};

const MODES: { value: string; title: string; text: string }[] = [
  {
    value: "auto",
    title: "โหมดอัตโนมัติเต็มรูปแบบ",
    text: "ระบบโพสต์คลิปที่พร้อมให้เองตามเวลาที่ตั้งไว้ โดยไม่ต้องรอคนตรวจ",
  },
  {
    value: "approved",
    title: "โหมดตรวจสอบโดยมนุษย์",
    text: "ระบบจะโพสต์เฉพาะคลิปที่คนตรวจสอบและอนุมัติแล้วเท่านั้น",
  },
  {
    value: "off",
    title: "ปิดการโพสต์อัตโนมัติ",
    text: "ระบบจะไม่โพสต์เอง คนที่ 1 เป็นผู้โพสต์เองตามเวลาที่กำหนด",
  },
];

const TIME_OPTIONS: string[] = (() => {
  const out: string[] = [];
  for (let h = 6; h <= 23; h++) {
    out.push(`${String(h).padStart(2, "0")}:00`);
    if (h < 23) out.push(`${String(h).padStart(2, "0")}:30`);
  }
  return out;
})();

const FORMAT_OPTIONS = [
  { value: "vertical", label: "แนวตั้ง 9:16 (Shorts / Reels)" },
  { value: "horizontal", label: "แนวนอน 16:9 (วิดีโอเต็ม)" },
];

/* ---------------------------------------------------------------- helpers */

function errMsg(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}

function PlatformLogo({ platform, size = 42 }: { platform: PlatformKey; size?: number }) {
  const meta = PLATFORM_META[platform];
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: Math.round(size * 0.3),
        background: meta.bg,
        color: meta.color,
        display: "grid",
        placeItems: "center",
        fontWeight: 700,
        fontSize: Math.round(size * 0.42),
        flex: "none",
        boxShadow: "var(--sh-sm)",
      }}
    >
      {meta.label.charAt(0)}
    </div>
  );
}

function NumberStepper({
  value,
  onChange,
  min = 0,
  max = 99,
  suffix,
}: {
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  suffix?: string;
}) {
  const clamp = (v: number) => Math.min(max, Math.max(min, Number.isFinite(v) ? v : min));
  return (
    <div className="row" style={{ gap: 6 }}>
      <button
        type="button"
        className="btn btn--soft btn--icon btn--sm"
        onClick={() => onChange(clamp(value - 1))}
        disabled={value <= min}
        aria-label="ลดลง"
      >
        <Minus size={13} />
      </button>
      <input
        className="input"
        type="number"
        value={value}
        min={min}
        max={max}
        onChange={(e) => onChange(clamp(Number(e.target.value)))}
        style={{ width: 62, textAlign: "center", padding: "7px 6px" }}
        aria-label="จำนวน"
      />
      <button
        type="button"
        className="btn btn--soft btn--icon btn--sm"
        onClick={() => onChange(clamp(value + 1))}
        disabled={value >= max}
        aria-label="เพิ่มขึ้น"
      >
        <Plus size={13} />
      </button>
      {suffix && <span className="xsmall muted">{suffix}</span>}
    </div>
  );
}

function SwitchRow({
  label,
  hint,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <div className="row" style={{ alignItems: "flex-start", gap: 12 }}>
      <label className="switch" style={disabled ? { opacity: 0.5, cursor: "not-allowed" } : undefined}>
        <input
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span className="switch__track" />
      </label>
      <div style={{ minWidth: 0 }}>
        <div className="small strong" style={{ lineHeight: 1.4 }}>
          {label}
        </div>
        {hint && (
          <div className="xsmall muted" style={{ lineHeight: 1.55, marginTop: 2 }}>
            {hint}
          </div>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------- page */

export default function PostingSettings() {
  const toast = useToast();
  const { data, loading, error, reload } = useApiData<PostingStatusResponse>(
    () => apiGet<PostingStatusResponse>("/api/posting/status"),
  );

  const [form, setForm] = useState<FormState | null>(null);
  const [saving, setSaving] = useState(false);
  const [busy, setBusy] = useState<PlatformKey | null>(null);
  const [modalPlatform, setModalPlatform] = useState<PlatformKey | null>(null);
  const dirty = useRef(false);

  /* seed the form from the real payload (only while the user has no edits) */
  useEffect(() => {
    if (!data?.posting || dirty.current) return;
    const p = data.posting;
    const platforms = {} as Record<PlatformKey, PlatformSettings>;
    for (const key of PLATFORM_KEYS) {
      const raw = (p.platforms?.[key]?.settings || {}) as Record<string, any>;
      platforms[key] = {
        enabled: raw.enabled === true,
        format: typeof raw.format === "string" ? raw.format : "vertical",
        max_per_day:
          typeof raw.max_per_day === "number" ? raw.max_per_day : Number(p.maxPerDay) || 2,
        privacy: typeof raw.privacy === "string" ? raw.privacy : "public",
        category_id: typeof raw.category_id === "string" ? raw.category_id : "",
        graph_version: typeof raw.graph_version === "string" ? raw.graph_version : "",
        redirect_port: typeof raw.redirect_port === "number" ? raw.redirect_port : 3455,
      };
    }
    setForm({
      mode: p.mode || "off",
      maxPerDay: Number(p.maxPerDay) || 2,
      postTimes: Array.isArray(p.postTimes) ? [...p.postTimes] : [],
      platforms,
    });
  }, [data]);

  const posting = data?.posting;
  const connectedList = useMemo(
    () => PLATFORM_KEYS.filter((k) => posting?.platforms?.[k]?.connected === true),
    [posting],
  );

  const update = (fn: (f: FormState) => FormState) => {
    dirty.current = true;
    setForm((f) => (f ? fn(f) : f));
  };

  const setPlatform = (key: PlatformKey, patch: Partial<PlatformSettings>) => {
    update((f) => ({
      ...f,
      platforms: { ...f.platforms, [key]: { ...f.platforms[key], ...patch } },
    }));
  };

  /* ----------------------------------------------------------- persistence */

  const buildSettings = (f: FormState) => ({
    mode: f.mode,
    max_per_day: f.maxPerDay,
    post_times: f.postTimes,
    tiktok: {
      enabled: f.platforms.tiktok.enabled,
      format: f.platforms.tiktok.format,
      redirect_port: Number(f.platforms.tiktok.redirect_port) || 3455,
      max_per_day: f.platforms.tiktok.max_per_day,
    },
    youtube: {
      enabled: f.platforms.youtube.enabled,
      format: f.platforms.youtube.format,
      privacy: f.platforms.youtube.privacy || "public",
      category_id: f.platforms.youtube.category_id || "",
      max_per_day: f.platforms.youtube.max_per_day,
    },
    facebook_page: {
      enabled: f.platforms.facebook_page.enabled,
      format: f.platforms.facebook_page.format,
      graph_version: f.platforms.facebook_page.graph_version || "",
      max_per_day: f.platforms.facebook_page.max_per_day,
    },
    facebook_profile: {
      enabled: f.platforms.facebook_profile.enabled,
      format: f.platforms.facebook_profile.format,
      max_per_day: f.platforms.facebook_profile.max_per_day,
    },
  });

  const save = async () => {
    if (!form) return;
    setSaving(true);
    try {
      await apiPost("/api/posting/save", { settings: buildSettings(form) });
      dirty.current = false;
      toast.success("บันทึกการตั้งค่าโพสต์แล้ว");
      await reload(true);
    } catch (e) {
      toast.error("บันทึกการตั้งค่าโพสต์ไม่สำเร็จ", errMsg(e));
    } finally {
      setSaving(false);
    }
  };

  const connect = async (key: PlatformKey) => {
    setBusy(key);
    try {
      const res = await apiPost<{ ok: boolean; connected: boolean; accountName?: string }>(
        "/api/posting/connect",
        { platform: key },
      );
      toast.success(
        `เชื่อมต่อ ${PLATFORM_LABEL[key]} สำเร็จ`,
        res?.accountName ? `บัญชี: ${res.accountName}` : undefined,
      );
      await reload(true);
    } catch (e) {
      toast.error(
        `เชื่อมต่อ ${PLATFORM_LABEL[key]} ไม่สำเร็จ`,
        `${errMsg(e)} — การเชื่อมต่อจะเปิดหน้าต่างเบราว์เซอร์ให้ล็อกอิน กรุณาทำต่อในเบราว์เซอร์`,
      );
      await reload(true);
    } finally {
      setBusy(null);
    }
  };

  const disconnect = async (key: PlatformKey) => {
    setBusy(key);
    try {
      await apiPost("/api/posting/disconnect", { platform: key });
      toast.success(`ยกเลิกการเชื่อมต่อ ${PLATFORM_LABEL[key]} แล้ว`);
      await reload(true);
    } catch (e) {
      toast.error(`ยกเลิกการเชื่อมต่อ ${PLATFORM_LABEL[key]} ไม่สำเร็จ`, errMsg(e));
    } finally {
      setBusy(null);
    }
  };

  const testConnection = async (key: PlatformKey) => {
    setBusy(key);
    try {
      const res = await apiGet<PostingStatusResponse>("/api/posting/status");
      const p = res.posting?.platforms?.[key];
      if (p?.connected) {
        toast.success(
          `${PLATFORM_LABEL[key]} เชื่อมต่ออยู่`,
          p.accountName ? `บัญชี: ${p.accountName}` : "เอนจินตรวจพบโทเคนของบัญชีนี้แล้ว",
        );
      } else {
        toast.warn(`${PLATFORM_LABEL[key]} ยังไม่ได้เชื่อมต่อ`, "เอนจินไม่พบโทเคนของบัญชีนี้");
      }
      await reload(true);
    } catch (e) {
      toast.error(`ทดสอบการเชื่อมต่อ ${PLATFORM_LABEL[key]} ไม่สำเร็จ`, errMsg(e));
    } finally {
      setBusy(null);
    }
  };

  const openSecretsFolder = async () => {
    try {
      const st = (await engineStatus()) as { root?: string } | null;
      const root = st?.root;
      if (!root) {
        toast.error("เปิดโฟลเดอร์ไฟล์การเชื่อมต่อไม่ได้", "ไม่พบพาธของสตูดิโอจากเอนจิน");
        return;
      }
      await revealPath(`${root}\\secrets`);
    } catch (e) {
      toast.error("เปิดโฟลเดอร์ไฟล์การเชื่อมต่อไม่ได้", errMsg(e));
    }
  };

  /* -------------------------------------------------------------- derived */

  const rotateOn = useMemo(() => {
    if (!form || !posting) return false;
    const connected = PLATFORM_KEYS.filter((k) => posting.platforms?.[k]?.connected === true);
    if (connected.length < 2) return false;
    return connected.every((k) => form.platforms[k]?.enabled === true);
  }, [form, posting]);

  const setRotate = (on: boolean) => {
    if (!form || !posting) return;
    const connected = PLATFORM_KEYS.filter((k) => posting.platforms?.[k]?.connected === true);
    if (!connected.length) {
      toast.warn("ยังไม่มีแพลตฟอร์มที่เชื่อมต่อ", "เชื่อมต่ออย่างน้อย 1 แพลตฟอร์มก่อน");
      return;
    }
    const keep = connected[0];
    update((f) => ({
      ...f,
      platforms: PLATFORM_KEYS.reduce(
        (acc, k) => {
          acc[k] = {
            ...f.platforms[k],
            enabled: on ? connected.includes(k) : k === keep,
          };
          return acc;
        },
        {} as Record<PlatformKey, PlatformSettings>,
      ),
    }));
  };

  const addPostTime = () => {
    const free = TIME_OPTIONS.find((t) => !form?.postTimes.includes(t));
    if (!free) {
      toast.info("เพิ่มเวลาโพสต์ได้ครบทุกช่วงแล้ว");
      return;
    }
    update((f) => ({ ...f, postTimes: [...f.postTimes, free] }));
  };

  const removePostTime = (idx: number) => {
    update((f) => ({ ...f, postTimes: f.postTimes.filter((_, i) => i !== idx) }));
  };

  /* --------------------------------------------------------------- render */

  if (loading && !form) {
    return (
      <>
        <PageHeader title="หน้าการตั้งค่าโพสต์ (คนที่ 2)" icon={Settings2} />
        <PastelCard>
          <LoadingState label="กำลังโหลดการตั้งค่าโพสต์..." />
        </PastelCard>
      </>
    );
  }

  if (error && !form) {
    return (
      <>
        <PageHeader title="หน้าการตั้งค่าโพสต์ (คนที่ 2)" icon={Settings2} />
        <PastelCard>
          <ErrorState message={error} onRetry={() => reload()} />
        </PastelCard>
      </>
    );
  }

  const modal = modalPlatform ? posting?.platforms?.[modalPlatform] : undefined;

  return (
    <>
      <PageHeader
        icon={Settings2}
        title="หน้าการตั้งค่าโพสต์ (คนที่ 2)"
        subtitle="ตั้งค่าการเชื่อมต่อบัญชี โหมดการโพสต์ และเวลาที่โพสต์ในแต่ละวัน"
        actions={
          connectedList.length ? (
            <StatusBadge tone="success" dot>
              ใช้งานอยู่
            </StatusBadge>
          ) : (
            <StatusBadge tone="muted" dot>
              ยังไม่ได้เชื่อมต่อ
            </StatusBadge>
          )
        }
      />

      <div className="stack">
      {busy && (
        <div className="card card--soft row" style={{ gap: 12 }}>
          <Loader2 size={18} className="spin" />
          <div style={{ minWidth: 0 }}>
            <div className="small strong">กำลังเชื่อมต่อ {PLATFORM_LABEL[busy]}...</div>
            <div className="xsmall muted">
              การเชื่อมต่อจะเปิดหน้าต่างเบราว์เซอร์ให้ล็อกอิน กรุณาทำต่อในหน้าต่างนั้น แล้วกลับมาที่นี่
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------- platform overview cards */}
      <PastelCard
        title="ดูการตั้งค่าโพสต์"
        subtitle="สถานะการเชื่อมต่อของแต่ละแพลตฟอร์ม"
        icon={Link2}
        iconTone="blue"
      >
        <div
          className="grid"
          style={{ gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))" }}
        >
        {PLATFORM_KEYS.map((key) => {
          const p: PostingPlatform | undefined = posting?.platforms?.[key];
          const connected = p?.connected === true;
          return (
            <button
              key={key}
              type="button"
              className="card"
              onClick={() => setModalPlatform(key)}
              style={{
                textAlign: "left",
                cursor: "pointer",
                padding: 14,
                borderColor: connected ? "var(--c-line)" : "var(--c-line-strong)",
                background: connected ? "var(--c-card)" : "var(--g-primary-soft-2)",
              }}
            >
              <div className="row" style={{ gap: 11 }}>
                <PlatformLogo platform={key} size={38} />
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div className="row row--between" style={{ gap: 8 }}>
                    <span className="strong truncate">{PLATFORM_LABEL[key]}</span>
                    {connected ? (
                      <StatusBadge tone="success">เชื่อมแล้ว</StatusBadge>
                    ) : (
                      <StatusBadge tone="danger">ยังไม่ได้เชื่อมต่อ</StatusBadge>
                    )}
                  </div>
                  <div className="xsmall muted truncate" style={{ marginTop: 3 }}>
                    {p?.accountName ? p.accountName : "ยังไม่มีบัญชีที่เชื่อมต่อ"}
                  </div>
                  <div className="xsmall muted" style={{ marginTop: 2 }}>
                    วันนี้โพสต์แล้ว {p?.postedToday ?? 0} คลิป
                  </div>
                </div>
                <ChevronRight size={17} />
              </div>
            </button>
          );
        })}
        </div>
      </PastelCard>

      {/* ----------------------------------------------- main settings card */}
      <PastelCard
        title="ตั้งค่าโพสต์และจำนวนสูงสุด"
        subtitle="กำหนดรูปแบบการโพสต์ จำนวนคลิปสูงสุดต่อวัน และเวลาที่โพสต์"
        icon={ShieldCheck}
        iconTone="mint"
      >
        {!form ? (
          <LoadingState />
        ) : (
          <div
            className="grid"
            style={{ gridTemplateColumns: "minmax(0, 1.55fr) minmax(0, 1fr)", alignItems: "start" }}
          >
            {/* left column */}
            <div className="col" style={{ gap: 16 }}>
              <div className="field">
                <span className="field__label">โหมดการโพสต์ในระบบ</span>
                <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
                  {MODES.map((m) => (
                    <label
                      key={m.value}
                      className="card"
                      style={{
                        padding: 13,
                        cursor: "pointer",
                        borderColor: form.mode === m.value ? "var(--c-primary)" : "var(--c-line)",
                        background: form.mode === m.value ? "var(--g-primary-soft)" : "#fff",
                        boxShadow: form.mode === m.value ? "var(--sh-sm)" : "none",
                      }}
                    >
                      <div className="row" style={{ gap: 10 }}>
                        <input
                          type="radio"
                          name="posting-mode"
                          checked={form.mode === m.value}
                          onChange={() => update((f) => ({ ...f, mode: m.value }))}
                          style={{ accentColor: "var(--c-primary)", width: 17, height: 17 }}
                        />
                        <div style={{ minWidth: 0 }}>
                          <div className="small strong">{m.title}</div>
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
                <textarea
                  className="textarea"
                  readOnly
                  value={
                    MODES.find((m) => m.value === form.mode)?.text ??
                    "เลือกโหมดการโพสต์เพื่อดูรายละเอียด"
                  }
                  style={{ minHeight: 66, color: "var(--c-muted)", background: "#fbfaff" }}
                />
              </div>

              <div className="field">
                <span className="field__label">จำนวนคลิปสูงสุดต่อวัน (ต่อ 1 แพลตฟอร์ม)</span>
                <div className="row row--wrap" style={{ gap: 10 }}>
                  <span className="xsmall muted" style={{ minWidth: 190 }}>
                    จำนวนที่เอนจินบังคับใช้จริง:
                  </span>
                  <NumberStepper
                    value={form.maxPerDay}
                    min={0}
                    max={50}
                    suffix="คลิป/แพลตฟอร์ม/วัน"
                    onChange={(v) => update((f) => ({ ...f, maxPerDay: v }))}
                  />
                </div>
                <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))" }}>
                  {PLATFORM_KEYS.map((key) => (
                    <div
                      key={key}
                      className="card"
                      style={{ padding: 12, background: "var(--c-primary-soft-2)", border: "1px solid var(--c-line)" }}
                    >
                      <div className="row" style={{ gap: 9, marginBottom: 8 }}>
                        <PlatformLogo platform={key} size={28} />
                        <div style={{ minWidth: 0 }}>
                          <div className="small strong truncate">{PLATFORM_LABEL[key]}</div>
                          <div className="xsmall muted">วันนี้โพสต์ {posting?.platforms?.[key]?.postedToday ?? 0} คลิป</div>
                        </div>
                      </div>
                      <NumberStepper
                        value={form.platforms[key].max_per_day}
                        min={0}
                        max={50}
                        suffix="คลิป/วัน"
                        onChange={(v) => setPlatform(key, { max_per_day: v })}
                      />
                    </div>
                  ))}
                </div>
                <span className="field__hint">
                  เอนจินเวอร์ชันนี้บังคับใช้ “จำนวนที่เอนจินบังคับใช้จริง” ต่อแพลตฟอร์มต่อวัน
                  ส่วนค่าที่ตั้งต่อแพลตฟอร์มจะถูกบันทึกไว้ แต่ยังไม่ถูกนำไปบังคับใช้
                </span>
              </div>

              <div className="field">
                <span className="field__label">เวลาที่โพสต์ในแต่ละวัน (ตัวอย่าง)</span>
                <span className="field__hint">
                  เวลานี้จะถูกบันทึกไว้เป็นตัวอย่างเวลาโพสต์ ส่วนเวลาที่เอนจินใช้จริงกำหนดได้ที่หน้า “ตั้งเวลา”
                </span>
                {form.postTimes.length === 0 ? (
                  <div
                    className="card"
                    style={{ padding: 12, background: "var(--c-primary-soft-2)", textAlign: "center" }}
                  >
                    <div className="small muted">ยังไม่ได้ตั้งเวลาโพสต์</div>
                  </div>
                ) : (
                  <div className="col" style={{ gap: 8 }}>
                    {form.postTimes.map((t, idx) => (
                      <div key={`${t}-${idx}`} className="row" style={{ gap: 8 }}>
                        <span className="xsmall muted" style={{ width: 52 }}>
                          เวลา {idx + 1}
                        </span>
                        <select
                          className="select"
                          value={t}
                          onChange={(e) => {
                            const next = [...form.postTimes];
                            next[idx] = e.target.value;
                            update((f) => ({ ...f, postTimes: next }));
                          }}
                          style={{ maxWidth: 160 }}
                        >
                          {TIME_OPTIONS.includes(t) ? null : <option value={t}>{t}</option>}
                          {TIME_OPTIONS.map((o) => (
                            <option key={o} value={o}>
                              {o}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          className="btn btn--danger btn--icon btn--sm"
                          onClick={() => removePostTime(idx)}
                          aria-label="ลบเวลาโพสต์"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <div>
                  <button type="button" className="btn btn--outline btn--sm" onClick={addPostTime}>
                    <Plus size={14} /> เพิ่มเวลาโพสต์
                  </button>
                </div>
              </div>
            </div>

            {/* right column */}
            <div
              className="card"
              style={{ background: "var(--c-primary-soft-2)", border: "1px solid var(--c-line)" }}
            >
              <div className="row" style={{ gap: 9, marginBottom: 12 }}>
                <Sparkles size={16} style={{ color: "var(--c-primary)" }} />
                <span className="strong">ตัวเลือกการเพิ่มเติม</span>
              </div>
              <div className="col" style={{ gap: 14 }}>
                <SwitchRow
                  label="ชั่วโมงโพสต์สำหรับคนที่ 1"
                  hint="ปิดการโพสต์อัตโนมัติ ระบบจะไม่โพสต์เอง ให้คนที่ 1 โพสต์เองตามเวลาที่ตั้งไว้ (ผูกกับโหมดการโพสต์ในระบบ)"
                  checked={form.mode === "off"}
                  onChange={(on) => update((f) => ({ ...f, mode: on ? "off" : "auto" }))}
                />
                <SwitchRow
                  label="สลับแพลตฟอร์มอัตโนมัติเมื่อมีคลิป"
                  hint="เปิดเพื่อให้ระบบโพสต์ไปยังทุกแพลตฟอร์มที่เชื่อมต่อแล้ว (หมุนเวียนตามลำดับ YouTube → Facebook Page → TikTok)"
                  checked={rotateOn}
                  onChange={setRotate}
                />
                <SwitchRow
                  label="หยุดโพสต์เมื่อไม่มีคลิปพร้อม"
                  hint="เปิดเพื่อให้ระบบรอคนอนุมัติก่อน ถ้ายังไม่มีคลิปที่อนุมัติก็จะไม่โพสต์ (ตรงกับโหมดตรวจสอบโดยมนุษย์)"
                  checked={form.mode === "approved"}
                  onChange={(on) =>
                    update((f) => ({ ...f, mode: on ? "approved" : "auto" }))
                  }
                />
              </div>
            </div>
          </div>
        )}
      </PastelCard>

      {/* ---------------------------------------- per platform action cards */}
      <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
        {PLATFORM_KEYS.map((key) => {
          const p = posting?.platforms?.[key];
          const connected = p?.connected === true;
          return (
            <div key={key} className="card" style={{ padding: 15 }}>
              <div className="row" style={{ gap: 11, marginBottom: 10 }}>
                <PlatformLogo platform={key} size={36} />
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div className="row row--between" style={{ gap: 8 }}>
                    <span className="strong truncate">{PLATFORM_LABEL[key]}</span>
                    {connected ? (
                      <StatusBadge tone="success">เชื่อมแล้ว</StatusBadge>
                    ) : (
                      <StatusBadge tone="danger">ยังไม่ได้เชื่อมต่อ</StatusBadge>
                    )}
                  </div>
                  <div className="xsmall muted truncate">{p?.accountName || "ยังไม่มีบัญชีที่เชื่อมต่อ"}</div>
                </div>
              </div>
              <div className="row row--wrap" style={{ gap: 7 }}>
                {connected ? (
                  <button
                    type="button"
                    className="btn btn--danger btn--sm"
                    onClick={() => disconnect(key)}
                    disabled={busy === key}
                  >
                    <Unplug size={14} /> ยกเลิกการเชื่อมต่อ
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn btn--outline btn--sm"
                    onClick={() => connect(key)}
                    disabled={busy === key}
                  >
                    <Link2 size={14} /> เชื่อมต่อ
                  </button>
                )}
                <button
                  type="button"
                  className="btn btn--soft btn--sm"
                  onClick={() => testConnection(key)}
                  disabled={busy === key}
                >
                  <RefreshCw size={14} /> ทดสอบการเชื่อมต่อ
                </button>
                <button
                  type="button"
                  className="btn btn--outline btn--sm"
                  onClick={() => setModalPlatform(key)}
                >
                  <Settings2 size={14} /> ตั้งค่าบัญชี
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* -------------------------------------------------------- bottom bar */}
      <div className="row row--wrap row--between" style={{ gap: 12 }}>
        <button type="button" className="btn btn--outline" onClick={openSecretsFolder}>
          <FolderOpen size={16} /> ดูการเชื่อมต่อของแต่ละแพลตฟอร์ม
          <ExternalLink size={14} />
        </button>
        <button
          type="button"
          className="btn btn--primary btn--lg"
          onClick={save}
          disabled={saving || !form}
        >
          {saving ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
          บันทึกการตั้งค่าโพสต์
        </button>
      </div>
      </div>

      {/* ----------------------------------------------------- platform modal */}
      {modalPlatform && form && (
        <Modal
          open
          title={`ตั้งค่าบัญชี ${PLATFORM_LABEL[modalPlatform]}`}
          icon={Settings2}
          onClose={() => setModalPlatform(null)}
          footer={
            <>
              <button
                type="button"
                className="btn btn--outline"
                onClick={() => setModalPlatform(null)}
              >
                ปิด
              </button>
              <button
                type="button"
                className="btn btn--primary"
                onClick={async () => {
                  await save();
                  setModalPlatform(null);
                }}
                disabled={saving}
              >
                {saving ? <Loader2 size={15} className="spin" /> : <CheckCircle2 size={15} />}
                บันทึกการตั้งค่า
              </button>
            </>
          }
        >
          <div className="col" style={{ gap: 14 }}>
                <div className="row" style={{ gap: 11 }}>
                  <PlatformLogo platform={modalPlatform} size={40} />
                  <div style={{ minWidth: 0 }}>
                    <div className="strong">{PLATFORM_LABEL[modalPlatform]}</div>
                    <div className="xsmall muted">{PLATFORM_DESC[modalPlatform]}</div>
                  </div>
                </div>
                <div className="row row--wrap" style={{ gap: 8 }}>
                  {modal?.connected ? (
                    <StatusBadge tone="success">เชื่อมแล้ว</StatusBadge>
                  ) : (
                    <StatusBadge tone="danger">ยังไม่ได้เชื่อมต่อ</StatusBadge>
                  )}
                  <StatusBadge tone="info">โพสต์วันนี้ {modal?.postedToday ?? 0} คลิป</StatusBadge>
                </div>
                <div className="xsmall muted">{PLATFORM_DESC[modalPlatform]}</div>
                {modal?.accountName && (
                  <div className="small">
                    บัญชีที่เชื่อมต่อ: <span className="strong">{modal.accountName}</span>
                  </div>
                )}

                <div className="field">
                  <span className="field__label">รูปแบบวิดีโอ</span>
                  <select
                    className="select"
                    value={form.platforms[modalPlatform].format}
                    onChange={(e) => setPlatform(modalPlatform, { format: e.target.value })}
                  >
                    {FORMAT_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="field">
                  <span className="field__label">เปิดใช้งานการโพสต์ของแพลตฟอร์มนี้</span>
                  <SwitchRow
                    label="ให้ระบบโพสต์คลิปลงแพลตฟอร์มนี้"
                    hint="ปิดไว้ถ้าต้องการโพสต์ด้วยตนเอง"
                    checked={form.platforms[modalPlatform].enabled}
                    onChange={(v) => setPlatform(modalPlatform, { enabled: v })}
                  />
                </div>

                {modalPlatform === "youtube" && (
                  <>
                    <div className="field">
                      <span className="field__label">ความเป็นส่วนตัวของวิดีโอ</span>
                      <select
                        className="select"
                        value={form.platforms.youtube.privacy || "public"}
                        onChange={(e) => setPlatform("youtube", { privacy: e.target.value })}
                      >
                        <option value="public">สาธารณะ (Public)</option>
                        <option value="unlisted">ไม่เผยแพร่ (Unlisted)</option>
                        <option value="private">ส่วนตัว (Private)</option>
                      </select>
                    </div>
                    <div className="field">
                      <span className="field__label">หมวดหมู่ (Category ID)</span>
                      <input
                        className="input"
                        value={form.platforms.youtube.category_id || ""}
                        onChange={(e) => setPlatform("youtube", { category_id: e.target.value })}
                        placeholder="เช่น 27 = Education"
                      />
                    </div>
                  </>
                )}

                {modalPlatform === "facebook_page" && (
                  <div className="field">
                    <span className="field__label">Graph API Version</span>
                    <input
                      className="input"
                      value={form.platforms.facebook_page.graph_version || ""}
                      onChange={(e) => setPlatform("facebook_page", { graph_version: e.target.value })}
                      placeholder="เช่น v26.0"
                    />
                  </div>
                )}

                {modalPlatform === "tiktok" && (
                  <div className="field">
                    <span className="field__label">พอร์ตรับ callback (Redirect Port)</span>
                    <input
                      className="input"
                      type="number"
                      value={form.platforms.tiktok.redirect_port ?? 3455}
                      onChange={(e) =>
                        setPlatform("tiktok", { redirect_port: Number(e.target.value) || 0 })
                      }
                    />
                  </div>
                )}

                {modalPlatform === "facebook_profile" && (
                  <div className="row" style={{ gap: 9, alignItems: "flex-start" }}>
                    <AlertTriangle size={15} style={{ color: "var(--c-warn)", flex: "none", marginTop: 2 }} />
                    <div className="xsmall muted" style={{ lineHeight: 1.6 }}>
                      Facebook Profile ไม่ได้เชื่อมผ่าน OAuth แต่โพสต์ผ่านพนักงาน AI (เบราว์เซอร์อัตโนมัติ)
                      ตั้งค่าเวลาและแพลตฟอร์มของพนักงานได้ที่หน้า “ตั้งเวลา”
                    </div>
                  </div>
                )}
              </div>
        </Modal>
      )}

      {!posting && !loading && !error && (
        <EmptyState title="ยังไม่มีข้อมูลการตั้งค่า" text="ลองกดรีเฟรชเพื่อโหลดข้อมูลใหม่" />
      )}
    </>
  );
}
