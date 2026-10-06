import { useEffect, useState } from "react";

export interface FilterState {
  start: string;
  end: string;
  countries: string[];
}

export function query(f: FilterState, extra: Record<string, string> = {}): string {
  const p = new URLSearchParams(extra);
  if (f.start) p.set("start", f.start);
  if (f.end) p.set("end", f.end);
  if (f.countries.length) p.set("countries", f.countries.join(","));
  const s = p.toString();
  return s ? `?${s}` : "";
}

const KEY_STORAGE = "anthropic-key";

export function storedKey(): string {
  try {
    return localStorage.getItem(KEY_STORAGE) ?? "";
  } catch {
    return "";
  }
}

export function saveKey(k: string) {
  try {
    if (k) localStorage.setItem(KEY_STORAGE, k);
    else localStorage.removeItem(KEY_STORAGE);
  } catch {
    /* storage unavailable: key lives for this page only */
  }
}

function headers(): HeadersInit {
  const k = storedKey();
  return k ? { "X-Anthropic-Key": k } : {};
}

export async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`/api/${path}`, { headers: headers() });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`/api/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export interface Loaded<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

/** Fetch `path` whenever it changes; keeps showing the previous data while reloading. */
export function useApi<T>(path: string | null): Loaded<T> {
  const [state, setState] = useState<Loaded<T>>({ data: null, loading: !!path, error: null });
  useEffect(() => {
    if (!path) return;
    let live = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    getJSON<T>(path)
      .then((data) => live && setState({ data, loading: false, error: null }))
      .catch((e) => live && setState((s) => ({ ...s, loading: false, error: String(e.message ?? e) })));
    return () => {
      live = false;
    };
  }, [path]);
  return state;
}

// ---- response types ---------------------------------------------------------

export interface Meta {
  dataset: string;
  min_date: string;
  max_date: string;
  countries: { name: string; revenue: number }[];
  ai_assistant: boolean;
  server_key: boolean;
  model: string;
}

export interface Summary {
  revenue: number;
  orders: number;
  customers: number;
  units: number;
  aov: number | null;
  products: number;
  cancelled_value: number;
  cancellation_rate: number | null;
}

export interface Kpis {
  period: { start: string; end: string; days: number };
  previous_period: { start: string; end: string; basis: string } | null;
  current: Summary;
  previous: Summary | null;
  change: Partial<Record<keyof Summary, number | null>>;
}

export interface TimePoint {
  date: string;
  revenue: number;
  orders: number;
  customers: number;
  units: number;
  aov?: number;
}

export interface CountryRow {
  country: string;
  revenue: number;
  orders: number;
  customers: number;
  share: number;
  aov: number;
}

export interface HeatCell {
  weekday: string;
  dow: number;
  hour: number;
  revenue: number;
}

export interface ProductRow {
  stock_code: string;
  description: string;
  revenue: number;
  units: number;
  orders: number;
  customers: number;
  avg_price: number;
  abc: string;
}

export interface Mover {
  stock_code: string;
  description: string;
  first_half: number;
  second_half: number;
  delta: number;
}

export interface Products {
  top_by_revenue: ProductRow[];
  top_by_units: ProductRow[];
  abc: { class: string; products: number; revenue: number; product_share: number; revenue_share: number }[];
  pareto: { product_pct: number; revenue_pct: number }[];
  movers: { rising: Mover[]; falling: Mover[] };
}

export interface Cohort {
  cohort: string;
  size: number;
  retention: (number | null)[];
}

export interface Segment {
  segment: string;
  customers: number;
  customer_share: number;
  revenue: number;
  revenue_share: number;
  median_recency_days: number;
  median_orders: number;
  median_spend: number;
  action: string;
}

export interface Segments {
  k: number;
  silhouette: number | null;
  customers: number;
  segments: Segment[];
  scatter: { customer_id: number; recency: number; frequency: number; monetary: number; segment: string }[];
}

export interface Forecast {
  available: boolean;
  history: { date: string; actual: number }[];
  forecast: { date: string; forecast: number; lower: number; upper: number }[];
  backtest: {
    weeks: number;
    mape: number;
    naive_last_year_mape: number;
    series: { date: string; actual: number; predicted: number }[];
  };
  total_next_30d: number;
  total_horizon: number;
  horizon_days: number;
  forecast_start: string;
  model: string;
}

export interface AnomalyDay {
  date: string;
  weekday: string;
  score: number;
  revenue: number;
  orders: number;
  aov: number;
  cancelled: number;
  typical_revenue: number | null;
  driver: string;
  direction: string;
  explanation: string;
}

export interface Anomalies {
  days: AnomalyDay[];
  series: { date: string; revenue: number; anomaly: boolean }[];
  method?: string;
}

export interface Churn {
  available: boolean;
  window_days: number;
  trained_on_cutoff: string;
  base_rate: number;
  metrics: { roc_auc: number; average_precision: number; test_customers: number };
  importance: { feature: string; importance: number }[];
  bands: { band: string; customers: number; spend: number }[];
  scored_customers: number;
  at_risk: {
    customer_id: number;
    country: string;
    churn_prob: number;
    recency: number;
    orders: number;
    spend: number;
    avg_gap_days: number;
    value_at_risk: number;
  }[];
}

export interface Basket {
  invoices: number;
  rules: {
    if_bought: string;
    then_buy: string;
    support: number;
    confidence: number;
    lift: number;
  }[];
}

export interface Insight {
  kind: "trend" | "risk" | "opportunity" | "info";
  title: string;
  detail: string;
}

export interface AskResponse {
  answer: string;
  error?: string;
  model?: string;
  tools?: { tool: string; input: Record<string, unknown>; result: unknown }[];
}
