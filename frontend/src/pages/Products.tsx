import { useState } from "react";
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { query, useApi, type Basket, type FilterState, type Mover, type Products as ProductData } from "../api";
import { Card, Status, Toggle } from "../components/Card";
import { Tip } from "../components/ChartBits";
import { gbp, num, pct, title } from "../format";
import { usePalette } from "../theme";

export function Products({ filters }: { filters: FilterState }) {
  const q = query(filters);
  const prod = useApi<ProductData>(`products${q}`);
  const basket = useApi<Basket>(`basket${q}`);
  const [by, setBy] = useState<"revenue" | "units">("revenue");
  const p = usePalette();
  const rows = prod.data ? (by === "revenue" ? prod.data.top_by_revenue : prod.data.top_by_units) : [];
  const maxV = rows.length ? Math.max(...rows.map((r) => r[by])) : 1;

  return (
    <div className="grid">
      <Card className="span-7" title="Best sellers" sub="Top 20 products"
        actions={<Toggle value={by} onChange={setBy} options={[{ value: "revenue", label: "By revenue" }, { value: "units", label: "By units" }]} />}>
        <Status loading={prod.loading && !prod.data} error={prod.error} empty={prod.data?.top_by_revenue.length === 0} />
        {rows.length > 0 && (
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Product</th><th className="num">{by === "revenue" ? "Revenue" : "Units"}</th><th className="num">Orders</th><th className="num">Customers</th><th className="num">Price</th><th>Class</th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.stock_code}>
                    <td title={r.stock_code}>{title(r.description)}</td>
                    <td className="num bar-cell"><span className="bar" style={{ width: `${(r[by] / maxV) * 100}%`, background: p.series[0] }} /><span>{by === "revenue" ? gbp(r.revenue, false) : num(r.units, false)}</span></td>
                    <td className="num">{num(r.orders, false)}</td>
                    <td className="num">{num(r.customers, false)}</td>
                    <td className="num">£{r.avg_price.toFixed(2)}</td>
                    <td><span className="pill">{r.abc}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card className="span-5" title="Revenue concentration" sub="Pareto curve with ABC classes">
        <Status loading={prod.loading && !prod.data} error={prod.error} />
        {prod.data && prod.data.pareto.length > 0 && (
          <>
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={prod.data.pareto} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={p.grid} vertical={false} />
                <XAxis dataKey="product_pct" type="number" domain={[0, 1]} tickFormatter={(v) => pct(v, 0)} tick={{ fill: p.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 1]} tickFormatter={(v) => pct(v, 0)} tick={{ fill: p.axis, fontSize: 11 }} axisLine={false} tickLine={false} width={40} />
                <ReferenceLine y={0.8} stroke={p.axis} strokeDasharray="3 3" label={{ value: "80% of revenue", fill: p.muted, fontSize: 11, position: "insideBottomRight" }} />
                <Tooltip content={({ active, payload }) => active && payload?.length ? (
                  <Tip title={`Top ${pct(Number(payload[0].payload.product_pct), 0)} of products`} rows={[{ label: "Share of revenue", value: pct(Number(payload[0].payload.revenue_pct)) }]} />
                ) : null} />
                <Area type="monotone" dataKey="revenue_pct" stroke={p.series[0]} strokeWidth={2} fill={p.series[0]} fillOpacity={0.12} />
              </AreaChart>
            </ResponsiveContainer>
            <table className="data" style={{ marginTop: 8 }}>
              <thead><tr><th>Class</th><th className="num">Products</th><th className="num">Share of products</th><th className="num">Share of revenue</th></tr></thead>
              <tbody>
                {prod.data.abc.map((c) => (
                  <tr key={c.class}><td><span className="pill">{c.class}</span></td><td className="num">{num(c.products, false)}</td><td className="num">{pct(c.product_share)}</td><td className="num">{pct(c.revenue_share)}</td></tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </Card>

      <Card className="span-6" title="Rising products" sub="Biggest revenue gain, second half of the period vs first half">
        {prod.data && <MoverTable rows={prod.data.movers.rising} />}
      </Card>
      <Card className="span-6" title="Falling products" sub="Biggest revenue drop, second half vs first half">
        {prod.data && <MoverTable rows={prod.data.movers.falling} />}
      </Card>

      <Card className="span-12" title="Bought together" sub={basket.data ? `Market-basket analysis across ${num(basket.data.invoices, false)} orders. Lift = how many times more often than chance.` : "Market-basket analysis"}>
        <Status loading={basket.loading && !basket.data} error={basket.error} empty={basket.data?.rules.length === 0} />
        {basket.data && basket.data.rules.length > 0 && (
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Customers who buy</th><th>also buy</th><th className="num">Confidence</th><th className="num">Lift</th><th className="num">Orders with both</th></tr></thead>
              <tbody>
                {basket.data.rules.slice(0, 15).map((r) => (
                  <tr key={r.if_bought + r.then_buy}>
                    <td>{title(r.if_bought)}</td><td>{title(r.then_buy)}</td>
                    <td className="num">{pct(r.confidence, 0)}</td><td className="num">{r.lift.toFixed(1)}×</td>
                    <td className="num">{pct(r.support, 1)}</td>
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

function MoverTable({ rows }: { rows: Mover[] }) {
  if (!rows.length) return <div className="empty">Not enough data.</div>;
  return (
    <div className="table-wrap">
      <table className="data">
        <thead><tr><th>Product</th><th className="num">First half</th><th className="num">Second half</th><th className="num">Change</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.stock_code}>
              <td>{title(r.description)}</td>
              <td className="num">{gbp(r.first_half)}</td>
              <td className="num">{gbp(r.second_half)}</td>
              <td className={`num delta ${r.delta >= 0 ? "up" : "down"}`}>{r.delta >= 0 ? "+" : "−"}{gbp(Math.abs(r.delta))}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
