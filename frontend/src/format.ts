export function gbp(x: number | null | undefined, compact = true): string {
  if (x == null || !Number.isFinite(x)) return "–";
  if (compact) {
    const a = Math.abs(x);
    if (a >= 1e6) return `£${(x / 1e6).toFixed(2)}M`;
    if (a >= 1e4) return `£${(x / 1e3).toFixed(0)}k`;
    if (a >= 1e3) return `£${(x / 1e3).toFixed(1)}k`;
  }
  return `£${x.toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;
}

export function num(x: number | null | undefined, compact = true): string {
  if (x == null || !Number.isFinite(x)) return "–";
  if (compact && Math.abs(x) >= 1e6) return `${(x / 1e6).toFixed(2)}M`;
  if (compact && Math.abs(x) >= 1e4) return `${(x / 1e3).toFixed(0)}k`;
  return x.toLocaleString("en-GB", { maximumFractionDigits: 1 });
}

export function pct(x: number | null | undefined, digits = 1, signed = false): string {
  if (x == null || !Number.isFinite(x)) return "–";
  const s = (x * 100).toFixed(digits);
  return `${signed && x > 0 ? "+" : ""}${s}%`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function monthLabel(iso: string): string {
  const [y, m] = iso.split("-");
  return `${MONTHS[Number(m) - 1]} ${y.slice(2)}`;
}

export function dayLabel(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${Number(d)} ${MONTHS[Number(m) - 1]} ${y}`;
}

export function shortDay(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${Number(d)} ${MONTHS[Number(m) - 1]}`;
}

export function title(s: string): string {
  return s.toLowerCase().replace(/(^|[\s\-/(&+.])([a-z])/g, (_, pre, c) => pre + c.toUpperCase());
}
