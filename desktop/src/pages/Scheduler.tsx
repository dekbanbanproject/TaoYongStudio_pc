import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  CircleStop,
  Clock,
  History,
  Info,
  Lightbulb,
  Loader2,
  Play,
  Plus,
  RefreshCw,
  Trash2,
  XCircle,
} from "lucide-react";
import { apiGet, apiPost, PLATFORM_META, type JobPayload } from "../services/api";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  PastelCard,
  StatusBadge,
  formatThaiDate,
} from "../components/common/ui";
import { DataTable, Pagination, SearchInput, filterRows, useDebounced } from "../components/common/DataTable";
import { useApiData } from "../hooks/useApiData";
import { useToast } from "../components/common/feedback";

/* ------------------------------------------------------------------ types */

type WorkerPlatform = "youtube" | "facebook_page" | "facebook_profile" | "tiktok" | "batch_render";

type SchedulerResponse = {
  ok: boolean;
  schedule: {
    enabled: boolean;
    times: string[];
    platforms: string[];
    perDay: number;
    mode: string;
    lastRun: string;
    nextRun: string;
    nextRunLabel: string;
    countdown: string;
  };
  presetTimes: string[];
};

type HistoryRow = {
  time: string;
  platforms: string[];
  results: Record<string, string>;
  success_count: number;
};

const WORKER_PLATFORMS: {
  key: WorkerPlatform;
  label: string;
  desc: string;
  logo: boolean;
}[] = [
  { key: "youtube", label: "YouTube", desc: "สร้างคลิปและโพสต์ผ่าน YouTube", logo: true },
  { key: "facebook_page", label: "Facebook Page", desc: "สร้างคลิปและโพสต์ผ่าน Facebook", logo: true },
  {
    key: "facebook_profile",
    label: "Facebook Profile",
    desc: "สร้างคลิปและโพสต์ผ่าน Facebook ด้วยพนักงาน AI",
    logo: true,
  },
  { key: "tiktok", label: "TikTok", desc: "สร้างคลิปและโพสต์ผ่าน TikTok", logo: true },
  {
    key: "batch_render",
    label: "แพลตฟอร์มอื่นๆ",
    desc: "เรนเดอร์คลิปใหม่อัตโนมัติจากบทใน inbox",
    logo: false,
  },
];

const UNSUPPORTED = { key: "instagram", label: "Instagram", desc: "ยังไม่รองรับ" };

const WORKER_PLATFORM_LABEL: Record<string, string> = {
  youtube: "YouTube",
  facebook_page: "Facebook Page",
  facebook_profile: "Facebook Profile",
  tiktok: "TikTok",
  batch_render: "เรนเดอร์คลิปอัตโนมัติ",
};

/* ---------------------------------------------------------------- helpers */

function errMsg(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}

/** The engine keeps `platforms` as a map of booleans; older files may hold a list. */
function normalizePlatforms(raw: unknown): Record<WorkerPlatform, boolean> {
  const out: Record<WorkerPlatform, boolean> = {
    youtube: false,
    facebook_page: false,
    facebook_profile: false,
    tiktok: false,
    batch_render: false,
  };
  if (Array.isArray(raw)) {
    for (const k of raw) {
      if (k in out) out[k as WorkerPlatform] = true;
    }
    return out;
  }
  if (raw && typeof raw === "object") {
    for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
      if (k in out) out[k as WorkerPlatform] = v === true;
    }
  }
  return out;
}

function periodLabel(time: string): string {
  const h = Number(time.slice(0, 2));
  if (h < 12) return "เช้า";
  if (h < 16) return "กลางวัน";
  if (h < 18) return "บ่าย";
  return "ค่ำ";
}

function logoFor(key: WorkerPlatform) {
  if (key === "youtube") return PLATFORM_META.youtube;
  if (key === "facebook_page" || key === "facebook_profile") return PLATFORM_META.facebook_page;
  if (key === "tiktok") return PLATFORM_META.tiktok;
  return null;
}

async function pollJob(
  jobId: string,
  onTick: (job: JobPayload) => void,
  isAlive: () => boolean,
): Promise<JobPayload> {
  for (let i = 0; i < 700; i++) {
    const res = await apiGet<{ ok: boolean; job: JobPayload }>("/api/job", { id: jobId });
    onTick(res.job);
    if (res.job.status !== "running") return res.job;
    if (!isAlive()) throw new Error("ยกเลิกการติดตามงาน");
    await new Promise((r) => setTimeout(r, 900));
  }
  throw new Error("งานใช้เวลานานเกินไป กรุณาลองใหม่");
}

/* ------------------------------------------------------------------- page */

export default function Scheduler() {
  const toast = useToast();
  const { data, loading, error, reload } = useApiData<SchedulerResponse>(
    () => apiGet<SchedulerResponse>("/api/scheduler"),
  );

  const [times, setTimes] = useState<string[]>([]);
  const [platforms, setPlatforms] = useState<Record<WorkerPlatform, boolean>>({
    youtube: false,
    facebook_page: false,
    facebook_profile: false,
    tiktok: false,
    batch_render: false,
  });
  const [enabled, setEnabled] = useState(false);
  const [perDay, setPerDay] = useState(2);
  const [mode, setMode] = useState("manual");
  const [lastRun, setLastRun] = useState("");
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [job, setJob] = useState<JobPayload | null>(null);
  const [testing, setTesting] = useState(false);
  const [hour, setHour] = useState(9);
  const [minute, setMinute] = useState(0);
  const [term, setTerm] = useState("");
  const [page, setPage] = useState(1);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  useEffect(() => {
    if (!data?.schedule) return;
    setTimes(Array.isArray(data.schedule.times) ? [...data.schedule.times] : []);
    setPlatforms(normalizePlatforms(data.schedule.platforms));
    setEnabled(!!data.schedule.enabled);
    setPerDay(Number(data.schedule.perDay) || 0);
    setMode(data.schedule.mode || "manual");
    setLastRun(data.schedule.lastRun || "");
  }, [data]);

  const presetTimes = data?.presetTimes?.length ? data.presetTimes : ["08:00", "12:00", "20:00"];
  const schedule = data?.schedule;

  /* ----------------------------------------------------------- persistence */

  const saveSchedule = async (
    patch: Partial<{
      enabled: boolean;
      times: string[];
      platforms: Record<WorkerPlatform, boolean>;
      perDay: number;
      mode: string;
    }>,
    quiet = false,
  ): Promise<boolean> => {
    const next = {
      enabled: patch.enabled ?? enabled,
      times: patch.times ?? times,
      platforms: patch.platforms ?? platforms,
      perDay: patch.perDay ?? perDay,
      mode: patch.mode ?? mode,
    };
    try {
      const res = await apiPost<{ ok: boolean; schedule: Record<string, any> }>(
        "/api/scheduler/save",
        {
          schedule: {
            enabled: next.enabled,
            times: next.times,
            platforms: next.platforms,
            per_day: next.perDay,
            mode: next.mode,
          },
        },
      );
      const s = res?.schedule;
      if (s) {
        if (Array.isArray(s.times)) setTimes([...s.times]);
        if (s.platforms) setPlatforms(normalizePlatforms(s.platforms));
        if (typeof s.enabled === "boolean") setEnabled(s.enabled);
        if (typeof s.per_day === "number") setPerDay(s.per_day);
        if (typeof s.last_run === "string") setLastRun(s.last_run);
        if (Array.isArray(s.history)) {
          setHistory(s.history as HistoryRow[]);
        }
      }
      if (!quiet) toast.success("บันทึกตารางเวลาแล้ว");
      return true;
    } catch (e) {
      toast.error("บันทึกตารางเวลาไม่สำเร็จ", errMsg(e));
      return false;
    }
  };

  const togglePlatform = async (key: WorkerPlatform) => {
    const next = { ...platforms, [key]: !platforms[key] };
    setPlatforms(next);
    await saveSchedule({ platforms: next }, true);
  };

  const toggleTime = async (time: string) => {
    const next = times.includes(time) ? times.filter((t) => t !== time) : [...times, time];
    setTimes(next);
    await saveSchedule({ times: next }, true);
  };

  const removeTime = async (time: string) => {
    const next = times.filter((t) => t !== time);
    setTimes(next);
    await saveSchedule({ times: next }, true);
  };

  const addCustomTime = async () => {
    const value = `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
    if (times.includes(value)) {
      toast.warn("เวลานี้ถูกตั้งไว้แล้ว", value);
      return;
    }
    const next = [...times, value];
    setTimes(next);
    await saveSchedule({ times: next }, true);
    toast.success(`เพิ่มเวลา ${value} แล้ว`);
  };

  const addPresetTime = async () => {
    const free = presetTimes.find((t) => !times.includes(t));
    if (!free) {
      toast.info("มีเวลาตั้งค่าครบทุกช่วงแล้ว", presetTimes.join(", "));
      return;
    }
    const next = [...times, free];
    setTimes(next);
    await saveSchedule({ times: next }, true);
    toast.success(`เพิ่มเวลา ${free} แล้ว`);
  };

  const startAuto = async () => {
    const ok = await saveSchedule({ enabled: true }, true);
    if (ok) {
      toast.success(
        "เปิดการตั้งเวลาอัตโนมัติแล้ว",
        "Windows Task Scheduler จะเรียกพนักงาน AI ตามเวลาที่ตั้งไว้ (เครื่องต้องเปิดอยู่)",
      );
      await reload(true);
    }
  };

  const stopAuto = async () => {
    try {
      await apiPost("/api/scheduler/stop");
      setEnabled(false);
      toast.success("ปิดการตั้งเวลาอัตโนมัติแล้ว", "ลบงานที่ตั้งไว้ใน Windows Task Scheduler เรียบร้อย");
      await reload(true);
    } catch (e) {
      toast.error("ปิดการตั้งเวลาไม่สำเร็จ", errMsg(e));
    }
  };

  const runTest = async () => {
    const targets = Object.entries(platforms)
      .filter(([, v]) => v)
      .map(([k]) => k);
    if (!targets.length) {
      toast.warn("ยังไม่ได้เลือกแพลตฟอร์ม", "เลือกอย่างน้อย 1 แพลตฟอร์มก่อนทดสอบ");
      return;
    }
    setTesting(true);
    setJob(null);
    try {
      const res = await apiPost<{ ok: boolean; jobId: string }>("/api/scheduler/test", {
        schedule: { platforms: targets },
      });
      const done = await pollJob(
        res.jobId,
        (j) => setJob(j),
        () => alive.current,
      );
      if (done.status === "done") {
        toast.success("ทดสอบรอบนี้เสร็จสิ้น", done.label);
        const result = done.result as HistoryRow | undefined;
        if (result && typeof result === "object") {
          setHistory((h) => [
            {
              time: result.time ?? done.finishedAt ?? "",
              platforms: Array.isArray(result.platforms) ? result.platforms : targets,
              results: result.results ?? {},
              success_count: Number(result.success_count) || 0,
            },
            ...h,
          ]);
        }
        await reload(true);
      } else if (done.status === "failed") {
        toast.error("ทดสอบรอบนี้ล้มเหลว", done.error || "ไม่ทราบสาเหตุ");
      } else {
        toast.warn("ทดสอบรอบนี้ถูกยกเลิก", done.error || undefined);
      }
    } catch (e) {
      toast.error("ทดสอบรอบนี้ไม่สำเร็จ", errMsg(e));
    } finally {
      setTesting(false);
    }
  };

  /** The engine only returns the stored history together with a save response. */
  const reloadHistory = async () => {
    const ok = await saveSchedule({}, true);
    if (ok) toast.success("โหลดประวัติการทำงานล่าสุดจากเอนจินแล้ว");
  };

  /* --------------------------------------------------------------- history */

  const debouncedTerm = useDebounced(term);
  const filtered = useMemo(
    () =>
      filterRows(history, debouncedTerm, ["time", "platforms", "results", "success_count"]),
    [history, debouncedTerm],
  );
  const perPage = 6;
  const pageCount = Math.max(1, Math.ceil(filtered.length / perPage));
  const currentPage = Math.min(page, pageCount);
  const pageRows = filtered.slice((currentPage - 1) * perPage, currentPage * perPage);

  const activePlatforms = Object.entries(platforms)
    .filter(([, v]) => v)
    .map(([k]) => k);

  /* --------------------------------------------------------------- render */

  if (loading && !schedule) {
    return (
      <>
        <PageHeader title="ตั้งเวลาพนักงาน AI ทำงานอัตโนมัติ" icon={Clock} />
        <PastelCard>
          <LoadingState label="กำลังโหลดตารางเวลาของพนักงาน AI..." />
        </PastelCard>
      </>
    );
  }

  if (error && !schedule) {
    return (
      <>
        <PageHeader title="ตั้งเวลาพนักงาน AI ทำงานอัตโนมัติ" icon={Clock} />
        <PastelCard>
          <ErrorState message={error} onRetry={() => reload()} />
        </PastelCard>
      </>
    );
  }

  return (
    <>
      <PageHeader
        icon={Clock}
        title="ตั้งเวลาพนักงาน AI ทำงานอัตโนมัติ"
        subtitle="กำหนดแพลตฟอร์มและเวลาที่พนักงาน AI จะทำงานอัตโนมัติตามรอบเวลา"
        actions={
          enabled ? (
            <StatusBadge tone="success" dot>
              ตั้งเวลาอัตโนมัติเปิดอยู่
            </StatusBadge>
          ) : (
            <StatusBadge tone="muted" dot>
              ยังไม่ได้เปิดการตั้งเวลา
            </StatusBadge>
          )
        }
      />

      <div className="stack">
        {/* ------------------------------------------- 1 + 2 : platform & time */}
        <div
          className="grid"
          style={{ gridTemplateColumns: "minmax(0, 1.35fr) minmax(0, 1fr)", alignItems: "start" }}
        >
          <PastelCard
            title="1 เลือกแพลตฟอร์มที่จะให้อัตโนมัติ"
            subtitle="เลือกแพลตฟอร์มที่พนักงาน AI จะไปทำงานให้อัตโนมัติ"
            icon={Play}
            iconTone="pink"
          >
            <div
              className="grid"
              style={{ gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))" }}
            >
              {WORKER_PLATFORMS.map((p) => {
                const logo = logoFor(p.key);
                const on = platforms[p.key];
                return (
                  <button
                    key={p.key}
                    type="button"
                    className="card"
                    onClick={() => togglePlatform(p.key)}
                    style={{
                      padding: 13,
                      textAlign: "center",
                      cursor: "pointer",
                      borderColor: on ? "var(--c-primary)" : "var(--c-line)",
                      background: on ? "var(--g-primary-soft)" : "#fff",
                      boxShadow: on ? "var(--sh-sm)" : "none",
                    }}
                  >
                    <div
                      className="row row--between"
                      style={{ gap: 6, marginBottom: 8, justifyContent: "flex-end" }}
                    >
                      {on ? (
                        <CheckCircle2 size={17} style={{ color: "var(--c-primary)" }} />
                      ) : (
                        <span style={{ width: 17 }} />
                      )}
                    </div>
                    {logo ? (
                      <div
                        style={{
                          width: 40,
                          height: 40,
                          borderRadius: 13,
                          background: logo.bg,
                          color: logo.color,
                          display: "grid",
                          placeItems: "center",
                          fontWeight: 700,
                          fontSize: 18,
                          margin: "0 auto 8px",
                        }}
                      >
                        {logo.label.charAt(0)}
                      </div>
                    ) : (
                      <div
                        style={{
                          width: 40,
                          height: 40,
                          borderRadius: 13,
                          background: "var(--g-mint)",
                          color: "var(--c-mint-strong)",
                          display: "grid",
                          placeItems: "center",
                          margin: "0 auto 8px",
                        }}
                      >
                        <Plus size={20} />
                      </div>
                    )}
                    <div className="small strong">{p.label}</div>
                    <div className="xsmall muted" style={{ lineHeight: 1.5, marginTop: 3 }}>
                      {p.desc}
                    </div>
                  </button>
                );
              })}

              <div
                className="card"
                style={{
                  padding: 13,
                  textAlign: "center",
                  background: "#f7f5ff",
                  borderStyle: "dashed",
                  opacity: 0.75,
                }}
              >
                <div
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: 13,
                    background: "var(--c-pink)",
                    color: "var(--c-pink-strong)",
                    display: "grid",
                    placeItems: "center",
                    margin: "0 auto 8px",
                  }}
                >
                  <Ban size={18} />
                </div>
                <div className="small strong">{UNSUPPORTED.label}</div>
                <div className="xsmall muted" style={{ lineHeight: 1.5, marginTop: 3 }}>
                  {UNSUPPORTED.desc}
                </div>
              </div>
            </div>
          </PastelCard>

          <PastelCard
            title="2 กำหนดเวลาในการทำงาน"
            subtitle="เลือกช่วงเวลาที่พนักงาน AI จะเริ่มทำงาน"
            icon={Clock}
            iconTone="blue"
          >
            <div
              className="grid"
              style={{ gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", marginBottom: 14 }}
            >
              {presetTimes.map((t) => {
                const on = times.includes(t);
                return (
                  <button
                    key={t}
                    type="button"
                    className="card"
                    onClick={() => toggleTime(t)}
                    style={{
                      padding: 11,
                      textAlign: "center",
                      cursor: "pointer",
                      borderColor: on ? "var(--c-primary)" : "var(--c-line)",
                      background: on ? "var(--g-primary-soft)" : "#fff",
                    }}
                  >
                    <div className="xsmall muted">{periodLabel(t)}</div>
                    <div className="strong">{t}</div>
                  </button>
                );
              })}
              <button
                type="button"
                className="card"
                onClick={addCustomTime}
                style={{
                  padding: 11,
                  textAlign: "center",
                  cursor: "pointer",
                  background: "var(--g-orange)",
                  borderColor: "transparent",
                }}
              >
                <div className="xsmall" style={{ color: "var(--c-orange-strong)" }}>
                  เพิ่มเวลา
                </div>
                <div className="strong" style={{ color: "var(--c-orange-strong)" }}>
                  เอง
                </div>
              </button>
            </div>

            <div className="row row--wrap" style={{ gap: 10, marginBottom: 14 }}>
              <span className="small strong">ตั้งเวลาของวัน</span>
              <select
                className="select"
                value={hour}
                onChange={(e) => setHour(Number(e.target.value))}
                style={{ width: 92 }}
                aria-label="ชั่วโมง"
              >
                {Array.from({ length: 24 }, (_, h) => (
                  <option key={h} value={h}>
                    {String(h).padStart(2, "0")}
                  </option>
                ))}
              </select>
              <span className="muted">:</span>
              <select
                className="select"
                value={minute}
                onChange={(e) => setMinute(Number(e.target.value))}
                style={{ width: 92 }}
                aria-label="นาที"
              >
                {[0, 15, 30, 45].map((m) => (
                  <option key={m} value={m}>
                    {String(m).padStart(2, "0")}
                  </option>
                ))}
              </select>
              <button type="button" className="btn btn--mint btn--sm" onClick={addCustomTime}>
                <Plus size={14} /> เพิ่มเวลา
              </button>
            </div>

            <div className="field">
              <span className="field__label">เวลาที่ตั้งไว้วันนี้ ({times.length} ครั้ง)</span>
              {times.length === 0 ? (
                <div
                  className="card"
                  style={{ padding: 12, background: "var(--c-primary-soft-2)", textAlign: "center" }}
                >
                  <div className="small muted">ยังไม่ได้ตั้งเวลาทำงาน</div>
                </div>
              ) : (
                <div className="col" style={{ gap: 7 }}>
                  {times.map((t) => (
                    <div key={t} className="row row--between" style={{ gap: 8 }}>
                      <span className="row" style={{ gap: 8 }}>
                        <Clock size={14} style={{ color: "var(--c-primary)" }} />
                        <span className="small strong">{t} น.</span>
                        <span className="xsmall muted">{periodLabel(t)}</span>
                      </span>
                      <button
                        type="button"
                        className="btn btn--danger btn--icon btn--sm"
                        onClick={() => removeTime(t)}
                        aria-label={`ลบเวลา ${t}`}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div>
                <button type="button" className="btn btn--outline btn--sm" onClick={addPresetTime}>
                  <Plus size={14} /> เพิ่มเวลาโพสต์
                </button>
              </div>
            </div>
          </PastelCard>
        </div>

        {/* ------------------------------------- 3 : worker status + controls */}
        <div
          className="grid"
          style={{ gridTemplateColumns: "minmax(0, 1.35fr) minmax(0, 1fr)", alignItems: "start" }}
        >
          <PastelCard
            title="3 ควบคุมการทำงานและสถานะปัจจุบัน"
            subtitle="จัดการการทำงานของพนักงาน AI และดูสถานะล่าสุด"
            icon={Play}
            iconTone="mint"
          >
            <div className="row row--wrap" style={{ gap: 12, marginBottom: 14 }}>
              <div
                className="card card--soft row"
                style={{ gap: 12, flex: "1 1 240px", background: "var(--g-mint)", border: "none" }}
              >
                <img
                  src="/characters/asset_avatar_circle.png"
                  alt="พนักงาน AI"
                  width={54}
                  height={54}
                  style={{ borderRadius: "50%", objectFit: "cover", flex: "none" }}
                />
                <div style={{ minWidth: 0 }}>
                  <div className="strong">พนักงาน AI</div>
                  <div className="xsmall muted" style={{ marginBottom: 5 }}>
                    พร้อมทำงานตามตารางเวลาที่ตั้งไว้
                  </div>
                  {enabled ? (
                    <StatusBadge tone="success" dot>
                      กำลังทำงานอยู่
                    </StatusBadge>
                  ) : (
                    <StatusBadge tone="muted" dot>
                      หยุดทำงาน
                    </StatusBadge>
                  )}
                </div>
              </div>

              <div className="col" style={{ gap: 9, flex: "1 1 260px" }}>
                <div className="row row--between" style={{ gap: 10 }}>
                  <span className="small muted">สถานะระบบ</span>
                  <span className="small strong">
                    {enabled ? "เปิดการตั้งเวลาอัตโนมัติ" : "ปิดการตั้งเวลาอัตโนมัติ"}
                  </span>
                </div>
                <div className="row row--between" style={{ gap: 10 }}>
                  <span className="small muted">เวลาทำงานถัดไป</span>
                  <span className="small strong">
                    {schedule?.countdown
                      ? `${schedule.nextRun} น. · ${schedule.countdown}`
                      : "ยังไม่ได้กำหนดเวลา"}
                  </span>
                </div>
                <div className="row row--between" style={{ gap: 10 }}>
                  <span className="small muted">แพลตฟอร์มที่ใช้งาน</span>
                  <span className="small strong truncate" style={{ textAlign: "right" }}>
                    {activePlatforms.length
                      ? activePlatforms.map((p) => WORKER_PLATFORM_LABEL[p] ?? p).join(", ")
                      : "ยังไม่ได้เลือก"}
                  </span>
                </div>
                <div className="row row--between" style={{ gap: 10 }}>
                  <span className="small muted">จำนวนงานต่อวัน (ที่ตั้งไว้)</span>
                  <span className="small strong">{perDay} คลิป</span>
                </div>
                <div className="row row--between" style={{ gap: 10 }}>
                  <span className="small muted">งานล่าสุด</span>
                  <span className="small strong">{formatThaiDate(lastRun)}</span>
                </div>
              </div>
            </div>

            {job && (
              <div className="col" style={{ gap: 8 }}>
                <div className="row row--between" style={{ gap: 10 }}>
                  <span className="small strong">
                    {job.label} · {job.status === "running" ? "กำลังทำงาน" : job.status}
                  </span>
                  <span className="xsmall muted">{Math.round(job.progress || 0)}%</span>
                </div>
                <div className="progress">
                  <div className="progress__bar" style={{ width: `${Math.min(100, job.progress || 0)}%` }} />
                </div>
                {job.log?.length ? (
                  <div className="log">
                    {job.log.map((line, i) => (
                      <div key={i}>{line}</div>
                    ))}
                  </div>
                ) : null}
                {job.error && (
                  <div className="row" style={{ gap: 8, alignItems: "flex-start" }}>
                    <XCircle size={15} style={{ color: "var(--c-danger)", flex: "none", marginTop: 2 }} />
                    <span className="xsmall" style={{ color: "var(--c-danger)", whiteSpace: "pre-wrap" }}>
                      {job.error}
                    </span>
                  </div>
                )}
              </div>
            )}
          </PastelCard>

          <div className="col" style={{ gap: 10 }}>
            <button
              type="button"
              className="btn btn--primary btn--lg btn--block"
              onClick={startAuto}
              disabled={testing}
            >
              <Play size={16} /> เริ่มทำงานอัตโนมัติ
            </button>
            <button
              type="button"
              className="btn btn--blue btn--lg btn--block"
              onClick={runTest}
              disabled={testing}
            >
              {testing ? <Loader2 size={16} className="spin" /> : <RefreshCw size={16} />}
              ทดสอบรอบนี้ทันที
            </button>
            <button
              type="button"
              className="btn btn--danger btn--lg btn--block"
              onClick={stopAuto}
              disabled={testing}
            >
              <CircleStop size={16} /> ปิดการตั้งเวลา
            </button>
          </div>
        </div>

        {/* ------------------------------------------- 4 + 5 : history & tips */}
        <div
          className="grid"
          style={{ gridTemplateColumns: "minmax(0, 1.35fr) minmax(0, 1fr)", alignItems: "start" }}
        >
          <PastelCard
            title="4 ประวัติการทำงานล่าสุด"
            subtitle="ดูรายละเอียดงานที่พนักงาน AI ทำในรอบล่าสุด"
            icon={History}
            iconTone="orange"
            actions={
              <button type="button" className="btn btn--ghost btn--sm" onClick={reloadHistory}>
                ดูทั้งหมด <RefreshCw size={14} />
              </button>
            }
          >
            <div className="col" style={{ gap: 12 }}>
              <SearchInput
                value={term}
                onChange={(v) => {
                  setTerm(v);
                  setPage(1);
                }}
                placeholder="ค้นหาวันที่ แพลตฟอร์ม หรือผลลัพธ์..."
                style={{ maxWidth: 340 }}
              />

              {pageRows.length === 0 ? (
                <EmptyState
                  title="ยังไม่มีประวัติการทำงาน"
                  text="เอนจินเก็บประวัติไว้สูงสุด 100 รายการ กด “ดูทั้งหมด” เพื่อดึงประวัติล่าสุดจากเอนจิน"
                  icon={History}
                />
              ) : (
                <>
                  <DataTable<HistoryRow>
                    columns={[
                      {
                        key: "time",
                        header: "วันที่ / เวลา",
                        width: 150,
                        render: (row) => <span className="small">{formatThaiDate(row.time)}</span>,
                      },
                      {
                        key: "platforms",
                        header: "แพลตฟอร์ม",
                        render: (row) =>
                          (row.platforms || [])
                            .map((p) => WORKER_PLATFORM_LABEL[p] ?? p)
                            .join(", ") || "-",
                      },
                      {
                        key: "results",
                        header: "งานที่ทำ",
                        render: (row) => Object.keys(row.results || {}).length,
                      },
                      {
                        key: "success_count",
                        header: "ผลลัพธ์",
                        width: 110,
                        render: (row) =>
                          row.success_count > 0 ? (
                            <StatusBadge tone="success">สำเร็จ {row.success_count} งาน</StatusBadge>
                          ) : (
                            <StatusBadge tone="danger">ไม่สำเร็จ</StatusBadge>
                          ),
                      },
                      {
                        key: "detail",
                        header: "รายละเอียด",
                        render: (row) =>
                          Object.entries(row.results || {})
                            .map(([k, v]) => `${WORKER_PLATFORM_LABEL[k] ?? k}: ${v}`)
                            .join(" · ") || "-",
                      },
                    ]}
                    rows={pageRows}
                    rowKey={(row, i) => `${row.time}-${i}`}
                    empty={<EmptyState title="ไม่พบรายการที่ค้นหา" />}
                  />
                  {filtered.length > perPage && (
                    <Pagination
                      page={currentPage}
                      perPage={perPage}
                      total={filtered.length}
                      onPage={setPage}
                    />
                  )}
                </>
              )}
            </div>
          </PastelCard>

          <PastelCard
            title="5 คำแนะนำและข้อควรรู้"
            subtitle="เคล็ดลับการตั้งค่าเวลาให้เหมาะกับช่องทางของคุณ"
            icon={Lightbulb}
            iconTone="orange"
          >
            <div className="col" style={{ gap: 12 }}>
              {[
                {
                  title: "แนะนำให้ตั้งเวลา 2-3 ตัว",
                  text: `ช่วงเวลาที่คนดูเยอะคือ ${presetTimes.join(", ")} ตั้งมากกว่านี้อาจทำให้คลิปกระจายจนได้ engagement น้อยลง`,
                },
                {
                  title: "ตรวจสอบการทำงานเป็นประจำ",
                  text: "กด “ทดสอบรอบนี้ทันที” เพื่อดูว่าพนักงาน AI ทำงานได้จริง ก่อนปล่อยให้ทำงานตามเวลาจริง",
                },
                {
                  title: "พนักงาน AI ใช้ Windows Task Scheduler",
                  text: "งานถูกตั้งเวลาให้เรียกใช้งานอัตโนมัติโดย Windows Task Scheduler ไม่ได้รันค้างอยู่ในแอป — เครื่องต้องเปิดอยู่และไม่เข้าโหมดพักเครื่อง งานจึงจะทำตามเวลาที่ตั้งไว้",
                },
                {
                  title: "จำนวนคลิปสูงสุดต่อวันตั้งไว้ที่หน้าตั้งค่าโพสต์",
                  text: "ขีดจำกัดจำนวนคลิปที่โพสต์ต่อแพลตฟอร์มต่อวันอยู่ที่หน้า “ตั้งค่าโพสต์ (คนที่ 2)” ไม่ใช่หน้านี้",
                },
              ].map((tip) => (
                <div key={tip.title} className="row" style={{ gap: 11, alignItems: "flex-start" }}>
                  <span
                    style={{
                      width: 30,
                      height: 30,
                      borderRadius: 10,
                      background: "var(--g-orange)",
                      color: "var(--c-orange-strong)",
                      display: "grid",
                      placeItems: "center",
                      flex: "none",
                    }}
                  >
                    <Lightbulb size={15} />
                  </span>
                  <div style={{ minWidth: 0 }}>
                    <div className="small strong">{tip.title}</div>
                    <div className="xsmall muted" style={{ lineHeight: 1.6, marginTop: 2 }}>
                      {tip.text}
                    </div>
                  </div>
                </div>
              ))}

              <div className="row" style={{ gap: 9, alignItems: "flex-start" }}>
                <Info size={15} style={{ color: "var(--c-info)", flex: "none", marginTop: 2 }} />
                <span className="xsmall muted" style={{ lineHeight: 1.6 }}>
                  โหมดการทำงานที่บันทึกไว้: {mode} · จำนวนงานต่อวัน: {perDay} คลิป
                </span>
              </div>

              <div className="row" style={{ gap: 9, alignItems: "flex-start" }}>
                <AlertTriangle size={15} style={{ color: "var(--c-warn)", flex: "none", marginTop: 2 }} />
                <span className="xsmall muted" style={{ lineHeight: 1.6 }}>
                  การโพสต์จริงต้องเชื่อมต่อบัญชีและเปิดใช้งานแพลตฟอร์มในหน้า “ตั้งค่าโพสต์ (คนที่ 2)” ก่อน
                </span>
              </div>
            </div>
          </PastelCard>
        </div>
      </div>
    </>
  );
}
