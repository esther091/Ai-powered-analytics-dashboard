import { useEffect, useRef, useState } from "react";
import type { FilterState, Meta } from "../api";
import { gbp } from "../format";

function shift(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export function FilterBar({ meta, value, onChange }: { meta: Meta; value: FilterState; onChange: (f: FilterState) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const max = meta.max_date;
  const presets = [
    { label: "All time", start: "", end: "" },
    { label: "2011", start: "2011-01-01", end: "" },
    { label: "2010", start: "2010-01-01", end: "2010-12-31" },
    { label: "Last 90 days", start: shift(max, -89), end: "" },
    { label: "Q4 2011", start: "2011-10-01", end: "" },
  ];
  const active = presets.find((p) => p.start === value.start && p.end === value.end)?.label;

  const toggleCountry = (c: string) => {
    const has = value.countries.includes(c);
    onChange({ ...value, countries: has ? value.countries.filter((x) => x !== c) : [...value.countries, c] });
  };
  const countryLabel = value.countries.length === 0 ? "All countries" : value.countries.length === 1 ? value.countries[0] : `${value.countries.length} countries`;

  return (
    <div className="filters">
      <div className="field">
        <label>Period</label>
        <div className="presets">
          {presets.map((p) => (
            <button key={p.label} className={`chip ${active === p.label ? "active" : ""}`} onClick={() => onChange({ ...value, start: p.start, end: p.end })}>
              {p.label}
            </button>
          ))}
        </div>
      </div>
      <div className="field">
        <label htmlFor="f-start">From</label>
        <input id="f-start" type="date" min={meta.min_date} max={max} value={value.start || meta.min_date}
          onChange={(e) => onChange({ ...value, start: e.target.value === meta.min_date ? "" : e.target.value })} />
      </div>
      <div className="field">
        <label htmlFor="f-end">To</label>
        <input id="f-end" type="date" min={meta.min_date} max={max} value={value.end || max}
          onChange={(e) => onChange({ ...value, end: e.target.value === max ? "" : e.target.value })} />
      </div>
      <div className="field country-picker" ref={ref}>
        <label>Country</label>
        <button className="chip" style={{ minHeight: 36, borderRadius: 8 }} onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          {countryLabel} ▾
        </button>
        {open && (
          <div className="country-menu">
            <label>
              <input type="checkbox" checked={value.countries.length === 0} onChange={() => onChange({ ...value, countries: [] })} />
              All countries
            </label>
            {meta.countries.map((c) => (
              <label key={c.name}>
                <input type="checkbox" checked={value.countries.includes(c.name)} onChange={() => toggleCountry(c.name)} />
                {c.name}
                <span className="rev">{gbp(c.revenue)}</span>
              </label>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
