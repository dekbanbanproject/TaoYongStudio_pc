import { useEffect, useMemo, useRef, useState } from "react";
import { openUrl } from "@tauri-apps/plugin-opener";
import {
  AlertTriangle,
  Clapperboard,
  Copy,
  Cpu,
  Eye,
  FileText,
  FolderOpen,
  Layers,
  Loader2,
  Monitor,
  MoreVertical,
  Pencil,
  Plus,
  RefreshCw,
  Send,
  Trash2,
  Upload,
  Video,
  Zap,
  type LucideIcon,
} from "lucide-react";
import {
  CHAR_LABEL,
  apiGet,
  apiPost,
  revealPath,
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
  Step,
  formatThaiDate,
} from "../components/common/ui";
import { DataTable, SearchInput, filterRows, useDebounced, type Column } from "../components/common/DataTable";
import { ConfirmDialog, Modal, useToast } from "../components/common/feedback";
import { useApiData } from "../hooks/useApiData";

/* ------------------------------------------------------------------ types */

interface ScriptsPayload {
  ok: boolean;
  inbox: ScriptSummary[];
  done: ScriptSummary[];
  samples: ScriptSummary[];
}

interface HardwarePayload {
  ok: boolean;
  hardware?: {
    cpu?: { name?: string; logical_cores?: number; mhz?: number };
    ram?: { total_gb?: number; avail_gb?: number; load_percent?: number };
    disk?: { free_gb?: number; total_gb?: number };
    gpus?: { name?: string; provider?: string; driver_version?: string }[];
    encoders?: Record<string, { ok?: boolean; error?: string }>;
    engines?: Record<string, { name?: string; status?: string; supported?: boolean; description?: string }>;
    devices?: {
      id: string;
      label?: string;
      status?: string;
      supported?: boolean;
      encoder?: string;
      details?: string;
    }[];
  };
}

interface RawScript {
  title?: string;
  description?: string;
  genre?: string;
  tags?: string[];
  characters?: string[];
  formats?: string[];
  scenes?: {
    background?: string;
    cast?: string[];
    beats?: ({ who?: string; say?: string; action?: string; card?: string; pause?: number } | null)[];
  }[];
  [k: string]: unknown;
}

/* -------------------------------------------------------------- constants */

const AVATAR_TOTAL = 6;

/** Stable character-id -> avatar slot so the same character always looks the same. */
const AVATAR_SLOT: Record<string, number> = {
  narrator: 1,
  bunny: 2,
  bear: 3,
  chick: 4,
  cat: 5,
  elephant: 6,
};

function avatarSlot(name: string): number {
  const key = (name || "").trim().toLowerCase();
  if (AVATAR_SLOT[key]) return AVATAR_SLOT[key];
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0;
  return (h % AVATAR_TOTAL) + 1;
}

function avatarUrl(name: string): string {
  return `/characters/char_avatar_circle_${avatarSlot(name)}.png`;
}

function charLabel(name: string): string {
  return CHAR_LABEL[name] || name;
}

function errorText(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}

const ASPECTS = [
  { value: "9:16", format: "vertical", label: "9:16 (แนวตั้ง)" },
  { value: "1:1", format: "square", label: "1:1 (สี่เหลี่ยม)" },
  { value: "16:9", format: "horizontal", label: "16:9 (แนวนอน)" },
] as const;

type Aspect = (typeof ASPECTS)[number]["value"];

const RESOLUTIONS = ["1080p", "720p", "480p"] as const;
const FPS_OPTIONS = [24, 30, 60] as const;

const ENGINE_3D = "3d_chibi_pastel";
const ENGINE_2D = "2d_cartoon";

const TARGETS = [
  { id: "youtube", label: "YouTube", icon: Monitor, aspect: "16:9" as Aspect },
  { id: "facebook", label: "Facebook", icon: Video, aspect: "9:16" as Aspect },
  { id: "tiktok", label: "TikTok", icon: Clapperboard, aspect: "9:16" as Aspect },
];

/* --------------------------------------------------------------- fragments */

function AvatarStack({
  characters,
  size = 26,
  max = 3,
}: {
  characters: string[];
  size?: number;
  max?: number;
}) {
  const list = characters.filter(Boolean);
  if (!list.length) return <span className="xsmall muted">ไม่มีตัวละคร</span>;
  const shown = list.slice(0, max);
  const rest = list.length - shown.length;
  return (
    <div className="row" style={{ gap: 5 }}>
      {shown.map((c) => (
        <img
          key={c}
          src={avatarUrl(c)}
          alt={charLabel(c)}
          title={charLabel(c)}
          style={{
            width: size,
            height: size,
            borderRadius: "50%",
            objectFit: "cover",
            background: "#fff",
            border: "2px solid #fff",
            boxShadow: "var(--sh-xs)",
            flex: "none",
          }}
        />
      ))}
      {rest > 0 && (
        <span
          className="xsmall muted"
          style={{
            borderRadius: "50%",
            background: "var(--c-primary-soft)",
            color: "var(--c-primary-darker)",
            padding: "2px 7px",
            fontWeight: 700,
          }}
        >
          +{rest}
        </span>
      )}
    </div>
  );
}

function OptionTile({
  selected,
  onClick,
  disabled,
  icon: Icon,
  title,
  text,
}: {
  selected: boolean;
  onClick: () => void;
  disabled?: boolean;
  icon?: LucideIcon;
  title: string;
  text?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        textAlign: "left",
        width: "100%",
        border: `1px solid ${selected ? "var(--c-primary)" : "var(--c-line)"}`,
        background: selected ? "var(--g-primary-soft)" : "#fff",
        borderRadius: 12,
        padding: "10px 12px",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.55 : 1,
        color: "var(--c-ink)",
      }}
    >
      {Icon && (
        <span style={{ display: "grid", placeItems: "center", color: selected ? "var(--c-primary)" : "var(--c-muted)" }}>
          <Icon size={16} />
        </span>
      )}
      <span style={{ minWidth: 0, flex: 1 }}>
        <span style={{ display: "block", fontWeight: 600, fontSize: "var(--fs-sm)" }}>{title}</span>
        {text && (
          <span className="xsmall muted" style={{ display: "block", lineHeight: 1.4 }}>
            {text}
          </span>
        )}
      </span>
      <span
        style={{
          width: 14,
          height: 14,
          borderRadius: "50%",
          flex: "none",
          border: `2px solid ${selected ? "var(--c-primary)" : "var(--c-line-strong)"}`,
          background: selected ? "var(--c-primary)" : "#fff",
        }}
      />
    </button>
  );
}

function RowMenu({
  items,
}: {
  items: { label: string; icon: LucideIcon; onClick: () => void; danger?: boolean }[];
}) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ position: "relative" }}>
      <button
        type="button"
        className="btn btn--ghost btn--icon btn--sm"
        aria-label="เมนูการทำงาน"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
      >
        <MoreVertical size={15} />
      </button>
      {open && (
        <>
          <div
            style={{ position: "fixed", inset: 0, zIndex: 40 }}
            onClick={(e) => {
              e.stopPropagation();
              setOpen(false);
            }}
          />
          <div
            style={{
              position: "absolute",
              right: 0,
              top: "100%",
              zIndex: 41,
              background: "#fff",
              border: "1px solid var(--c-line)",
              borderRadius: 12,
              boxShadow: "var(--sh-lg)",
              padding: 6,
              minWidth: 200,
            }}
          >
            {items.map((it) => (
              <button
                key={it.label}
                type="button"
                className="btn btn--ghost btn--sm"
                style={{
                  width: "100%",
                  justifyContent: "flex-start",
                  color: it.danger ? "var(--c-danger)" : undefined,
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  setOpen(false);
                  it.onClick();
                }}
              >
                <it.icon size={14} /> {it.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------- page */

export default function Scripts() {
  const toast = useToast();

  const { data, loading, error, reload } = useApiData<ScriptsPayload>(
    () => apiGet<ScriptsPayload>("/api/scripts"),
    [],
  );
  const { data: hwData, loading: hwLoading, error: hwError } = useApiData<HardwarePayload>(
    () => apiGet<HardwarePayload>("/api/hardware"),
    [],
  );

  const [search, setSearch] = useState("");
  const [genre, setGenre] = useState("");
  const [sort, setSort] = useState("latest");
  const debounced = useDebounced(search);

  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [activePath, setActivePath] = useState<string | null>(null);

  const [importOpen, setImportOpen] = useState(false);
  const [importText, setImportText] = useState("");
  const [importBusy, setImportBusy] = useState(false);
  const [importResult, setImportResult] = useState<{ errors: string[]; warnings: string[] } | null>(null);

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const [raw, setRaw] = useState<RawScript | null>(null);
  const [rawError, setRawError] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);

  const [platform, setPlatform] = useState<"local" | "flow">("local");
  const [target, setTarget] = useState("tiktok");
  const [deviceId, setDeviceId] = useState("");
  const [engineType, setEngineType] = useState(ENGINE_2D);
  const [resolution, setResolution] = useState<(typeof RESOLUTIONS)[number]>("1080p");
  const [fps, setFps] = useState<(typeof FPS_OPTIONS)[number]>(30);
  const [aspect, setAspect] = useState<Aspect>("9:16");

  const [flow, setFlow] = useState<{ prompts: string[]; title: string; flowUrl: string } | null>(null);
  const [flowBusy, setFlowBusy] = useState(false);

  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<JobPayload | null>(null);
  const [renderBusy, setRenderBusy] = useState(false);
  const [resultFolder, setResultFolder] = useState<string | null>(null);

  const toolRef = useRef<HTMLDivElement | null>(null);

  const hw = hwData?.hardware;
  const hwKnown = !!hw;
  const gpuList = hw?.gpus ?? [];
  const hasGpu = gpuList.length > 0;
  const devices = hw?.devices ?? [];
  const engines = hw?.engines ?? {};
  const encoders = hw?.encoders ?? {};

  const all = useMemo<ScriptSummary[]>(
    () => [...(data?.inbox ?? []), ...(data?.done ?? [])],
    [data],
  );

  const genres = useMemo(
    () =>
      Array.from(new Set(all.map((s) => s.genre).filter(Boolean))).sort((a, b) =>
        a.localeCompare(b, "th"),
      ),
    [all],
  );

  const searched = useMemo(
    () => filterRows(all, debounced, ["title", "genre", "tags", "characters"]),
    [all, debounced],
  );

  const rows = useMemo(() => {
    const list = genre ? searched.filter((s) => s.genre === genre) : searched;
    const out = [...list];
    if (sort === "oldest") {
      out.sort((a, b) => String(a.modifiedAt).localeCompare(String(b.modifiedAt)));
    } else if (sort === "title") {
      out.sort((a, b) => String(a.title).localeCompare(String(b.title), "th"));
    } else {
      out.sort((a, b) => String(b.modifiedAt).localeCompare(String(a.modifiedAt)));
    }
    return out;
  }, [searched, genre, sort]);

  const active = useMemo(
    () => all.find((s) => s.path === activePath) ?? null,
    [all, activePath],
  );

  /* keep a valid selection */
  useEffect(() => {
    if (rows.length === 0) {
      if (activePath) setActivePath(null);
      return;
    }
    if (!activePath || !all.some((s) => s.path === activePath)) {
      setActivePath(rows[0].path);
    }
  }, [rows, all, activePath]);

  /* load the raw script of the selected row */
  useEffect(() => {
    if (!activePath) {
      setRaw(null);
      setRawError(null);
      return;
    }
    let alive = true;
    setRaw(null);
    setRawError(null);
    apiGet<{ ok: boolean; script: RawScript }>("/api/scripts/detail", { path: activePath })
      .then((res) => {
        if (alive) setRaw(res.script);
      })
      .catch((e) => {
        if (alive) setRawError(errorText(e));
      });
    return () => {
      alive = false;
    };
  }, [activePath]);

  /* default the device once the real hardware is known */
  useEffect(() => {
    if (!devices.length) return;
    setDeviceId((prev) => {
      if (prev && devices.some((d) => d.id === prev)) return prev;
      const usable = devices.find((d) => d.supported !== false);
      return usable?.id ?? devices[0].id;
    });
  }, [devices]);

  /* ------------------------------------------------------- render job poll */
  useEffect(() => {
    if (!jobId) return;
    let alive = true;
    const scriptTitle = active?.title || "";

    const tick = async () => {
      try {
        const res = await apiGet<{ ok: boolean; job: JobPayload }>("/api/job", { id: jobId });
        if (!alive) return;
        setJob(res.job);
        const st = res.job.status;
        if (st === "done" || st === "failed" || st === "cancelled") {
          alive = false;
          setJobId(null);
          if (st === "done") {
            reload(true);
            try {
              const clipsRes = await apiGet<{ ok: boolean; clips: ClipEntry[] }>("/api/clips");
              const match = (clipsRes.clips || []).find((c) => c.title === scriptTitle);
              if (match) {
                setResultFolder(match.folder);
                toast.success("สร้างคลิปสำเร็จ", `${match.title} — ${match.folder}`);
              } else {
                toast.success("สร้างคลิปสำเร็จ", `งาน ${res.job.label} เสร็จสิ้น`);
              }
            } catch {
              toast.success("สร้างคลิปสำเร็จ", `งาน ${res.job.label} เสร็จสิ้น`);
            }
          } else if (st === "failed") {
            toast.error("สร้างคลิปไม่สำเร็จ", res.job.error || "ไม่ทราบสาเหตุ");
          } else {
            toast.info("ยกเลิกงานแล้ว", res.job.label);
          }
        }
      } catch (e) {
        if (!alive) return;
        alive = false;
        setJobId(null);
        toast.error("อ่านสถานะงานไม่สำเร็จ", errorText(e));
      }
    };

    const timer = setInterval(tick, 1200);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [jobId, active?.title, reload, toast]);

  /* --------------------------------------------------------------- actions */

  const refresh = () => {
    reload(true);
    toast.info("รีเฟรชรายการบทแล้ว");
  };

  const runImport = async () => {
    const text = importText.trim();
    if (!text) {
      toast.error("ยังไม่ได้ใส่ข้อความ", "วางเนื้อหาไฟล์บท (JSON) ที่ต้องการนำเข้า");
      return;
    }
    setImportBusy(true);
    try {
      const res = await apiPost<{
        ok: boolean;
        path: string;
        id: string;
        warnings: string[];
        errors: string[];
      }>("/api/scripts/import", { text });
      const errors = res.errors ?? [];
      const warnings = res.warnings ?? [];
      setImportResult({ errors, warnings });
      if (errors.length) {
        toast.error("นำเข้าบทไม่สมบูรณ์", errors.join(" · "));
      } else {
        toast.success("นำเข้าบทสำเร็จ", `บท: ${res.id}`);
        if (warnings.length) toast.warn("มีคำเตือนจากการตรวจสอบบท", warnings.join(" · "));
        setImportOpen(false);
        setImportText("");
        setImportResult(null);
      }
      reload(true);
    } catch (e) {
      setImportResult({ errors: [errorText(e)], warnings: [] });
      toast.error("นำเข้าบทไม่สำเร็จ", errorText(e));
    } finally {
      setImportBusy(false);
    }
  };

  const addSample = async () => {
    try {
      const res = await apiPost<{ ok: boolean; added: string[]; count: number }>(
        "/api/scripts/add-sample",
        {},
      );
      toast.success("เพิ่มบทตัวอย่างแล้ว", `เพิ่ม ${res.count} บทจากโฟลเดอร์ตัวอย่าง`);
      reload(true);
    } catch (e) {
      toast.error("เพิ่มบทตัวอย่างไม่สำเร็จ", errorText(e));
    }
  };

  const deleteScripts = async (paths: string[]) => {
    if (!paths.length) return;
    setDeleteBusy(true);
    try {
      const res = await apiPost<{ ok: boolean; removed: string[]; count: number }>(
        "/api/scripts/delete",
        { paths },
      );
      toast.success("ลบบทแล้ว", `ย้ายไปที่โฟลเดอร์ removed ${res.count} ไฟล์`);
      setChecked(new Set());
      setDeleteOpen(false);
      reload(true);
    } catch (e) {
      toast.error("ลบบทไม่สำเร็จ", errorText(e));
    } finally {
      setDeleteBusy(false);
    }
  };

  const sendToFlow = async () => {
    if (!active) return;
    setFlowBusy(true);
    try {
      const res = await apiPost<{
        ok: boolean;
        prompts: string[];
        title: string;
        flowUrl: string;
      }>("/api/scripts/send-to-flow", {
        path: active.path,
        format: ASPECTS.find((a) => a.value === aspect)?.format ?? "vertical",
      });
      setFlow(res);
      toast.success("สร้างพรอมต์สำหรับ Google Flow แล้ว", `บท: ${res.title}`);
    } catch (e) {
      toast.error("สร้างพรอมต์ไม่สำเร็จ", errorText(e));
    } finally {
      setFlowBusy(false);
    }
  };

  const startRender = async () => {
    if (!active) return;
    setRenderBusy(true);
    setResultFolder(null);
    try {
      const device = devices.find((d) => d.id === deviceId);
      const res = await apiPost<{ ok: boolean; jobId: string }>("/api/render", {
        path: active.path,
        format: ASPECTS.find((a) => a.value === aspect)?.format ?? "vertical",
        resolution,
        fps,
        encoder: device?.encoder || "auto",
        engineType,
        deviceId,
        chibiOptions: {},
      });
      setJob(null);
      setJobId(res.jobId);
      toast.info("เริ่มสร้างคลิปแล้ว", `งาน: ${res.jobId}`);
    } catch (e) {
      toast.error("เริ่มสร้างคลิปไม่สำเร็จ", errorText(e));
    } finally {
      setRenderBusy(false);
    }
  };

  const cancelRender = async () => {
    if (!jobId) return;
    try {
      await apiPost("/api/job/cancel", { id: jobId });
      setJobId(null);
      toast.info("ส่งคำสั่งยกเลิกงานแล้ว");
    } catch (e) {
      toast.error("ยกเลิกงานไม่สำเร็จ", errorText(e));
    }
  };

  const copyText = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(`คัดลอก${label}แล้ว`);
    } catch (e) {
      toast.error(`คัดลอก${label}ไม่สำเร็จ`, errorText(e));
    }
  };

  const focusTool = () => {
    toolRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  /* ---------------------------------------------------------------- table */

  const columns: Column<ScriptSummary>[] = [
    {
      key: "cover",
      header: "",
      width: 64,
      render: (s) => <AvatarStack characters={s.characters ?? []} size={24} max={2} />,
    },
    {
      key: "title",
      header: "ชื่อบท",
      render: (s) => (
        <div style={{ minWidth: 0 }}>
          <div className="strong truncate" title={s.title}>
            {s.title}
          </div>
          <div className="row" style={{ gap: 6, marginTop: 3 }}>
            <StatusBadge tone={s.group === "done" ? "success" : "primary"}>
              {s.group === "done" ? "สร้างแล้ว" : "รอสร้างคลิป"}
            </StatusBadge>
            {s.genre && <span className="xsmall muted truncate">{s.genre}</span>}
          </div>
        </div>
      ),
    },
    {
      key: "characters",
      header: "ตัวละคร",
      render: (s) => <AvatarStack characters={s.characters ?? []} size={28} max={3} />,
    },
    {
      key: "review",
      header: "ผลการตรวจสอบ",
      render: (s) =>
        s.group === "done" ? (
          <StatusBadge tone="success" dot>
            ผ่าน
          </StatusBadge>
        ) : (
          <StatusBadge tone="warn" dot>
            รอตรวจสอบ
          </StatusBadge>
        ),
    },
    {
      key: "created",
      header: "วันที่สร้าง",
      width: 150,
      render: (s) => <span className="small muted">{formatThaiDate(s.modifiedAt)}</span>,
    },
    {
      key: "actions",
      header: "",
      width: 52,
      align: "right",
      render: (s) => (
        <RowMenu
          items={[
            {
              label: "ส่งไปสร้างคลิป",
              icon: Send,
              onClick: () => {
                setActivePath(s.path);
                setPlatform("local");
                setTimeout(focusTool, 60);
              },
            },
            {
              label: "ดูรายละเอียด",
              icon: Eye,
              onClick: () => setActivePath(s.path),
            },
            {
              label: "ลบบทนี้",
              icon: Trash2,
              danger: true,
              onClick: () => {
                setChecked(new Set([s.path]));
                setDeleteOpen(true);
              },
            },
          ]}
        />
      ),
    },
  ];

  const selectedPaths = useMemo(
    () => Array.from(checked).filter((p) => all.some((s) => s.path === p)),
    [checked, all],
  );

  /* ---------------------------------------------------------------- render */

  const engine3d = engines[ENGINE_3D];
  const engine2d = engines[ENGINE_2D];
  const engineReady = (key: string) => hwKnown && engines[key]?.supported !== false;

  return (
    <div>
      <PageHeader
        icon={FileText}
        title="บทที่รอสร้างคลิป"
        subtitle="จัดการบทการ์ตูนเพื่อสร้างคลิปพร้อมโพสต์ในรูปแบบ TikTok, YouTube, Shopee และ Facebook"
        actions={
          <>
            <button className="btn btn--outline" onClick={refresh}>
              <RefreshCw size={15} /> รีเฟรช
            </button>
            <button className="btn btn--mint" onClick={addSample}>
              <Plus size={15} /> เพิ่มบทตัวอย่าง
            </button>
            <button className="btn btn--primary" onClick={() => setImportOpen(true)}>
              <Upload size={15} /> เพิ่มบทจากไฟล์...
            </button>
            <button
              className="btn btn--danger"
              disabled={!selectedPaths.length}
              onClick={() => setDeleteOpen(true)}
            >
              <Trash2 size={15} /> ลบบทที่เลือก
            </button>
          </>
        }
      />

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.45fr) minmax(0, 1fr)",
          gap: 16,
          alignItems: "start",
        }}
      >
        {/* ------------------------------------------------------- left column */}
        <div className="col" style={{ gap: 16 }}>
          <PastelCard flush>
            <div
              className="row row--wrap"
              style={{ padding: "14px 16px", borderBottom: "1px solid var(--c-line)", gap: 10 }}
            >
              <SearchInput
                value={search}
                onChange={setSearch}
                placeholder="ค้นหาชื่อเรื่อง หรือชื่อตัวละคร..."
                style={{ flex: 1, minWidth: 200 }}
              />
              <select
                className="select"
                value={genre}
                onChange={(e) => setGenre(e.target.value)}
                style={{ width: 170 }}
                aria-label="กรองตามหมวดหมู่"
              >
                <option value="">ทุกหมวดหมู่</option>
                {genres.map((g) => (
                  <option key={g} value={g}>
                    {g}
                  </option>
                ))}
              </select>
              <select
                className="select"
                value={sort}
                onChange={(e) => setSort(e.target.value)}
                style={{ width: 160 }}
                aria-label="เรียงล่าสุด"
              >
                <option value="latest">เรียงล่าสุด</option>
                <option value="oldest">เรียงเก่าสุด</option>
                <option value="title">ชื่อ ก-ฮ</option>
              </select>
            </div>

            {loading ? (
              <LoadingState label="กำลังโหลดรายการบท..." />
            ) : error ? (
              <ErrorState message={error} onRetry={() => reload()} />
            ) : (
              <DataTable<ScriptSummary>
                columns={columns}
                rows={rows}
                rowKey={(s) => s.path}
                selected={checked}
                onSelect={(key, isChecked) =>
                  setChecked((prev) => {
                    const next = new Set(prev);
                    if (isChecked) next.add(key);
                    else next.delete(key);
                    return next;
                  })
                }
                onRowClick={(s) => setActivePath(s.path)}
                empty={
                  <EmptyState
                    title="ยังไม่มีบทในรายการ"
                    text={
                      all.length
                        ? "ไม่พบบทที่ตรงกับคำค้นหาหรือหมวดหมู่ที่เลือก ลองเปลี่ยนตัวกรองดูอีกครั้ง"
                        : "ยังไม่มีบทในโฟลเดอร์ inbox ของโปรแกรม กดปุ่มเพิ่มบทจากไฟล์ หรือเพิ่มบทตัวอย่างเพื่อเริ่มต้น"
                    }
                  />
                }
              />
            )}

            {!loading && !error && (
              <div className="pagination">
                <span className="small muted">
                  แสดง {rows.length} จาก {all.length} รายการ
                  {checked.size > 0 ? ` (เลือกไว้ ${selectedPaths.length} รายการ)` : ""}
                </span>
                <span className="small muted">
                  รอสร้างคลิป {data?.inbox?.length ?? 0} บท · สร้างแล้ว {data?.done?.length ?? 0} บท
                </span>
              </div>
            )}
          </PastelCard>
        </div>

        {/* ------------------------------------------------------ right column */}
        <div className="col" style={{ gap: 16 }}>
          <PastelCard
            title={active ? active.title : "รายละเอียดบท"}
            subtitle={active ? `ไฟล์: ${active.fileName}` : "เลือกบทจากตารางเพื่อดูรายละเอียด"}
            icon={Eye}
            iconTone="pink"
          >
            {!active ? (
              <EmptyState
                title="ยังไม่ได้เลือกบท"
                text="คลิกที่แถวในตารางด้านซ้ายเพื่อดูรายละเอียดบทและเตรียมสร้างคลิป"
                icon={FileText}
              />
            ) : (
              <div className="col" style={{ gap: 14 }}>
                <div
                  style={{
                    borderRadius: 16,
                    background: "var(--g-primary-soft)",
                    padding: 16,
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                  }}
                >
                  <AvatarStack characters={active.characters ?? []} size={52} max={4} />
                  <div style={{ minWidth: 0 }}>
                    <div className="small strong truncate" title={active.title}>
                      {active.title}
                    </div>
                    <div className="xsmall muted">
                      {active.sceneCount} ฉาก · {active.beatCount} จังหวะ
                    </div>
                  </div>
                </div>

                {rawError && (
                  <div className="small" style={{ color: "var(--c-danger)" }}>
                    อ่านรายละเอียดบทไม่สำเร็จ: {rawError}
                  </div>
                )}

                <p className="small" style={{ margin: 0, lineHeight: 1.7, color: "#4b4875" }}>
                  {active.description || "บทนี้ยังไม่มีคำอธิบาย"}
                </p>

                <div>
                  <div className="xsmall muted" style={{ marginBottom: 6 }}>
                    ตัวละครในบท
                  </div>
                  <div className="row row--wrap" style={{ gap: 10 }}>
                    {(active.characters ?? []).length === 0 && (
                      <span className="small muted">บทนี้ไม่มีตัวละครที่ระบุ</span>
                    )}
                    {(active.characters ?? []).map((c) => (
                      <div key={c} className="row" style={{ gap: 6 }}>
                        <img
                          src={avatarUrl(c)}
                          alt={charLabel(c)}
                          title={charLabel(c)}
                          style={{
                            width: 34,
                            height: 34,
                            borderRadius: "50%",
                            objectFit: "cover",
                            border: "2px solid #fff",
                            boxShadow: "var(--sh-xs)",
                          }}
                        />
                        <span className="small">{charLabel(c)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="row row--wrap" style={{ gap: 6 }}>
                  {active.genre && <Chip tone="primary">หมวด: {active.genre}</Chip>}
                  <Chip tone="blue">ฉาก: {active.sceneCount}</Chip>
                  <Chip tone="mint">จังหวะ: {active.beatCount}</Chip>
                  {(active.formats ?? []).map((f) => (
                    <Chip key={f} tone="orange">
                      รูปแบบ: {f === "vertical" ? "แนวตั้ง" : f === "horizontal" ? "แนวนอน" : f}
                    </Chip>
                  ))}
                </div>

                <div className="row row--wrap" style={{ gap: 8 }}>
                  <button className="btn btn--primary" onClick={focusTool}>
                    <Clapperboard size={15} /> สร้างคลิป
                  </button>
                  <button className="btn btn--soft" onClick={() => setEditOpen(true)} disabled={!raw}>
                    <Pencil size={15} /> แก้ไขบท
                  </button>
                  <button className="btn btn--outline" onClick={() => setPreviewOpen(true)} disabled={!raw}>
                    <Eye size={15} /> ดูตัวอย่าง
                  </button>
                </div>
              </div>
            )}
          </PastelCard>

          {/* ------------------------------------------- animation tool card */}
          <div ref={toolRef}>
            <PastelCard
              title="เครื่องมือสร้าง Animation"
              subtitle="ตั้งค่าการสร้างคลิปก่อนส่งงาน เลือกวิธีสร้าง แพลตฟอร์ม อุปกรณ์ประมวลผล และคุณภาพตามต้องการ"
              icon={Clapperboard}
              iconTone="mint"
            >
              <div className="col" style={{ gap: 16 }}>
                {/* step 1 */}
                <Step
                  n={1}
                  tone="primary"
                  title="เลือกสิ่งที่จะทำ"
                  text={active ? `บทที่กำลังทำงาน: ${active.title}` : "ยังไม่ได้เลือกบท"}
                />
                <div className="grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
                  <OptionTile
                    selected={platform === "local"}
                    onClick={() => setPlatform("local")}
                    icon={Monitor}
                    title="Local Animation"
                    text="สร้างด้วย AI ในเครื่อง (เรนเดอร์ในเครื่องนี้)"
                  />
                  <OptionTile
                    selected={platform === "flow"}
                    onClick={() => setPlatform("flow")}
                    icon={Send}
                    title="Google Flow"
                    text="สร้างด้วย Google AI (ส่งออกเป็นพรอมต์ไปยัง flow.google.com)"
                  />
                </div>

                {/* step 2 */}
                <Step n={2} tone="pink" title="แพลตฟอร์มปลายทาง" text="เลือกปลายทางที่จะเอาคลิปไปใช้" />
                <div className="grid" style={{ gridTemplateColumns: "1fr 1fr 1fr" }}>
                  {TARGETS.map((t) => (
                    <OptionTile
                      key={t.id}
                      selected={target === t.id}
                      onClick={() => {
                        setTarget(t.id);
                        setAspect(t.aspect);
                      }}
                      icon={t.icon}
                      title={t.label}
                      text={t.aspect}
                    />
                  ))}
                </div>

                {/* step 3 — real hardware */}
                <Step
                  n={3}
                  tone="blue"
                  title="อุปกรณ์ประมวลผล"
                  text="ข้อมูลด้านล่างมาจากการตรวจเครื่องจริงของโปรแกรม"
                />
                <div className="col" style={{ gap: 8 }}>
                  {hwLoading && (
                    <div className="small row" style={{ gap: 8, color: "var(--c-muted)" }}>
                      <Loader2 size={15} className="spin" />
                      <span>กำลังตรวจสอบอุปกรณ์ประมวลผลของเครื่อง...</span>
                    </div>
                  )}
                  {hwError && (
                    <div
                      className="small row"
                      style={{
                        gap: 8,
                        background: "var(--c-danger-soft)",
                        color: "var(--c-danger)",
                        padding: "9px 12px",
                        borderRadius: 12,
                      }}
                    >
                      <AlertTriangle size={15} />
                      <span>ตรวจสอบอุปกรณ์ประมวลผลไม่สำเร็จ: {hwError}</span>
                    </div>
                  )}
                  {!hwLoading && !hwError && !hasGpu && (
                    <div
                      className="small row"
                      style={{
                        gap: 8,
                        background: "var(--c-warn-soft)",
                        color: "var(--c-warn)",
                        padding: "9px 12px",
                        borderRadius: 12,
                      }}
                    >
                      <AlertTriangle size={15} />
                      <span>ไม่พบการ์ดกราฟิก (GPU) ในเครื่องนี้ ระบบจะเรนเดอร์ด้วย CPU</span>
                    </div>
                  )}
                  {hasGpu && (
                    <div className="small row row--wrap" style={{ gap: 6 }}>
                      {gpuList.map((g, i) => (
                        <Chip key={`${g.name}-${i}`} tone="blue">
                          GPU: {g.name || "ไม่ทราบชื่อ"}
                          {g.provider ? ` (${g.provider})` : ""}
                        </Chip>
                      ))}
                    </div>
                  )}

                  <div className="row row--wrap" style={{ gap: 6 }}>
                    {Object.keys(encoders).length === 0 && (
                      <span className="xsmall muted">ยังไม่มีผลตรวจสอบตัวเข้ารหัสวิดีโอ</span>
                    )}
                    {Object.entries(encoders).map(([name, v]) => (
                      <Chip key={name} tone={v?.ok ? "mint" : "pink"}>
                        {name}: {v?.ok ? "ใช้ได้" : "ใช้ไม่ได้"}
                      </Chip>
                    ))}
                  </div>

                  {devices.length === 0 ? (
                    <div className="small muted">
                      {hwLoading
                        ? "กำลังตรวจสอบอุปกรณ์ประมวลผล..."
                        : "ยังไม่พบอุปกรณ์ประมวลผลที่ตรวจสอบได้"}
                    </div>
                  ) : (
                    <div className="grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
                      {devices.map((d) => (
                        <OptionTile
                          key={d.id}
                          selected={deviceId === d.id}
                          disabled={d.supported === false}
                          onClick={() => setDeviceId(d.id)}
                          icon={d.id === "cpu" ? Cpu : Zap}
                          title={d.label || d.id}
                          text={
                            d.supported === false
                              ? `ใช้ไม่ได้ — ${d.status || "ไม่รองรับ"}`
                              : `${d.status || ""}${d.details ? ` | ${d.details}` : ""}`
                          }
                        />
                      ))}
                    </div>
                  )}

                  <div className="xsmall muted">
                    เอนจินที่ตรวจพบ:{" "}
                    {Object.keys(engines).length
                      ? Object.values(engines)
                          .map((e) => `${e?.name || ""} (${e?.status || "ไม่ทราบสถานะ"})`)
                          .join(", ")
                      : "ไม่ทราบข้อมูล"}
                  </div>
                </div>

                {/* step 4 */}
                <Step n={4} tone="orange" title="รูปแบบภาพ" text="เลือกสไตล์การ์ตูนของคลิป" />
                <div className="grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
                  <OptionTile
                    selected={engineType === ENGINE_3D}
                    disabled={!engineReady(ENGINE_3D)}
                    onClick={() => setEngineType(ENGINE_3D)}
                    icon={Layers}
                    title="3D Cartoon"
                    text={
                      !hwKnown
                        ? "ยังตรวจสอบสถานะเอนจินไม่ได้"
                        : engineReady(ENGINE_3D)
                          ? engine3d?.status || "การ์ตูน 3D สไตล์น่ารัก"
                          : `ใช้ไม่ได้ — ${engine3d?.status || "ยังไม่ได้ติดตั้งส่วนประกอบ"}`
                    }
                  />
                  <OptionTile
                    selected={engineType === ENGINE_2D}
                    disabled={!engineReady(ENGINE_2D)}
                    onClick={() => setEngineType(ENGINE_2D)}
                    icon={Video}
                    title="2D Animation"
                    text={
                      !hwKnown
                        ? "ยังตรวจสอบสถานะเอนจินไม่ได้"
                        : engineReady(ENGINE_2D)
                          ? engine2d?.status || "การ์ตูน 2 มิติ"
                          : `ใช้ไม่ได้ — ${engine2d?.status || "ยังไม่ได้ติดตั้งส่วนประกอบ"}`
                    }
                  />
                </div>

                {/* step 5 */}
                <Step n={5} tone="primary" title="ค่าความละเอียด" text="กำหนดขนาดภาพ พรีเฟรม และอัตราส่วนภาพ" />
                <div className="grid" style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
                  <label className="field">
                    <span className="field__label">ความละเอียด (Resolution)</span>
                    <select
                      className="select"
                      value={resolution}
                      onChange={(e) => setResolution(e.target.value as (typeof RESOLUTIONS)[number])}
                    >
                      {RESOLUTIONS.map((r) => (
                        <option key={r} value={r}>
                          {r === "1080p" ? "1920 x 1080 (Full HD)" : r === "720p" ? "1280 x 720 (HD)" : "854 x 480 (SD)"}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span className="field__label">พรีเฟรม (FPS)</span>
                    <select
                      className="select"
                      value={fps}
                      onChange={(e) => setFps(Number(e.target.value) as (typeof FPS_OPTIONS)[number])}
                    >
                      {FPS_OPTIONS.map((f) => (
                        <option key={f} value={f}>
                          {f} FPS
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span className="field__label">อัตราส่วนภาพ (Aspect Ratio)</span>
                    <select
                      className="select"
                      value={aspect}
                      onChange={(e) => setAspect(e.target.value as Aspect)}
                    >
                      {ASPECTS.map((a) => (
                        <option key={a.value} value={a.value}>
                          {a.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                {/* google flow panel */}
                {platform === "flow" && (
                  <div className="col" style={{ gap: 8 }}>
                    <div className="small muted">
                      Google Flow สร้างคลิปบนเว็บไซต์ — โปรแกรมนี้จัดเตรียมพรอมต์ให้คุณ
                      แล้วเปิดหน้าเว็บให้เท่านั้น การโพสต์/เรนเดอร์จริงทำบน Google Flow
                    </div>
                    <div className="row row--wrap" style={{ gap: 8 }}>
                      <button
                        className="btn btn--soft"
                        onClick={sendToFlow}
                        disabled={!active || flowBusy}
                      >
                        {flowBusy ? <Loader2 size={15} className="spin" /> : <Send size={15} />} สร้างพรอมต์
                        จากบท
                      </button>
                      <button
                        className="btn btn--outline"
                        disabled={!flow?.flowUrl}
                        onClick={() => {
                          if (!flow?.flowUrl) return;
                          openUrl(flow.flowUrl).catch((e) =>
                            toast.error("เปิด Google Flow ไม่สำเร็จ", errorText(e)),
                          );
                        }}
                      >
                        เปิด Google Flow
                      </button>
                      {!!flow?.prompts?.length && (
                        <button
                          className="btn btn--outline"
                          onClick={() => copyText(flow.prompts.join("\n\n"), "พรอมต์")}
                        >
                          <Copy size={15} /> คัดลอกพรอมต์
                        </button>
                      )}
                    </div>
                    {!!flow?.prompts?.length && (
                      <textarea
                        className="textarea"
                        readOnly
                        value={flow.prompts.join("\n\n")}
                        style={{ minHeight: 160, fontFamily: "var(--font-thai)" }}
                      />
                    )}
                  </div>
                )}

                {/* job progress */}
                {job && (
                  <div className="col" style={{ gap: 8 }}>
                    <div className="row row--between">
                      <span className="small strong">{job.label}</span>
                      <span className="small muted">{Math.round(job.progress || 0)}%</span>
                    </div>
                    <div className="progress">
                      <div className="progress__bar" style={{ width: `${Math.min(100, job.progress || 0)}%` }} />
                    </div>
                    <div className="log">{job.log?.join("\n") || "กำลังทำงาน..."}</div>
                    {job.error && <div className="log log__err">{job.error}</div>}
                  </div>
                )}

                {/* action row */}
                <div className="row row--wrap" style={{ gap: 8 }}>
                  {platform === "local" ? (
                    <button
                      className="btn btn--primary"
                      onClick={startRender}
                      disabled={!active || !!jobId || renderBusy}
                    >
                      {renderBusy || jobId ? (
                        <Loader2 size={15} className="spin" />
                      ) : (
                        <Clapperboard size={15} />
                      )}{" "}
                      สร้างคลิป
                    </button>
                  ) : (
                    <button className="btn btn--primary" onClick={sendToFlow} disabled={!active || flowBusy}>
                      <Send size={15} /> ส่งออกไป Google Flow
                    </button>
                  )}

                  {!!jobId && (
                    <button className="btn btn--outline" onClick={cancelRender}>
                      ยกเลิกงาน
                    </button>
                  )}

                  <button className="btn btn--soft" onClick={() => setEditOpen(true)} disabled={!raw}>
                    <Pencil size={15} /> แก้ไขบท
                  </button>

                  {resultFolder && (
                    <button
                      className="btn btn--outline"
                      onClick={() => {
                        revealPath(resultFolder).catch((e) =>
                          toast.error("เปิดโฟลเดอร์คลิปไม่สำเร็จ", errorText(e)),
                        );
                      }}
                    >
                      <FolderOpen size={15} /> เปิดโฟลเดอร์คลิปที่สร้าง
                    </button>
                  )}

                  <button
                    className="btn btn--danger"
                    disabled={!selectedPaths.length}
                    onClick={() => setDeleteOpen(true)}
                  >
                    <Trash2 size={15} /> ลบบทที่เลือก
                  </button>
                </div>
              </div>
            </PastelCard>
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------------ modals */}
      <Modal
        open={importOpen}
        title="เพิ่มบทจากไฟล์"
        icon={Upload}
        onClose={() => {
          setImportOpen(false);
          setImportResult(null);
        }}
        width={720}
        footer={
          <>
            <button
              className="btn btn--outline"
              onClick={() => {
                setImportOpen(false);
                setImportResult(null);
              }}
            >
              ยกเลิก
            </button>
            <button className="btn btn--primary" onClick={runImport} disabled={importBusy}>
              {importBusy ? <Loader2 size={15} className="spin" /> : <Upload size={15} />} นำเข้าบท
            </button>
          </>
        }
      >
        <div className="col" style={{ gap: 10 }}>
          <div className="small muted">
            วางเนื้อหาไฟล์บท (JSON) ที่ต้องการนำเข้า โปรแกรมจะบันทึกลงโฟลเดอร์ inbox
            พร้อมตรวจสอบความครบถ้วนของบทให้อัตโนมัติ
          </div>
          <textarea
            className="textarea"
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            placeholder='{"title": "ชื่อบท", "characters": ["bunny"], "scenes": [...]}'
            style={{ minHeight: 280, fontFamily: "var(--font-thai)" }}
          />
          {importResult && importResult.errors.length > 0 && (
            <div
              className="small col"
              style={{
                gap: 4,
                background: "var(--c-danger-soft)",
                color: "var(--c-danger)",
                padding: "10px 12px",
                borderRadius: 12,
              }}
            >
              <strong>พบข้อผิดพลาดในบท:</strong>
              {importResult.errors.map((e, i) => (
                <span key={i}>• {e}</span>
              ))}
            </div>
          )}
          {importResult && importResult.warnings.length > 0 && (
            <div
              className="small col"
              style={{
                gap: 4,
                background: "var(--c-warn-soft)",
                color: "var(--c-warn)",
                padding: "10px 12px",
                borderRadius: 12,
              }}
            >
              <strong>คำเตือนจากการตรวจสอบบท:</strong>
              {importResult.warnings.map((w, i) => (
                <span key={i}>• {w}</span>
              ))}
            </div>
          )}
        </div>
      </Modal>

      <Modal
        open={editOpen}
        title="แก้ไขบท (ข้อมูลดิบของไฟล์บท)"
        icon={Pencil}
        onClose={() => setEditOpen(false)}
        width={820}
        footer={
          <>
            <button className="btn btn--outline" onClick={() => setEditOpen(false)}>
              ปิด
            </button>
            <button
              className="btn btn--primary"
              onClick={() => copyText(JSON.stringify(raw ?? {}, null, 2), "JSON ของบท")}
            >
              <Copy size={15} /> คัดลอก JSON
            </button>
          </>
        }
      >
        <div className="col" style={{ gap: 10 }}>
          <div className="small muted">
            ไฟล์บทต้นฉบับถูกจัดการโดย Python Engine — คัดลอก JSON ไปแก้ไขแล้วนำเข้ากลับได้
            ผ่านปุ่มเพิ่มบทจากไฟล์
          </div>
          <textarea
            className="textarea"
            readOnly
            value={raw ? JSON.stringify(raw, null, 2) : ""}
            style={{ minHeight: 380, fontFamily: "Cascadia Mono, Consolas, monospace", fontSize: 12 }}
          />
        </div>
      </Modal>

      <Modal
        open={previewOpen}
        title="ตัวอย่างเนื้อหาบท"
        icon={Eye}
        onClose={() => setPreviewOpen(false)}
        width={760}
        footer={
          <button className="btn btn--outline" onClick={() => setPreviewOpen(false)}>
            ปิด
          </button>
        }
      >
        <div className="col" style={{ gap: 14 }}>
          {(raw?.scenes ?? []).length === 0 && (
            <div className="small muted">บทนี้ไม่มีฉากให้แสดงตัวอย่าง</div>
          )}
          {(raw?.scenes ?? []).map((sc, si) => (
            <div key={si} className="col" style={{ gap: 8 }}>
              <div className="row row--wrap" style={{ gap: 8 }}>
                <Chip tone="primary">ฉากที่ {si + 1}</Chip>
                {sc.background && <Chip tone="blue">พื้นหลัง: {sc.background}</Chip>}
                {(sc.cast ?? []).map((c) => (
                  <Chip key={c} tone="mint">
                    {charLabel(c)}
                  </Chip>
                ))}
              </div>
              <div className="col" style={{ gap: 6 }}>
                {(sc.beats ?? []).map((b, bi) => {
                  if (!b) return null;
                  if (typeof b.pause === "number") {
                    return (
                      <div key={bi} className="xsmall muted">
                        · หยุดภาพ {b.pause} วินาที
                      </div>
                    );
                  }
                  return (
                    <div key={bi} className="row" style={{ gap: 8, alignItems: "flex-start" }}>
                      {b.who && (
                        <img
                          src={avatarUrl(b.who)}
                          alt={charLabel(b.who)}
                          title={charLabel(b.who)}
                          style={{
                            width: 24,
                            height: 24,
                            borderRadius: "50%",
                            objectFit: "cover",
                            flex: "none",
                          }}
                        />
                      )}
                      <div style={{ minWidth: 0 }}>
                        <div className="xsmall strong">{b.who ? charLabel(b.who) : "ฉาก"}</div>
                        <div className="small">{b.say || b.card || b.action || "—"}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </Modal>

      <ConfirmDialog
        open={deleteOpen}
        danger
        title="ยืนยันการลบบท"
        confirmLabel="ลบบท"
        cancelLabel="ยกเลิก"
        message={
          <div className="col" style={{ gap: 8 }}>
            <div>
              ต้องการลบบทที่เลือก <strong>{selectedPaths.length}</strong> รายการ
              ใช่หรือไม่? ไฟล์จะถูกย้ายไปยังโฟลเดอร์ removed ของโปรแกรม
            </div>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {selectedPaths.slice(0, 8).map((p) => (
                <li key={p} className="small">
                  {p.split(/[\\/]/).pop()}
                </li>
              ))}
            </ul>
            {deleteBusy && <div className="small muted">กำลังลบ...</div>}
          </div>
        }
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => deleteScripts(selectedPaths)}
      />
    </div>
  );
}
