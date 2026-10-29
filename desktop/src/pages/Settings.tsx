import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Eye,
  EyeOff,
  Info,
  KeyRound,
  Loader2,
  Music,
  RefreshCw,
  RotateCcw,
  Save,
  Settings as SettingsIcon,
  Sparkles,
  Trash2,
  Volume2,
} from "lucide-react";
import { apiGet, apiPost, assetUrl, openPath, CHAR_LABEL, type JobPayload } from "../services/api";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  PastelCard,
  StatusBadge,
} from "../components/common/ui";
import { DataTable } from "../components/common/DataTable";
import { useApiData } from "../hooks/useApiData";
import { ConfirmDialog, useToast } from "../components/common/feedback";

/* ------------------------------------------------------------------ types */

type VoiceCfg = { edge: string; rate: string; pitch: string };
type CharacterRow = { who: string; label: string; emoji: string };

type SettingsResponse = {
  ok: boolean;
  settings: {
    channelName: string;
    outroText: string;
    readTitle: boolean;
    readOutro: boolean;
    formats: string[];
    musicVolume: number;
    voiceVolume: number;
    sfxVolume: number;
    fps: number;
    voices: Record<string, { edge?: string; rate?: string; pitch?: string }>;
    ttsEngines: string[];
    azureRegion: string;
    allowTestVoice: boolean;
  };
  providers: {
    gemini: { connected: boolean; label: string };
    azure: { connected: boolean; label: string; region: string };
    facebookPage: { connected: boolean; label: string };
  };
  characters: string[];
  voiceOptions: string[];
};

type FormState = {
  channelName: string;
  outroText: string;
  readTitle: boolean;
  readOutro: boolean;
  formats: string[];
  musicVolume: number;
  voiceVolume: number;
  sfxVolume: number;
  fps: number;
  voices: Record<string, VoiceCfg>;
  ttsEngines: string[];
  azureRegion: string;
  allowTestVoice: boolean;
};

const TABS = [
  { key: "general", label: "การตั้งค่าทั่วไป" },
  { key: "channel", label: "ช่องและคลิป" },
  { key: "ai", label: "AI & บริการภายนอก" },
  { key: "voice", label: "เสียงตัวละคร" },
  { key: "etc", label: "อื่น ๆ" },
];

const AZURE_REGIONS = [
  { value: "southeastasia", label: "Southeast Asia (Thailand)" },
  { value: "eastasia", label: "East Asia" },
  { value: "northeurope", label: "North Europe" },
  { value: "japaneast", label: "Japan East" },
];

const TTS_ENGINES = [
  { value: "azure", label: "Azure (เสียงทางการ ต้องมี Key)" },
  { value: "edge", label: "Edge (ฟรี ต้องต่อเน็ต)" },
  { value: "sapi", label: "SAPI (เสียงใน Windows)" },
  { value: "espeak", label: "espeak (เสียงทดสอบ)" },
];

const CHARACTER_EMOJI: Record<string, string> = {
  narrator: "🧑‍🎤",
  bunny: "🐰",
  bear: "🐻",
  chick: "🐤",
  cat: "🐱",
};

/** Defaults of the engine config (engine/taoyong/config.py). */
const DEFAULTS: FormState = {
  channelName: "",
  outroText: "แล้วพบกันใหม่นะ!",
  readTitle: true,
  readOutro: true,
  formats: ["vertical", "horizontal"],
  musicVolume: 0.16,
  voiceVolume: 1,
  sfxVolume: 0.5,
  fps: 30,
  voices: {
    narrator: { edge: "th-TH-PremwadeeNeural", rate: "-5%", pitch: "+0Hz" },
    bunny: { edge: "th-TH-PremwadeeNeural", rate: "+5%", pitch: "+35Hz" },
    bear: { edge: "th-TH-NiwatNeural", rate: "-5%", pitch: "-5Hz" },
    chick: { edge: "th-TH-PremwadeeNeural", rate: "+12%", pitch: "+60Hz" },
    cat: { edge: "th-TH-PremwadeeNeural", rate: "-3%", pitch: "+15Hz" },
  },
  ttsEngines: ["azure", "edge", "sapi", "espeak"],
  azureRegion: "southeastasia",
  allowTestVoice: false,
};

/* ---------------------------------------------------------------- helpers */

function errMsg(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}

function numOf(value: string | undefined, fallback: number): number {
  if (!value) return fallback;
  const m = value.match(/-?\d+/);
  return m ? Number(m[0]) : fallback;
}

function sign(value: number, unit: string): string {
  return `${value >= 0 ? "+" : ""}${value}${unit}`;
}

async function pollJob(
  jobId: string,
  onTick: (job: JobPayload) => void,
  isAlive: () => boolean,
): Promise<JobPayload> {
  for (let i = 0; i < 200; i++) {
    const res = await apiGet<{ ok: boolean; job: JobPayload }>("/api/job", { id: jobId });
    onTick(res.job);
    if (res.job.status !== "running") return res.job;
    if (!isAlive()) throw new Error("ยกเลิกการติดตามงาน");
    await new Promise((r) => setTimeout(r, 700));
  }
  throw new Error("การสร้างเสียงใช้เวลานานเกินไป กรุณาลองใหม่");
}

/* ------------------------------------------------------------------- page */

export default function Settings() {
  const toast = useToast();
  const { data, loading, error, reload } = useApiData<SettingsResponse>(
    () => apiGet<SettingsResponse>("/api/settings"),
  );

  const [tab, setTab] = useState("general");
  const [form, setForm] = useState<FormState | null>(null);
  const [saving, setSaving] = useState(false);
  const [geminiKey, setGeminiKey] = useState("");
  const [azureKey, setAzureKey] = useState("");
  const [showGemini, setShowGemini] = useState(false);
  const [showAzure, setShowAzure] = useState(false);
  const [keyBusy, setKeyBusy] = useState(false);
  const [testingWho, setTestingWho] = useState<string | null>(null);
  const [audioUrl, setAudioUrl] = useState("");
  const [resetOpen, setResetOpen] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioPathRef = useRef("");
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  useEffect(() => {
    if (!data?.settings) return;
    const s = data.settings;
    const voices: Record<string, VoiceCfg> = {};
    for (const who of data.characters ?? []) {
      const raw = s.voices?.[who] ?? {};
      voices[who] = {
        edge: raw.edge ?? DEFAULTS.voices[who]?.edge ?? DEFAULTS.voices.narrator.edge,
        rate: raw.rate ?? DEFAULTS.voices[who]?.rate ?? DEFAULTS.voices.narrator.rate,
        pitch: raw.pitch ?? DEFAULTS.voices[who]?.pitch ?? DEFAULTS.voices.narrator.pitch,
      };
    }
    setForm({
      channelName: s.channelName ?? "",
      outroText: s.outroText ?? "",
      readTitle: s.readTitle !== false,
      readOutro: s.readOutro !== false,
      formats: Array.isArray(s.formats) && s.formats.length ? [...s.formats] : [...DEFAULTS.formats],
      musicVolume: Number(s.musicVolume) || 0,
      voiceVolume: Number(s.voiceVolume) || 0,
      sfxVolume: Number(s.sfxVolume) || 0,
      fps: Number(s.fps) || 30,
      voices,
      ttsEngines: Array.isArray(s.ttsEngines) ? [...s.ttsEngines] : [...DEFAULTS.ttsEngines],
      azureRegion: s.azureRegion || DEFAULTS.azureRegion,
      allowTestVoice: s.allowTestVoice === true,
    });
  }, [data]);

  const patch = (p: Partial<FormState>) => setForm((f) => (f ? { ...f, ...p } : f));

  const patchVoice = (who: string, p: Partial<VoiceCfg>) =>
    setForm((f) =>
      f ? { ...f, voices: { ...f.voices, [who]: { ...f.voices[who], ...p } } } : f,
    );

  const characters = useMemo<CharacterRow[]>(
    () =>
      (data?.characters ?? Object.keys(DEFAULTS.voices)).map((who) => ({
        who,
        label: CHAR_LABEL[who] ?? who,
        emoji: CHARACTER_EMOJI[who] ?? "🎭",
      })),
    [data],
  );

  const voiceOptions = data?.voiceOptions ?? ["th-TH-PremwadeeNeural", "th-TH-NiwatNeural"];

  const voiceName = (voice: string) => {
    if (voice === "th-TH-PremwadeeNeural") return "th-TH-PremwadeeNeural (หญิง, เป็นกันเอง)";
    if (voice === "th-TH-NiwatNeural") return "th-TH-NiwatNeural (ชาย, เป็นกันเอง)";
    return voice;
  };

  /* ----------------------------------------------------------- persistence */

  const buildSettings = (f: FormState) => ({
    channelName: f.channelName,
    outroText: f.outroText,
    readTitle: f.readTitle,
    readOutro: f.readOutro,
    formats: f.formats,
    musicVolume: f.musicVolume,
    voiceVolume: f.voiceVolume,
    sfxVolume: f.sfxVolume,
    fps: f.fps,
    voices: f.voices,
    ttsEngines: f.ttsEngines,
    azureRegion: f.azureRegion,
    allowTestVoice: f.allowTestVoice,
  });

  const save = async (silent = false) => {
    if (!form) return false;
    setSaving(true);
    try {
      await apiPost("/api/settings/save", { settings: buildSettings(form) });
      if (!silent) toast.success("บันทึกการตั้งค่าแล้ว");
      await reload(true);
      return true;
    } catch (e) {
      toast.error("บันทึกการตั้งค่าไม่สำเร็จ", errMsg(e));
      return false;
    } finally {
      setSaving(false);
    }
  };

  const saveGeminiKey = async () => {
    if (!geminiKey.trim()) {
      toast.warn("ยังไม่ได้ใส่ Gemini API Key", "วางคีย์ลงในช่องก่อนบันทึก");
      return;
    }
    setKeyBusy(true);
    try {
      await apiPost("/api/settings/key", { key: geminiKey.trim() });
      setGeminiKey("");
      toast.success("บันทึก Gemini API Key แล้ว", "คีย์ถูกเก็บในเครื่องแบบเข้ารหัส ไม่ถูกส่งกลับมาแสดงในหน้านี้");
      await reload(true);
    } catch (e) {
      toast.error("บันทึก Gemini API Key ไม่สำเร็จ", errMsg(e));
    } finally {
      setKeyBusy(false);
    }
  };

  const deleteGeminiKey = async () => {
    setKeyBusy(true);
    try {
      await apiPost("/api/settings/key/delete");
      setGeminiKey("");
      toast.success("ลบ Gemini API Key แล้ว");
      await reload(true);
    } catch (e) {
      toast.error("ลบ Gemini API Key ไม่สำเร็จ", errMsg(e));
    } finally {
      setKeyBusy(false);
    }
  };

  const saveAzureKey = async () => {
    if (!azureKey.trim()) {
      toast.warn("ยังไม่ได้ใส่ Speech Key", "วางคีย์ลงในช่องก่อนบันทึก");
      return;
    }
    setKeyBusy(true);
    try {
      await apiPost("/api/settings/azure-key", { key: azureKey.trim() });
      await apiPost("/api/settings/save", {
        settings: { azureRegion: form?.azureRegion ?? DEFAULTS.azureRegion },
      });
      const check = await apiGet<SettingsResponse>("/api/settings");
      setAzureKey("");
      if (check?.providers?.azure?.connected) {
        toast.success(
          "บันทึก Speech Key แล้ว",
          `Azure Speech เชื่อมต่ออยู่ (Region: ${check.providers.azure.region || form?.azureRegion})`,
        );
      } else {
        toast.error("ยังบันทึก Speech Key ไม่สำเร็จ", "ลองใหม่อีกครั้งหรือตรวจสอบสิทธิ์ของคีย์");
      }
      await reload(true);
    } catch (e) {
      toast.error("บันทึก Speech Key ไม่สำเร็จ", errMsg(e));
    } finally {
      setKeyBusy(false);
    }
  };

  const deleteAzureKey = async () => {
    setKeyBusy(true);
    try {
      await apiPost("/api/settings/azure-key/delete", {});
      await apiPost("/api/settings/save", { settings: { azureKey: "" } });
      const check = await apiGet<SettingsResponse>("/api/settings");
      if (!check?.providers?.azure?.connected) {
        toast.success("ลบ Speech Key แล้ว");
        setAzureKey("");
      } else {
        toast.error("ยังลบ Speech Key ไม่สำเร็จ", "ลองใหม่อีกครั้ง");
      }
      await reload(true);
    } catch (e) {
      toast.error("ลบ Speech Key ไม่สำเร็จ", errMsg(e));
    } finally {
      setKeyBusy(false);
    }
  };

  const testAzure = async () => {
    setKeyBusy(true);
    try {
      const res = await apiPost<{ ok: boolean; connected: boolean; detail?: string; error?: string }>(
        "/api/settings/test-azure",
      );
      if (res?.ok && res.connected) {
        toast.success("เชื่อมต่อ Azure Speech สำเร็จ", res.detail);
      } else {
        toast.error("ทดสอบการเชื่อมต่อ Azure Speech ไม่สำเร็จ", res?.error || "ไม่ทราบสาเหตุ");
      }
      await reload(true);
    } catch (e) {
      toast.error("ทดสอบการเชื่อมต่อ Azure Speech ไม่สำเร็จ", errMsg(e));
    } finally {
      setKeyBusy(false);
    }
  };

  const resetDefaults = async () => {
    setResetOpen(false);
    const next: FormState = {
      ...DEFAULTS,
      voices: JSON.parse(JSON.stringify(DEFAULTS.voices)) as Record<string, VoiceCfg>,
      formats: [...DEFAULTS.formats],
      ttsEngines: [...DEFAULTS.ttsEngines],
    };
    setForm(next);
    setSaving(true);
    try {
      await apiPost("/api/settings/save", { settings: buildSettings(next) });
      toast.success("คืนค่าเริ่มต้นแล้ว", "บันทึกค่าเริ่มต้นของสตูดิโอลงใน config.json เรียบร้อย");
      await reload(true);
    } catch (e) {
      toast.error("คืนค่าเริ่มต้นไม่สำเร็จ", errMsg(e));
    } finally {
      setSaving(false);
    }
  };

  /* ---------------------------------------------------------- voice preview */

  useEffect(() => {
    if (!audioUrl) return;
    const el = audioRef.current;
    if (!el) return;
    el.src = audioUrl;
    el.play().catch(() => {
      const p = audioPathRef.current;
      if (p) openPath(p).catch(() => {});
    });
  }, [audioUrl]);

  const testVoice = async (who: string) => {
    setTestingWho(who);
    try {
      const res = await apiPost<{ ok: boolean; jobId: string }>("/api/settings/test-voice", { who });
      const job = await pollJob(
        res.jobId,
        () => {},
        () => alive.current,
      );
      if (job.status === "done") {
        const path = (job.result as { path?: string } | null)?.path;
        if (!path) {
          toast.warn("ไม่พบไฟล์เสียง", "เอนจินสร้างเสียงไม่สำเร็จหรือไม่ได้คืนพาธไฟล์");
          return;
        }
        audioPathRef.current = path;
        setAudioUrl(assetUrl(path));
        toast.success(`สร้างเสียงตัวอย่าง ${CHAR_LABEL[who] ?? who} สำเร็จ`);
      } else {
        toast.error(
          `สร้างเสียงตัวอย่าง ${CHAR_LABEL[who] ?? who} ไม่สำเร็จ`,
          job.error || "ไม่ทราบสาเหตุ",
        );
      }
    } catch (e) {
      toast.error(`สร้างเสียงตัวอย่าง ${CHAR_LABEL[who] ?? who} ไม่สำเร็จ`, errMsg(e));
    } finally {
      setTestingWho(null);
    }
  };

  /* --------------------------------------------------------------- render */

  if (loading && !form) {
    return (
      <>
        <PageHeader title="ตั้งค่า" icon={SettingsIcon} />
        <PastelCard>
          <LoadingState label="กำลังโหลดการตั้งค่า..." />
        </PastelCard>
      </>
    );
  }

  if (error && !form) {
    return (
      <>
        <PageHeader title="ตั้งค่า" icon={SettingsIcon} />
        <PastelCard>
          <ErrorState message={error} onRetry={() => reload()} />
        </PastelCard>
      </>
    );
  }

  const providers = data?.providers;
  const geminiConnected = !!providers?.gemini?.connected;
  const azureConnected = !!providers?.azure?.connected;

  const channelCard = form ? (
    <PastelCard
      title="ช่องและคลิป"
      subtitle="ตั้งชื่อช่อง ข้อความปิดท้ายคลิป และรูปแบบวิดีโอที่ใช้ทั้งหมด"
      icon={Music}
      iconTone="primary"
    >
      <div className="col" style={{ gap: 16 }}>
        <div className="field">
          <div className="row row--between" style={{ gap: 10 }}>
            <span className="field__label">ชื่อช่อง YouTube / Facebook</span>
            <span className="xsmall muted">
              {form.channelName.length}/50
            </span>
          </div>
          <input
            className="input"
            maxLength={50}
            value={form.channelName}
            onChange={(e) => patch({ channelName: e.target.value })}
            placeholder="เช่น TaoYongStudio"
          />
        </div>

        <div className="field">
          <div className="row row--between" style={{ gap: 10 }}>
            <span className="field__label">ข้อความปิดท้ายคลิป (Outro)</span>
            <span className="xsmall muted">
              {form.outroText.length}/200
            </span>
          </div>
          <textarea
            className="textarea"
            maxLength={200}
            value={form.outroText}
            onChange={(e) => patch({ outroText: e.target.value })}
            placeholder="ข้อความที่พูดปิดท้ายคลิปแต่ละคลิป"
          />
        </div>

        <div className="field">
          <span className="field__label">รูปแบบวิดีโอที่ใช้ทั้งหมด</span>
          <div className="col" style={{ gap: 9 }}>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={form.formats.includes("vertical")}
                onChange={(e) =>
                  patch({
                    formats: e.target.checked
                      ? [...form.formats, "vertical"]
                      : form.formats.filter((f) => f !== "vertical"),
                  })
                }
              />
              <span>
                <span className="small strong">แนวตั้ง (9:16)</span>
                <span className="xsmall muted" style={{ display: "block" }}>
                  เหมาะกับ TikTok, Reels, YouTube Shorts
                </span>
              </span>
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={form.formats.includes("horizontal")}
                onChange={(e) =>
                  patch({
                    formats: e.target.checked
                      ? [...form.formats, "horizontal"]
                      : form.formats.filter((f) => f !== "horizontal"),
                  })
                }
              />
              <span>
                <span className="small strong">แนวนอน (16:9)</span>
                <span className="xsmall muted" style={{ display: "block" }}>
                  เหมาะกับ YouTube และ Facebook
                </span>
              </span>
            </label>
          </div>
        </div>

        <div className="field">
          <div className="row row--between" style={{ gap: 10 }}>
            <span className="field__label">ระดับเสียงเพลงประกอบ</span>
            <span className="small strong">{Math.round(form.musicVolume * 100)}%</span>
          </div>
          <input
            className="slider"
            type="range"
            min={0}
            max={100}
            value={Math.round(form.musicVolume * 100)}
            onChange={(e) => patch({ musicVolume: Number(e.target.value) / 100 })}
            aria-label="ระดับเสียงเพลงประกอบ"
          />
        </div>
      </div>
    </PastelCard>
  ) : null;

  const providerCards = form ? (
    <>
      <PastelCard
        title="พนักงาน AI เขียนข้อความโพสต์ (Google Gemini)"
        subtitle="ใช้ Google Gemini ช่วยคิดแคปชันและข้อความโพสต์ให้อัตโนมัติ"
        icon={Sparkles}
        iconTone="pink"
        actions={
          geminiConnected ? (
            <StatusBadge tone="success" dot>
              เชื่อมต่อแล้ว
            </StatusBadge>
          ) : (
            <StatusBadge tone="muted" dot>
              ยังไม่ได้ตั้งค่า
            </StatusBadge>
          )
        }
      >
        <div
          className="grid"
          style={{ gridTemplateColumns: "minmax(0, 1fr) 190px", alignItems: "start", gap: 14 }}
        >
          <div className="col" style={{ gap: 12 }}>
            <div className="field">
              <span className="field__label">Gemini API Key</span>
              <div className="search" style={{ display: "block" }}>
                <input
                  className="input"
                  type={showGemini ? "text" : "password"}
                  value={geminiKey}
                  onChange={(e) => setGeminiKey(e.target.value)}
                  placeholder="วางคีย์ของคุณที่นี่"
                  autoComplete="off"
                  style={{ paddingRight: 42 }}
                />
                <button
                  type="button"
                  className="btn btn--ghost btn--icon btn--sm"
                  style={{ position: "absolute", right: 4, top: 4 }}
                  onClick={() => setShowGemini((v) => !v)}
                  aria-label={showGemini ? "ซ่อนคีย์" : "แสดงคีย์"}
                >
                  {showGemini ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
              <span className="field__hint">
                เก็บคีย์ไว้ในเครื่องนี้แบบเข้ารหัส (DPAPI) โปรแกรมจะไม่แสดงคีย์เดิมกลับมาให้เห็น
              </span>
            </div>
            <div className="row row--wrap" style={{ gap: 9 }}>
              <button
                type="button"
                className="btn btn--primary btn--sm"
                onClick={saveGeminiKey}
                disabled={keyBusy}
              >
                {keyBusy ? <Loader2 size={14} className="spin" /> : <KeyRound size={14} />} บันทึกคีย์
              </button>
              <button
                type="button"
                className="btn btn--danger btn--sm"
                onClick={deleteGeminiKey}
                disabled={keyBusy}
              >
                <Trash2 size={14} /> ลบคีย์
              </button>
            </div>
          </div>

          <div
            className="card"
            style={{
              background: "var(--g-primary-soft)",
              textAlign: "center",
              padding: 14,
              border: "none",
            }}
          >
            <div
              style={{
                width: 46,
                height: 46,
                borderRadius: 14,
                margin: "0 auto 8px",
                background: "linear-gradient(135deg,#a86bff,#f43f7e)",
                color: "#fff",
                display: "grid",
                placeItems: "center",
              }}
            >
              <Sparkles size={22} />
            </div>
            <div className="small strong">Google Gemini</div>
            <div className="xsmall muted" style={{ lineHeight: 1.55, marginTop: 4 }}>
              ช่วยคิดแคปชัน
              <br />
              สร้างข้อความโพสต์ในภาษาไทย
            </div>
          </div>
        </div>
      </PastelCard>

      <PastelCard
        title="เสียงตัวละคร (Azure Speech)"
        subtitle="ใช้เสียงคุณภาพจาก Microsoft Azure สำหรับการพากย์เสียง"
        icon={Volume2}
        iconTone="blue"
        actions={
          azureConnected ? (
            <StatusBadge tone="success" dot>
              เชื่อมต่อแล้ว
            </StatusBadge>
          ) : (
            <StatusBadge tone="muted" dot>
              ยังไม่ได้ตั้งค่า
            </StatusBadge>
          )
        }
      >
        <div
          className="grid"
          style={{ gridTemplateColumns: "minmax(0, 1fr) 190px", alignItems: "start", gap: 14 }}
        >
          <div className="col" style={{ gap: 12 }}>
            <div className="field">
              <span className="field__label">Speech Key</span>
              <div className="search" style={{ display: "block" }}>
                <input
                  className="input"
                  type={showAzure ? "text" : "password"}
                  value={azureKey}
                  onChange={(e) => setAzureKey(e.target.value)}
                  placeholder="วาง Speech Key ของคุณที่นี่"
                  autoComplete="off"
                  style={{ paddingRight: 42 }}
                />
                <button
                  type="button"
                  className="btn btn--ghost btn--icon btn--sm"
                  style={{ position: "absolute", right: 4, top: 4 }}
                  onClick={() => setShowAzure((v) => !v)}
                  aria-label={showAzure ? "ซ่อนคีย์" : "แสดงคีย์"}
                >
                  {showAzure ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>
            <div className="field">
              <span className="field__label">Region</span>
              <select
                className="select"
                value={form.azureRegion}
                onChange={(e) => patch({ azureRegion: e.target.value })}
              >
                {AZURE_REGIONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="row row--wrap" style={{ gap: 9 }}>
              <button
                type="button"
                className="btn btn--primary btn--sm"
                onClick={saveAzureKey}
                disabled={keyBusy}
              >
                {keyBusy ? <Loader2 size={14} className="spin" /> : <KeyRound size={14} />} บันทึกคีย์
              </button>
              <button
                type="button"
                className="btn btn--danger btn--sm"
                onClick={deleteAzureKey}
                disabled={keyBusy}
              >
                <Trash2 size={14} /> ลบคีย์
              </button>
              <button
                type="button"
                className="btn btn--soft btn--sm"
                onClick={testAzure}
                disabled={keyBusy}
              >
                <RefreshCw size={14} /> ทดสอบการเชื่อมต่อ
              </button>
            </div>
            <span className="field__hint">
              Speech Key ถูกเข้ารหัสด้วย Windows DPAPI และไม่ถูกส่งกลับมาที่หน้าจอ
              เมื่อบันทึกแล้วสถานะจะขึ้น "เชื่อมต่อแล้ว"
            </span>
          </div>

          <div
            className="card"
            style={{
              background: "var(--g-blue)",
              textAlign: "center",
              padding: 14,
              border: "none",
            }}
          >
            <div
              style={{
                width: 46,
                height: 46,
                borderRadius: 14,
                margin: "0 auto 8px",
                background: "#0078d4",
                color: "#fff",
                display: "grid",
                placeItems: "center",
                fontWeight: 700,
                fontSize: 22,
              }}
            >
              A
            </div>
            <div className="small strong">Azure Speech</div>
            <div className="xsmall muted" style={{ lineHeight: 1.55, marginTop: 4 }}>
              เสียงเตอร์ไทยคุณภาพสูง
              <br />
              เบราว์เซอร์ใช้ฟรี
            </div>
          </div>
        </div>
      </PastelCard>
    </>
  ) : null;

  const voicesCard = form ? (
    <PastelCard
      title="เสียงตัวละคร"
      subtitle="กำหนดเสียง ระดับเสียง และความเร็วของการพากย์เสียงแต่ละตัวละคร"
      icon={Volume2}
      iconTone="pink"
    >
      <div className="col" style={{ gap: 12 }}>
        <div className="row" style={{ gap: 9, alignItems: "flex-start" }}>
          <Info size={15} style={{ color: "var(--c-info)", flex: "none", marginTop: 2 }} />
          <span className="xsmall muted" style={{ lineHeight: 1.6 }}>
            ปรับตั้งค่าความเสียง และดูตัวอย่างเสียงก่อนบันทึก — เสียงที่สร้างได้จริงจากเอนจินที่กำลังทำงาน
          </span>
        </div>

        <DataTable<CharacterRow>
          columns={[
            {
              key: "who",
              header: "ตัวละคร",
              width: 200,
              render: (row) => (
                <span className="row" style={{ gap: 9 }}>
                  <span
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: "50%",
                      background: "var(--c-primary-soft)",
                      display: "grid",
                      placeItems: "center",
                      fontSize: 17,
                      flex: "none",
                    }}
                  >
                    {row.emoji}
                  </span>
                  <span className="small strong truncate">{row.label}</span>
                </span>
              ),
            },
            {
              key: "voice",
              header: "เสียง (Voice)",
              width: 250,
              render: (row) => (
                <select
                  className="select"
                  value={form.voices[row.who]?.edge ?? ""}
                  onChange={(e) => patchVoice(row.who, { edge: e.target.value })}
                >
                  {voiceOptions.map((v) => (
                    <option key={v} value={v}>
                      {voiceName(v)}
                    </option>
                  ))}
                </select>
              ),
            },
            {
              key: "pitch",
              header: "ระดับเสียง (Pitch)",
              width: 220,
              render: (row) => {
                const value = numOf(form.voices[row.who]?.pitch, 0);
                return (
                  <span className="row" style={{ gap: 8 }}>
                    <input
                      className="slider"
                      type="range"
                      min={-50}
                      max={50}
                      value={value}
                      onChange={(e) =>
                        patchVoice(row.who, { pitch: sign(Number(e.target.value), "Hz") })
                      }
                      style={{ width: 120 }}
                      aria-label={`ระดับเสียง ${row.label}`}
                    />
                    <input
                      className="input"
                      type="number"
                      min={-50}
                      max={50}
                      value={value}
                      onChange={(e) =>
                        patchVoice(row.who, {
                          pitch: sign(Math.max(-50, Math.min(50, Number(e.target.value) || 0)), "Hz"),
                        })
                      }
                      style={{ width: 68, textAlign: "center", padding: "6px 6px" }}
                      aria-label={`ตัวเลขระดับเสียง ${row.label}`}
                    />
                  </span>
                );
              },
            },
            {
              key: "rate",
              header: "ความเร็ว (Rate)",
              width: 220,
              render: (row) => {
                const value = numOf(form.voices[row.who]?.rate, 0);
                return (
                  <span className="row" style={{ gap: 8 }}>
                    <input
                      className="slider"
                      type="range"
                      min={-50}
                      max={50}
                      value={value}
                      onChange={(e) =>
                        patchVoice(row.who, { rate: sign(Number(e.target.value), "%") })
                      }
                      style={{ width: 120 }}
                      aria-label={`ความเร็วเสียง ${row.label}`}
                    />
                    <input
                      className="input"
                      type="number"
                      min={-50}
                      max={50}
                      value={value}
                      onChange={(e) =>
                        patchVoice(row.who, {
                          rate: sign(Math.max(-50, Math.min(50, Number(e.target.value) || 0)), "%"),
                        })
                      }
                      style={{ width: 68, textAlign: "center", padding: "6px 6px" }}
                      aria-label={`ตัวเลขความเร็วเสียง ${row.label}`}
                    />
                  </span>
                );
              },
            },
            {
              key: "preview",
              header: "ตัวอย่างเสียง",
              width: 120,
              render: (row) => (
                <button
                  type="button"
                  className="btn btn--primary btn--sm"
                  onClick={() => testVoice(row.who)}
                  disabled={testingWho === row.who}
                >
                  {testingWho === row.who ? (
                    <Loader2 size={13} className="spin" />
                  ) : (
                    <Volume2 size={13} />
                  )}
                  ฟังเสียง
                </button>
              ),
            },
          ]}
          rows={characters}
          rowKey={(row) => row.who}
          empty={<EmptyState title="ยังไม่มีตัวละคร" />}
        />

        <audio ref={audioRef} style={{ display: "none" }} />
      </div>
    </PastelCard>
  ) : null;

  const tipCard = (
    <div className="card card--soft" style={{ background: "var(--g-orange)", border: "none" }}>
      <div className="row" style={{ gap: 11, alignItems: "flex-start" }}>
        <span
          style={{
            width: 34,
            height: 34,
            borderRadius: 12,
            background: "#fff",
            color: "var(--c-orange-strong)",
            display: "grid",
            placeItems: "center",
            flex: "none",
          }}
        >
          <Sparkles size={17} />
        </span>
        <div style={{ minWidth: 0 }}>
          <div className="strong" style={{ color: "var(--c-orange-strong)" }}>
            เคล็ดลับการตั้งค่า
          </div>
          <div className="xsmall" style={{ lineHeight: 1.7, color: "#7a5417", marginTop: 3 }}>
            คุณสามารถเปลี่ยนชื่อช่องและข้อความปิดท้ายคลิปได้ทุกครั้งที่สร้างคลิปใหม่
            เสียงตัวละครแต่ละตัวปรับได้อิสระ ควรทดสอบเสียงก่อนเรนเดอร์คลิปจริงเสมอ
            และใช้ Azure Speech เมื่อต้องการเสียงทางการที่ใช้เชิงพาณิชย์ได้
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <>
      <PageHeader
        icon={SettingsIcon}
        title="ตั้งค่า"
        subtitle="ปรับแต่งการใช้งาน TaoYongStudio ให้เหมาะกับสไตล์ของคุณ"
      />

      <div className="tabs" style={{ marginBottom: 16 }}>
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            className={`tabs__item ${tab === t.key ? "tabs__item--active" : ""}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="stack">
        {tab === "general" && (
          <>
            {channelCard}
            {providerCards}
            {voicesCard}
            {tipCard}
          </>
        )}

        {tab === "channel" && (
          <>
            {channelCard}
            <PastelCard title="ระดับเสียงรวม" subtitle="ปรับความดังของเสียงพากย์และเสียงประกอบในคลิป" icon={Volume2} iconTone="mint">
              {form && (
                <div className="col" style={{ gap: 16 }}>
                  <div className="field">
                    <div className="row row--between" style={{ gap: 10 }}>
                      <span className="field__label">ระดับเสียงพากย์</span>
                      <span className="small strong">{Math.round(form.voiceVolume * 100)}%</span>
                    </div>
                    <input
                      className="slider"
                      type="range"
                      min={0}
                      max={200}
                      value={Math.round(form.voiceVolume * 100)}
                      onChange={(e) => patch({ voiceVolume: Number(e.target.value) / 100 })}
                      aria-label="ระดับเสียงพากย์"
                    />
                  </div>
                  <div className="field">
                    <div className="row row--between" style={{ gap: 10 }}>
                      <span className="field__label">ระดับเสียงประกอบ (SFX)</span>
                      <span className="small strong">{Math.round(form.sfxVolume * 100)}%</span>
                    </div>
                    <input
                      className="slider"
                      type="range"
                      min={0}
                      max={100}
                      value={Math.round(form.sfxVolume * 100)}
                      onChange={(e) => patch({ sfxVolume: Number(e.target.value) / 100 })}
                      aria-label="ระดับเสียงประกอบ"
                    />
                  </div>
                </div>
              )}
            </PastelCard>
            {tipCard}
          </>
        )}

        {tab === "ai" && (
          <>
            {providerCards}
            <PastelCard
              title="สถานะการเชื่อมต่อของช่องทางอื่น"
              subtitle="ตรวจสอบว่าช่องทางที่ต้องใช้งานร่วมกับ AI เชื่อมต่ออยู่แล้วหรือไม่"
              icon={CheckCircle2}
              iconTone="mint"
            >
              <div className="row row--wrap" style={{ gap: 10 }}>
                <StatusBadge tone={providers?.facebookPage?.connected ? "success" : "muted"} dot>
                  Facebook Page: {providers?.facebookPage?.connected ? "เชื่อมต่อแล้ว" : "ยังไม่ได้เชื่อมต่อ"}
                </StatusBadge>
                <StatusBadge tone={geminiConnected ? "success" : "muted"} dot>
                  Google Gemini: {geminiConnected ? "เชื่อมต่อแล้ว" : "ยังไม่ได้ตั้งค่า"}
                </StatusBadge>
                <StatusBadge tone={azureConnected ? "success" : "muted"} dot>
                  Azure Speech: {azureConnected ? "เชื่อมต่อแล้ว" : "ยังไม่ได้ตั้งค่า"}
                </StatusBadge>
              </div>
            </PastelCard>
          </>
        )}

        {tab === "voice" && (
          <>
            {voicesCard}
            {tipCard}
          </>
        )}

        {tab === "etc" && form && (
          <>
            <PastelCard title="ความเร็วเฟรมของคลิป" subtitle="จำนวนเฟรมต่อวินาทีที่ใช้เรนเดอร์คลิป" icon={SettingsIcon} iconTone="blue">
              <div className="field">
                <span className="field__label">เฟรมต่อวินาที (FPS)</span>
                <select
                  className="select"
                  value={form.fps}
                  onChange={(e) => patch({ fps: Number(e.target.value) })}
                  style={{ maxWidth: 180 }}
                >
                  {[24, 25, 30, 60].map((f) => (
                    <option key={f} value={f}>
                      {f} fps
                    </option>
                  ))}
                </select>
              </div>
            </PastelCard>

            <PastelCard title="เครื่องมือสร้างเสียง" subtitle="ลำดับการทดลองใช้งานเครื่องมือสร้างเสียงแต่ละตัว" icon={Volume2} iconTone="mint">
              <div className="col" style={{ gap: 10 }}>
                {TTS_ENGINES.map((e) => (
                  <label key={e.value} className="checkbox">
                    <input
                      type="checkbox"
                      checked={form.ttsEngines.includes(e.value)}
                      onChange={(ev) =>
                        patch({
                          ttsEngines: ev.target.checked
                            ? [...form.ttsEngines, e.value]
                            : form.ttsEngines.filter((x) => x !== e.value),
                        })
                      }
                    />
                    <span>
                      <span className="small strong">{e.label}</span>
                    </span>
                  </label>
                ))}
                <div className="row" style={{ gap: 9, alignItems: "flex-start" }}>
                  <AlertTriangle size={15} style={{ color: "var(--c-warn)", flex: "none", marginTop: 2 }} />
                  <span className="xsmall muted" style={{ lineHeight: 1.6 }}>
                    ถ้าไม่มีเสียงประกอบในเครื่อง (espeak / SAPI) ระบบจะข้ามไปใช้ตัวถัดไปในลำดับ
                  </span>
                </div>
              </div>
            </PastelCard>

            <PastelCard title="การอ่านเสียงอัตโนมัติ" subtitle="ให้ระบบอ่านชื่อคลิปและข้อความปิดท้ายให้ฟังเองหรือไม่" icon={Volume2} iconTone="orange">
              <div className="col" style={{ gap: 12 }}>
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={form.readTitle}
                    onChange={(e) => patch({ readTitle: e.target.checked })}
                  />
                  <span className="small">อ่านชื่อคลิป (Title) ในคลิป</span>
                </label>
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={form.readOutro}
                    onChange={(e) => patch({ readOutro: e.target.checked })}
                  />
                  <span className="small">อ่านข้อความปิดท้าย (Outro) ในคลิป</span>
                </label>
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={form.allowTestVoice}
                    onChange={(e) => patch({ allowTestVoice: e.target.checked })}
                  />
                  <span className="small">อนุญาตให้ใช้เสียงทดสอบ (espeak / เสียงเงียบ)</span>
                </label>
              </div>
            </PastelCard>
          </>
        )}

        {/* ------------------------------------------------------- footer bar */}
        <div className="row row--wrap row--between" style={{ gap: 12 }}>
          <span className="xsmall muted">
            การตั้งค่าจะถูกบันทึกลงไฟล์ config.json ของสตูดิโอในเครื่องนี้
          </span>
          <div className="row row--wrap" style={{ gap: 10 }}>
            <button
              type="button"
              className="btn btn--outline btn--lg"
              onClick={() => setResetOpen(true)}
              disabled={saving}
            >
              <RotateCcw size={16} /> คืนค่าเริ่มต้น
            </button>
            <button
              type="button"
              className="btn btn--primary btn--lg"
              onClick={() => save()}
              disabled={saving || !form}
            >
              {saving ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
              บันทึกการตั้งค่า
            </button>
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={resetOpen}
        title="คืนค่าเริ่มต้น"
        message={
          <span>
            การตั้งค่าทั้งหมดในหน้านี้จะถูกคืนค่าเป็นค่าเริ่มต้นของสตูดิโอ
            (ชื่อช่องว่าง รูปแบบวิดีโอแนวตั้ง+แนวนอน เสียงตัวละครค่าเริ่มต้น และปิดการทดสอบเสียง)
            แล้วบันทึกทับการตั้งค่าปัจจุบัน — คีย์ Gemini / Speech จะไม่ถูกลบ
          </span>
        }
        confirmLabel="คืนค่าเริ่มต้น"
        cancelLabel="ยกเลิก"
        danger
        onConfirm={resetDefaults}
        onCancel={() => setResetOpen(false)}
      />
    </>
  );
}
