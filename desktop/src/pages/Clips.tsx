import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { openUrl } from "@tauri-apps/plugin-opener";
import {
  ClipboardCopy,
  Copy,
  ExternalLink,
  FolderOpen,
  Info,
  MoreVertical,
  RefreshCw,
  Trash2,
  Upload,
  Video,
  type LucideIcon,
} from "lucide-react";
import {
  STATUS_LABEL,
  apiGet,
  apiPost,
  revealPath,
  type ClipEntry,
  type JobPayload,
  type PostingStatus,
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
  formatThaiDate,
  type BadgeTone,
} from "../components/common/ui";
import { DataTable, Pagination, SearchInput, filterRows, useDebounced, type Column } from "../components/common/DataTable";
import { ConfirmDialog, useToast } from "../components/common/feedback";
import { useApiData } from "../hooks/useApiData";
import { VideoPlayer, VideoThumbnail } from "../components/media/VideoPlayer";

/* ------------------------------------------------------------------ types */

interface ClipsPayload {
  ok: boolean;
  clips: ClipEntry[];
}

interface PostingStatusPayload {
  ok: boolean;
  posting: PostingStatus;
}

/* -------------------------------------------------------------- constants */

const PER_PAGE = 8;

const FORMAT_LABEL: Record<string, { label: string; tone: BadgeTone }> = {
  vertical: { label: "9:16", tone: "primary" },
  horizontal: { label: "16:9", tone: "blue" },
  square: { label: "1:1", tone: "pink" },
};

const FORMAT_ORDER = ["vertical", "horizontal", "square"];

/** Platforms where publishing is a manual step — we only export the caption. */
const MANUAL_EXPORT_TARGETS = [
  { id: "shopee", label: "Shopee", url: "https://seller.shopee.co.th/" },
  { id: "facebook_profile", label: "Facebook Profile", url: "https://www.facebook.com/" },
];

/** Platforms this product can publish through a real API path. */
const API_PUBLISH_TARGETS = [
  { id: "youtube", label: "YouTube", route: "/create/youtube", tone: "#FF0000" },
  { id: "facebook_page", label: "Facebook Page", route: "/create/facebook_page", tone: "#1877F2" },
  { id: "tiktok", label: "TikTok (แบบร่าง)", route: "/create/tiktok", tone: "#111111" },
];

function errorText(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}

function clipFormats(clip: ClipEntry): string[] {
  const files = clip.files || {};
  return FORMAT_ORDER.filter((f) => !!files[f]);
}

function statusTone(status: string): BadgeTone {
  switch (status) {
    case "done":
    case "posted":
    case "posted_manual":
      return "success";
    case "failed":
    case "rejected":
      return "danger";
    case "ready_for_approval":
      return "info";
    case "approved":
      return "primary";
    case "cancelled":
      return "muted";
    default:
      return "muted";
  }
}

/** Mirrors the engine's own caption builder (taoyong/publish/__init__.py). */
function buildCaption(clip: ClipEntry, platform: string): string {
  const prepared = (clip.platformCaptions || {})[platform] as
    | { title?: string; description?: string; tags?: string[] }
    | undefined;
  const title = String(prepared?.title ?? clip.title ?? "").trim();
  const desc = String(prepared?.description ?? clip.description ?? "").trim();
  const tags = prepared?.tags ?? clip.tags ?? [];
  const hashtags = tags
    .slice(0, 8)
    .map((t) => "#" + String(t).replace(/\s+/g, ""))
    .join(" ");
  if (platform === "youtube") {
    return [desc, hashtags].filter(Boolean).join("\n\n");
  }
  return [title, desc, hashtags].filter(Boolean).join("\n\n");
}

function hashtagsOf(clip: ClipEntry): string {
  return (clip.tags ?? [])
    .slice(0, 8)
    .map((t) => "#" + String(t).replace(/\s+/g, ""))
    .join(" ");
}

/* --------------------------------------------------------------- fragments */

function RowMenu({ items }: { items: { label: string; icon: LucideIcon; onClick: () => void; danger?: boolean }[] }) {
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

function PlatformButton({
  label,
  icon: Icon,
  onClick,
  tone,
  disabled = false,
}: {
  label: string;
  icon: LucideIcon;
  onClick: () => void;
  tone: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        flex: 1,
        minWidth: 108,
        padding: "9px 12px",
        borderRadius: 12,
        border: "1px solid var(--c-line)",
        background: "#fff",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.55 : 1,
        fontWeight: 600,
        fontSize: "var(--fs-xs)",
        color: "var(--c-ink)",
        textAlign: "left",
      }}
    >
      <span
        style={{
          width: 22,
          height: 22,
          borderRadius: 7,
          display: "grid",
          placeItems: "center",
          color: "#fff",
          background: tone,
          flex: "none",
        }}
      >
        <Icon size={12} />
      </span>
      <span className="truncate">{label}</span>
    </button>
  );
}

/* ------------------------------------------------------------------- page */

export default function Clips() {
  const toast = useToast();
  const navigate = useNavigate();

  const { data, loading, error, reload } = useApiData<ClipsPayload>(
    () => apiGet<ClipsPayload>("/api/clips"),
    [],
  );

  const { data: posting } = useApiData<PostingStatusPayload>(
    () => apiGet<PostingStatusPayload>("/api/posting/status"),
    [],
  );

  useEffect(() => {
    const map: Record<string, boolean> = {};
    for (const [key, value] of Object.entries(posting?.posting?.platforms ?? {})) {
      map[key] = !!value.connected;
    }
    setConnected(map);
  }, [posting]);

  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("latest");
  const [page, setPage] = useState(1);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [activeFolder, setActiveFolder] = useState<string | null>(null);
  const [playFormat, setPlayFormat] = useState<string>("vertical");

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string[]>([]);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const [connected, setConnected] = useState<Record<string, boolean>>({});
  const [publishing, setPublishing] = useState<string | null>(null);

  const debounced = useDebounced(search);

  const clips = useMemo<ClipEntry[]>(() => data?.clips ?? [], [data]);

  const searched = useMemo(
    () => filterRows(clips, debounced, ["title", "tags", "description"]),
    [clips, debounced],
  );

  const rows = useMemo(() => {
    const out = [...searched];
    if (sort === "oldest") {
      out.sort((a, b) => String(a.createdAt).localeCompare(String(b.createdAt)));
    } else if (sort === "title") {
      out.sort((a, b) => String(a.title).localeCompare(String(b.title), "th"));
    } else if (sort === "longest") {
      out.sort((a, b) => Number(b.durationSeconds || 0) - Number(a.durationSeconds || 0));
    } else {
      out.sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
    }
    return out;
  }, [searched, sort]);

  const pageCount = Math.max(1, Math.ceil(rows.length / PER_PAGE));
  const safePage = Math.min(page, pageCount);
  const paged = useMemo(
    () => rows.slice((safePage - 1) * PER_PAGE, safePage * PER_PAGE),
    [rows, safePage],
  );

  const active = useMemo(
    () => clips.find((c) => c.folder === activeFolder) ?? null,
    [clips, activeFolder],
  );

  /* keep a valid selection */
  useEffect(() => {
    if (!clips.length) {
      if (activeFolder) setActiveFolder(null);
      return;
    }
    if (!activeFolder || !clips.some((c) => c.folder === activeFolder)) {
      setActiveFolder(clips[0].folder);
    }
  }, [clips, activeFolder]);

  /* reset to page 1 when the filter changes */
  useEffect(() => {
    setPage(1);
  }, [debounced, sort]);

  /* --------------------------------------------------------------- actions */

  const deleteClips = async (folders: string[]) => {
    if (!folders.length) return;
    setDeleteBusy(true);
    try {
      const res = await apiPost<{ ok: boolean; removed: string[]; count: number }>(
        "/api/clips/delete",
        { folders },
      );
      toast.success("ลบคลิปแล้ว", `ย้ายไปที่โฟลเดอร์ removed ${res.count} คลิป`);
      setChecked(new Set());
      setDeleteOpen(false);
      reload(true);
    } catch (e) {
      toast.error("ลบคลิปไม่สำเร็จ", errorText(e));
    } finally {
      setDeleteBusy(false);
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

  const exportToPlatform = async (platform: string, label: string, url: string) => {
    if (!active) return;
    const caption = buildCaption(active, platform);
    try {
      await navigator.clipboard.writeText(caption);
    } catch (e) {
      toast.error(`คัดลอกแคปชันไม่สำเร็จ`, errorText(e));
      return;
    }
    try {
      await openUrl(url);
    } catch (e) {
      toast.error("เปิดหน้าเว็บไซต์ไม่สำเร็จ", errorText(e));
      return;
    }
    toast.info(`คัดลอกแคปชันสำหรับ ${label} แล้ว`, "กรุณาอัปโหลดไฟล์คลิปและกดโพสต์เองในหน้าเว็บที่เปิด");
  };

  /** Publish through the real platform API (YouTube / Facebook Page / TikTok draft). */
  const publishViaApi = async (platform: string, label: string) => {
    if (!active) return;
    setPublishing(platform);
    try {
      const res = await apiPost<{ ok: boolean; jobId: string }>("/api/publish/clip", {
        folder: active.folder,
        platform,
      });
      toast.info(`กำลังโพสต์ไปยัง ${label}...`, "กำลังอัปโหลดไฟล์คลิป");
      let done = false;
      for (let i = 0; i < 150; i += 1) {
        await new Promise((r) => setTimeout(r, 1500));
        const job = await apiGet<{ ok: boolean; job: JobPayload }>(
          `/api/job?id=${encodeURIComponent(res.jobId)}`,
        );
        if (job.job?.status === "done") {
          done = true;
          toast.success(`โพสต์ไปยัง ${label} สำเร็จ`, "อัปโหลดคลิปเรียบร้อยแล้ว");
          reload(true);
          break;
        }
        if (job.job?.status === "failed") {
          toast.error(`โพสต์ไปยัง ${label} ไม่สำเร็จ`, job.job.error || "ไม่ทราบสาเหตุ");
          done = true;
          break;
        }
      }
      if (!done) {
        toast.warn(`โพสต์ไปยัง ${label} ยังไม่เสร็จ`, "งานยังทำงานอยู่ในเบื้องหลัง — ดูสถานะได้ที่หน้าตั้งค่าโพสต์");
      }
    } catch (e) {
      toast.error(`โพสต์ไปยัง ${label} ไม่สำเร็จ`, errorText(e));
    } finally {
      setPublishing(null);
    }
  };

  const goToCreate = (platform: string, label: string, route: string) => {
    if (!active) return;
    const caption = buildCaption(active, platform);
    copyText(caption, `แคปชันสำหรับ ${label}`);
    navigate(route);
  };

  /* ---------------------------------------------------------------- table */

  const columns: Column<ClipEntry>[] = [
    {
      key: "clip",
      header: "คลิป",
      width: 84,
      render: (c) => <VideoThumbnail thumb={c.thumb} duration={c.durationSeconds} size={60} label={c.title} />,
    },
    {
      key: "title",
      header: "ชื่อคลิป",
      render: (c) => (
        <div style={{ minWidth: 0 }}>
          <div className="strong truncate" title={c.title}>
            {c.title}
          </div>
          <div className="xsmall muted truncate">{hashtagsOf(c) || "ไม่มีแฮชแท็ก"}</div>
        </div>
      ),
    },
    {
      key: "duration",
      header: "ระยะเวลา",
      width: 90,
      render: (c) => <span className="small">{formatDuration(c.durationSeconds)}</span>,
    },
    {
      key: "formats",
      header: "รูปแบบ",
      width: 120,
      render: (c) => {
        const fmts = clipFormats(c);
        if (!fmts.length) return <span className="xsmall muted">ไม่พบไฟล์วิดีโอ</span>;
        return (
          <div className="row row--wrap" style={{ gap: 5 }}>
            {fmts.map((f) => (
              <StatusBadge key={f} tone={FORMAT_LABEL[f]?.tone ?? "muted"}>
                {FORMAT_LABEL[f]?.label ?? f}
              </StatusBadge>
            ))}
          </div>
        );
      },
    },
    {
      key: "status",
      header: "สถานะ",
      width: 170,
      render: (c) => {
        const review = c.needsReview ?? [];
        if (review.length) {
          return (
            <span title={review.join(" / ")}>
              <StatusBadge tone="warn">ต้องตรวจสอบ {review.length} รายการ</StatusBadge>
            </span>
          );
        }
        return (
          <StatusBadge tone={statusTone(c.status)} dot>
            {STATUS_LABEL[c.status] || c.status || "ไม่ทราบสถานะ"}
          </StatusBadge>
        );
      },
    },
    {
      key: "created",
      header: "วันที่สร้าง",
      width: 150,
      render: (c) => <span className="small muted">{formatThaiDate(c.createdAt)}</span>,
    },
    {
      key: "actions",
      header: "",
      width: 52,
      align: "right",
      render: (c) => (
        <RowMenu
          items={[
            {
              label: "ดูรายละเอียด",
              icon: Video,
              onClick: () => setActiveFolder(c.folder),
            },
            {
              label: "เปิดโฟลเดอร์คลิป",
              icon: FolderOpen,
              onClick: () => {
                revealPath(c.folder).catch((e) =>
                  toast.error("เปิดโฟลเดอร์คลิปไม่สำเร็จ", errorText(e)),
                );
              },
            },
            {
              label: "ลบคลิปนี้",
              icon: Trash2,
              danger: true,
              onClick: () => {
                setDeleteTarget([c.folder]);
                setDeleteOpen(true);
              },
            },
          ]}
        />
      ),
    },
  ];

  const selectedFolders = useMemo(
    () => Array.from(checked).filter((f) => clips.some((c) => c.folder === f)),
    [checked, clips],
  );

  const playVertical = active?.files?.vertical;
  const playHorizontal = active?.files?.horizontal;
  const playSquare = active?.files?.square;
  const requested = active?.files?.[playFormat];
  const playFile = requested || playVertical || playHorizontal || playSquare;
  const playIsVertical = !!playFile && playFile === playVertical;
  const playAspect: "9:16" | "16:9" | "1:1" =
    playFile && playFile === playVertical ? "9:16" : playFile && playFile === playSquare ? "1:1" : "16:9";

  /* ---------------------------------------------------------------- render */

  return (
    <div>
      <PageHeader
        icon={Video}
        title="คลิปที่สร้างแล้ว"
        subtitle="จัดการคลิปที่สร้างเสร็จแล้ว ดูตัวอย่าง และส่งออกไปโพสต์ต่อได้ทุกแพลตฟอร์ม"
        actions={
          <>
            <select
              className="select"
              value={sort}
              onChange={(e) => setSort(e.target.value)}
              style={{ width: 170 }}
              aria-label="กรองตามรูปแบบ"
            >
              <option value="latest">ทั้งหมด (ใหม่สุด)</option>
              <option value="oldest">เก่าสุด</option>
              <option value="title">ชื่อ ก-ฮ</option>
              <option value="longest">ความยาวมากสุด</option>
            </select>
            <button
              className="btn btn--outline"
              onClick={() => {
                reload(true);
                toast.info("รีเฟรชรายการคลิปแล้ว");
              }}
            >
              <RefreshCw size={15} /> รีเฟรช
            </button>
            <button
              className="btn btn--danger"
              disabled={!selectedFolders.length}
              onClick={() => {
                setDeleteTarget(selectedFolders);
                setDeleteOpen(true);
              }}
            >
              <Trash2 size={15} /> ลบคลิปที่เลือก
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
        <PastelCard flush>
          <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--c-line)" }}>
            <SearchInput
              value={search}
              onChange={setSearch}
              placeholder="ค้นหาชื่อคลิป, แฮชแท็ก, คำอธิบาย..."
            />
          </div>

          {loading ? (
            <LoadingState label="กำลังโหลดรายการคลิป..." />
          ) : error ? (
            <ErrorState message={error} onRetry={() => reload()} />
          ) : (
            <>
              <DataTable<ClipEntry>
                columns={columns}
                rows={paged}
                rowKey={(c) => c.folder}
                selected={checked}
                onSelect={(key, isChecked) =>
                  setChecked((prev) => {
                    const next = new Set(prev);
                    if (isChecked) next.add(key);
                    else next.delete(key);
                    return next;
                  })
                }
                onRowClick={(c) => {
                  setActiveFolder(c.folder);
                  const fmts = clipFormats(c);
                  setPlayFormat(
                    fmts.includes("vertical")
                      ? "vertical"
                      : fmts.includes("horizontal")
                        ? "horizontal"
                        : "square",
                  );
                }}
                empty={
                  <EmptyState
                    title="ยังไม่มีคลิป"
                    text={
                      clips.length
                        ? "ไม่พบคลิปที่ตรงกับคำค้นหา ลองเปลี่ยนคำค้นหาดูอีกครั้ง"
                        : "ยังไม่มีคลิปในโฟลเดอร์ output ของโปรแกรม — เริ่มจากสร้างคลิปจากบทในหน้า บทที่รอสร้างคลิป"
                    }
                    icon={Video}
                  />
                }
              />
              <Pagination page={safePage} perPage={PER_PAGE} total={rows.length} onPage={setPage} />
            </>
          )}
        </PastelCard>

        {/* ------------------------------------------------------ right column */}
        <div className="col" style={{ gap: 16 }}>
          <PastelCard title="ตัวอย่างคลิป" subtitle="เล่นไฟล์จริงจากโฟลเดอร์คลิปบนเครื่อง" icon={Video}>
            {!active ? (
              <EmptyState
                title="ยังไม่ได้เลือกคลิป"
                text="เลือกคลิปจากตารางด้านซ้ายเพื่อดูตัวอย่าง คัดลอกแคปชัน และส่งออกไปโพสต์"
                icon={Video}
              />
            ) : (
              <div className="col" style={{ gap: 14 }}>
                <VideoPlayer
                  src={playFile}
                  poster={active.thumb}
                  aspect={playAspect}
                  onError={(m) => toast.error("เปิดไฟล์วิดีโอไม่ได้", m)}
                />

                <div>
                  <div className="strong" style={{ lineHeight: 1.35 }}>
                    {active.title}
                  </div>
                  <div className="small muted" style={{ marginTop: 4, lineHeight: 1.6 }}>
                    {active.description || "ไม่มีคำอธิบายของคลิปนี้"}
                  </div>
                </div>

                {(active.tags ?? []).length > 0 && (
                  <div className="row row--wrap" style={{ gap: 6 }}>
                    {(active.tags ?? []).map((t) => (
                      <Chip key={t} tone="blue">
                        #{String(t).replace(/\s+/g, "")}
                      </Chip>
                    ))}
                  </div>
                )}

                <div
                  className="row row--wrap small"
                  style={{
                    gap: 12,
                    background: "var(--c-primary-soft)",
                    borderRadius: 12,
                    padding: "10px 12px",
                    color: "var(--c-primary-darker)",
                  }}
                >
                  <span>ระยะเวลา: {formatDuration(active.durationSeconds)}</span>
                  <span>รูปแบบ: {active.resolution || "ไม่ระบุ"}{active.fps ? ` @ ${active.fps} FPS` : ""}</span>
                  <span>วันที่สร้าง: {formatThaiDate(active.createdAt)}</span>
                </div>

                {(active.needsReview ?? []).length > 0 && (
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
                    <strong>ควรตรวจสอบก่อนโพสต์:</strong>
                    {(active.needsReview ?? []).map((r, i) => (
                      <span key={i}>• {r}</span>
                    ))}
                  </div>
                )}

                {/* format switch */}
                <div className="row row--wrap" style={{ gap: 8 }}>
                  {playVertical && (
                    <button
                      className={`btn ${playIsVertical ? "btn--primary" : "btn--outline"}`}
                      onClick={() => setPlayFormat("vertical")}
                    >
                      <Video size={15} /> ดูคลิปแนวตั้ง (9:16)
                    </button>
                  )}
                  {playHorizontal && (
                    <button
                      className={`btn ${playFile === playHorizontal ? "btn--primary" : "btn--outline"}`}
                      onClick={() => setPlayFormat("horizontal")}
                    >
                      <Video size={15} /> ดูคลิปแนวนอน (16:9)
                    </button>
                  )}
                  {playSquare && (
                    <button
                      className={`btn ${playFile === playSquare ? "btn--primary" : "btn--outline"}`}
                      onClick={() => setPlayFormat("square")}
                    >
                      <Video size={15} /> ดูคลิปสี่เหลี่ยม (1:1)
                    </button>
                  )}
                  {!playVertical && !playHorizontal && !playSquare && (
                    <span className="small muted">คลิปนี้ไม่มีไฟล์วิดีโอให้เล่น</span>
                  )}
                </div>

                {/* copy row */}
                <div className="row row--wrap" style={{ gap: 8 }}>
                  <button
                    className="btn btn--outline btn--sm"
                    onClick={() => copyText(active.title || "", "ชื่อคลิป")}
                  >
                    <Copy size={14} /> คัดลอกชื่อ
                  </button>
                  <button
                    className="btn btn--outline btn--sm"
                    onClick={() => copyText(active.description || "", "คำอธิบาย")}
                  >
                    <Copy size={14} /> คัดลอกคำอธิบาย
                  </button>
                  <button
                    className="btn btn--outline btn--sm"
                    onClick={() => copyText(hashtagsOf(active), "แฮชแท็ก")}
                  >
                    <Copy size={14} /> คัดลอกแฮชแท็ก
                  </button>
                </div>

                <button
                  className="btn btn--outline btn--block"
                  onClick={() => {
                    revealPath(active.folder).catch((e) =>
                      toast.error("เปิดโฟลเดอร์คลิปไม่สำเร็จ", errorText(e)),
                    );
                  }}
                >
                  <FolderOpen size={15} /> เปิดโฟลเดอร์คลิป
                </button>

                {/* platform export */}
                <div
                  className="col"
                  style={{
                    gap: 8,
                    background: "var(--g-orange)",
                    borderRadius: 14,
                    padding: 12,
                  }}
                >
                  <div className="row" style={{ gap: 8 }}>
                    <Upload size={15} style={{ color: "var(--c-orange-strong)" }} />
                    <div style={{ minWidth: 0 }}>
                      <div className="small strong">โพสต์คลิปที่สร้างแล้ว</div>
                      <div className="xsmall" style={{ color: "var(--c-orange-strong)" }}>
                        แพลตฟอร์มที่เชื่อมต่ออยู่จะโพสต์ผ่าน API ของโปรแกรมได้จริง
                        ส่วนที่ยังไม่ได้เชื่อมต่อ โปรแกรมจะคัดลอกแคปชันและเปิดหน้าเว็บให้คุณโพสต์เอง
                      </div>
                    </div>
                  </div>

                  <div className="row row--wrap" style={{ gap: 8 }}>
                    {API_PUBLISH_TARGETS.map((p) =>
                      connected[p.id] ? (
                        <PlatformButton
                          key={p.id}
                          label={publishing === p.id ? "กำลังโพสต์..." : `โพสต์ ${p.label}`}
                          icon={Upload}
                          tone={p.tone}
                          disabled={publishing !== null}
                          onClick={() => publishViaApi(p.id, p.label)}
                        />
                      ) : (
                        <PlatformButton
                          key={p.id}
                          label={p.label}
                          icon={ExternalLink}
                          tone={p.tone}
                          onClick={() => goToCreate(p.id, p.label, p.route)}
                        />
                      ),
                    )}
                    {MANUAL_EXPORT_TARGETS.map((p) => (
                      <PlatformButton
                        key={p.id}
                        label={p.label}
                        icon={ClipboardCopy}
                        tone={p.id === "shopee" ? "#EE4D2D" : "#1877F2"}
                        onClick={() => exportToPlatform(p.id, p.label, p.url)}
                      />
                    ))}
                  </div>

                  <div className="xsmall row" style={{ gap: 6, color: "var(--c-orange-strong)" }}>
                    <Info size={13} />
                    ปุ่มสีสด (โพสต์ …) คือการโพสต์ผ่าน API จริง — ใช้ได้เมื่อเชื่อมต่อบัญชีแล้วในหน้าตั้งค่าโพสต์
                  </div>
                </div>

                <button
                  className="btn btn--danger btn--block"
                  onClick={() => {
                    setDeleteTarget([active.folder]);
                    setDeleteOpen(true);
                  }}
                >
                  <Trash2 size={15} /> ลบคลิปนี้
                </button>
                <div className="xsmall muted" style={{ textAlign: "center" }}>
                  คลิปที่ลบจะถูกย้ายไปยังโฟลเดอร์ removed ของโปรแกรม
                </div>
              </div>
            )}
          </PastelCard>
        </div>
      </div>

      <ConfirmDialog
        open={deleteOpen}
        danger
        title="ยืนยันการลบคลิป"
        confirmLabel="ลบคลิป"
        cancelLabel="ยกเลิก"
        message={
          <div className="col" style={{ gap: 8 }}>
            <div>
              ต้องการลบคลิป <strong>{deleteTarget.length}</strong> รายการใช่หรือไม่?
              โฟลเดอร์คลิปจะถูกย้ายไปยังโฟลเดอร์ removed ของโปรแกรม
            </div>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {deleteTarget.slice(0, 8).map((f) => (
                <li key={f} className="small">
                  {f.split(/[\\/]/).pop()}
                </li>
              ))}
            </ul>
            {deleteBusy && <div className="small muted">กำลังลบ...</div>}
          </div>
        }
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => deleteClips(deleteTarget)}
      />
    </div>
  );
}
