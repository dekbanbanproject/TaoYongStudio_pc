import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  Clock,
  Copy,
  ExternalLink,
  Facebook,
  FolderOpen,
  Image as ImageIcon,
  MessageSquare,
  Play,
  RefreshCw,
  Search,
  ShoppingBag,
  Sparkles,
  Star,
  Trash2,
  Upload,
  Video as VideoIcon,
  Wand2,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { openUrl } from "@tauri-apps/plugin-opener";
import { open as openFileDialog } from "@tauri-apps/plugin-dialog";
import { apiGet, apiPost, assetUrl, type ClipEntry } from "../services/api";
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
import { DataTable, Pagination, SearchInput } from "../components/common/DataTable";
import { Modal, useToast } from "../components/common/feedback";
import { useApiData } from "../hooks/useApiData";

/* ------------------------------------------------------------------ types */

interface ShopeeProductsResp {
  ok: boolean;
  products: any[];
  total: number;
  page: number;
  perPage: number;
}
interface CategoriesResp {
  ok: boolean;
  categories: string[];
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

const PER_PAGE = 5;
const FLOW_URL = "https://flow.google.com/";
const FACEBOOK_URL = "https://www.facebook.com/";

/** Style keys the engine really understands (see engine/taoyong/facebook_profile_flow.py). */
const FB_STYLES: { key: string; label: string; hint: string }[] = [
  { key: "presenter", label: "พรีเซนเตอร์ถือสินค้า", hint: "โฮลต์สินค้าใกล้กล้อง" },
  { key: "problem", label: "ปัญหา → ทางออก", hint: "เล่าปัญหาแล้วชวนแก้" },
  { key: "unboxing", label: "แกะกล่องสินค้า", hint: "เปิดกล่องพร้อมเสียง ASMR" },
  { key: "asmr", label: "เสียงและภาพใกล้", hint: "ภาพมาโครสัมผัสสินค้า" },
  { key: "cartoon", label: "การ์ตูน 3D สดใส", hint: "ตัวการ์ตูนน่ารักโชว์สินค้า" },
];

/** Durations accepted by the prompt generator (8/10/12/15/20/25/30). */
const FB_DURATIONS = [8, 15, 30];

const SORT_OPTIONS = [
  { key: "default", label: "ค่าเริ่มต้น (คะแนนสูงสุด)" },
  { key: "sold", label: "ยอดขายมากที่สุด" },
  { key: "rating", label: "คะแนนสูงสุด" },
  { key: "price_asc", label: "ราคาต่ำสุด" },
  { key: "price_desc", label: "ราคาสูงสุด" },
];

/* ---------------------------------------------------------------- helpers */

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

function productKey(p: any): string {
  return String(p?.id ?? p?.product_id ?? p?.name ?? "");
}

function productPrice(p: any): number {
  const v = p?.sale_price ?? p?.price ?? 0;
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function productOriginal(p: any): number {
  const n = Number(p?.original_price ?? 0);
  return Number.isFinite(n) ? n : 0;
}

function discountPct(p: any): number {
  const sale = productPrice(p);
  const orig = productOriginal(p);
  if (!sale || !orig || orig <= sale) return 0;
  return Math.round((1 - sale / orig) * 100);
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

function clipPoster(clip?: ClipEntry): string | undefined {
  if (!clip) return undefined;
  const files = clip.files || {};
  const raw = files["thumb_vertical"] || files["thumb_horizontal"] || clip.thumb || "";
  if (!raw) return undefined;
  const url = assetUrl(raw);
  return url || undefined;
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

/* -------------------------------------------------------------- fragments */

function CardTitle({
  icon: Icon,
  title,
  sub,
  action,
}: {
  icon: LucideIcon;
  title: string;
  sub?: string;
  action?: ReactNode;
}) {
  return (
    <div className="row row--between" style={{ alignItems: "flex-start", gap: 12, marginBottom: 14 }}>
      <div className="row" style={{ gap: 10, minWidth: 0 }}>
        <span className="card__title-icon">
          <Icon size={17} />
        </span>
        <div style={{ minWidth: 0 }}>
          <div className="strong">{title}</div>
          {sub && <div className="xsmall muted">{sub}</div>}
        </div>
      </div>
      {action}
    </div>
  );
}

/* ------------------------------------------------------------------- page */

export default function FacebookProfile() {
  const toast = useToast();

  const [searchInput, setSearchInput] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState("default");
  const [page, setPage] = useState(1);
  const [checked, setChecked] = useState<Set<string>>(new Set());

  const productsQ = useApiData<ShopeeProductsResp>(
    () =>
      apiGet<ShopeeProductsResp>("/api/shopee/products", {
        search: appliedSearch,
        category,
        sort,
        page,
        perPage: PER_PAGE,
      }),
    [appliedSearch, category, sort, page],
  );
  const categoriesQ = useApiData<CategoriesResp>(() => apiGet<CategoriesResp>("/api/shopee/categories"));
  const clipsQ = useApiData<{ ok: boolean; clips: ClipEntry[] }>(() =>
    apiGet("/api/platform/clips"),
  );
  const postingQ = useApiData<PostingResp>(() => apiGet<PostingResp>("/api/posting/status"));

  const products = productsQ.data?.products ?? [];
  const categories = categoriesQ.data?.categories ?? [];
  const clips = clipsQ.data?.clips ?? [];
  const posting = normalizePosting(postingQ.data);
  const fb = posting.platforms.facebook_profile;

  const [duration, setDuration] = useState(16);
  const [style, setStyle] = useState("cartoon");
  const [prompt, setPrompt] = useState("");
  const [caption, setCaption] = useState("");
  const [clipOpen, setClipOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const selected = useMemo(() => {
    const marked = products.filter((p) => checked.has(productKey(p)));
    return marked[0] || products[0] || null;
  }, [products, checked]);

  useEffect(() => {
    setPage(1);
  }, [appliedSearch, category, sort]);

  /* ------------------------------------------------------------- actions */

  const runSearch = () => setAppliedSearch(searchInput.trim());

  const toggleCheck = (key: string, isChecked: boolean) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (isChecked) next.add(key);
      else next.delete(key);
      return next;
    });
  };

  const buildPromptFromApi = async () => {
    if (!selected) {
      toast.warn("ยังไม่ได้เลือกสินค้า", "เลือกสินค้าจากตารางก่อน");
      return;
    }
    setBusy(true);
    try {
      const res = await apiPost<{ ok: boolean; prompt: string }>("/api/facebook/prompt", {
        product: selected,
        duration,
        style,
      });
      setPrompt(res.prompt || "");
      toast.success("สร้างพรอมต์แล้ว", "ตรวจสอบและแก้ไขก่อนนำไปใช้ได้");
    } catch (e) {
      toast.error("สร้างพรอมต์ไม่สำเร็จ", errText(e));
    } finally {
      setBusy(false);
    }
  };

  const analyzePrompt = async () => {
    if (!prompt.trim()) {
      toast.warn("ยังไม่มีพรอมต์", "กดปุ่มสร้างพรอมต์ก่อน");
      return;
    }
    setBusy(true);
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
    } finally {
      setBusy(false);
    }
  };

  const copyPrompt = async () => {
    const ok = await copyText(prompt);
    if (ok) toast.success("คัดลอกพรอมต์แล้ว", "วางใน Google Flow เพื่อสร้างวิดีโอ");
    else toast.error("คัดลอกไม่สำเร็จ", "ลองเลือกข้อความแล้วกดคัดลอกด้วยตัวเอง");
  };

  const sendToFlow = async () => {
    await copyText(prompt);
    await openUrl(FLOW_URL);
    toast.info("เปิด Google Flow แล้ว", "พรอมต์ถูกคัดลอกไว้ในคลิปบอร์ดแล้ว");
  };

  const buildCaption = async () => {
    if (!selected) {
      toast.warn("ยังไม่ได้เลือกสินค้า", "เลือกสินค้าจากตารางก่อน");
      return;
    }
    setBusy(true);
    try {
      const res = await apiPost<{ ok: boolean; caption: string }>("/api/facebook/caption", {
        product: selected,
        style: "reels",
      });
      setCaption(res.caption || "");
      toast.success("สร้างแคปชันแล้ว", "ตรวจสอบข้อความก่อนโพสต์");
    } catch (e) {
      toast.error("สร้างแคปชันไม่สำเร็จ", errText(e));
    } finally {
      setBusy(false);
    }
  };

  const copyCaption = async () => {
    const ok = await copyText(caption);
    if (ok) toast.success("คัดลอกแคปชันแล้ว", "วางในโพสต์ของ Facebook Profile ได้เลย");
    else toast.error("คัดลอกไม่สำเร็จ", "ลองเลือกข้อความแล้วกดคัดลอกด้วยตัวเอง");
  };

  const importVideo = async (path: string, sourceLabel: string) => {
    setBusy(true);
    try {
      const res = await apiPost<{ ok: boolean; folder: string; meta: any }>("/api/platform/import-video", {
        platform: "facebook_profile",
        path,
        title: selected?.name || sourceLabel,
        description: caption,
        tags: ["ช้อปปี้", "Shopee", "TaoYongStudio"],
        format: "vertical",
      });
      toast.success("นำเข้าวิดีโอแล้ว", res?.meta?.title || res?.folder || "");
      clipsQ.reload();
    } catch (e) {
      toast.error("นำเข้าวิดีโอไม่สำเร็จ", errText(e));
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
      if (typeof picked === "string" && picked) await importVideo(picked, "คลิปใหม่");
    } catch (e) {
      toast.error("เลือกไฟล์ไม่สำเร็จ", errText(e));
    }
  };

  const manualPost = async () => {
    if (!caption.trim()) {
      toast.warn("ยังไม่มีแคปชัน", "กดใช้แคปชันอัตโนมัติหรือเขียนข้อความก่อน");
      return;
    }
    await copyText(caption);
    await openUrl(FACEBOOK_URL);
    toast.info(
      "คัดลอกแคปชันแล้ว เปิด Facebook Profile",
      "Facebook ส่วนตัวไม่มีช่องทาง API — ต้องอัปโหลดวิดีโอและกดโพสต์เอง",
    );
  };

  /* --------------------------------------------------------------- render */

  const tableRows = products;

  return (
    <div className="stack">
      <PageHeader
        title="Facebook Profile"
        subtitle="ค้นหาสินค้าจาก Shopee สร้างวิดีโอ + แคปชัน + โพสต์อัตโนมัติสำหรับโปรไฟล์ Facebook ของคุณ"
        icon={Facebook}
        tone="blue"
      />

      <div
        className="grid"
        style={{ gridTemplateColumns: "minmax(0, 1.12fr) minmax(0, 0.88fr)", alignItems: "start", gap: 16 }}
      >
        {/* ------------------------------------------------ left: shopee search */}
        <div className="col" style={{ gap: 16 }}>
          <PastelCard>
            <CardTitle
              icon={ShoppingBag}
              title="ค้นหาสินค้าจาก Shopee"
              sub="เลือกสินค้าที่จะโปรโมตในโปรไฟล์ Facebook ของคุณ"
              action={
                <button className="btn btn--soft btn--sm" onClick={() => setClipOpen(true)}>
                  <FolderOpen size={14} /> คลังคลิป
                </button>
              }
            />

            <div className="col" style={{ gap: 12 }}>
              <div className="row" style={{ gap: 10 }}>
                <SearchInput
                  value={searchInput}
                  onChange={setSearchInput}
                  placeholder="ค้นหาสินค้า เช่น ของเล่น กระตุ้นน้ำ หมอน..."
                  style={{ flex: 1 }}
                />
                <button className="btn btn--primary" onClick={runSearch}>
                  <Search size={15} /> ค้นหา
                </button>
              </div>

              <div className="row row--wrap" style={{ gap: 10 }}>
                <div className="field" style={{ minWidth: 200 }}>
                  <label className="field__label" htmlFor="fb-category">
                    หมวดหมู่
                  </label>
                  <select
                    id="fb-category"
                    className="select"
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                  >
                    {categories.length === 0 && <option value="">ทุกหมวดหมู่</option>}
                    {categories.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field" style={{ minWidth: 200 }}>
                  <label className="field__label" htmlFor="fb-sort">
                    เรียงตาม
                  </label>
                  <select
                    id="fb-sort"
                    className="select"
                    value={sort}
                    onChange={(e) => setSort(e.target.value)}
                  >
                    {SORT_OPTIONS.map((s) => (
                      <option key={s.key} value={s.key}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {productsQ.loading ? (
                <LoadingState label="กำลังโหลดรายการสินค้า..." />
              ) : productsQ.error ? (
                <ErrorState message={productsQ.error} onRetry={() => productsQ.reload()} />
              ) : (
                <div className="card card--flush">
                  <DataTable
                    rows={tableRows}
                    rowKey={(r) => productKey(r)}
                    selected={checked}
                    onSelect={(key, isChecked) => toggleCheck(key, isChecked)}
                    onRowClick={(r) => toggleCheck(productKey(r), !checked.has(productKey(r)))}
                    empty={
                      <EmptyState
                        title="ไม่พบสินค้า"
                        text="ลองเปลี่ยนคำค้นหาหรือหมวดหมู่"
                        icon={ShoppingBag}
                      />
                    }
                    columns={[
                      { key: "no", header: "#", width: 48, align: "center", render: (_r, i) => i + 1 },
                      {
                        key: "region",
                        header: "ภูมิภาค",
                        width: 90,
                        render: (r) => r?.region || r?.ship_from || "-",
                      },
                      {
                        key: "name",
                        header: "ชื่อสินค้า",
                        render: (r) => (
                          <div className="row" style={{ gap: 9 }}>
                            {r?.image_url ? (
                              <span className="thumb" style={{ width: 38, height: 38 }}>
                                <img src={r.image_url} alt={r?.name || "สินค้า"} />
                              </span>
                            ) : (
                              <span className="thumb" style={{ width: 38, height: 38 }}>
                                <ImageIcon size={15} color="#a48cf0" />
                              </span>
                            )}
                            <span className="truncate" style={{ maxWidth: 240 }}>
                              {r?.name || "-"}
                            </span>
                          </div>
                        ),
                      },
                      {
                        key: "price",
                        header: "ราคา",
                        width: 110,
                        align: "right",
                        render: (r) => (
                          <span className="strong">฿{productPrice(r).toLocaleString("th-TH")}</span>
                        ),
                      },
                      {
                        key: "sold",
                        header: "ยอดขาย",
                        width: 100,
                        align: "right",
                        render: (r) =>
                          r?.sold_count ? Number(r.sold_count).toLocaleString("th-TH") : "-",
                      },
                      {
                        key: "rating",
                        header: "คะแนน",
                        width: 90,
                        align: "right",
                        render: (r) =>
                          r?.rating ? (
                            <span className="row" style={{ gap: 4, justifyContent: "flex-end" }}>
                              <Star size={13} color="#e8a33d" fill="#e8a33d" />
                              {Number(r.rating).toFixed(1)}
                            </span>
                          ) : (
                            "-"
                          ),
                      },
                    ]}
                  />
                  <Pagination
                    page={productsQ.data?.page ?? page}
                    perPage={productsQ.data?.perPage ?? PER_PAGE}
                    total={productsQ.data?.total ?? 0}
                    onPage={setPage}
                  />
                </div>
              )}

              {/* selected product preview */}
              {selected ? (
                <div className="card card--soft">
                  <div className="row" style={{ alignItems: "flex-start", gap: 14 }}>
                    {selected.image_url ? (
                      <span className="thumb" style={{ width: 118, height: 118 }}>
                        <img src={selected.image_url} alt={selected.name || "สินค้า"} />
                      </span>
                    ) : (
                      <span className="thumb" style={{ width: 118, height: 118 }}>
                        <ShoppingBag size={22} color="#a48cf0" />
                      </span>
                    )}
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div className="strong clamp-2">{selected.name}</div>
                      <div className="row row--wrap" style={{ gap: 8, marginTop: 6 }}>
                        <span className="strong" style={{ color: "var(--c-pink-strong)", fontSize: "var(--fs-lg)" }}>
                          ฿{productPrice(selected).toLocaleString("th-TH")}
                        </span>
                        {discountPct(selected) > 0 ? (
                          <>
                            <span className="small muted" style={{ textDecoration: "line-through" }}>
                              ฿{productOriginal(selected).toLocaleString("th-TH")}
                            </span>
                            <StatusBadge tone="danger">ลด {discountPct(selected)}%</StatusBadge>
                          </>
                        ) : null}
                      </div>
                      <div className="row row--wrap" style={{ gap: 8, marginTop: 6 }}>
                        {selected.seller_name ? <Chip tone="blue">ร้าน: {selected.seller_name}</Chip> : null}
                        {selected.rating ? (
                          <Chip tone="orange">
                            คะแนน {Number(selected.rating).toFixed(1)}/5
                          </Chip>
                        ) : null}
                        {selected.sold_count ? (
                          <Chip tone="mint">ขายแล้ว {Number(selected.sold_count).toLocaleString("th-TH")} ชิ้น</Chip>
                        ) : null}
                      </div>
                      <div className="row row--wrap" style={{ gap: 8, marginTop: 10 }}>
                        {selected.product_url ? (
                          <button
                            className="btn btn--orange btn--sm"
                            onClick={() => {
                              void copyText(selected.product_url);
                              void openUrl(selected.product_url);
                            }}
                          >
                            <ShoppingBag size={14} /> เปิดหน้า Shopee
                          </button>
                        ) : null}
                        {selected.product_url ? (
                          <button
                            className="btn btn--outline btn--sm"
                            onClick={async () => {
                              const ok = await copyText(selected.product_url);
                              if (ok) toast.success("คัดลอกลิงก์สินค้าแล้ว", "");
                              else toast.error("คัดลอกไม่สำเร็จ", "ลองใหม่อีกครั้ง");
                            }}
                          >
                            <Copy size={14} /> คัดลอกลิงก์
                          </button>
                        ) : null}
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </PastelCard>
        </div>

        {/* ------------------------------------------------- right: the 4 cards */}
        <div className="col" style={{ gap: 16 }}>
          {/* 1. google flow prompt */}
          <PastelCard>
            <CardTitle
              icon={Play}
              title="สร้างวิดีโอตามข้อมูล Google Flow"
              sub="สร้างวิดีโอจากสินค้าที่เลือก ให้ไปสร้างต่อที่ Google Flow"
              action={
                <button className="btn btn--soft btn--sm" onClick={() => void buildPromptFromApi()} disabled={busy}>
                  <RefreshCw size={14} /> สร้างพรอมต์
                </button>
              }
            />
            <div className="grid" style={{ gridTemplateColumns: "minmax(0, 0.9fr) minmax(0, 1.1fr)", gap: 14 }}>
              <div className="col" style={{ gap: 8 }}>
                <span className="field__label">ความยาววิดีโอ</span>
                <div className="col" style={{ gap: 6 }}>
                  {FB_DURATIONS.map((d) => (
                    <label
                      key={d}
                      className="checkbox"
                      style={{
                        justifyContent: "space-between",
                        border: `1px solid ${duration === d ? "var(--c-primary)" : "var(--c-line)"}`,
                        background: duration === d ? "var(--g-primary-soft)" : "#fff",
                        borderRadius: "var(--r-md)",
                        padding: "8px 12px",
                      }}
                    >
                      <span className="row" style={{ gap: 8 }}>
                        <input
                          type="radio"
                          name="fb-duration"
                          checked={duration === d}
                          onChange={() => setDuration(d)}
                        />
                        <span>{d} วินาที</span>
                      </span>
                    </label>
                  ))}
                </div>
                <span className="xsmall muted">ระบบรองรับ 8, 10, 12, 15, 20, 25 และ 30 วินาที</span>
              </div>
              <div className="col" style={{ gap: 8 }}>
                <span className="field__label">สไตล์วิดีโอ</span>
                <div className="grid" style={{ gridTemplateColumns: "repeat(2, minmax(0,1fr))", gap: 8 }}>
                  {FB_STYLES.map((s) => (
                    <button
                      key={s.key}
                      type="button"
                      onClick={() => setStyle(s.key)}
                      className="card"
                      style={{
                        padding: 9,
                        textAlign: "left",
                        cursor: "pointer",
                        boxShadow: "none",
                        border: `1.5px solid ${style === s.key ? "var(--c-primary)" : "var(--c-line)"}`,
                        background: style === s.key ? "var(--g-primary-soft)" : "#fff",
                      }}
                    >
                      <div className="small strong truncate">{s.label}</div>
                      <div className="xsmall muted truncate">{s.hint}</div>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="field" style={{ marginTop: 14 }}>
              <label className="field__label" htmlFor="fb-prompt">
                พรอมต์สำหรับ Google Flow (TH)
              </label>
              <textarea
                id="fb-prompt"
                className="textarea"
                value={prompt}
                maxLength={2000}
                onChange={(e) => setPrompt(e.target.value)}
                style={{ minHeight: 150 }}
              />
              <span className="field__hint">{prompt.length}/2000</span>
            </div>

            <div className="row row--wrap" style={{ gap: 8, marginTop: 10 }}>
              <button className="btn btn--outline btn--sm" onClick={() => void analyzePrompt()} disabled={busy}>
                <Wand2 size={14} /> วิเคราะห์พรอมต์
              </button>
              <button className="btn btn--outline btn--sm" onClick={() => void copyPrompt()}>
                <Copy size={14} /> คัดลอกพรอมต์
              </button>
              <button className="btn btn--primary btn--sm" onClick={() => void sendToFlow()}>
                <ExternalLink size={14} /> ส่งไปที่ Google Flow
              </button>
            </div>
          </PastelCard>

          {/* 2. caption */}
          <PastelCard>
            <CardTitle
              icon={MessageSquare}
              title="แคปชัน Facebook Profile (อยู่ติดความ)"
              sub="สร้างแคปชันอัตโนมัติจากสินค้าที่เลือก แล้วแก้ไขได้ตามต้องการ"
              action={
                <button className="btn btn--soft btn--sm" onClick={() => void buildCaption()} disabled={busy}>
                  <Sparkles size={14} /> ใช้แคปชันอัตโนมัติ
                </button>
              }
            />
            <textarea
              className="textarea"
              aria-label="แคปชันสำหรับโพสต์ในโปรไฟล์ Facebook"
              value={caption}
              maxLength={2000}
              onChange={(e) => setCaption(e.target.value)}
              placeholder="ข้อความแคปชันสำหรับโพสต์ในโปรไฟล์ Facebook"
              style={{ minHeight: 170 }}
            />
            <div className="row row--between" style={{ marginTop: 8 }}>
              <span className="xsmall muted">{caption.length}/2000</span>
              <div className="row" style={{ gap: 8 }}>
                <button className="btn btn--outline btn--sm" onClick={() => void copyCaption()}>
                  <Copy size={14} /> คัดลอกแคปชัน
                </button>
                <button className="btn btn--danger btn--sm" onClick={() => setCaption("")}>
                  <Trash2 size={14} /> ล้างข้อความ
                </button>
              </div>
            </div>
          </PastelCard>

          {/* 3. bring video + post */}
          <PastelCard>
            <CardTitle
              icon={Upload}
              title="นำวิดีโอเดิมมา & โพสต์ไปที่ Facebook Profile"
              sub="นำวิดีโอเดิมมาใช้ หรือสร้างใหม่จากพรอมต์ที่คัดลอกไว้"
            />
            <div className="col" style={{ gap: 10 }}>
              <button className="btn btn--outline" onClick={() => void pickFile()} disabled={busy}>
                <Upload size={15} /> อัปโหลดวิดีโอจากเครื่อง
              </button>
              <button
                className="btn btn--outline"
                onClick={() => {
                  void copyText(prompt);
                  void openUrl(FLOW_URL);
                  toast.info("เปิด Google Flow แล้ว", "สร้างวิดีโอเสร็จแล้วนำมาวางในโฟลเดอร์คลิปได้เลย");
                }}
              >
                <ExternalLink size={15} /> นำเข้าจาก Google Flow
              </button>
              <button className="btn btn--outline" onClick={() => setClipOpen(true)}>
                <FolderOpen size={15} /> เลือกโฟลเดอร์ที่มีคลิปอยู่
              </button>
              <button className="btn btn--primary" onClick={() => void manualPost()}>
                <Facebook size={15} /> เปิด Facebook เพื่อโพสต์เอง
              </button>
              <span className="xsmall muted">
                <AlertTriangle size={12} style={{ verticalAlign: "-2px" }} /> Facebook ส่วนตัวไม่มีช่องทาง API —
                ระบบจะคัดลอกแคปชันและเปิดหน้า Facebook ให้คุณอัปโหลดและกดโพสต์เอง
              </span>
            </div>
          </PastelCard>

          {/* 4. auto posting */}
          <PastelCard>
            <CardTitle
              icon={Clock}
              title="โพสต์อัตโนมัติ (แนะนำ)"
              sub="ให้พนักงาน AI โพสต์ตามเวลาที่กำหนด"
              action={
                <StatusBadge tone={posting.mode === "off" ? "muted" : "success"}>
                  {posting.mode === "off" ? "โหมดปิดอยู่" : posting.mode === "approved" ? "เฉพาะคลิปที่อนุมัติ" : "อัตโนมัติทั้งหมด"}
                </StatusBadge>
              }
            />
            <div className="col" style={{ gap: 12 }}>
              <div className="row" style={{ gap: 10 }}>
                <span className="card__title-icon" style={{ background: "var(--g-blue)", color: "#fff" }}>
                  <Facebook size={16} />
                </span>
                <div style={{ minWidth: 0 }}>
                  <div className="small strong">TaoYong (Facebook Profile)</div>
                  <div className="xsmall muted">
                    {fb?.connected
                      ? `เชื่อมต่อแล้ว${fb.accountName ? " — " + fb.accountName : ""}`
                      : "ยังไม่ได้เชื่อมต่อบัญชี"}
                  </div>
                </div>
              </div>

              <div className="col" style={{ gap: 6 }}>
                <span className="field__label">เวลาที่ตั้งไว้ให้โพสต์</span>
                <div className="row row--wrap" style={{ gap: 7 }}>
                  {posting.postTimes.length === 0 ? (
                    <span className="small muted">ยังไม่ได้ตั้งเวลาโพสต์</span>
                  ) : (
                    posting.postTimes.map((t) => (
                      <Chip key={t} tone="primary">
                        {t}
                      </Chip>
                    ))
                  )}
                </div>
                {posting.maxPerDay ? (
                  <span className="xsmall muted">โพสต์ได้ไม่เกิน {posting.maxPerDay} คลิปต่อวัน</span>
                ) : null}
              </div>

              <div className="row row--wrap" style={{ gap: 8 }}>
                <Link className="btn btn--primary btn--sm" to="/scheduler">
                  <Clock size={14} /> เปิดการตั้งค่าหน้าต่าง
                </Link>
                <Link className="btn btn--outline btn--sm" to="/posting-settings">
                  <ExternalLink size={14} /> ตั้งค่าโพสต์
                </Link>
              </div>
            </div>
          </PastelCard>
        </div>
      </div>

      {/* clip library picker */}
      <Modal open={clipOpen} title="โฟลเดอร์ที่มีคลิปอยู่" icon={VideoIcon} onClose={() => setClipOpen(false)} width={640}>
        {clipsQ.loading ? (
          <LoadingState />
        ) : clipsQ.error ? (
          <ErrorState message={clipsQ.error} onRetry={() => clipsQ.reload()} />
        ) : clips.length === 0 ? (
          <EmptyState title="ยังไม่มีคลิปในระบบ" text="สร้างวิดีโอก่อนจึงจะนำเข้าได้" icon={VideoIcon} />
        ) : (
          <div className="col" style={{ gap: 8 }}>
            {clips.map((c) => (
              <div key={c.folder || c.id} className="card" style={{ padding: 10, boxShadow: "none" }}>
                <div className="row" style={{ gap: 12 }}>
                  <span className="thumb" style={{ width: 92, height: 62 }}>
                    {clipPoster(c) ? (
                      <img src={clipPoster(c)} alt={c.title || "คลิป"} />
                    ) : (
                      <Play size={18} color="#a48cf0" />
                    )}
                  </span>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div className="small strong truncate">{c.title || c.id}</div>
                    <div className="xsmall muted">
                      {formatDuration(c.durationSeconds)} • {c.resolution || "-"} • {c.folderName}
                    </div>
                  </div>
                  <button
                    className="btn btn--soft btn--sm"
                    onClick={() => {
                      const path = clipVideo(c);
                      if (!path) {
                        toast.error("คลิปนี้ไม่มีไฟล์วิดีโอ", "เลือกคลิปที่เรนเดอร์เสร็จแล้ว");
                        return;
                      }
                      void importVideo(path, c.title || c.id);
                      setClipOpen(false);
                    }}
                  >
                    นำเข้า
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Modal>
    </div>
  );
}
