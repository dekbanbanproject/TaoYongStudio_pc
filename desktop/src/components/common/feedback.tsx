import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";

/* ------------------------------------------------------------------ toast */
export type ToastKind = "success" | "error" | "info" | "warn";

interface Toast {
  id: number;
  kind: ToastKind;
  title: string;
  text?: string;
}

interface ToastApi {
  success: (title: string, text?: string) => void;
  error: (title: string, text?: string) => void;
  info: (title: string, text?: string) => void;
  warn: (title: string, text?: string) => void;
}

const Ctx = createContext<ToastApi>({
  success: () => {},
  error: () => {},
  info: () => {},
  warn: () => {},
});

export function useToast() {
  return useContext(Ctx);
}

const ICONS: Record<ToastKind, typeof Info> = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
  warn: AlertTriangle,
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);

  const push = useCallback((kind: ToastKind, title: string, text?: string) => {
    const id = Date.now() + Math.random();
    setItems((s) => [...s, { id, kind, title, text }]);
    setTimeout(() => setItems((s) => s.filter((t) => t.id !== id)), kind === "error" ? 7000 : 4200);
  }, []);

  const api = useMemo<ToastApi>(
    () => ({
      success: (t, x) => push("success", t, x),
      error: (t, x) => push("error", t, x),
      info: (t, x) => push("info", t, x),
      warn: (t, x) => push("warn", t, x),
    }),
    [push],
  );

  return (
    <Ctx.Provider value={api}>
      {children}
      <div className="toast-stack">
        {items.map((t) => {
          const Icon = ICONS[t.kind];
          return (
            <div key={t.id} className={`toast toast--${t.kind}`}>
              <Icon size={18} className="toast__icon" />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="toast__title">{t.title}</div>
                {t.text && <div className="toast__text">{t.text}</div>}
              </div>
              <button
                className="btn btn--ghost btn--icon btn--sm"
                onClick={() => setItems((s) => s.filter((x) => x.id !== t.id))}
                aria-label="ปิด"
              >
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </Ctx.Provider>
  );
}

/* ------------------------------------------------------------------ modal */
export function Modal({
  open,
  title,
  icon: Icon,
  children,
  onClose,
  footer,
  width,
}: {
  open: boolean;
  title: ReactNode;
  icon?: typeof Info;
  children?: ReactNode;
  onClose: () => void;
  footer?: ReactNode;
  width?: number;
}) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        style={width ? { width: `min(${width}px, 100%)` } : undefined}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="modal__head">
          {Icon && (
            <span className="card__title-icon">
              <Icon size={17} />
            </span>
          )}
          <h2 className="modal__title">{title}</h2>
        </div>
        <div className="modal__body">{children}</div>
        {footer && <div className="modal__foot">{footer}</div>}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------- confirm dialog */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "ยืนยัน",
  cancelLabel = "ยกเลิก",
  danger = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal
      open={open}
      title={title}
      icon={danger ? AlertTriangle : Info}
      onClose={onCancel}
      footer={
        <>
          <button className="btn btn--outline" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            className={`btn ${danger ? "btn--danger" : "btn--primary"}`}
            onClick={onConfirm}
            autoFocus
          >
            {confirmLabel}
          </button>
        </>
      }
    >
      {message}
    </Modal>
  );
}
