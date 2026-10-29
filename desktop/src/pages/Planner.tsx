import { useMemo, useState } from "react";
import {
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  ClipboardPaste,
  Clock,
  Copy,
  Eye,
  Gem,
  History,
  Lightbulb,
  MessageCircle,
  PencilLine,
  RefreshCw,
  Send,
  Sparkles,
  TriangleAlert,
  Wand2,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import {
  STATUS_LABEL,
  apiGet,
  apiPost,
  type Idea,
  type PlannerRequest,
} from "../services/api";
import { useApiData } from "../hooks/useApiData";
import { DataTable, type Column } from "../components/common/DataTable";
import { ConfirmDialog, Modal, useToast } from "../components/common/feedback";
import {
  Chip,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  PastelCard,
  StatusBadge,
  formatThaiDate,
} from "../components/common/ui";

/* --------------------------------------------------------------- types */

interface IdeasPayload {
  ok: boolean;
  ideas: Idea[];
  genres: string[];
  note: string;
  updated: string;
  productIdeas: unknown[];
}

interface RequestsPayload {
  ok: boolean;
  requests: PlannerRequest[];
}

interface RequestResponse {
  ok: boolean;
  requestId: string;
  status: string;
  resultPath?: string;
  note?: string;
  error?: string;
}

interface ResultResponse {
  ok: boolean;
  result: unknown;
  path: string;
}

interface ImportResponse {
  ok: boolean;
  resultPath?: string;
  imported?: boolean;
}

type ProviderId = "gemini" | "claude" | "chatgpt";
type WhenId = "now" | "scheduled";

interface ProviderMeta {
  id: ProviderId;
  label: string;
  icon: LucideIcon;
  /** Short line under the name — never claims a capability we do not have. */
  hint: string;
  callable: boolean;
}

const PROVIDERS: ProviderMeta[] = [
  {
    id: "gemini",
    label: "Gemini",
    icon: Gem,
    hint: "เรียก API ได้จริง",
    callable: true,
  },
  {
    id: "claude",
    label: "Claude",
    icon: Sparkles,
    hint: "เปิดในเว็บ / คัดลอกคำสั่ง",
    callable: false,
  },
  {
    id: "chatgpt",
    label: "ChatGPT",
    icon: MessageCircle,
    hint: "เปิดในเว็บ / คัดลอกคำสั่ง",
    callable: false,
  },
];

const DETAIL_LIMIT = 500;

const GENRE_TONES = ["pink", "mint", "blue", "orange", "primary"] as const;

/* ------------------------------------------------------------- helpers */

function errText(e: unknown): string {
  if (e instanceof Error) return e.message;
  if (typeof e === "string") return e;
  return "ไม่ทราบสาเหตุ";
}

const ideaTitle = (i: Idea) => String(i.title ?? i.hook ?? i.id ?? "-");
const ideaSummary = (i: Idea) => String(i.summary ?? i.hook ?? "");
const ideaWhy = (i: Idea) => String(i.why ?? "");
const ideaLength = (i: Idea) => String(i.suggested_length ?? i.length ?? "");
const ideaGenre = (i: Idea) => String(i.genre ?? i.category ?? "");

function genreTone(genre: string): (typeof GENRE_TONES)[number] {
  let h = 0;
  for (let i = 0; i < genre.length; i++) h = (h * 31 + genre.charCodeAt(i)) >>> 0;
  return GENRE_TONES[h % GENRE_TONES.length];
}

function statusTone(status: string) {
  if (status === "done") return "success" as const;
  if (status === "failed") return "danger" as const;
  if (status === "pending") return "warn" as const;
  if (status === "cancelled") return "muted" as const;
  return "info" as const;
}

function providerLabel(provider: string): string {
  const found = PROVIDERS.find((p) => p.id === provider);
  if (found) return found.label;
  if (!provider) return "-";
  return provider;
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

/** The prompt the user has to paste into Claude / ChatGPT by hand. */
function buildPrompt(ideas: Idea[], details: string, lengths: string[]): string {
  const topics = ideas.map((i) => ({
    title: ideaTitle(i),
    summary: ideaSummary(i),
    genre: ideaGenre(i),
    characters: Array.isArray(i.characters) ? i.characters : [],
  }));
  const example = {
    scripts: [
      {
        id: "ep-new-01",
        title: "ชื่อคลิปภาษาไทย",
        description: "คำอธิบายสั้น ๆ สำหรับโพสต์",
        tags: ["การ์ตูนเด็ก"],
        genre: "แนว",
        characters: ["bunny", "bear"],
        formats: ["vertical", "horizontal"],
        scenes: [
          {
            background: "meadow",
            beats: [
              { who: "bunny", say: "สวัสดีจ้ะ", action: "wave" },
              { who: "bear", say: "มาเรียนรู้กันนะ", action: "point" },
            ],
          },
        ],
      },
    ],
  };
  const lines: string[] = [
    "คุณเป็นพนักงาน AI ฝ่ายเขียนบทการ์ตูนเด็กภาษาไทยของ TaoYongStudio",
    "เขียนบทตามคำขอด้านล่าง และตอบเป็น JSON object อย่างเดียว ห้ามใส่ Markdown หรือคำอธิบายอื่น",
    "หัวข้อที่ต้องการ:",
    JSON.stringify(topics, null, 2),
  ];
  if (details.trim()) lines.push("รายละเอียดเพิ่มเติมจากผู้ใช้: " + details.trim());
  if (lengths.length) lines.push("ความยาวแนะนำ: " + lengths.join(", "));
  lines.push(
    "รูปแบบผลลัพธ์ (เปลี่ยนข้อความและเพิ่มบทตามคำขอ):",
    JSON.stringify(example, null, 2),
    "กฎ: แต่ละบทต้องมี id ไม่ซ้ำ ใช้ตัวอังกฤษเล็ก ตัวเลข และขีด; title, description, tags, characters และ scenes ต้องครบ; ตัวลักษณ์เลือก bunny, bear, chick, cat สูงสุด 4 ตัว; background เลือก meadow, beach, night, bedroom, classroom; beats แต่ละรายการมี say เป็นภาษาไทยสั้น ๆ และ who เป็นตัวลักษณ์ในฉากหรือ narrator; action ใช้ talk, wave, jump, cheer, point, happy, dance, none; เนื้อหาปลอดภัย เหมาะกับเด็ก ไม่มีแบรนด์และไม่มีคำชวนซื้อ",
    "ตอบให้ JSON ถูกต้องและครบทุกบท",
  );
  return lines.join("\n");
}

function RadioDot({ active }: { active: boolean }) {
  return (
    <span
      style={{
        width: 18,
        height: 18,
        borderRadius: "50%",
        border: `2px solid ${active ? "var(--c-primary)" : "var(--c-line-strong)"}`,
        display: "grid",
        placeItems: "center",
        flex: "none",
      }}
    >
      {active && (
        <span
          style={{
            width: 9,
            height: 9,
            borderRadius: "50%",
            background: "var(--c-primary)",
          }}
        />
      )}
    </span>
  );
}

/* ------------------------------------------------------------------ page */

export default function Planner() {
  const toast = useToast();

  const [provider, setProvider] = useState<ProviderId>("gemini");
  const [when, setWhen] = useState<WhenId>("now");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [details, setDetails] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);

  const [ideaDetail, setIdeaDetail] = useState<Idea | null>(null);
  const [promptPreview, setPromptPreview] = useState<string | null>(null);
  const [resultView, setResultView] = useState<{ title: string; body: string } | null>(null);
  const [importState, setImportState] = useState<{
    requestId: string;
    provider: string;
    prompt?: string;
  } | null>(null);
  const [pasteText, setPasteText] = useState("");
  const [cancelTarget, setCancelTarget] = useState<PlannerRequest | null>(null);

  const ideasState = useApiData<IdeasPayload>(
    () => apiGet<IdeasPayload>("/api/planner/ideas"),
    [],
  );
  const requestsState = useApiData<RequestsPayload>(
    () => apiGet<RequestsPayload>("/api/planner/requests"),
    [],
  );

  const ideas = ideasState.data?.ideas ?? [];
  const requests = requestsState.data?.requests ?? [];

  const selectedIdeas = useMemo(
    () => ideas.filter((i) => selected.has(String(i.id))),
    [ideas, selected],
  );
  const lengths = useMemo(
    () =>
      Array.from(
        new Set(selectedIdeas.map(ideaLength).filter((x) => !!x)),
      ),
    [selectedIdeas],
  );

  const current = PROVIDERS.find((p) => p.id === provider) ?? PROVIDERS[0];
  const canSchedule = current.callable;
  const effectiveWhen: WhenId = canSchedule ? when : "now";
  const scheduledAt = date && time ? `${date}T${time}` : "";
  const customTime = date && time ? `${date} ${time}` : "";

  function reloadAll() {
    ideasState.reload();
    requestsState.reload();
  }

  function pickProvider(p: ProviderMeta) {
    setProvider(p.id);
    if (!p.callable) setWhen("now");
  }

  /* ------------------------------------------------------------- actions */

  async function submit() {
    if (selectedIdeas.length === 0 && !details.trim()) {
      toast.warn("ยังไม่ได้เลือกไอเดีย", "เลือกไอเดียจากตาราง หรือใส่รายละเอียดเพิ่มเติมก่อนส่งคำขอ");
      return;
    }
    if (effectiveWhen === "scheduled" && !scheduledAt) {
      toast.warn("ยังไม่ได้เลือกวันและเวลา", "กรุณาเลือกวันที่และเวลาที่จะสร้างคำขอ");
      return;
    }

    setBusy(true);
    try {
      const topic =
        selectedIdeas.map(ideaTitle).join(", ").slice(0, 120) ||
        details.trim().slice(0, 120);

      const res = await apiPost<RequestResponse>("/api/planner/request", {
        provider,
        when: effectiveWhen,
        details: details.trim(),
        ideaIds: selectedIdeas.map((i) => String(i.id)),
        customTime,
        scheduledAt,
        topic,
      });

      requestsState.reload(true);

      if (current.callable && effectiveWhen === "now" && res.status === "done") {
        toast.success(
          `สร้างไอเดียด้วย ${current.label} แล้ว`,
          res.note || `สถานะ: ${res.status}`,
        );
      } else if (current.callable) {
        toast.info(
          "บันทึกคำขอที่กำหนดเวลาไว้แล้ว",
          res.note || `สถานะ: ${res.status}`,
        );
      } else {
        // The engine cannot reach Claude / ChatGPT — say so, never fake success.
        const prompt = buildPrompt(selectedIdeas, details, lengths);
        const copied = await copyText(prompt);
        toast.info(
          `สร้างคำขอแล้ว — ยังไม่ได้ติดต่อ ${current.label}`,
          res.note ||
            "โปรแกรมไม่ได้ส่งคำขอไปยัง AI — คัดลอกคำสั่งไปวางในเว็บแล้วนำผลลัพธ์กลับมาวางได้",
        );
        setPasteText("");
        setImportState({ requestId: res.requestId, provider, prompt });
        if (!copied) {
          toast.warn(
            "คัดลอกคำสั่งไม่สำเร็จ",
            "กรุณาเลือกข้อความในกล่องคำสั่งแล้วกด Ctrl+C เอง",
          );
        }
      }
    } catch (e) {
      toast.error("ส่งคำขอไม่สำเร็จ", errText(e));
    } finally {
      setBusy(false);
    }
  }

  async function openResult(req: PlannerRequest) {
    const path = req.hasResult && req.resultPath ? req.resultPath : req.requestPath;
    if (!path) {
      toast.error("เปิดผลลัพธ์ไม่ได้", "คำขอนี้ไม่มีไฟล์ผลลัพธ์");
      return;
    }
    try {
      const res = await apiGet<ResultResponse>("/api/planner/result", { path });
      const body =
        typeof res.result === "string"
          ? res.result
          : JSON.stringify(res.result, null, 2);
      setResultView({
        title:
          req.hasResult && req.resultPath ? "ผลลัพธ์คำขอ" : "รายละเอียดคำขอ",
        body: body || "ไม่มีข้อมูล",
      });
    } catch (e) {
      toast.error("เปิดผลลัพธ์ไม่ได้", errText(e));
    }
  }

  async function doCancel() {
    const target = cancelTarget;
    if (!target) return;
    try {
      await apiPost("/api/planner/cancel", { requestId: target.id });
      toast.success("ยกเลิกคำขอแล้ว", `คำขอ ${target.id} ถูกยกเลิกเรียบร้อย`);
      setCancelTarget(null);
      requestsState.reload(true);
    } catch (e) {
      toast.error("ยกเลิกคำขอไม่สำเร็จ", errText(e));
    }
  }

  async function doImport() {
    if (!importState) return;
    if (!pasteText.trim()) {
      toast.warn("ยังไม่ได้วางผลลัพธ์", "วาง JSON ที่ AI ตอบกลับมาในช่องด้านบนก่อน");
      return;
    }
    setBusy(true);
    try {
      const res = await apiPost<ImportResponse>("/api/planner/import-response", {
        requestId: importState.requestId,
        text: pasteText,
      });
      toast.success(
        "นำเข้าบทจาก AI เรียบร้อย",
        res.resultPath ? `บันทึกผลลัพธ์ไว้ที่ ${res.resultPath}` : undefined,
      );
      setImportState(null);
      setPasteText("");
      requestsState.reload(true);
    } catch (e) {
      toast.error("นำเข้าบทจาก AI ไม่สำเร็จ", errText(e));
    } finally {
      setBusy(false);
    }
  }

  /* -------------------------------------------------------------- tables */

  const ideaColumns: Column<Idea>[] = [
    {
      key: "no",
      header: "#",
      width: 44,
      render: (_row, i) => i + 1,
    },
    {
      key: "genre",
      header: "แนว",
      width: 150,
      render: (row) => {
        const g = ideaGenre(row);
        return <Chip tone={genreTone(g)}>{g || "ไม่ระบุ"}</Chip>;
      },
    },
    {
      key: "title",
      header: "ไอเดีย",
      render: (row) => (
        <div style={{ minWidth: 0 }}>
          <div className="small strong clamp-2">{ideaTitle(row)}</div>
          <div className="xsmall muted clamp-2">{ideaSummary(row)}</div>
        </div>
      ),
    },
    {
      key: "why",
      header: "ทำไมน่าสนใจ",
      render: (row) => (
        <div className="small clamp-2" title={ideaWhy(row)}>
          {ideaWhy(row) || "-"}
        </div>
      ),
    },
    {
      key: "length",
      header: "ความยาวแนะนำ",
      width: 140,
      render: (row) => (
        <StatusBadge tone="primary">{ideaLength(row) || "ไม่ระบุ"}</StatusBadge>
      ),
    },
    {
      key: "more",
      header: "",
      width: 52,
      align: "center",
      render: (row) => (
        <button
          type="button"
          className="btn btn--soft btn--icon btn--sm"
          title="ดูรายละเอียดไอเดีย"
          onClick={() => setIdeaDetail(row)}
        >
          <ChevronRight size={15} />
        </button>
      ),
    },
  ];

  const requestColumns: Column<PlannerRequest>[] = [
    {
      key: "no",
      header: "#",
      width: 44,
      render: (_row, i) => i + 1,
    },
    {
      key: "createdAt",
      header: "วันที่ส่งคำขอ",
      width: 165,
      render: (row) => <span className="small">{formatThaiDate(row.createdAt)}</span>,
    },
    {
      key: "topic",
      header: "คำขอ (Prompt)",
      render: (row) => (
        <div className="small clamp-2" title={row.topic || row.details || ""}>
          {row.topic || row.details || "-"}
        </div>
      ),
    },
    {
      key: "provider",
      header: "ผู้ใช้บริการ",
      width: 120,
      render: (row) => (
        <span className="small strong">{providerLabel(row.provider)}</span>
      ),
    },
    {
      key: "ideaCount",
      header: "จำนวนไอเดีย",
      width: 100,
      align: "center",
      render: (row) => <span className="small">{row.ideaCount ?? 0}</span>,
    },
    {
      key: "status",
      header: "สถานะ",
      width: 130,
      render: (row) => (
        <StatusBadge tone={statusTone(row.status)} dot>
          {STATUS_LABEL[row.status] || row.status || "-"}
        </StatusBadge>
      ),
    },
    {
      key: "actions",
      header: "การดำเนินการ",
      width: 250,
      align: "right",
      render: (row) => (
        <div className="table__actions">
          <button
            type="button"
            className="btn btn--soft btn--sm"
            onClick={() => openResult(row)}
          >
            <Eye size={13} /> ดูผลลัพธ์
          </button>
          <button
            type="button"
            className="btn btn--outline btn--sm"
            onClick={() => {
              setPasteText("");
              setImportState({
                requestId: row.id,
                provider: row.provider,
              });
            }}
          >
            <ClipboardPaste size={13} /> นำเข้าบทจาก AI
          </button>
          {row.status === "pending" && (
            <button
              type="button"
              className="btn btn--danger btn--sm"
              onClick={() => setCancelTarget(row)}
            >
              ยกเลิก
            </button>
          )}
        </div>
      ),
    },
  ];

  /* --------------------------------------------------------------- render */

  return (
    <>
      <PageHeader
        icon={CalendarDays}
        title="วางแผนไอเดียด้วย AI"
        subtitle="ให้ AI ช่วยคัดเลือกแนวคลิปสำหรับเด็กไทย สร้างบทจริง ปลอดภัย และเหมาะกับทุกแพลตฟอร์ม"
        actions={
          <button className="btn btn--soft btn--sm" onClick={reloadAll}>
            <RefreshCw size={14} /> รีเฟรชข้อมูล
          </button>
        }
      />

      <div className="stack">
        <div
          className="grid"
          style={{
            gridTemplateColumns: "minmax(0, 1.5fr) minmax(330px, 0.9fr)",
            gap: 16,
            alignItems: "start",
          }}
        >
          {/* ------------------------------------------ ideas created by AI */}
          <PastelCard
            title="ไอเดียที่ AI สร้างให้"
            icon={Lightbulb}
            iconTone="orange"
            actions={
              <>
                <StatusBadge tone="primary">ทั้งหมด {ideas.length} ไอเดีย</StatusBadge>
                {selected.size > 0 && (
                  <StatusBadge tone="success">เลือกแล้ว {selected.size}</StatusBadge>
                )}
              </>
            }
          >
            {ideasState.loading ? (
              <LoadingState label="กำลังโหลดไอเดีย..." />
            ) : ideasState.error ? (
              <ErrorState
                message={ideasState.error}
                onRetry={() => ideasState.reload()}
              />
            ) : ideas.length === 0 ? (
              <EmptyState
                title="ยังไม่มีไอเดียในระบบ"
                text="ยังไม่พบไอเดียที่ AI สร้างไว้ — กดรีเฟรชเพื่อโหลดใหม่อีกครั้ง"
                icon={Lightbulb}
              />
            ) : (
              <div style={{ maxHeight: 430, overflow: "auto" }}>
                <DataTable<Idea>
                  columns={ideaColumns}
                  rows={ideas}
                  rowKey={(row) => String(row.id)}
                  selected={selected}
                  onSelect={(key, checked) =>
                    setSelected((prev) => {
                      const next = new Set(prev);
                      if (checked) next.add(key);
                      else next.delete(key);
                      return next;
                    })
                  }
                />
              </div>
            )}
          </PastelCard>

          {/* ------------------------------------------- right request panel */}
          <div className="col" style={{ gap: 16 }}>
            <PastelCard
              title="สร้างคำขอไอเดียใหม่"
              subtitle="เลือกผู้ให้บริการ AI ที่จะใช้"
              icon={Sparkles}
              iconTone="primary"
              actions={
                <button
                  type="button"
                  className="btn btn--outline btn--sm"
                  onClick={() =>
                    setPromptPreview(
                      buildPrompt(selectedIdeas, details, lengths),
                    )
                  }
                >
                  <Wand2 size={13} /> ดูคำขอตัวอย่าง
                </button>
              }
            >
              <div className="col" style={{ gap: 10 }}>
                <div className="row" style={{ gap: 8, alignItems: "stretch" }}>
                  {PROVIDERS.map((p) => {
                    const Icon = p.icon;
                    const active = provider === p.id;
                    return (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => pickProvider(p)}
                        style={{
                          flex: "1 1 0",
                          minWidth: 0,
                          cursor: "pointer",
                          padding: "12px 8px",
                          borderRadius: "var(--r-lg)",
                          border: active
                            ? "2px solid var(--c-primary)"
                            : "1px solid var(--c-line)",
                          background: active ? "var(--g-primary-soft)" : "#fff",
                          boxShadow: active ? "var(--sh-primary-sm)" : "var(--sh-xs)",
                          display: "flex",
                          flexDirection: "column",
                          alignItems: "center",
                          gap: 5,
                        }}
                      >
                        <Icon
                          size={24}
                          color={active ? "var(--c-primary)" : "#a48cf0"}
                        />
                        <span
                          className="small strong"
                          style={{
                            color: active
                              ? "var(--c-primary-darker)"
                              : "var(--c-ink)",
                          }}
                        >
                          {p.label}
                        </span>
                        <span className="xsmall muted">{p.hint}</span>
                      </button>
                    );
                  })}
                </div>

                <StatusBadge tone={current.callable ? "success" : "warn"} dot>
                  {current.callable
                    ? `โปรแกรมเรียก ${current.label} API ได้จริง`
                    : `โปรแกรมยังติดต่อ ${current.label} ไม่ได้ — จะคัดลอกคำสั่งให้ไปวางในเว็บ`}
                </StatusBadge>
              </div>
            </PastelCard>

            <PastelCard
              title="กำหนดเวลา"
              subtitle="เลือกว่าจะสร้างคำขอทันทีหรือรอเวลา"
              icon={Clock}
              iconTone="blue"
            >
              <div className="col" style={{ gap: 8 }}>
                <button
                  type="button"
                  onClick={() => setWhen("now")}
                  className="row"
                  style={{
                    gap: 10,
                    textAlign: "left",
                    cursor: "pointer",
                    padding: "10px 12px",
                    borderRadius: "var(--r-md)",
                    border: `1px solid ${when === "now" ? "var(--c-primary)" : "var(--c-line)"}`,
                    background: when === "now" ? "var(--g-primary-soft)" : "#fff",
                    width: "100%",
                  }}
                >
                  <RadioDot active={when === "now"} />
                  <span style={{ minWidth: 0 }}>
                    <span className="small strong" style={{ display: "block" }}>
                      ตอนนี้
                    </span>
                    <span className="xsmall muted">สร้างคำขอเลย</span>
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => canSchedule && setWhen("scheduled")}
                  disabled={!canSchedule}
                  className="row"
                  style={{
                    gap: 10,
                    textAlign: "left",
                    cursor: canSchedule ? "pointer" : "not-allowed",
                    padding: "10px 12px",
                    borderRadius: "var(--r-md)",
                    border: `1px solid ${when === "scheduled" ? "var(--c-primary)" : "var(--c-line)"}`,
                    background:
                      when === "scheduled" ? "var(--g-primary-soft)" : "#fff",
                    opacity: canSchedule ? 1 : 0.55,
                    width: "100%",
                  }}
                >
                  <RadioDot active={when === "scheduled"} />
                  <span style={{ minWidth: 0 }}>
                    <span className="small strong" style={{ display: "block" }}>
                      กำหนดเวลา
                    </span>
                    <span className="xsmall muted">
                      {canSchedule
                        ? "เลือกวันและเวลาที่จะสร้างคำขอ"
                        : "การกำหนดเวลาใช้ได้เฉพาะ Gemini เท่านั้น"}
                    </span>
                  </span>
                </button>

                {when === "scheduled" && canSchedule && (
                  <div className="row" style={{ gap: 10, alignItems: "flex-end" }}>
                    <label className="field" style={{ flex: 1 }}>
                      <span className="field__label">วันที่</span>
                      <input
                        type="date"
                        className="input"
                        value={date}
                        onChange={(e) => setDate(e.target.value)}
                      />
                    </label>
                    <label className="field" style={{ flex: 1 }}>
                      <span className="field__label">เวลา</span>
                      <input
                        type="time"
                        className="input"
                        value={time}
                        onChange={(e) => setTime(e.target.value)}
                      />
                    </label>
                  </div>
                )}
              </div>
            </PastelCard>

            <PastelCard
              title="รายละเอียดเพิ่มเติม"
              subtitle="บอก AI เพิ่มเติมว่าอยากได้คลิปแบบไหน"
              icon={PencilLine}
              iconTone="mint"
            >
              <div className="field">
                <textarea
                  className="textarea"
                  value={details}
                  maxLength={DETAIL_LIMIT}
                  placeholder="เช่น เน้นให้เด็กตอบด้วยเสียง ใช้เสียงพากย์เด็กผู้หญิง ปลอดภัยสำหรับเด็ก"
                  onChange={(e) => setDetails(e.target.value)}
                />
                <span className="field__hint">
                  {details.length}/{DETAIL_LIMIT} ตัวอักษร
                </span>
              </div>
            </PastelCard>

            <button
              type="button"
              className="btn btn--primary btn--lg btn--block"
              onClick={submit}
              disabled={busy}
            >
              <Send size={17} /> ส่งคำขอไปยัง {current.label}
            </button>
            {!current.callable && (
              <div className="xsmall muted" style={{ textAlign: "center" }}>
                โปรแกรมจะสร้างคำขอและคัดลอกคำสั่งให้คุณ แต่จะไม่ส่งไปยัง{" "}
                {current.label} เอง
              </div>
            )}
          </div>
        </div>

        {/* ---------------------------------------------- request history */}
        <PastelCard
          title="ประวัติการขอไอเดีย"
          subtitle="คำขอทั้งหมดที่ส่งออกไปยัง AI"
          icon={History}
          iconTone="pink"
          actions={
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => requestsState.reload()}
            >
              <RefreshCw size={13} /> รีเฟรช
            </button>
          }
          bodyClassName="card--flush"
        >
          {requestsState.loading ? (
            <LoadingState label="กำลังโหลดประวัติ..." />
          ) : requestsState.error ? (
            <ErrorState
              message={requestsState.error}
              onRetry={() => requestsState.reload()}
            />
          ) : requests.length === 0 ? (
            <EmptyState
              title="ยังไม่มีประวัติการขอไอเดีย"
              text="เมื่อคุณส่งคำขอไปยัง AI รายการจะปรากฏที่นี่"
              icon={History}
            />
          ) : (
            <div style={{ maxHeight: 340, overflow: "auto" }}>
              <DataTable<PlannerRequest>
                columns={requestColumns}
                rows={requests}
                rowKey={(row) => row.id}
              />
            </div>
          )}
        </PastelCard>
      </div>

      {/* ------------------------------------------------------ idea modal */}
      <Modal
        open={!!ideaDetail}
        title="รายละเอียดไอเดีย"
        icon={Lightbulb}
        onClose={() => setIdeaDetail(null)}
        footer={
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => {
              if (!ideaDetail) return;
              const id = String(ideaDetail.id);
              setSelected((prev) => {
                const next = new Set(prev);
                next.add(id);
                return next;
              });
              setIdeaDetail(null);
              toast.success("เลือกไอเดียแล้ว", ideaTitle(ideaDetail));
            }}
          >
            <CheckCircle2 size={15} /> เลือกไอเดียนี้
          </button>
        }
      >
        {ideaDetail && (
          <div className="col" style={{ gap: 12 }}>
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <Chip tone={genreTone(ideaGenre(ideaDetail))}>
                {ideaGenre(ideaDetail) || "ไม่ระบุแนว"}
              </Chip>
              {ideaLength(ideaDetail) && (
                <StatusBadge tone="primary">{ideaLength(ideaDetail)}</StatusBadge>
              )}
            </div>
            <div>
              <div className="xsmall muted">หัวข้อ</div>
              <div className="strong">{ideaTitle(ideaDetail)}</div>
            </div>
            {ideaSummary(ideaDetail) && (
              <div>
                <div className="xsmall muted">เรื่องย่อ</div>
                <div className="small">{ideaSummary(ideaDetail)}</div>
              </div>
            )}
            {ideaWhy(ideaDetail) && (
              <div>
                <div className="xsmall muted">ทำไมน่าสนใจ</div>
                <div className="small">{ideaWhy(ideaDetail)}</div>
              </div>
            )}
            {Array.isArray(ideaDetail.characters) && ideaDetail.characters.length > 0 && (
              <div>
                <div className="xsmall muted">ตัวละคร</div>
                <div className="small">
                  {(ideaDetail.characters as string[]).join(", ")}
                </div>
              </div>
            )}
            <div>
              <div className="xsmall muted">ข้อมูลทั้งหมดจากระบบ</div>
              <pre className="log" style={{ maxHeight: 220 }}>
                {JSON.stringify(ideaDetail, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </Modal>

      {/* ------------------------------------------------- prompt preview */}
      <Modal
        open={promptPreview !== null}
        title="คำขอตัวอย่าง"
        icon={Wand2}
        onClose={() => setPromptPreview(null)}
        width={640}
        footer={
          <>
            <button
              type="button"
              className="btn btn--outline"
              onClick={async () => {
                const ok = await copyText(promptPreview || "");
                if (ok) toast.success("คัดลอกคำสั่งแล้ว");
                else toast.error("คัดลอกไม่สำเร็จ", "กรุณาเลือกข้อความแล้วกด Ctrl+C เอง");
              }}
            >
              <Copy size={15} /> คัดลอกคำสั่ง
            </button>
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => setPromptPreview(null)}
            >
              ปิด
            </button>
          </>
        }
      >
        <p className="small muted" style={{ marginTop: 0 }}>
          คำสั่งนี้จะถูกส่งไปยัง AI ตามผู้ให้บริการที่เลือกไว้
        </p>
        <pre className="log">{promptPreview}</pre>
      </Modal>

      {/* ---------------------------------------------------- result modal */}
      <Modal
        open={resultView !== null}
        title={resultView?.title || "ผลลัพธ์"}
        icon={Eye}
        onClose={() => setResultView(null)}
        width={640}
        footer={
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => setResultView(null)}
          >
            ปิด
          </button>
        }
      >
        <pre className="log">{resultView?.body}</pre>
      </Modal>

      {/* -------------------------------------------- import response modal */}
      <Modal
        open={importState !== null}
        title="นำเข้าบทจาก AI"
        icon={ClipboardPaste}
        onClose={() => {
          setImportState(null);
          setPasteText("");
        }}
        width={640}
        footer={
          <>
            <button
              type="button"
              className="btn btn--outline"
              onClick={() => {
                setImportState(null);
                setPasteText("");
              }}
            >
              ยกเลิก
            </button>
            <button
              type="button"
              className="btn btn--primary"
              onClick={doImport}
              disabled={busy}
            >
              <ClipboardPaste size={15} /> นำเข้าผลลัพธ์
            </button>
          </>
        }
      >
        <div className="col" style={{ gap: 12 }}>
          {!importState?.prompt && (
            <div
              className="row"
              style={{
                gap: 9,
                alignItems: "flex-start",
                padding: "10px 12px",
                borderRadius: "var(--r-md)",
                background: "var(--c-warn-soft)",
                color: "var(--c-warn)",
              }}
            >
              <TriangleAlert size={16} style={{ flex: "none", marginTop: 2 }} />
              <span className="small">
                วาง JSON ที่ AI ตอบกลับมา (มีช่อง scripts) ลงในช่องด้านล่าง
                โปรแกรมจะตรวจสอบความถูกต้องก่อนบันทึกบทลงในระบบ
              </span>
            </div>
          )}
          {importState?.prompt && (
            <>
              <div
                className="row"
                style={{
                  gap: 9,
                  alignItems: "flex-start",
                  padding: "10px 12px",
                  borderRadius: "var(--r-md)",
                  background: "var(--c-warn-soft)",
                  color: "var(--c-warn)",
                }}
              >
                <TriangleAlert size={16} style={{ flex: "none", marginTop: 2 }} />
                <span className="small">
                  โปรแกรมยังไม่ได้ส่งคำขอไปยัง {providerLabel(importState.provider)}{" "}
                  — คัดลอกคำสั่งด้านล่างไปวางในเว็บไซต์ของผู้ให้บริการ แล้ววางผลลัพธ์กลับมาในช่องด้านล่าง
                </span>
              </div>
              <div className="field">
                <span className="field__label">คำสั่งสำหรับวางในเว็บไซต์ AI</span>
                <pre className="log" style={{ maxHeight: 240 }}>
                  {importState.prompt}
                </pre>
                <button
                  type="button"
                  className="btn btn--soft btn--sm"
                  onClick={async () => {
                    const ok = await copyText(importState.prompt || "");
                    if (ok) toast.success("คัดลอกคำสั่งแล้ว");
                    else
                      toast.error(
                        "คัดลอกไม่สำเร็จ",
                        "กรุณาเลือกข้อความในกล่องคำสั่งแล้วกด Ctrl+C เอง",
                      );
                  }}
                >
                  <Copy size={14} /> คัดลอกคำสั่ง
                </button>
              </div>
            </>
          )}
          <div className="field">
            <span className="field__label">วางผลลัพธ์จาก AI ที่นี่</span>
            <textarea
              className="textarea"
              style={{ minHeight: 140 }}
              value={pasteText}
              placeholder='{"scripts": [ ... ]}'
              onChange={(e) => setPasteText(e.target.value)}
            />
          </div>
        </div>
      </Modal>

      {/* -------------------------------------------------- confirm cancel */}
      <ConfirmDialog
        open={!!cancelTarget}
        title="ยกเลิกคำขอ"
        danger
        confirmLabel="ยกเลิกคำขอ"
        cancelLabel="กลับไป"
        message={
          cancelTarget
            ? `ต้องการยกเลิกคำขอ ${cancelTarget.id} ใช่หรือไม่ การยกเลิกแล้วจะกลับไปไม่ได้`
            : ""
        }
        onConfirm={doCancel}
        onCancel={() => setCancelTarget(null)}
      />
    </>
  );
}
