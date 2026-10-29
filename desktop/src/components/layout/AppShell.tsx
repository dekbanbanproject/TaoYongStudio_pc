import { NavLink, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import {
  Bell,
  CalendarDays,
  Clock,
  Facebook,
  FileText,
  HelpCircle,
  Home,
  Maximize2,
  Minimize2,
  Play,
  Settings,
  SlidersHorizontal,
  Sparkles,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { engineStatus } from "../../services/api";

const NAV = [
  { to: "/", label: "หน้าแรก", icon: Home, end: true },
  { to: "/planner", label: "วางแผน", icon: CalendarDays },
  { to: "/scripts", label: "บท", icon: FileText },
  { to: "/clips", label: "คลิป", icon: Play },
  { to: "/create", label: "สร้างและโพสต์", icon: Sparkles },
  { to: "/posting-settings", label: "ตั้งค่าโพสต์", icon: SlidersHorizontal },
  { to: "/scheduler", label: "ตั้งเวลา", icon: Clock },
  { to: "/settings", label: "ตั้งค่า", icon: Settings },
  { to: "/facebook-profile", label: "Facebook Profile", icon: Facebook },
];

function Sidebar() {
  const location = useLocation();
  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <img className="sidebar__logo" src="/branding/ui_avatar.png" alt="TaoYongStudio" />
        <div style={{ minWidth: 0 }}>
          <p className="sidebar__title">
            TaoYong<span>Studio</span>
          </p>
          <p className="sidebar__subtitle">สร้างวิดีโอการ์ตูนเด็กด้วย AI สำหรับเด็กไทย</p>
        </div>
      </div>

      <nav className="sidebar__nav">
        {NAV.map((n) => {
          const Icon = n.icon;
          const active = n.end
            ? location.pathname === "/"
            : location.pathname.startsWith(n.to);
          return (
            <NavLink
              key={n.to}
              to={n.to}
              className={`nav-item ${active ? "nav-item--active" : ""}`}
            >
              <span className="nav-item__icon">
                <Icon size={17} />
              </span>
              <span className="truncate">{n.label}</span>
            </NavLink>
          );
        })}
      </nav>

      <div className="sidebar__footer">
        <img className="sidebar__art" src="/branding/asset_side_temple.png" alt="" />
        <div className="sidebar__version">
          <strong>TaoYongStudio v2.0.0</strong>
          AI Cartoon Video Production
          <br />
          for Thai Kids
        </div>
      </div>
    </aside>
  );
}

function WindowControls() {
  const [maximized, setMaximized] = useState(false);
  useEffect(() => {
    const w = getCurrentWindow();
    w.isMaximized().then(setMaximized).catch(() => {});
  }, []);

  return (
    <div className="window-controls">
      <button title="ย่อหน้าต่าง" onClick={() => getCurrentWindow().minimize()}>
        <Minimize2 size={16} />
      </button>
      <button
        title={maximized ? "กลับสู่ขนาดปกติ" : "ขยายเต็มหน้าจอ"}
        onClick={() => getCurrentWindow().toggleMaximize()}
      >
        <Maximize2 size={15} />
      </button>
      <button data-danger="true" title="ปิดโปรแกรม" onClick={() => getCurrentWindow().close()}>
        <X size={16} />
      </button>
    </div>
  );
}

function Header() {
  const [engineUp, setEngineUp] = useState<boolean | null>(null);

  useEffect(() => {
    let alive = true;
    const probe = async () => {
      try {
        const s = await engineStatus();
        if (alive) setEngineUp(!!s?.running);
      } catch {
        if (alive) setEngineUp(false);
      }
    };
    probe();
    const t = setInterval(probe, 15000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  return (
    <header className="header" data-tauri-drag-region>
      <div className="header__banner" style={{ backgroundImage: "url(/branding/asset_top_banner.png)" }} />
      <div className="header__slogan">
        <strong>จัดหมากระยองเด็กไทย</strong>
        <span>สร้างได้ด้วย AI ✨</span>
      </div>

      <div className="header__right">
        <button className="header__icon-btn" title="การแจ้งเตือน">
          <Bell size={17} />
          <span className="header__dot" />
        </button>
        <button className="header__icon-btn" title="ช่วยเหลือ">
          <HelpCircle size={17} />
        </button>
        <div className="header__user">
          <img src="/characters/char_avatar_circle_1.png" alt="" />
          <div>
            <div className="header__user-name">สวัสดีครับ</div>
            <div className="header__user-role">TaoYong</div>
          </div>
        </div>
        <WindowControls />
      </div>

      {engineUp === false && (
        <div
          className="xsmall"
          style={{
            position: "absolute",
            right: 20,
            top: 56,
            background: "var(--c-danger-soft)",
            color: "var(--c-danger)",
            padding: "3px 10px",
            borderRadius: 999,
          }}
        >
          Python Engine ไม่ได้ทำงาน
        </div>
      )}
    </header>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-shell__main">
        <Header />
        <main className="app-shell__content">{children}</main>
      </div>
    </div>
  );
}
