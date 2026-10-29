import type { ReactNode } from "react";
import { LucideIcon, AlertTriangle, Inbox, Loader2, RefreshCw } from "lucide-react";

/* ------------------------------------------------------------------ card */
export function PastelCard({
  title,
  subtitle,
  icon: Icon,
  iconTone = "primary",
  actions,
  children,
  className = "",
  bodyClassName = "",
  flush = false,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  icon?: LucideIcon;
  iconTone?: "primary" | "pink" | "mint" | "blue" | "orange";
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
  bodyClassName?: string;
  flush?: boolean;
}) {
  return (
    <section className={`card ${flush ? "card--flush" : ""} ${className}`}>
      {(title || actions) && (
        <header className="card__head">
          <div style={{ minWidth: 0 }}>
            <h2 className="card__title">
              {Icon && (
                <span className={`card__title-icon card__title-icon--${iconTone}`}>
                  <Icon size={17} />
                </span>
              )}
              <span className="truncate">{title}</span>
            </h2>
            {subtitle && <p className="card__sub">{subtitle}</p>}
          </div>
          {actions && <div className="row" style={{ flexShrink: 0 }}>{actions}</div>}
        </header>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}

/* ------------------------------------------------------------ page header */
export function PageHeader({
  title,
  subtitle,
  icon: Icon,
  tone = "primary",
  actions,
  extra,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  icon?: LucideIcon;
  tone?: "primary" | "pink" | "mint" | "blue" | "orange";
  actions?: ReactNode;
  extra?: ReactNode;
}) {
  return (
    <>
      <div className="page-header">
        {Icon && (
          <div className={`page-header__icon page-header__icon--${tone}`}>
            <Icon size={26} />
          </div>
        )}
        <div className="page-header__body">
          <h1 className="page-header__title">
            <span>{title}</span>
          </h1>
          {subtitle && <p className="page-header__sub">{subtitle}</p>}
        </div>
        {actions && <div className="page-header__actions">{actions}</div>}
      </div>
      {extra}
    </>
  );
}

/* ----------------------------------------------------------------- badge */
export type BadgeTone = "success" | "warn" | "danger" | "info" | "primary" | "muted" | "pink" | "mint" | "orange" | "blue";

export function StatusBadge({
  tone = "muted",
  children,
  dot = false,
}: {
  tone?: BadgeTone;
  children: ReactNode;
  dot?: boolean;
}) {
  return (
    <span className={`badge badge--${tone}`}>
      {dot && <i className="dot" />}
      {children}
    </span>
  );
}

/* ----------------------------------------------------------------- state */
export function EmptyState({
  title = "ยังไม่มีข้อมูล",
  text,
  icon: Icon = Inbox,
  action,
}: {
  title?: string;
  text?: ReactNode;
  icon?: LucideIcon;
  action?: ReactNode;
}) {
  return (
    <div className="state">
      <div className="state__icon">
        <Icon size={26} />
      </div>
      <div className="state__title">{title}</div>
      {text && <div className="state__text">{text}</div>}
      {action}
    </div>
  );
}

export function LoadingState({ label = "กำลังโหลดข้อมูล..." }: { label?: string }) {
  return (
    <div className="state">
      <div className="state__icon">
        <Loader2 size={26} className="spin" />
      </div>
      <div className="state__text">{label}</div>
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="state">
      <div className="state__icon" style={{ background: "var(--c-danger-soft)", color: "var(--c-danger)" }}>
        <AlertTriangle size={26} />
      </div>
      <div className="state__title">เกิดข้อผิดพลาด</div>
      <div className="state__text">{message}</div>
      {onRetry && (
        <button className="btn btn--soft btn--sm" onClick={onRetry}>
          <RefreshCw size={14} /> ลองอีกครั้ง
        </button>
      )}
    </div>
  );
}

/* -------------------------------------------------------------- stat card */
export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "primary",
  onClick,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: LucideIcon;
  tone?: "primary" | "pink" | "mint" | "blue" | "orange";
  onClick?: () => void;
}) {
  const toneStyle: Record<string, { bg: string; fg: string }> = {
    primary: { bg: "var(--g-primary-soft)", fg: "var(--c-primary)" },
    pink: { bg: "var(--g-pink)", fg: "var(--c-pink-strong)" },
    mint: { bg: "var(--g-mint)", fg: "var(--c-mint-strong)" },
    blue: { bg: "var(--g-blue)", fg: "var(--c-blue-strong)" },
    orange: { bg: "var(--g-orange)", fg: "var(--c-orange-strong)" },
  };
  const t = toneStyle[tone];
  return (
    <div
      className="stat"
      onClick={onClick}
      style={onClick ? { cursor: "pointer" } : undefined}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => e.key === "Enter" && onClick() : undefined}
    >
      {Icon && (
        <div className="stat__icon" style={{ background: t.bg, color: t.fg }}>
          <Icon size={22} />
        </div>
      )}
      <div style={{ minWidth: 0 }}>
        <div className="stat__value">{value}</div>
        <div className="stat__label">{label}</div>
        {hint && <div className="stat__hint">{hint}</div>}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ step */
export function Step({
  n,
  title,
  text,
  tone = "primary",
  icon: Icon,
}: {
  n?: number;
  title: ReactNode;
  text?: ReactNode;
  tone?: "primary" | "pink" | "mint" | "blue" | "orange";
  icon?: LucideIcon;
}) {
  return (
    <div className="step">
      {Icon ? (
        <div className={`step__num step__num--${tone}`}>
          <Icon size={17} />
        </div>
      ) : (
        <div className={`step__num step__num--${tone}`}>{n}</div>
      )}
      <div style={{ minWidth: 0 }}>
        <h3 className="step__title">{title}</h3>
        {text && <p className="step__text">{text}</p>}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ chip */
export function Chip({
  children,
  active = false,
  onClick,
  tone = "primary",
}: {
  children: ReactNode;
  active?: boolean;
  onClick?: () => void;
  tone?: "primary" | "pink" | "mint" | "blue" | "orange";
}) {
  const bg: Record<string, string> = {
    primary: "var(--c-primary-soft)",
    pink: "var(--g-pink)",
    mint: "var(--g-mint)",
    blue: "var(--g-blue)",
    orange: "var(--g-orange)",
  };
  const fg: Record<string, string> = {
    primary: "var(--c-primary-darker)",
    pink: "var(--c-pink-strong)",
    mint: "var(--c-mint-strong)",
    blue: "var(--c-blue-strong)",
    orange: "var(--c-orange-strong)",
  };
  if (!onClick) {
    return (
      <span className="chip chip--static" style={{ background: bg[tone], color: fg[tone] }}>
        {children}
      </span>
    );
  }
  return (
    <button
      type="button"
      className={`chip ${active ? "chip--active" : ""}`}
      style={active ? undefined : { background: bg[tone], color: fg[tone] }}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

/* --------------------------------------------------------------- helpers */
export function formatDuration(seconds?: number): string {
  if (!seconds || seconds <= 0) return "--:--";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function formatThaiDate(iso?: string): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("th-TH", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatRelative(iso?: string): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const diff = Date.now() - d.getTime();
  const mins = Math.round(diff / 60000);
  if (mins < 1) return "เมื่อสักครู่";
  if (mins < 60) return `${mins} นาทีที่แล้ว`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} ชั่วโมงที่แล้ว`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} วันที่แล้ว`;
  return formatThaiDate(iso);
}
