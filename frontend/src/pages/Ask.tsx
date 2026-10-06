import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { postJSON, saveKey, storedKey, type AskResponse, type Meta } from "../api";

interface Msg {
  role: "user" | "assistant";
  content: string;
  tools?: AskResponse["tools"];
}

const SUGGESTIONS = [
  "Which countries grew fastest in 2011 compared with 2010?",
  "What were the top 5 products in November 2011?",
  "Which customer segment should we target with a win-back campaign, and how big is it?",
  "How much revenue do you expect over the next month?",
  "What's the average order value on weekdays vs Sundays?",
  "Which products are most often bought with the Regency cakestand?",
];

const TOOL_LABEL: Record<string, string> = {
  query_sales: "queried sales",
  get_kpis: "read KPIs",
  get_customer_segments: "read segments",
  get_churn_risk: "read churn model",
  get_forecast: "read forecast",
  get_anomalies: "read anomalies",
  get_product_associations: "read basket rules",
  get_auto_insights: "read insights",
};

export function Ask({ meta, onKeyChange }: { meta: Meta; onKeyChange: () => void }) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [key, setKey] = useState(storedKey());
  const endRef = useRef<HTMLDivElement>(null);
  const enabled = meta.server_key || !!storedKey();

  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }), [msgs, busy]);

  async function send(text: string) {
    const question = text.trim();
    if (!question || busy) return;
    const history = msgs.map(({ role, content }) => ({ role, content }));
    setMsgs((m) => [...m, { role: "user", content: question }]);
    setInput("");
    setBusy(true);
    try {
      const res = await postJSON<AskResponse>("ask", { question, history });
      setMsgs((m) => [...m, { role: "assistant", content: res.answer, tools: res.tools }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "assistant", content: `Something went wrong: ${String(e)}` }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid">
      <section className="card span-12 chat">
        <div className="card-head">
          <div>
            <h2>Ask the data</h2>
            <div className="sub">Claude answers by running read-only queries and the dashboard's models, then explains the numbers. Model: {meta.model}.</div>
          </div>
          {msgs.length > 0 && <div className="actions"><button className="chip" onClick={() => setMsgs([])}>New conversation</button></div>}
        </div>

        {!meta.server_key && (
          <div className="warn-box">
            <div style={{ marginBottom: 8 }}>
              {enabled ? "Using the API key saved in this browser." : "Ask the data uses the Claude API. Paste an Anthropic API key to switch it on (or set ANTHROPIC_API_KEY on the server)."}
              {" "}The key is kept in this browser only and sent to your own API server with each question.
            </div>
            <div className="key-box">
              <input type="password" placeholder="sk-ant-…" value={key} onChange={(e) => setKey(e.target.value)} aria-label="Anthropic API key" />
              <button className="btn" onClick={() => { saveKey(key.trim()); onKeyChange(); }}>Save key</button>
              {storedKey() && <button className="btn secondary" onClick={() => { saveKey(""); setKey(""); onKeyChange(); }}>Remove</button>}
            </div>
          </div>
        )}

        <div className="chat-log">
          {msgs.length === 0 && (
            <div>
              <p style={{ color: "var(--text-2)", marginTop: 0 }}>Try one of these:</p>
              <div className="suggestions">
                {SUGGESTIONS.map((s) => <button key={s} className="chip" disabled={!enabled} onClick={() => send(s)}>{s}</button>)}
              </div>
            </div>
          )}
          {msgs.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              {m.role === "user" ? m.content : (
                <>
                  <div className="md"><ReactMarkdown>{m.content}</ReactMarkdown></div>
                  {m.tools && m.tools.length > 0 && (
                    <div className="tool-trace">
                      Checked: {m.tools.map((t, j) => <code key={j} title={JSON.stringify(t.input)}>{TOOL_LABEL[t.tool] ?? t.tool}</code>).reduce<React.ReactNode[]>((a, c, j) => (j ? [...a, " ", c] : [c]), [])}
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
          {busy && <div className="msg assistant"><div className="md thinking">Analysing…</div></div>}
          <div ref={endRef} />
        </div>

        <form className="composer" onSubmit={(e) => { e.preventDefault(); send(input); }}>
          <textarea rows={1} value={input} disabled={!enabled} placeholder={enabled ? "Ask anything about sales, products or customers…" : "Add an API key above to start"}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }} />
          <button className="btn" type="submit" disabled={!enabled || busy || !input.trim()}>Ask</button>
        </form>
      </section>
    </div>
  );
}
