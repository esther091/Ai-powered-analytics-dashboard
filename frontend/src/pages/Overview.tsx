import { Area, AreaChart, Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { query, useApi, type CountryRow, type FilterState, type Insight, type Kpis, type TimePoint } from "../api";
import { Card, Status } from "../components/Card";
import { Tip } from "../components/ChartBits";
import { InsightList } from "../components/Insights";
import { KpiRow } from "../components/Kpis";
import { gbp, monthLabel, num, pct } from "../format";
import { usePalette } from "../theme";

export function Overview({ filters, onAsk }: { filters: FilterState; onAsk: () => void }) {
  const q = query(filters);
  const kpis = useApi<Kpis>(`kpis${q}`);
  const ts = useApi<TimePoint[]>(`timeseries${query(filters, { freq: "M" })}`);
  const countries = useApi<CountryRow[]>(`countries${q}`);
  const insights = useApi<Insight[]>(`insights${q}`);
  const p = usePalette();

  return (
    <div className="grid">
      <div className="span-12">
        <KpiRow data={kpis.data} />
      </div>

      <Card className="span-12" title="AI insights" sub="Generated from the data and the models on every filter change. No API key needed."
        actions={<button className="chip" onClick={onAsk}>Ask a question →</button>}>
        <Status loading={insights.loading && !insights.data} error={insights.error} />
        {insights.data && <InsightList items={insights.data} limit={8} />}
      </Card>

      <Card className="span-8" title="Monthly revenue" sub="Valid product sales, £. December 2011 is partial (data ends 9 Dec).">
        <Status loading={ts.loading && !ts.data} error={ts.error} empty={ts.data?.length === 0} />
        {ts.data && ts.data.length > 0 && (
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={ts.data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="revFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={p.series[0]} stopOpacity={0.25} />
                  <stop offset="100%" stopColor={p.series[0]} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={p.grid} vertical={false} />
              <XAxis dataKey="date" tickFormatter={monthLabel} tick={{ fill: p.axis, fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={16} />
              <YAxis tickFormatter={(v) => gbp(v)} tick={{ fill: p.axis, fontSize: 11 }} axisLine={false} tickLine={false} width={56} />
              <Tooltip cursor={{ stroke: p.axis, strokeDasharray: "3 3" }}
                content={({ active, payload }) => active && payload?.length ? (
                  <Tip title={monthLabel(String(payload[0].payload.date))} rows={[
                    { label: "Revenue", value: gbp(payload[0].payload.revenue, false), color: p.series[0] },
                    { label: "Orders", value: num(payload[0].payload.orders, false) },
                    { label: "Customers", value: num(payload[0].payload.customers, false) },
                  ]} />
                ) : null} />
              <Area type="monotoneX" dataKey="revenue" stroke={p.series[0]} strokeWidth={2} fill="url(#revFill)" activeDot={{ r: 4, strokeWidth: 2, stroke: p.surface }} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </Card>

      <Card className="span-4" title="Top countries" sub="Share of revenue">
        <Status loading={countries.loading && !countries.data} error={countries.error} empty={countries.data?.length === 0} />
        {countries.data && countries.data.length > 0 && (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={countries.data.slice(0, 8)} layout="vertical" margin={{ top: 0, right: 40, left: 0, bottom: 0 }}>
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="country" width={104} tick={{ fill: p.text, fontSize: 12 }} axisLine={false} tickLine={false} />
              <Tooltip cursor={{ fill: p.grid, opacity: 0.4 }}
                content={({ active, payload }) => active && payload?.length ? (
                  <Tip title={String(payload[0].payload.country)} rows={[
                    { label: "Revenue", value: gbp(payload[0].payload.revenue, false) },
                    { label: "Share", value: pct(payload[0].payload.share) },
                    { label: "Orders", value: num(payload[0].payload.orders, false) },
                    { label: "Avg order", value: gbp(payload[0].payload.aov, false) },
                  ]} />
                ) : null} />
              <Bar dataKey="share" fill={p.series[0]} radius={[0, 4, 4, 0]} barSize={16} isAnimationActive={false}>
                <LabelList dataKey="share" position="right" fill={p.muted} fontSize={11} formatter={(v: unknown) => pct(Number(v), 1)} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </Card>
    </div>
  );
}
