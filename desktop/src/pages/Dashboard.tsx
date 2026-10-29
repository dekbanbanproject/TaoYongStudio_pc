import { useNavigate } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  CalendarDays,
  CircleDot,
  Cpu,
  Facebook,
  FileText,
  Film,
  FolderOpen,
  Home,
  Library,
  ListChecks,
  MessageCircle,
  MonitorPlay,
  PencilLine,
  Rocket,
  Settings,
  Sparkles,
  Wand2,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { apiGet, type DashboardPayload } from "../services/api";
import { useApiData } from "../hooks/useApiData";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  PastelCard,
  StatCard,
  StatusBadge,
  Step,
  formatRelative,
} from "../components/common/ui";

/* ------------------------------------------------------------- constants */

const SYSTEM_LABEL: Record<string, string> = {
  ai: "ระบบ AI",
  python: "Python Engine",
  tts: "เสียงพากย์",
  renderer: "ตัวเข้ารหัสวิดีโอ",
  gpu: "การ์ดกราฟิกส์",
  facebook: "Facebook",
};

const SYSTEM_ICON: Record<string, LucideIcon> = {
  ai: Sparkles,
  python: Cpu,
  tts: MessageCircle,
  renderer: Film,
  gpu: MonitorPlay,
  facebook: Facebook,
};

const QUICK: {
  to: string;
  title: string;
  desc: string;
  icon: LucideIcon;
  bg: string;
  fg: string;
}[] = [
  {
    to: "/scripts",
    title: "เขียนบทใหม่",
    desc: "เริ่มเขียนบทการ์ตูนเด็กชิ้นใหม่",
    icon: PencilLine,
    bg: "var(--g-primary-soft)",
    fg: "var(--c-primary)",
  },
  {
    to: "/clips",
    title: "คลิปที่สร้างแล้ว",
    desc: "ดูคลิปทั้งหมดที่เรนเดอร์เสร็จแล้ว",
    icon: Film,
    bg: "var(--g-blue)",
    fg: "var(--c-blue-strong)",
  },
  {
    to: "/planner",
    title: "นำเข้าบทจาก AI",
    desc: "ขอไอเดียและนำเข้าบทที่ AI เขียนให้",
    icon: Wand2,
    bg: "var(--g-pink)",
    fg: "var(--c-pink-strong)",
  },
  {
    to: "/clips",
    title: "เปิดโฟลเดอร์คลิป",
    desc: "ไปที่คลิปเพื่อเปิดโฟลเดอร์ไฟล์วิดีโอ",
    icon: FolderOpen,
    bg: "var(--g-mint)",
    fg: "var(--c-mint-strong)",
  },
  {
    to: "/settings",
    title: "ตรวจสอบความพร้อมระบบ",
    desc: "ดูว่าระบบส่วนไหนพร้อมใช้งานแล้ว",
    icon: Settings,
    bg: "var(--g-orange)",
    fg: "var(--c-orange-strong)",
  },
];

const STEPS = [
  {
    n: 1,
    title: "เขียนบท",
    text: "เลือกไอเดียจาก AI หรือเขียนบทเอง ให้เด็กไทยที่ชอบดู",
    tone: "primary" as const,
    icon: PencilLine,
  },
  {
    n: 2,
    title: "สร้างภาพ",
    text: "ระบบสร้างภาพประกอบและภาพเคลื่อนไหวให้แต่ละฉาก",
    tone: "pink" as const,
    icon: Sparkles,
  },
  {
    n: 3,
    title: "สร้างคลิป",
    text: "ตัดต่อเสียงพากย์และคลิปให้พร้อมลง TikTok, YouTube, Shopee และ Facebook",
    tone: "mint" as const,
    icon: Film,
  },
  {
    n: 4,
    title: "โพสต์ไปยังแพลตฟอร์ม",
    text: "ตั้งเวลาโพสต์อัตโนมัติ หรือโพสต์เองได้จากหน้าเดียว",
    tone: "orange" as const,
    icon: Rocket,
  },
];

const ACTIVITY_ICON: Record<string, LucideIcon> = {
  planner: Wand2,
  clip: Film,
  script: PencilLine,
};

/* --------------------------------------------------------------- helpers */

function activityIcon(kind: string): LucideIcon {
  return ACTIVITY_ICON[kind] ?? Activity;
}

/* ------------------------------------------------------------------ page */

export default function Dashboard() {
  const navigate = useNavigate();
  const { data, loading, error, reload } = useApiData<DashboardPayload>(
    () => apiGet<DashboardPayload>("/api/dashboard"),
    [],
  );

  if (loading) return <LoadingState label="กำลังโหลดข้อมูลหน้าแรก..." />;
  if (error) return <ErrorState message={error} onRetry={() => reload()} />;
  if (!data) return <EmptyState title="ยังไม่มีข้อมูลหน้าแรก" text="ลองกดรีเฟรชเพื่อโหลดข้อมูลใหม่อีกครั้ง" />;

  const channel = data.channelName?.trim() ? data.channelName.trim() : "";
  const systems = Object.entries(data.systems ?? {});
  const activity = data.activity ?? [];

  return (
    <>
      <PageHeader
        icon={Home}
        title="หน้าแรก"
        subtitle={
          channel
            ? `ยินดีต้อนรับ ${channel} — สร้างวิดีโอการ์ตูนเด็กภาษาไทยได้ที่นี่ที่เดียว`
            : "ยินดีต้อนรับสู่ TaoYongStudio — สร้างวิดีโอการ์ตูนเด็กภาษาไทยได้ที่นี่ที่เดียว"
        }
        actions={
          <button className="btn btn--soft btn--sm" onClick={() => reload()}>
            <Activity size={14} /> รีเฟรชข้อมูล
          </button>
        }
      />

      <div className="page-fit">
        {/* ------------------------------------------------- welcome banner */}
        <section
          className="card"
          style={{
            background:
              "linear-gradient(120deg, #f3ecff 0%, #ede4ff 42%, #ffe5f0 100%)",
            borderColor: "transparent",
            boxShadow: "var(--sh-md)",
          }}
        >
          <div className="row" style={{ gap: 16, alignItems: "center" }}>
            <span
              style={{
                width: 58,
                height: 58,
                borderRadius: 18,
                background: "var(--g-primary)",
                color: "#fff",
                display: "grid",
                placeItems: "center",
                flex: "none",
                boxShadow: "var(--sh-primary-sm)",
              }}
            >
              <Sparkles size={28} />
            </span>
            <div style={{ minWidth: 0 }}>
              <h2
                style={{
                  margin: 0,
                  fontSize: "var(--fs-xl)",
                  fontWeight: 700,
                  color: "var(--c-primary-darker)",
                }}
              >
                สวัสดีครับ{channel ? ` ${channel}` : ""} ✨
              </h2>
              <p className="small muted" style={{ margin: "4px 0 0" }}>
                เริ่มจากเลือกไอเดียในหน้า วางแผน แล้วให้ระบบเขียนบท สร้างภาพ และเรนเดอร์คลิปให้อัตโนมัติ
              </p>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------ stat cards */}
        <div className="grid" style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}>
          <StatCard
            icon={FileText}
            tone="primary"
            label="บทที่รอสร้าง"
            value={data.stats?.scriptsPending ?? 0}
            hint="บทที่ยังไม่ได้สร้างคลิป"
          />
          <StatCard
            icon={Film}
            tone="mint"
            label="คลิปที่สร้างวันนี้"
            value={data.stats?.clipsToday ?? 0}
            hint="คลิปที่เรนเดอร์ในวันนี้"
          />
          <StatCard
            icon={AlertTriangle}
            tone="orange"
            label="คลิปที่รอการตรวจสอบ"
            value={data.stats?.clipsNeedsReview ?? 0}
            hint="คลิปที่ยังต้องดูอีกครั้ง"
          />
          <StatCard
            icon={Library}
            tone="blue"
            label="คลิปทั้งหมด"
            value={data.stats?.clipsTotal ?? 0}
            hint="คลิปที่มีอยู่ในโฟลเดอร์ผลลัพธ์"
          />
        </div>

        {/* ------------------------------------------- quick menu + workflow */}
        <div className="page-fit__grid">
          <div className="page-fit__col">
            <PastelCard
              title="เมนูด่วน"
              subtitle="เลือกงานที่ต้องการทำต่อได้ทันที"
              icon={Rocket}
              iconTone="primary"
            >
              <div
                className="grid"
                style={{ gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 10 }}
              >
                {QUICK.map((q) => {
                  const Icon = q.icon;
                  return (
                    <button
                      key={q.title}
                      type="button"
                      className="stat"
                      onClick={() => navigate(q.to)}
                      style={{ cursor: "pointer", textAlign: "left", alignItems: "center" }}
                    >
                      <span
                        className="stat__icon"
                        style={{ background: q.bg, color: q.fg, width: 40, height: 40 }}
                      >
                        <Icon size={19} />
                      </span>
                      <span style={{ minWidth: 0 }}>
                        <span className="strong" style={{ display: "block" }}>
                          {q.title}
                        </span>
                        <span className="xsmall muted" style={{ display: "block" }}>
                          {q.desc}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>
            </PastelCard>

            <PastelCard
              title="ขั้นตอนการทำงาน"
              subtitle="ตั้งแต่ไอเดียจนถึงโพสต์ขึ้นแพลตฟอร์ม"
              icon={ListChecks}
              iconTone="blue"
            >
              <div className="col" style={{ gap: 16 }}>
                {STEPS.map((s) => (
                  <Step
                    key={s.n}
                    n={s.n}
                    title={s.title}
                    text={s.text}
                    tone={s.tone}
                    icon={s.icon}
                  />
                ))}
              </div>
            </PastelCard>
          </div>

          <div className="page-fit__col">
            {/* --------------------------------------------- system status */}
            <PastelCard
              title="สถานะระบบ"
              subtitle="ตรวจความพร้อมของแต่ละส่วนแบบเรียลไทม์"
              icon={Settings}
              iconTone="mint"
              actions={
                <button className="btn btn--ghost btn--sm" onClick={() => reload()}>
                  รีเฟรช
                </button>
              }
            >
              <div className="col" style={{ gap: 12 }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "10px 12px",
                    borderRadius: "var(--r-md)",
                    background: "var(--g-primary-soft)",
                  }}
                >
                  <CalendarDays size={17} color="var(--c-primary)" />
                  <div style={{ minWidth: 0 }}>
                    <div className="xsmall muted">โพสต์อัตโนมัติครั้งถัดไป</div>
                    <div className="strong" style={{ color: "var(--c-primary-darker)" }}>
                      {data.nextPost
                        ? `${data.nextPost.label} · ${data.nextPost.countdown}`
                        : "ยังไม่ได้ตั้งเวลา"}
                    </div>
                  </div>
                </div>

                {systems.length === 0 ? (
                  <EmptyState
                    title="ยังไม่มีข้อมูลสถานะระบบ"
                    text="ระบบยังไม่ได้รายงานสถานะของแต่ละส่วน ลองกดรีเฟรชอีกครั้ง"
                    icon={CircleDot}
                  />
                ) : (
                  <div className="col" style={{ gap: 8 }}>
                    {systems.map(([key, sys]) => {
                      const Icon = SYSTEM_ICON[key] ?? CircleDot;
                      const ready = !!sys?.ready;
                      return (
                        <div
                          key={key}
                          className="row"
                          style={{
                            gap: 10,
                            padding: "9px 10px",
                            borderRadius: "var(--r-md)",
                            border: "1px solid var(--c-line)",
                          }}
                        >
                          <span
                            style={{
                              width: 30,
                              height: 30,
                              borderRadius: 9,
                              display: "grid",
                              placeItems: "center",
                              background: ready ? "var(--g-mint)" : "var(--c-warn-soft)",
                              color: ready ? "var(--c-mint-strong)" : "var(--c-warn)",
                              flex: "none",
                            }}
                          >
                            <Icon size={15} />
                          </span>
                          <div style={{ minWidth: 0, flex: 1 }}>
                            <div className="small strong">
                              {SYSTEM_LABEL[key] ?? key}
                              <span className="xsmall muted"> · {sys?.label || "-"}</span>
                            </div>
                            <div className="xsmall muted truncate" title={sys?.detail || ""}>
                              {sys?.detail || "-"}
                            </div>
                          </div>
                          <StatusBadge tone={ready ? "success" : "warn"} dot>
                            {ready ? "พร้อม" : "ยังไม่พร้อม"}
                          </StatusBadge>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </PastelCard>

            {/* --------------------------------------------------- activity */}
            <PastelCard
              title="กิจกรรมล่าสุด"
              subtitle="สิ่งที่เพิ่งเกิดขึ้นในสตูดิโอ"
              icon={Activity}
              iconTone="orange"
            >
              {activity.length === 0 ? (
                <EmptyState
                  title="ยังไม่มีกิจกรรม"
                  text="เมื่อคุณส่งคำขอไอเดียหรือสร้างคลิป ระบบจะแสดงความเคลื่อนไหวที่นี่"
                  icon={Activity}
                />
              ) : (
                <div className="col" style={{ gap: 10 }}>
                  {activity.map((a, i) => {
                    const Icon = activityIcon(a.kind);
                    return (
                      <div
                        key={`${a.at}-${i}`}
                        className="row"
                        style={{ gap: 10, alignItems: "flex-start" }}
                      >
                        <span
                          style={{
                            width: 30,
                            height: 30,
                            borderRadius: 9,
                            display: "grid",
                            placeItems: "center",
                            background: "var(--g-primary-soft)",
                            color: "var(--c-primary)",
                            flex: "none",
                          }}
                        >
                          <Icon size={15} />
                        </span>
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div className="small strong truncate" title={a.title}>
                            {a.title}
                          </div>
                          <div className="xsmall muted truncate" title={a.detail}>
                            {a.detail}
                          </div>
                        </div>
                        <span className="xsmall muted" style={{ flex: "none" }}>
                          {formatRelative(a.at)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </PastelCard>
          </div>
        </div>
      </div>
    </>
  );
}
