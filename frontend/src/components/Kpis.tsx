import type { Kpis as KpiData, Summary } from "../api";
import { gbp, num, pct } from "../format";

const ITEMS: { key: keyof Summary; label: string; fmt: (v: number | null) => string; lowerIsBetter?: boolean }[] = [
  { key: "revenue", label: "Revenue", fmt: (v) => gbp(v) },
  { key: "orders", label: "Orders", fmt: (v) => num(v, false) },
  { key: "customers", label: "Customers", fmt: (v) => num(v, false) },
  { key: "aov", label: "Average order value", fmt: (v) => gbp(v, false) },
  { key: "cancellation_rate", label: "Cancellation rate", fmt: (v) => pct(v), lowerIsBetter: true },
];

export function KpiRow({ data }: { data: KpiData | null }) {
  const basis = data?.previous_period?.basis;
  return (
    <div className="kpis">
      {ITEMS.map((it) => {
        const v = data ? (data.current[it.key] as number | null) : null;
        // A rate's change reads better in percentage points than as a relative change.
        const prev = data?.previous ? (data.previous[it.key] as number | null) : null;
        const isRate = it.key === "cancellation_rate";
        const c = isRate ? (v != null && prev != null ? v - prev : null) : data?.change[it.key];
        const good = c != null && (it.lowerIsBetter ? c < 0 : c > 0);
        return (
          <div className="card kpi" key={it.key}>
            <div className="label">{it.label}</div>
            <div className="value">{data ? it.fmt(v) : "…"}</div>
            {c != null ? (
              <div className={`delta ${good ? "up" : "down"}`} title={`vs ${basis}`}>
                {c > 0 ? "▲" : "▼"} {isRate ? `${(Math.abs(c) * 100).toFixed(1)} pts` : pct(Math.abs(c))} <span className="vs">vs {basis === "same period last year" ? "last year" : "prior period"}</span>
              </div>
            ) : (
              <div className="delta"><span className="vs">{data ? "no comparison period in data" : " "}</span></div>
            )}
          </div>
        );
      })}
    </div>
  );
}
