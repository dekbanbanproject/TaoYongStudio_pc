import { invoke, convertFileSrc } from "@tauri-apps/api/core";

/**
 * The app normally runs inside Tauri, where every call is proxied through the
 * Rust bridge to the Python engine. When the UI is opened in a plain browser
 * (design review / development) it talks to the engine service directly.
 */
const IN_TAURI = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
const DEV_ENGINE_URL =
  (import.meta.env?.VITE_ENGINE_URL as string | undefined) || "http://127.0.0.1:8787";
const DEV_ENGINE_TOKEN =
  (import.meta.env?.VITE_ENGINE_TOKEN as string | undefined) || "dev-token";

async function browserRequest(
  method: string,
  path: string,
  body?: unknown,
): Promise<any> {
  const res = await fetch(`${DEV_ENGINE_URL}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-TAOYONG-TOKEN": DEV_ENGINE_TOKEN,
    },
    body: body === undefined || body === null ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  let json: any = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    throw new Error(`คำตอบจาก Engine ไม่ถูกต้อง (${res.status})`);
  }
  if (!res.ok) throw new Error(json?.error || `คำขอไม่สำเร็จ (${res.status})`);
  return json;
}

/** Every call goes through the Tauri Rust bridge -> local Python engine. */
export async function apiRequest<T = any>(
  method: "GET" | "POST" | "PUT" | "DELETE",
  path: string,
  body?: unknown,
): Promise<T> {
  if (!IN_TAURI) {
    return (await browserRequest(method, path, body)) as T;
  }
  const res = await invoke<any>("api_request", { method, path, body: body ?? null });
  if (res && typeof res === "object" && res.ok === false) {
    throw new Error(res.error || "คำขอไม่สำเร็จ");
  }
  return res as T;
}

export const apiGet = <T = any,>(path: string, query?: Record<string, unknown>) =>
  apiRequest<T>("GET", withQuery(path, query));

export const apiPost = <T = any,>(path: string, body?: unknown) =>
  apiRequest<T>("POST", path, body ?? {});

export const apiDelete = <T = any,>(path: string, body?: unknown) =>
  apiRequest<T>("DELETE", path, body ?? {});

export function withQuery(path: string, query?: Record<string, unknown>) {
  if (!query) return path;
  const q = Object.entries(query)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join("&");
  return q ? `${path}?${q}` : path;
}

/** Turn an absolute local path into a URL the webview can load. */
export function assetUrl(path?: string): string {
  if (!path) return "";
  if (/^(https?:|data:|blob:|asset:)/i.test(path)) return path;
  if (!IN_TAURI) return "";
  try {
    return convertFileSrc(path);
  } catch {
    return "";
  }
}

export async function openPath(path: string) {
  if (!IN_TAURI) return;
  await invoke<void>("open_path", { path });
}

export async function revealPath(path: string) {
  if (!IN_TAURI) return;
  await invoke<void>("reveal_path", { path });
}

export async function engineStatus() {
  if (!IN_TAURI) {
    try {
      await browserRequest("GET", "/api/health");
      return { running: true };
    } catch (e: any) {
      return { running: false, error: e?.message || String(e) };
    }
  }
  return invoke<any>("engine_status");
}

export async function engineRestart() {
  if (!IN_TAURI) return { running: false };
  return invoke<any>("engine_restart");
}

/* ------------------------------------------------------------------ types */

export interface DashboardStats {
  scriptsPending: number;
  scriptsDone: number;
  clipsToday: number;
  clipsTotal: number;
  clipsNeedsReview: number;
}

export interface SystemState {
  ready: boolean;
  label: string;
  detail: string;
}

export interface ActivityItem {
  title: string;
  detail: string;
  at: string;
  kind: string;
}

export interface DashboardPayload {
  ok: boolean;
  stats: DashboardStats;
  nextPost: { at: string; label: string; countdown: string } | null;
  systems: Record<string, SystemState>;
  activity: ActivityItem[];
  channelName: string;
}

export interface ScriptSummary {
  id: string;
  title: string;
  description: string;
  genre: string;
  tags: string[];
  characters: string[];
  sceneCount: number;
  beatCount: number;
  backgrounds: string[];
  group: string;
  path: string;
  fileName: string;
  modifiedAt: string;
  requestId: string;
  review: string;
  formats: string[];
}

export interface ClipEntry {
  folder: string;
  folderName: string;
  day: string;
  id: string;
  title: string;
  description: string;
  tags: string[];
  characters: string[];
  genre: string;
  durationSeconds: number;
  status: string;
  needsReview: string[];
  files: Record<string, string>;
  thumb: string;
  resolution: string;
  fps: number;
  engineType: string;
  voiceEngines: string[];
  createdAt: string;
  renderSeconds: number;
  posts: Record<string, any>;
  platformCaptions: Record<string, any>;
  madeForKids: boolean;
}

export interface Idea {
  id: string;
  genre?: string;
  title?: string;
  hook?: string;
  why?: string;
  length?: string;
  category?: string;
  [k: string]: any;
}

export interface PlannerRequest {
  id: string;
  provider: string;
  when: string;
  scheduledAt: string;
  topic: string;
  details: string;
  status: string;
  ideaCount: number;
  createdAt: string;
  hasResult: boolean;
  requestPath: string;
  resultPath: string;
}

export interface PostingPlatform {
  label: string;
  connected: boolean;
  accountName: string;
  postedToday: number;
  settings: Record<string, any>;
}

export interface PostingStatus {
  mode: string;
  maxPerDay: number;
  postTimes: string[];
  platforms: Record<string, PostingPlatform>;
}

export interface SchedulerPayload {
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
}

export interface SettingsPayload {
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
}

export interface ShopeeProduct {
  id?: string;
  product_id?: string;
  name: string;
  category?: string;
  seller_name?: string;
  price?: number | string;
  sale_price?: number | string;
  original_price?: number | string;
  rating?: number | string;
  sold_count?: number | string;
  image_url?: string;
  product_url?: string;
  [k: string]: any;
}

export interface JobPayload {
  id: string;
  kind: string;
  label: string;
  status: string;
  progress: number;
  log: string[];
  result: any;
  error: string | null;
  startedAt: string;
  finishedAt: string | null;
}

export const PLATFORM_META: Record<
  string,
  { label: string; color: string; bg: string; route: string }
> = {
  tiktok: { label: "TikTok", color: "#fff", bg: "#111111", route: "/create/tiktok" },
  youtube: { label: "YouTube", color: "#fff", bg: "#FF0000", route: "/create/youtube" },
  shopee: { label: "Shopee", color: "#fff", bg: "#EE4D2D", route: "/create/shopee" },
  facebook_profile: { label: "Facebook Profile", color: "#fff", bg: "#1877F2", route: "/facebook-profile" },
  facebook_page: { label: "Facebook Page", color: "#fff", bg: "#1877F2", route: "/create/facebook_page" },
};

export const CHAR_LABEL: Record<string, string> = {
  narrator: "ผู้เล่าเรื่อง",
  bunny: "กระต่าย (ปุยฝ้าย)",
  bear: "หมี (โกโก้)",
  chick: "ลูกเจี๊ยบ",
  cat: "แมว (มิวมิว)",
};

export const STATUS_LABEL: Record<string, string> = {
  ready_for_approval: "พร้อมตรวจสอบ",
  approved: "อนุมัติแล้ว",
  posted: "โพสต์แล้ว",
  posted_manual: "โพสต์เองแล้ว",
  rejected: "ไม่ผ่าน",
  draft_sent: "ส่งเป็นแบบร่าง",
  cancelled: "ยกเลิกแล้ว",
  pending: "รอดำเนินการ",
  done: "สำเร็จแล้ว",
  failed: "ล้มเหลว",
};
