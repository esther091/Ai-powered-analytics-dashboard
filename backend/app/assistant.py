"""'Ask the data': a natural-language analyst built on the Claude API.

Claude never sees raw rows and never writes code that we execute. It answers by
calling a fixed set of read-only tools that run pandas queries and the models
in `ml.py`, then explains the results. Switched on when an Anthropic API key is
available (ANTHROPIC_API_KEY on the server, or a key the user pastes in the UI).
"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

import pandas as pd

from . import analytics, insights, ml
from .analytics import _r
from .data import Filters, cancellations, date_bounds, sales

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
MAX_TOOL_ROUNDS = 8

METRICS = ["revenue", "orders", "customers", "units", "aov", "cancelled_value"]
GROUPS = ["none", "day", "week", "month", "year", "country", "product", "customer", "weekday", "hour"]

_filter_props = {
    "start": {"type": "string", "description": "Inclusive start date, YYYY-MM-DD."},
    "end": {"type": "string", "description": "Inclusive end date, YYYY-MM-DD."},
    "countries": {"type": "array", "items": {"type": "string"}, "description": "Country names, e.g. ['Germany', 'France']."},
}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "query_sales",
        "description": (
            "Aggregate valid sales (cancellations, fees and bad rows already excluded). Returns a table of one metric "
            "grouped by a dimension. Use group_by='none' for a single total. 'product' groups by stock code with its "
            "description; 'customer' by customer ID. Results sorted by the metric descending unless sort says otherwise."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {"type": "string", "enum": METRICS},
                "group_by": {"type": "string", "enum": GROUPS},
                **_filter_props,
                "product_search": {"type": "string", "description": "Case-insensitive substring of the product description."},
                "customer_id": {"type": "integer"},
                "top_n": {"type": "integer", "description": "Max rows to return (default 15, max 60)."},
                "sort": {"type": "string", "enum": ["desc", "asc", "chronological"]},
            },
            "required": ["metric", "group_by"],
        },
    },
    {
        "name": "get_kpis",
        "description": "Headline KPIs for a period (revenue, orders, customers, units, AOV, cancellations) with the change vs the same period last year (or the previous period).",
        "input_schema": {"type": "object", "properties": {**_filter_props}},
    },
    {
        "name": "get_customer_segments",
        "description": "RFM customer segmentation (K-means). Segment sizes, revenue share, typical recency/frequency/spend and a recommended action.",
        "input_schema": {"type": "object", "properties": {**_filter_props}},
    },
    {
        "name": "get_churn_risk",
        "description": "Churn model: accuracy, top drivers, risk bands and the highest value-at-risk customers (probability of no order in the next 90 days).",
        "input_schema": {"type": "object", "properties": {"countries": _filter_props["countries"]}},
    },
    {
        "name": "get_forecast",
        "description": "Weekly revenue forecast for the next 90 days after the data ends, with an 80% band and backtest accuracy.",
        "input_schema": {"type": "object", "properties": {"countries": _filter_props["countries"]}},
    },
    {
        "name": "get_anomalies",
        "description": "Unusual trading days found by an Isolation Forest, with the metric that made each day unusual.",
        "input_schema": {"type": "object", "properties": {**_filter_props}},
    },
    {
        "name": "get_product_associations",
        "description": "Market-basket rules: products frequently bought together (support, confidence, lift). Optionally only rules involving a product.",
        "input_schema": {"type": "object", "properties": {**_filter_props, "product_search": {"type": "string"}}},
    },
    {
        "name": "get_auto_insights",
        "description": "The dashboard's automatically generated findings for a period.",
        "input_schema": {"type": "object", "properties": {**_filter_props}},
    },
]


def _filters(args: dict) -> Filters:
    def d(key):
        v = args.get(key)
        return date.fromisoformat(v) if v else None
    countries = tuple(sorted(args.get("countries") or ()))
    return Filters(start=d("start"), end=d("end"), countries=countries)


def query_sales(args: dict) -> dict:
    metric, group = args["metric"], args["group_by"]
    if metric not in METRICS or group not in GROUPS:
        raise ValueError(f"metric must be one of {METRICS}; group_by one of {GROUPS}")
    f = _filters(args)
    df = cancellations(f) if metric == "cancelled_value" else sales(f)
    if args.get("product_search"):
        df = df[df["Description"].astype(str).str.contains(args["product_search"], case=False, na=False, regex=False)]
    if args.get("customer_id") is not None:
        df = df[df["CustomerID"] == int(args["customer_id"])]
    if df.empty:
        return {"rows": [], "note": "No matching sales."}

    keys = {
        "none": None, "day": df["Date"], "week": df["InvoiceDate"].dt.to_period("W-SUN").dt.start_time,
        "month": df["InvoiceDate"].dt.to_period("M").dt.start_time, "year": df["InvoiceDate"].dt.year,
        "country": df["Country"], "product": df["StockCode"], "customer": df["CustomerID"],
        "weekday": df["InvoiceDate"].dt.dayofweek, "hour": df["InvoiceDate"].dt.hour,
    }
    key = keys[group]
    g = df.groupby(key, observed=True) if key is not None else df.groupby(lambda _: "total")
    agg = {
        "revenue": g["Revenue"].sum(), "orders": g["Invoice"].nunique(), "customers": g["CustomerID"].nunique(),
        "units": g["Quantity"].sum(), "cancelled_value": g["Revenue"].sum().abs(),
    }
    if metric == "aov":
        value = g["Revenue"].sum() / g["Invoice"].nunique()
    else:
        value = agg[metric]
    table = pd.DataFrame({metric: value})
    if group == "product":
        table["description"] = df.groupby("StockCode", observed=True)["Description"].first().reindex(table.index)

    sort = args.get("sort") or ("chronological" if group in ("day", "week", "month", "year", "weekday", "hour") else "desc")
    if sort == "chronological":
        table = table.sort_index()
    else:
        table = table.sort_values(metric, ascending=(sort == "asc"))
    n = min(int(args.get("top_n") or (60 if sort == "chronological" else 15)), 60)
    total_rows = len(table)
    table = table.head(n)

    rows = []
    for idx, r in table.iterrows():
        label = idx
        if group in ("day", "week", "month"):
            label = str(pd.Timestamp(idx).date())
        elif group == "weekday":
            label = analytics.WEEKDAYS[int(idx)]
        elif group == "customer":
            label = int(idx)
        row = {group if group != "none" else "label": label if not isinstance(label, (pd.Timestamp,)) else str(label)}
        if group == "product":
            row["description"] = str(r["description"])
        row[metric] = _r(r[metric]) if metric in ("revenue", "aov", "cancelled_value") else int(r[metric])
        rows.append(row)
    return {"metric": metric, "group_by": group, "rows": rows, "total_groups": total_rows,
            "truncated": total_rows > n}


def run_tool(name: str, args: dict) -> dict:
    f = _filters(args)
    if name == "query_sales":
        return query_sales(args)
    if name == "get_kpis":
        return analytics.kpis(f)
    if name == "get_customer_segments":
        s = ml.segments(f)
        return {k: v for k, v in s.items() if k != "scatter"}
    if name == "get_churn_risk":
        c = ml.churn(f.without_dates())
        return {**c, "at_risk": c.get("at_risk", [])[:15]}
    if name == "get_forecast":
        fc = ml.forecast(f.without_dates())
        return {k: v for k, v in fc.items() if k != "history"}
    if name == "get_anomalies":
        a = ml.anomalies(f)
        return {"method": a.get("method"), "days": a["days"][:20]}
    if name == "get_product_associations":
        rules = ml.basket_rules(f)["rules"]
        q = (args.get("product_search") or "").lower()
        if q:
            rules = [r for r in rules if q in r["if_bought"].lower() or q in r["then_buy"].lower()]
        return {"rules": rules[:25]}
    if name == "get_auto_insights":
        return {"insights": insights.generate(f)}
    raise ValueError(f"Unknown tool {name}")


def system_prompt() -> str:
    lo, hi = date_bounds()
    return f"""You are the analyst behind an analytics dashboard for a UK-based online gift retailer.

Data: the Online Retail II dataset (UCI). Transactions from {lo.date()} to {hi.date()} (the last month is partial).
Currency is GBP (£). Many customers are wholesalers, so order values vary a lot.
Valid sales exclude cancellations (invoices starting with C), postage/fees/adjustment codes, duplicates,
zero or negative prices and two erroneous bulk orders. About 23% of lines have no customer ID; they count towards
revenue and orders but not customer metrics.

How to answer:
- Always get numbers from the tools; never guess or invent figures. Call several tools if needed.
- Lead with the direct answer in one or two sentences, then the supporting numbers, then (if useful) one practical recommendation.
- Keep it short: a few sentences or a compact markdown table. Format money like £12.3k or £1.24M.
- Say plainly when the data cannot answer something (for example profit, marketing spend or stock levels are not in it).
- When you compare periods, say which periods you compared."""


def _client(api_key: str | None):
    import anthropic

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    return anthropic.Anthropic(api_key=key)


def available(api_key: str | None = None) -> bool:
    return bool(api_key or os.environ.get("ANTHROPIC_API_KEY"))


def _create(client, **kwargs):
    """Call Claude with server-side refusal fallbacks; retry once without them if the account rejects the beta."""
    import anthropic

    try:
        return client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
    except anthropic.BadRequestError as e:
        if "fallback" not in str(e).lower():
            raise
        return client.messages.create(**kwargs)


def ask(question: str, history: list[dict] | None = None, api_key: str | None = None) -> dict:
    import anthropic

    client = _client(api_key)
    if client is None:
        return {"error": "no_key", "answer": "Add an Anthropic API key to use Ask the data."}

    messages: list[dict] = []
    for turn in (history or [])[-10:]:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": str(turn["content"])})
    messages.append({"role": "user", "content": question})

    tool_log: list[dict] = []
    try:
        for _ in range(MAX_TOOL_ROUNDS):
            response = _create(
                client, model=MODEL, max_tokens=16000, system=system_prompt(), tools=TOOLS,
                output_config={"effort": "medium"}, messages=messages,
            )
            if response.stop_reason == "refusal":
                return {"answer": "Claude declined to answer that question.", "tools": tool_log}
            if response.stop_reason != "tool_use":
                text = "".join(b.text for b in response.content if b.type == "text").strip()
                return {"answer": text or "(no answer)", "tools": tool_log, "model": response.model}

            # Append the assistant turn unchanged, then every tool result in one user message.
            messages.append({"role": "assistant", "content": response.content})
            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                try:
                    out = run_tool(block.name, dict(block.input or {}))
                    content, is_error = json.dumps(out, default=str)[:30000], False
                    tool_log.append({"tool": block.name, "input": block.input, "result": out})
                except Exception as exc:  # bad arguments: tell Claude so it can retry
                    content, is_error = f"Error: {exc}", True
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": is_error})
            messages.append({"role": "user", "content": results})
        return {"answer": "That needed more steps than allowed; try a narrower question.", "tools": tool_log}
    except anthropic.AuthenticationError:
        return {"error": "auth", "answer": "That API key was rejected. Check it and try again."}
    except anthropic.RateLimitError:
        return {"error": "rate_limit", "answer": "Rate limited by the Claude API. Try again in a minute."}
    except anthropic.APIConnectionError:
        return {"error": "network", "answer": "Couldn't reach the Claude API from the server."}
    except anthropic.APIStatusError as e:
        return {"error": "api", "answer": f"Claude API error ({e.status_code}): {e.message}"}
