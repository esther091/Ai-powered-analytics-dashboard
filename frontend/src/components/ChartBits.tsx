import type { ReactNode } from "react";

export interface TipRow {
  label: string;
  value: string;
  color?: string;
  dashed?: boolean;
}

/** Shared tooltip body. Values in text ink; a colour swatch carries series identity. */
export function Tip({ title, rows }: { title: ReactNode; rows: TipRow[] }) {
  return (
    <div className="tt">
      <div className="tt-title">{title}</div>
      {rows.map((r) => (
        <div className="tt-row" key={r.label}>
          <span>
            {r.color && <span className="swatch" style={{ background: r.color }} />}
            {r.label}
          </span>
          <b>{r.value}</b>
        </div>
      ))}
    </div>
  );
}

export function Legend({ items }: { items: { label: string; color: string; dashed?: boolean; box?: boolean }[] }) {
  return (
    <div className="legend">
      {items.map((i) => (
        <span className="item" key={i.label}>
          {i.box ? (
            <span className="swatch" style={{ background: i.color }} />
          ) : (
            <span className={`line ${i.dashed ? "dash" : ""}`} style={{ background: i.color, borderColor: i.color }} />
          )}
          {i.label}
        </span>
      ))}
    </div>
  );
}
