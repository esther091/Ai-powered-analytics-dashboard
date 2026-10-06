import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";
import { query, useApi, type Anomalies, type FilterState, type Forecast } from "../api";
import { Card, Status } from "../components/Card";
import { Legend, Tip } from "../components/ChartBits";
import { dayLabel, gbp, pct, shortDay } from "../format";
import { usePalette } from "../theme";

export function Predictions({ filters }: { filters: FilterState }) {
  const fc = useApi<Forecast>(`forecast${query({ ...filters, start: "", end: "" })}`);
  const an = useApi<Anomalies>(`anomalies${query(filters)}`);
  const p = usePalette();

  const series = fc.data?.available
    ? [
        ...fc.data.history.map((h) => ({ date: h.date, actual: h.actual })),
        ...fc.data.forecast.map((f) => ({ date: f.date, forecast: f.forecast, band: [f.lower, f.upper] as [number, number] })),
      ]
    : [];
  // Join the forecast line to the last actual week so the two read as one series.
  if (fc.data?.available && fc.data.history.length) {
    const last = fc.data.history[fc.data.history.length - 1];
    const i = fc.data.history.length - 1;
    (series[i] as Record<string, unknown>).forecast = last.actual;
  }
  const noisy = fc.data?.available && fc.data.backtest.mape > 0.3;

  return (
    <div className="grid">
      <Card className="span-8" title="Revenue forecast" sub={fc.data?.available ? `Next ${fc.data.horizon_days} days from ${dayLabel(fc.data.forecast_start)}, weekly` : "Weekly"}>
        <Status loading={fc.loading && !fc.data} error={fc.error} />
        {fc.data && !fc.data.available && <div className="empty">Not enough history for a forecast in this selection.</div>}
        {fc.data?.available && (
          <>
            {noisy && <div className="warn-box">⚠ Backtest error is {pct(fc.data.backtest.mape, 0)} for this selection: sales here are too sparse to forecast reliably. Treat this as a rough guide.</div>}
            <Legend items={[
              { label: "Actual", color: p.series[0] },
              { label: "Forecast", color: p.series[1], dashed: true },
              { label: "80% range", color: `${p.series[1]}44`, box: true },
            ]} />
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={p.grid} vertical={false} />
                <XAxis dataKey="date" tickFormatter={shortDay} tick={{ fill: p.axis, fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={24} />
                <YAxis tickFormatter={(v) => gbp(v)} tick={{ fill: p.axis, fontSize: 11 }} axisLine={false} tickLine={false} width={56} />
                <Tooltip cursor={{ stroke: p.axis, strokeDasharray: "3 3" }} content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload as { date: string; actual?: number; forecast?: number; band?: [number, number] };
                  const rows = d.band
                    ? [{ label: "Forecast", value: gbp(d.forecast!, false), color: p.series[1] }, { label: "Range", value: `${gbp(d.band[0])} – ${gbp(d.band[1])}` }]
                    : [{ label: "Actual", value: gbp(d.actual!, false), color: p.series[0] }];
                  return <Tip title={`Week of ${dayLabel(d.date)}`} rows={rows} />;
                }} />
                <Area dataKey="band" stroke="none" fill={p.series[1]} fillOpacity={0.15} isAnimationActive={false} />
                <Line dataKey="actual" stroke={p.series[0]} strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: p.surface }} />
                <Line dataKey="forecast" stroke={p.series[1]} strokeWidth={2} strokeDasharray="5 4" dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: p.surface }} />
              </ComposedChart>
            </ResponsiveContainer>
            <p className="note">{fc.data.model} Christmas week and New Year are close to zero because the shop shuts. Ignores the date filter.</p>
          </>
        )}
      </Card>

      <Card className="span-4" title="How accurate is it?" sub="Backtest on the last 13 weeks, model trained without them">
        {fc.data?.available && (
          <>
            <div className="stat-row">
              <div className="stat"><div className="v">{gbp(fc.data.total_next_30d)}</div><div className="l">Forecast, next 30 days</div></div>
              <div className="stat"><div className="v">{pct(fc.data.backtest.mape, 0)}</div><div className="l">Avg weekly error</div></div>
              <div className="stat"><div className="v">{pct(fc.data.backtest.naive_last_year_mape, 0)}</div><div className="l">"Same week last year" error</div></div>
            </div>
            <Legend items={[{ label: "Actual", color: p.series[0] }, { label: "Predicted", color: p.series[1], dashed: true }]} />
            <ResponsiveContainer width="100%" height={170}>
              <ComposedChart data={fc.data.backtest.series} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={p.grid} vertical={false} />
                <XAxis dataKey="date" tickFormatter={shortDay} tick={{ fill: p.axis, fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={20} />
                <YAxis tickFormatter={(v) => gbp(v)} tick={{ fill: p.axis, fontSize: 10 }} axisLine={false} tickLine={false} width={48} />
                <Tooltip content={({ active, payload }) => active && payload?.length ? (
                  <Tip title={`Week of ${dayLabel(String(payload[0].payload.date))}`} rows={[
                    { label: "Actual", value: gbp(Number(payload[0].payload.actual), false), color: p.series[0] },
                    { label: "Predicted", value: gbp(Number(payload[0].payload.predicted), false), color: p.series[1] },
                  ]} />
                ) : null} />
                <Line dataKey="actual" stroke={p.series[0]} strokeWidth={2} dot={false} />
                <Line dataKey="predicted" stroke={p.series[1]} strokeWidth={2} strokeDasharray="5 4" dot={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </>
        )}
      </Card>

      <Card className="span-12" title="Unusual trading days" sub={an.data?.method ?? "Anomaly detection"}>
        <Status loading={an.loading && !an.data} error={an.error} empty={an.data?.series.length === 0} />
        {an.data && an.data.series.length > 0 && (
          <>
            <Legend items={[{ label: "Daily revenue", color: p.series[0] }, { label: "Flagged day", color: p.critical, box: true }]} />
            <ResponsiveContainer width="100%" height={260}>
              <ComposedChart data={an.data.series.map((d) => ({ ...d, flagged: d.anomaly ? d.revenue : null }))} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={p.grid} vertical={false} />
                <XAxis dataKey="date" tickFormatter={shortDay} tick={{ fill: p.axis, fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={32} />
                <YAxis tickFormatter={(v) => gbp(v)} tick={{ fill: p.axis, fontSize: 11 }} axisLine={false} tickLine={false} width={56} />
                <Tooltip cursor={{ stroke: p.axis, strokeDasharray: "3 3" }} content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload as { date: string; revenue: number; anomaly: boolean };
                  const info = an.data!.days.find((x) => x.date === d.date);
                  return <Tip title={dayLabel(d.date)} rows={[
                    { label: "Revenue", value: gbp(d.revenue, false), color: p.series[0] },
                    ...(info ? [{ label: "Flag", value: info.explanation }] : []),
                  ]} />;
                }} />
                <Line dataKey="revenue" stroke={p.series[0]} strokeWidth={1.5} dot={false} isAnimationActive={false} />
                <Scatter dataKey="flagged" fill={p.critical} stroke={p.surface} strokeWidth={2} shape="circle" />
              </ComposedChart>
            </ResponsiveContainer>
            <div className="table-wrap" style={{ marginTop: 12 }}>
              <table className="data">
                <thead><tr><th>Date</th><th className="num">Revenue</th><th className="num">Typical for weekday</th><th className="num">Orders</th><th className="num">Avg order</th><th>Why it was flagged</th></tr></thead>
                <tbody>
                  {an.data.days.slice(0, 12).map((d) => (
                    <tr key={d.date}>
                      <td>{d.weekday} {dayLabel(d.date)}</td>
                      <td className="num">{gbp(d.revenue, false)}</td>
                      <td className="num">{d.typical_revenue ? gbp(d.typical_revenue, false) : "–"}</td>
                      <td className="num">{d.orders}</td>
                      <td className="num">{gbp(d.aov, false)}</td>
                      <td><span className={`delta ${d.direction === "unusually high" ? "up" : "down"}`}>{d.direction === "unusually high" ? "▲" : "▼"}</span> {d.explanation}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
