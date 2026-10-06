import { useEffect, useMemo, useState } from "react";
import { getJSON, type FilterState, type Meta } from "./api";
import { FilterBar } from "./components/FilterBar";
import { Ask } from "./pages/Ask";
import { Customers } from "./pages/Customers";
import { Overview } from "./pages/Overview";
import { Predictions } from "./pages/Predictions";
import { Products } from "./pages/Products";
import { Sales } from "./pages/Sales";
import { palettes, ThemeContext } from "./theme";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "sales", label: "Sales" },
  { id: "products", label: "Products" },
  { id: "customers", label: "Customers", ai: true },
  { id: "predictions", label: "Forecast & anomalies", ai: true },
  { id: "ask", label: "Ask the data", ai: true },
] as const;
type TabId = (typeof TABS)[number]["id"];

function initialTab(): TabId {
  const h = window.location.hash.slice(1);
  return (TABS.find((t) => t.id === h)?.id ?? "overview") as TabId;
}

type ThemePref = "system" | "light" | "dark";

function useTheme() {
  const [pref, setPref] = useState<ThemePref>(() => {
    try { return (localStorage.getItem("theme") as ThemePref) || "system"; } catch { return "system"; }
  });
  const [systemDark, setSystemDark] = useState(() => window.matchMedia("(prefers-color-scheme: dark)").matches);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const on = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  useEffect(() => {
    if (pref === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", pref);
    try { localStorage.setItem("theme", pref); } catch { /* ignore */ }
  }, [pref]);
  const dark = pref === "dark" || (pref === "system" && systemDark);
  return { dark, cycle: () => setPref(dark ? "light" : "dark") };
}

export default function App() {
  const [tab, setTab] = useState<TabId>(initialTab);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterState>({ start: "2011-01-01", end: "", countries: [] });
  const [keyVersion, setKeyVersion] = useState(0);
  const theme = useTheme();
  const palette = useMemo(() => (theme.dark ? palettes.dark : palettes.light), [theme.dark]);

  useEffect(() => {
    const onHash = () => setTab(initialTab());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    getJSON<Meta>("meta").then(setMeta).catch((e) => setMetaError(String(e.message ?? e)));
  }, [keyVersion]);

  const go = (id: TabId) => {
    setTab(id);
    window.history.replaceState(null, "", `#${id}`);
  };

  return (
    <ThemeContext.Provider value={palette}>
      <div className="app">
        <header className="topbar">
          <div className="brand">
            <div className="brand-mark" aria-hidden>
              <svg width="18" height="18" viewBox="0 0 32 32"><path d="M8 24V15M14 24V9M20 24v-7M26 24V12" stroke="#fff" strokeWidth="3.4" strokeLinecap="round" /></svg>
            </div>
            <div>
              <h1>Retail Analytics</h1>
              <p>{meta ? `${meta.dataset} · ${meta.min_date} to ${meta.max_date}` : "AI-powered dashboard"}</p>
            </div>
          </div>
          <button className="icon-btn" onClick={theme.cycle} aria-label="Toggle dark mode">{theme.dark ? "☀ Light" : "☾ Dark"}</button>
        </header>

        <nav className="tabs" role="tablist">
          {TABS.map((t) => (
            <button key={t.id} role="tab" aria-selected={tab === t.id} className={`tab ${tab === t.id ? "active" : ""}`} onClick={() => go(t.id)}>
              {t.label}{"ai" in t && t.ai && <span className="ai-dot">AI</span>}
            </button>
          ))}
        </nav>

        {metaError && <div className="error-box" style={{ marginTop: 16 }}>Can't reach the API ({metaError}). Start it with <code>uvicorn app.main:app</code> in <code>backend/</code>.</div>}

        {meta && (
          <>
            {tab !== "ask" ? <FilterBar meta={meta} value={filters} onChange={setFilters} /> : <div style={{ height: 16 }} />}
            {tab === "overview" && <Overview filters={filters} onAsk={() => go("ask")} />}
            {tab === "sales" && <Sales filters={filters} />}
            {tab === "products" && <Products filters={filters} />}
            {tab === "customers" && <Customers filters={filters} />}
            {tab === "predictions" && <Predictions filters={filters} />}
            {tab === "ask" && <Ask meta={meta} onKeyChange={() => setKeyVersion((v) => v + 1)} />}
          </>
        )}

        <footer className="footer">
          Data: Online Retail II, UCI Machine Learning Repository (Chen, 2019), CC BY 4.0. Revenue counts valid product sales only: cancellations, postage, fees and duplicates are excluded.
        </footer>
      </div>
    </ThemeContext.Provider>
  );
}
