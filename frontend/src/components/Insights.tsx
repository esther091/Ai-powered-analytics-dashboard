import type { Insight } from "../api";
import { usePalette } from "../theme";

const META: Record<Insight["kind"], { icon: string; label: string }> = {
  trend: { icon: "↗", label: "Trend" },
  risk: { icon: "!", label: "Risk" },
  opportunity: { icon: "★", label: "Opportunity" },
  info: { icon: "i", label: "Finding" },
};

export function InsightList({ items, limit }: { items: Insight[]; limit?: number }) {
  const p = usePalette();
  const color: Record<Insight["kind"], string> = { trend: p.good, risk: p.critical, opportunity: p.series[0], info: p.muted };
  return (
    <div className="insights">
      {items.slice(0, limit ?? items.length).map((i) => (
        <article className="insight" key={i.title}>
          <div className="ico" style={{ background: `${color[i.kind]}22`, color: color[i.kind] }} aria-hidden>
            {META[i.kind].icon}
          </div>
          <div>
            <div className="kind-label">{META[i.kind].label}</div>
            <h3>{i.title}</h3>
            <p>{i.detail}</p>
          </div>
        </article>
      ))}
    </div>
  );
}
