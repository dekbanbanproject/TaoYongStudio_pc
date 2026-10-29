import type { ReactNode } from "react";
import { Search } from "lucide-react";
import { useEffect, useState } from "react";

/* ----------------------------------------------------------- search input */
export function SearchInput({
  value,
  onChange,
  placeholder = "ค้นหา...",
  style,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div className="search" style={style}>
      <span className="search__icon">
        <Search size={16} />
      </span>
      <input
        className="input"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

/* ------------------------------------------------------------- data table */
export interface Column<T> {
  key: string;
  header: ReactNode;
  render?: (row: T, index: number) => ReactNode;
  width?: number | string;
  align?: "left" | "right" | "center";
  className?: string;
}

export function DataTable<T extends { [k: string]: any }>({
  columns,
  rows,
  rowKey,
  selected,
  onSelect,
  onRowClick,
  empty,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string;
  selected?: Set<string>;
  onSelect?: (key: string, checked: boolean, row: T) => void;
  onRowClick?: (row: T) => void;
  empty?: ReactNode;
}) {
  const allKeys = rows.map((r, i) => rowKey(r, i));
  const allChecked = allKeys.length > 0 && allKeys.every((k) => selected?.has(k));

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            {onSelect && (
              <th style={{ width: 44 }}>
                <input
                  type="checkbox"
                  checked={allChecked}
                  onChange={(e) =>
                    allKeys.forEach((k) => onSelect(k, e.target.checked, rows[allKeys.indexOf(k)]))
                  }
                />
              </th>
            )}
            {columns.map((c) => (
              <th key={c.key} style={{ width: c.width, textAlign: c.align ?? "left" }}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length + (onSelect ? 1 : 0)} style={{ padding: 0 }}>
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((row, i) => {
              const key = rowKey(row, i);
              const isSel = selected?.has(key);
              return (
                <tr
                  key={key}
                  data-selected={isSel ? "true" : "false"}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  style={onRowClick ? { cursor: "pointer" } : undefined}
                >
                  {onSelect && (
                    <td onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={!!isSel}
                        onChange={(e) => onSelect(key, e.target.checked, row)}
                      />
                    </td>
                  )}
                  {columns.map((c) => (
                    <td
                      key={c.key}
                      className={`${c.align === "right" ? "table__num" : ""} ${c.className ?? ""}`}
                      style={{ textAlign: c.align === "center" ? "center" : undefined }}
                    >
                      {c.render ? c.render(row, i) : row[c.key]}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------- pagination */
export function Pagination({
  page,
  perPage,
  total,
  onPage,
}: {
  page: number;
  perPage: number;
  total: number;
  onPage: (p: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / perPage));
  const nums: (number | "...")[] = [];
  const push = (n: number | "...") => nums.push(n);
  if (pages <= 7) {
    for (let i = 1; i <= pages; i++) push(i);
  } else {
    push(1);
    if (page > 3) push("...");
    for (let i = Math.max(2, page - 1); i <= Math.min(pages - 1, page + 1); i++) push(i);
    if (page < pages - 2) push("...");
    push(pages);
  }
  const from = total === 0 ? 0 : (page - 1) * perPage + 1;
  const to = Math.min(total, page * perPage);

  return (
    <div className="pagination">
      <span className="small muted">
        แสดง {from} - {to} จาก {total} รายการ
      </span>
      <div className="pagination__pages">
        <button
          className="pagination__btn"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          aria-label="หน้าก่อนหน้า"
        >
          ‹
        </button>
        {nums.map((n, i) =>
          n === "..." ? (
            <span key={`e${i}`} className="small muted" style={{ padding: "0 4px" }}>
              …
            </span>
          ) : (
            <button
              key={n}
              className={`pagination__btn ${n === page ? "pagination__btn--active" : ""}`}
              onClick={() => onPage(n)}
            >
              {n}
            </button>
          ),
        )}
        <button
          className="pagination__btn"
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
          aria-label="หน้าถัดไป"
        >
          ›
        </button>
      </div>
    </div>
  );
}

/* --------------------------------------------------- local filter helper */
export function useDebounced<T>(value: T, delay = 220): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return v;
}

export function filterRows<T>(rows: T[], term: string, fields: (keyof T)[]): T[] {
  const q = term.trim().toLowerCase();
  if (!q) return rows;
  return rows.filter((r) =>
    fields.some((f) => {
      const v = r[f];
      if (v === null || v === undefined) return false;
      if (Array.isArray(v)) return v.some((x) => String(x).toLowerCase().includes(q));
      return String(v).toLowerCase().includes(q);
    }),
  );
}
