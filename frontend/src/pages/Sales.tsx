import { useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { query, useApi, type CountryRow, type FilterState, type HeatCell, type TimePoint } from "../api";
import { Card, Status, Toggle } from "../components/Card";
import { Legend, Tip } from "../components/ChartBits";
import { dayLabel, gbp, monthLabel, num, pct, shortDay } from "../format";
import { seqColor, usePalette } from "../theme";

type Metric = "revenue" | "orders" | "customers" | "aov";
type Freq = "D" | "W" | "M";
const METRIC_LABEL: Record<Metric, string> = { revenue: "Revenue", orders: "Orders", customers: "Customers", aov: "Avg order value" };
const fmtMetric = (m: Metric, v: number, compact = true) => (m === "revenue" || m === "aov" ? gbp(v, compact) : num(v, compact));

export function Sales({ filters }: { filters: FilterState }) {
  const [metric, setMetric] = useState<Metric>("revenue");
  const [freq, setFreq] = useState<Freq>("W");
  const ts = useApi<TimePoint[]>(`timeseries${query(filters, { freq })}`);
  const yoy = useApi<Record<string, string | number>[]>(`yoy${query(filters)}`);
  const heat = useApi<HeatCell[]>(`heatmap${query(filters)}`);
  const countries = useApi<CountryRow[]>(`countries${query(filters)}`);
  const p = usePalette();
  const xFmt = freq === "M" ? monthLabel : shortDay;

  const years = yoy.data ? Array.from(new Set(yoy.data.flatMap((r) => Object.keys(r).filter((k) => k !== "month")))).sort() : [];
  // Fixed colour per year (entity), assigned in palette order from the earliest year in the dataset.
  const yearColor = (y: string) => p.series[(Number(y) - 2009) % p.series.length];

  return (
    <div className="grid">
      <Card className="span-12" title={`${METRIC_LABEL[metric]} over time`} sub="Valid product sales"
        actions={<>
          <Toggle value={metric} onChange={setMetric} options={(Object.keys(METRIC_LABEL) as Metric[]).map((m) => ({ value: m, label: METRIC_LABEL[m] }))} />
          <Toggle value={freq} onChange={setFreq} options={[{ value: "D", label: "Day" }, { value: "W", label: "Week" }, { value: "M", label: "Month" }]} />
        </>}>
        <Status loading={ts.loading && !ts.data} error={ts.error} empty={ts.data?.length === 0} />
        {ts.data && ts.data.length > 0 && (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={ts.data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={p.grid} vertical={false} />
              <XAxis dataKey="date" tickFormatter={xFmt} tick={{ fill: p.axis, fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={24} />
              <YAxis tickFormatter={(v) => fmtMetric(metric, v)} tick={{ fill: p.axis, fontSize: 11 }} axisLine={false} tickLine={false} width={56} />
              <Tooltip cursor={{ stroke: p.axis, strokeDasharray: "3 3" }}
                content={({ active, payload }) => active && payload?.length ? (
                  <Tip title={(freq === "W" ? "Week of " : "") + (freq === "M" ? monthLabel : dayLabel)(String(payload[0].payload.date))}
                    rows={[{ label: METRIC_LABEL[metric], value: fmtMetric(metric, Number(payload[0].value), false), color: p.series[0] }]} />
                ) : null} />
              <Line type="monotone" dataKey={metric} stroke={p.series[0]} strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: p.surface }} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </Card>

      <Card className="span-7" title="Year over year" sub="Revenue by calendar month, every year (ignores the date filter). The peak builds from September to November.">
        <Status loading={yoy.loading && !yoy.data} error={yoy.error} />
        {yoy.data && (
          <>
            <Legend items={years.map((y) => ({ label: y, color: yearColor(y) }))} />
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={yoy.data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={p.grid} vertical={false} />
                <XAxis dataKey="month" tick={{ fill: p.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tickFormatter={(v) => gbp(v)} tick={{ fill: p.axis, fontSize: 11 }} axisLine={false} tickLine={false} width={56} />
                <Tooltip cursor={{ stroke: p.axis, strokeDasharray: "3 3" }}
                  content={({ active, payload, label }) => active && payload?.length ? (
                    <Tip title={String(label)} rows={payload.map((s) => ({ label: String(s.dataKey), value: gbp(Number(s.value), false), color: String(s.color) }))} />
                  ) : null} />
                {years.map((y) => (
                  <Line key={y} type="monotone" dataKey={y} stroke={yearColor(y)} strokeWidth={2} connectNulls={false}
                    dot={{ r: 3, strokeWidth: 0, fill: yearColor(y) }} activeDot={{ r: 5, strokeWidth: 2, stroke: p.surface }} />
                ))}
              </LineChart>
            </ResponsiveContainer>
            <p className="note">December 2011 stops on the 9th, so its point is partial.</p>
          </>
        )}
      </Card>

      <Card className="span-5" title="When customers buy" sub="Revenue by weekday and hour">
        <Status loading={heat.loading && !heat.data} error={heat.error} empty={heat.data?.length === 0} />
        {heat.data && heat.data.length > 0 && <Heatmap cells={heat.data} />}
      </Card>

      <Card className="span-12" title="Countries" sub="Top 15 by revenue">
        <Status loading={countries.loading && !countries.data} error={countries.error} empty={countries.data?.length === 0} />
        {countries.data && countries.data.length > 0 && (
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Country</th><th className="num">Revenue</th><th className="num">Share</th><th className="num">Orders</th><th className="num">Customers</th><th className="num">Avg order</th></tr></thead>
              <tbody>
                {countries.data.map((c) => (
                  <tr key={c.country}>
                    <td>{c.country}</td>
                    <td className="num bar-cell"><span className="bar" style={{ width: `${(c.revenue / countries.data![0].revenue) * 100}%`, background: p.series[0] }} /><span>{gbp(c.revenue, false)}</span></td>
                    <td className="num">{pct(c.share)}</td>
                    <td className="num">{num(c.orders, false)}</td>
                    <td className="num">{num(c.customers, false)}</td>
                    <td className="num">{gbp(c.aov, false)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function Heatmap({ cells }: { cells: HeatCell[] }) {
  const p = usePalette();
  const hours = Array.from(new Set(cells.map((c) => c.hour))).sort((a, b) => a - b);
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const max = Math.max(...cells.map((c) => c.revenue));
  const at = new Map(cells.map((c) => [`${c.weekday}-${c.hour}`, c.revenue]));
  return (
    <div>
      <div className="heat" style={{ gridTemplateColumns: `36px repeat(${hours.length}, minmax(0, 1fr))` }}>
        <div />
        {hours.map((h) => <div key={h} className="lab collab">{h}</div>)}
        {days.map((d) => (
          <Row key={d} d={d} hours={hours} at={at} max={max} p={p} />
        ))}
      </div>
      <div className="legend-ramp">
        <span>Less</span>
        <span className="ramp">{p.seq.map((c) => <span key={c} style={{ background: c }} />)}</span>
        <span>More (peak {gbp(max)} per hour slot)</span>
      </div>
    </div>
  );
}

function Row({ d, hours, at, max, p }: { d: string; hours: number[]; at: Map<string, number>; max: number; p: ReturnType<typeof usePalette> }) {
  return (
    <>
      <div className="lab">{d}</div>
      {hours.map((h) => {
        const v = at.get(`${d}-${h}`) ?? 0;
        return <div key={h} className="cell" style={{ background: seqColor(p, v / max) }} title={`${d} ${h}:00 · ${gbp(v, false)}`} />;
      })}
    </>
  );
}
