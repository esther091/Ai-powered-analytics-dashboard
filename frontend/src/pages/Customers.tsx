import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { query, useApi, type Churn, type Cohort, type FilterState, type Segments } from "../api";
import { Card, Status } from "../components/Card";
import { Legend, Tip } from "../components/ChartBits";
import { gbp, monthLabel, num, pct } from "../format";
import { SEGMENT_SLOT, seqColor, usePalette } from "../theme";

export function Customers({ filters }: { filters: FilterState }) {
  const q = query(filters);
  const seg = useApi<Segments>(`segments${q}`);
  const cohorts = useApi<Cohort[]>(`cohorts${q}`);
  const churn = useApi<Churn>(`churn${query({ ...filters, start: "", end: "" })}`);
  const p = usePalette();
  const segColor = (s: string) => p.series[SEGMENT_SLOT[s.replace(/ \(\d\)$/, "")] ?? 7];

  return (
    <div className="grid">
      <Card className="span-12" title="Customer segments"
        sub={seg.data ? `K-means on recency, frequency and spend (RFM) for ${num(seg.data.customers, false)} customers · ${seg.data.k} clusters chosen by silhouette score (${seg.data.silhouette})` : "K-means on RFM"}>
        <Status loading={seg.loading && !seg.data} error={seg.error} empty={seg.data?.segments.length === 0} />
        {seg.data && seg.data.segments.length > 0 && (
          <div className="seg-cards">
            {seg.data.segments.map((s) => (
              <div className="seg-card" key={s.segment}>
                <h3><span className="swatch" style={{ background: segColor(s.segment) }} />{s.segment}</h3>
                <div className="nums">
                  <span><b>{num(s.customers, false)}</b>customers ({pct(s.customer_share, 0)})</span>
                  <span><b>{pct(s.revenue_share, 0)}</b>of revenue</span>
                </div>
                <div className="nums">
                  <span>Last order <b>{s.median_recency_days}d</b></span>
                  <span>Orders <b>{s.median_orders}</b></span>
                  <span>Spend <b>{gbp(s.median_spend)}</b></span>
                </div>
                <p>{s.action}</p>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="span-6" title="Segment map" sub="Each dot is a customer (sample). Medians shown on the cards.">
        {seg.data && seg.data.scatter.length > 0 && (
          <>
            <Legend items={seg.data.segments.map((s) => ({ label: s.segment, color: segColor(s.segment), box: true }))} />
            <ResponsiveContainer width="100%" height={300}>
              <ScatterChart margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
                <CartesianGrid stroke={p.grid} />
                <XAxis type="number" dataKey="recency" name="Days since last order" tick={{ fill: p.axis, fontSize: 11 }} axisLine={false} tickLine={false}
                  label={{ value: "Days since last order", position: "insideBottom", offset: -4, fill: p.muted, fontSize: 11 }} />
                <YAxis type="number" dataKey="monetary" scale="log" domain={[10, "auto"]} allowDataOverflow tickFormatter={(v) => gbp(v)} tick={{ fill: p.axis, fontSize: 11 }} axisLine={false} tickLine={false} width={56} />
                <ZAxis range={[18, 18]} />
                <Tooltip content={({ active, payload }) => active && payload?.length ? (
                  <Tip title={`Customer ${payload[0].payload.customer_id}`} rows={[
                    { label: "Segment", value: String(payload[0].payload.segment), color: segColor(String(payload[0].payload.segment)) },
                    { label: "Last order", value: `${payload[0].payload.recency} days ago` },
                    { label: "Orders", value: String(payload[0].payload.frequency) },
                    { label: "Spend", value: gbp(Number(payload[0].payload.monetary), false) },
                  ]} />
                ) : null} />
                {seg.data.segments.map((s) => (
                  <Scatter key={s.segment} data={seg.data!.scatter.filter((d) => d.segment === s.segment && d.monetary > 0)} fill={segColor(s.segment)} fillOpacity={0.7} stroke={p.surface} strokeWidth={1} />
                ))}
              </ScatterChart>
            </ResponsiveContainer>
          </>
        )}
      </Card>

      <Card className="span-6" title="Churn risk model" sub={churn.data?.available ? `Probability a customer places no order in the next ${churn.data.window_days} days` : "Gradient-boosted classifier"}>
        <Status loading={churn.loading && !churn.data} error={churn.error} />
        {churn.data && !churn.data.available && <div className="empty">Not enough customers in this selection to train the model.</div>}
        {churn.data?.available && (
          <>
            <div className="stat-row">
              <div className="stat"><div className="v">{churn.data.metrics.roc_auc.toFixed(2)}</div><div className="l">ROC AUC on held-out customers</div></div>
              {churn.data.bands.map((b) => (
                <div className="stat" key={b.band}><div className="v">{num(b.customers, false)}</div><div className="l">{b.band} risk</div></div>
              ))}
            </div>
            <div className="sub" style={{ color: "var(--text-3)", fontSize: 12, marginBottom: 4 }}>What drives the prediction (permutation importance)</div>
            <ResponsiveContainer width="100%" height={190}>
              <BarChart data={churn.data.importance.slice(0, 6)} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="feature" width={170} tick={{ fill: p.text, fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip cursor={{ fill: p.grid, opacity: 0.4 }} content={({ active, payload }) => active && payload?.length ? (
                  <Tip title={String(payload[0].payload.feature)} rows={[{ label: "Drop in AUC when shuffled", value: Number(payload[0].value).toFixed(3) }]} />
                ) : null} />
                <Bar dataKey="importance" fill={p.series[0]} radius={[0, 4, 4, 0]} barSize={14} />
              </BarChart>
            </ResponsiveContainer>
            <p className="note">Trained on behaviour up to {churn.data.trained_on_cutoff} and whether each customer bought in the following {churn.data.window_days} days, then applied to every customer active in the last year. Ignores the date filter.</p>
          </>
        )}
      </Card>

      {churn.data?.available && (
        <Card className="span-12" title="Customers to win back first" sub="Highest expected value at risk (churn probability × typical half-year spend)">
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Customer</th><th>Country</th><th className="num">Churn probability</th><th className="num">Days since last order</th><th className="num">Usual gap (days)</th><th className="num">Orders</th><th className="num">Lifetime spend</th><th className="num">Value at risk</th></tr></thead>
              <tbody>
                {churn.data.at_risk.slice(0, 12).map((c) => (
                  <tr key={c.customer_id}>
                    <td>{c.customer_id}</td><td>{c.country}</td>
                    <td className="num">{pct(c.churn_prob, 0)}</td><td className="num">{c.recency}</td><td className="num">{c.avg_gap_days}</td>
                    <td className="num">{c.orders}</td><td className="num">{gbp(c.spend, false)}</td><td className="num">{gbp(c.value_at_risk, false)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Card className="span-12" title="Cohort retention" sub="Share of each month's new customers who ordered again N months later">
        <Status loading={cohorts.loading && !cohorts.data} error={cohorts.error} empty={cohorts.data?.length === 0} />
        {cohorts.data && cohorts.data.length > 0 && <CohortGrid rows={cohorts.data} />}
      </Card>
    </div>
  );
}

function CohortGrid({ rows }: { rows: Cohort[] }) {
  const p = usePalette();
  const months = rows[0].retention.length;
  const maxR = Math.max(0.01, ...rows.flatMap((r) => r.retention.slice(1).filter((x): x is number => x != null)));
  const dark = p.surface !== "#fcfcfb";
  return (
    <div className="table-wrap">
      <div className="heat cohort" style={{ gridTemplateColumns: `70px 54px repeat(${months - 1}, minmax(34px, 1fr))`, minWidth: 640 }}>
        <div className="lab">Cohort</div><div className="lab">New</div>
        {Array.from({ length: months - 1 }, (_, i) => <div key={i} className="lab collab">+{i + 1}</div>)}
        {rows.map((r) => (
          <CohortRow key={r.cohort} r={r} maxR={maxR} dark={dark} />
        ))}
      </div>
      <p className="note">Stronger blue = more customers came back. The first cohort also contains customers who were already buying before the selected period starts, so it looks unusually loyal. The partial final month (December 2011) is left out.</p>
    </div>
  );
}

function CohortRow({ r, maxR, dark }: { r: Cohort; maxR: number; dark: boolean }) {
  const p = usePalette();
  return (
    <>
      <div className="lab">{monthLabel(r.cohort)}</div>
      <div className="lab">{r.size}</div>
      {r.retention.slice(1).map((v, i) => {
        if (v == null) return <div key={i} />;
        const t = v / maxR;
        const fg = (dark ? t < 0.75 : t > 0.5) ? "#fff" : p.text;
        return <div key={i} className="cell" style={{ background: seqColor(p, t), color: dark ? "#fff" : fg }} title={`${monthLabel(r.cohort)} cohort, month +${i + 1}: ${pct(v)}`}>{Math.round(v * 100)}</div>;
      })}
    </>
  );
}
