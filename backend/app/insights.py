"""Automatic insights: turns the analytics and model outputs into plain-English findings.

Rule-based, so it works without an API key. Each insight says what was found,
the number behind it, and (where it makes sense) what to do about it.
"""

from __future__ import annotations

import string
from functools import lru_cache

from . import analytics, ml
from .data import Filters, sales


FULL_DAY = {"Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday",
            "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday"}


def _title(s: str) -> str:
    return string.capwords(s.lower())


def _gbp(x: float) -> str:
    if abs(x) >= 1e6:
        return f"£{x / 1e6:.2f}M"
    if abs(x) >= 1e3:
        return f"£{x / 1e3:.0f}k"
    return f"£{x:,.0f}"


def _pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


@lru_cache(maxsize=32)
def generate(f: Filters) -> list[dict]:
    out: list[dict] = []
    if sales(f).empty:
        return [{"kind": "info", "title": "No sales in this selection", "detail": "Widen the date range or country filter."}]

    k = analytics.kpis(f)
    cur, chg = k["current"], k["change"]
    if k["previous"] and chg.get("revenue") is not None:
        basis = k["previous_period"]["basis"]
        drivers = []
        for key, label in (("orders", "orders"), ("aov", "average order value"), ("customers", "active customers")):
            if chg.get(key) is not None:
                drivers.append(f"{label} {_pct(chg[key])}")
        out.append({
            "kind": "trend" if chg["revenue"] >= 0 else "risk",
            "title": f"Revenue {'up' if chg['revenue'] >= 0 else 'down'} {abs(chg['revenue']) * 100:.1f}% vs {basis}",
            "detail": f"{_gbp(cur['revenue'])} this period against {_gbp(k['previous']['revenue'])}. Drivers: {', '.join(drivers)}.",
        })

    if cur.get("cancellation_rate") is not None and cur["cancellation_rate"] > 0.03:
        out.append({
            "kind": "risk",
            "title": f"{cur['cancellation_rate'] * 100:.1f}% of order value was cancelled",
            "detail": f"{_gbp(cur['cancelled_value'])} in cancelled lines. Check which products and customers cancel most "
                      "(often stock or delivery issues on bulk orders).",
        })

    countries = analytics.countries_breakdown(f, top=50)
    if countries and len(countries) > 1:
        top = countries[0]
        out.append({
            "kind": "info",
            "title": f"{top['country']} is {top['share'] * 100:.0f}% of revenue",
            "detail": "Outside it, the biggest markets are " + ", ".join(
                f"{c['country']} ({_gbp(c['revenue'])})" for c in countries[1:4]) + ".",
        })
        big_aov = max(countries[1:], key=lambda c: c["aov"] if c["orders"] >= 30 else 0)
        if big_aov["orders"] >= 30 and big_aov["aov"] > 2 * top["aov"]:
            out.append({
                "kind": "opportunity",
                "title": f"{big_aov['country']} orders are {big_aov['aov'] / top['aov']:.1f}x larger than {top['country']}'s",
                "detail": f"Average order {_gbp(big_aov['aov'])} from {big_aov['customers']} customers: "
                          "a wholesale-heavy market worth a dedicated account manager.",
            })

    heat = analytics.weekday_hour_heatmap(f)
    if heat:
        by_day: dict[str, float] = {}
        by_hour: dict[int, float] = {}
        for h in heat:
            by_day[h["weekday"]] = by_day.get(h["weekday"], 0) + h["revenue"]
            by_hour[h["hour"]] = by_hour.get(h["hour"], 0) + h["revenue"]
        best_day = max(by_day, key=by_day.get)
        best_hour = max(by_hour, key=by_hour.get)
        out.append({
            "kind": "info",
            "title": f"Peak trading: {FULL_DAY[best_day]}s around {best_hour}:00",
            "detail": "Saturdays are almost empty. Time email campaigns and stock checks for weekday late mornings.",
        })

    prods = analytics.products(f, top=5)
    a_class = next((c for c in prods["abc"] if c["class"] == "A"), None)
    if a_class:
        out.append({
            "kind": "info",
            "title": f"{a_class['product_share'] * 100:.0f}% of products make {a_class['revenue_share'] * 100:.0f}% of revenue",
            "detail": f"{a_class['products']} 'A' products. Protect their stock levels first; review the long tail for delisting.",
        })
    if prods["movers"]["rising"]:
        r = prods["movers"]["rising"][0]
        out.append({
            "kind": "opportunity",
            "title": f"Fastest riser: {_title(r['description'])}",
            "detail": f"{_gbp(r['first_half'])} → {_gbp(r['second_half'])} between the first and second half of the period.",
        })
    if prods["movers"]["falling"]:
        r = prods["movers"]["falling"][0]
        out.append({
            "kind": "risk",
            "title": f"Biggest decline: {_title(r['description'])}",
            "detail": f"{_gbp(r['first_half'])} → {_gbp(r['second_half'])}. Check pricing, stock and whether a newer line replaced it.",
        })

    seg = ml.segments(f)
    champs = next((s for s in seg["segments"] if s["segment"] == "Champions"), None)
    risk = next((s for s in seg["segments"] if s["segment"].startswith("At risk")), None)
    if champs:
        out.append({
            "kind": "info",
            "title": f"Champions: {champs['customer_share'] * 100:.0f}% of customers, {champs['revenue_share'] * 100:.0f}% of revenue",
            "detail": f"{champs['customers']:,} customers with a median of {champs['median_orders']:.0f} orders. {champs['action']}",
        })
    if risk:
        out.append({
            "kind": "risk",
            "title": f"{risk['customers']:,} once-regular customers have gone quiet",
            "detail": f"The 'At risk' segment spent {_gbp(risk['revenue'])} but last ordered a median {risk['median_recency_days']} days ago. {risk['action']}",
        })

    ch = ml.churn(f)
    if ch.get("available"):
        high = next((b for b in ch["bands"] if b["band"] == "High"), None)
        if high:
            out.append({
                "kind": "risk",
                "title": f"{high['customers']:,} active customers are likely to churn",
                "detail": f"Churn model (ROC AUC {ch['metrics']['roc_auc']:.2f}) gives them over 60% probability of no order in the next "
                          f"{ch['window_days']} days. Top driver: {ch['importance'][0]['feature'].lower()}.",
            })

    fc = ml.forecast(f)
    if fc.get("available"):
        reliable = fc["backtest"]["mape"] is not None and fc["backtest"]["mape"] < 0.3
        out.append({
            "kind": "trend" if reliable else "info",
            "title": f"Forecast: {_gbp(fc['total_next_30d'])} in the next 30 days",
            "detail": f"Backtest error {fc['backtest']['mape'] * 100:.0f}% per week"
                      + ("" if reliable else " (too noisy for this selection; treat as a rough guide)") + ".",
        })

    an = ml.anomalies(f)
    if an["days"]:
        d = an["days"][0]
        out.append({
            "kind": "risk" if d["direction"] == "unusually low" else "opportunity",
            "title": f"{len(an['days'])} unusual trading days detected",
            "detail": f"Most unusual: {d['weekday']} {d['date']}. {d['explanation']} Revenue {_gbp(d['revenue'])}"
                      + (f" vs a typical {_gbp(d['typical_revenue'])}." if d.get("typical_revenue") else "."),
        })

    rules = ml.basket_rules(f)
    if rules["rules"]:
        r = rules["rules"][0]
        out.append({
            "kind": "opportunity",
            "title": "Cross-sell: products bought together",
            "detail": f"{r['confidence'] * 100:.0f}% of orders with {_title(r['if_bought'])} also include {_title(r['then_buy'])} "
                      f"({r['lift']:.0f}x more than chance). Bundle or recommend them together.",
        })
    return out
