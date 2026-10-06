import type { ReactNode } from "react";

export function Card({ title, sub, actions, children, className = "" }: {
  title?: ReactNode;
  sub?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-head">
          <div>
            {title && <h2>{title}</h2>}
            {sub && <div className="sub">{sub}</div>}
          </div>
          {actions && <div className="actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function Toggle<T extends string>({ value, options, onChange }: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="seg" role="group">
      {options.map((o) => (
        <button key={o.value} className={o.value === value ? "on" : ""} aria-pressed={o.value === value} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Status({ loading, error, empty }: { loading?: boolean; error?: string | null; empty?: boolean }) {
  if (error) return <div className="error-box">Couldn't load this view: {error}</div>;
  if (loading) return <div className="empty">Loading…</div>;
  if (empty) return <div className="empty">No data for this selection.</div>;
  return null;
}
