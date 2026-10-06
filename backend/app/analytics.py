"""Descriptive analytics: KPIs, trends, products, countries, cohorts."""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from .data import Filters, cancellations, date_bounds, sales

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _r(x, n: int = 2):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), n)


def _summary(df: pd.DataFrame, canc: pd.DataFrame) -> dict:
    orders = df["Invoice"].nunique()
    revenue = df["Revenue"].sum()
    gross_with_canc = revenue + abs(canc["Revenue"].sum())
    return {
        "revenue": _r(revenue),
        "orders": int(orders),
        "customers": int(df["CustomerID"].nunique()),
        "units": int(df["Quantity"].sum()),
        "aov": _r(revenue / orders) if orders else None,
        "products": int(df["StockCode"].nunique()),
        "cancelled_value": _r(abs(canc["Revenue"].sum())),
        "cancellation_rate": _r(abs(canc["Revenue"].sum()) / gross_with_canc, 4) if gross_with_canc else None,
    }


def _period(f: Filters) -> tuple[pd.Timestamp, pd.Timestamp]:
    lo, hi = date_bounds()
    start = pd.Timestamp(f.start) if f.start else lo.normalize()
    end = pd.Timestamp(f.end) if f.end else hi.normalize()
    return start, end


@lru_cache(maxsize=64)
def kpis(f: Filters) -> dict:
    """Headline numbers for the period plus the same metrics for the prior period of equal length."""
    cur = _summary(sales(f), cancellations(f))
    start, end = _period(f)
    days = (end - start).days + 1
    lo, _ = date_bounds()
    # Retail here is strongly seasonal, so compare with the same dates a year
    # earlier when the data covers them; otherwise with the preceding period.
    yoy_start = start - pd.DateOffset(years=1)
    if yoy_start >= lo.normalize():
        basis = "same period last year"
        prev_f = Filters(start=yoy_start.date(), end=(end - pd.DateOffset(years=1)).date(), countries=f.countries)
    else:
        basis = "previous period"
        prev_f = Filters(start=(start - pd.Timedelta(days=days)).date(),
                         end=(start - pd.Timedelta(days=1)).date(), countries=f.countries)
    prev = None
    if pd.Timestamp(prev_f.start) >= lo.normalize():
        prev = _summary(sales(prev_f), cancellations(prev_f))
    change = {}
    if prev:
        for k, v in cur.items():
            p = prev.get(k)
            change[k] = _r((v - p) / p, 4) if (v is not None and p) else None
    return {
        "period": {"start": str(start.date()), "end": str(end.date()), "days": days},
        "previous_period": {"start": str(prev_f.start), "end": str(prev_f.end), "basis": basis} if prev else None,
        "current": cur,
        "previous": prev,
        "change": change,
    }


@lru_cache(maxsize=64)
def timeseries(f: Filters, freq: str = "M") -> list[dict]:
    rule = {"D": "D", "W": "W-MON", "M": "MS"}[freq]
    df = sales(f)
    g = df.set_index("InvoiceDate").resample(rule, label="left", closed="left")
    out = pd.DataFrame({
        "revenue": g["Revenue"].sum(),
        "orders": g["Invoice"].nunique(),
        "customers": g["CustomerID"].nunique(),
        "units": g["Quantity"].sum(),
    })
    out["aov"] = out["revenue"] / out["orders"].replace(0, np.nan)
    return [
        {"date": str(idx.date()), **{k: _r(v) if k in ("revenue", "aov") else int(v) for k, v in row.items() if pd.notna(v)}}
        for idx, row in out.iterrows()
    ]


@lru_cache(maxsize=64)
def yoy_monthly(f: Filters) -> list[dict]:
    """Revenue by calendar month, one value per year, for year-over-year comparison."""
    df = sales(f.without_dates())  # always every year, so the comparison is complete
    m = df.groupby([df["InvoiceDate"].dt.year.rename("year"), df["InvoiceDate"].dt.month.rename("month")])["Revenue"].sum()
    rows = []
    for month in range(1, 13):
        row = {"month": pd.Timestamp(2000, month, 1).strftime("%b")}
        for year in sorted(m.index.get_level_values(0).unique()):
            if (year, month) in m.index:
                row[str(year)] = _r(m[(year, month)])
        rows.append(row)
    return rows


@lru_cache(maxsize=64)
def countries_breakdown(f: Filters, top: int = 15) -> list[dict]:
    df = sales(f)
    g = df.groupby("Country", observed=True).agg(
        revenue=("Revenue", "sum"), orders=("Invoice", "nunique"), customers=("CustomerID", "nunique"),
    ).sort_values("revenue", ascending=False)
    total = g["revenue"].sum()
    g["share"] = g["revenue"] / total if total else 0
    g["aov"] = g["revenue"] / g["orders"]
    return [
        {"country": str(k), "revenue": _r(r.revenue), "orders": int(r.orders), "customers": int(r.customers),
         "share": _r(r.share, 4), "aov": _r(r.aov)}
        for k, r in g.head(top).iterrows()
    ]


@lru_cache(maxsize=64)
def weekday_hour_heatmap(f: Filters) -> list[dict]:
    df = sales(f)
    g = df.groupby([df["InvoiceDate"].dt.dayofweek.rename("dow"), df["InvoiceDate"].dt.hour.rename("hour")])["Revenue"].sum()
    return [{"weekday": WEEKDAYS[d], "dow": int(d), "hour": int(h), "revenue": _r(v)} for (d, h), v in g.items()]


@lru_cache(maxsize=64)
def products(f: Filters, top: int = 20) -> dict:
    df = sales(f)
    g = df.groupby("StockCode", observed=True).agg(
        description=("Description", "first"),
        revenue=("Revenue", "sum"), units=("Quantity", "sum"),
        orders=("Invoice", "nunique"), customers=("CustomerID", "nunique"), avg_price=("Price", "median"),
    ).sort_values("revenue", ascending=False)
    g = g[g["revenue"] > 0]

    # ABC / Pareto classification: A = top 80% of revenue, B = next 15%, C = last 5%.
    cum = g["revenue"].cumsum() / g["revenue"].sum()
    g["abc"] = np.where(cum <= 0.8, "A", np.where(cum <= 0.95, "B", "C"))
    abc = g.groupby("abc").agg(products=("revenue", "size"), revenue=("revenue", "sum"))
    pareto_points = np.linspace(0, len(g) - 1, 50).astype(int)

    def rows(d: pd.DataFrame) -> list[dict]:
        return [
            {"stock_code": str(k), "description": str(r.description), "revenue": _r(r.revenue), "units": int(r.units),
             "orders": int(r.orders), "customers": int(r.customers), "avg_price": _r(r.avg_price), "abc": r.abc}
            for k, r in d.iterrows()
        ]

    return {
        "top_by_revenue": rows(g.head(top)),
        "top_by_units": rows(g.sort_values("units", ascending=False).head(top)),
        "abc": [{"class": k, "products": int(r.products), "revenue": _r(r.revenue),
                 "product_share": _r(r.products / len(g), 4), "revenue_share": _r(r.revenue / g["revenue"].sum(), 4)}
                for k, r in abc.iterrows()],
        "pareto": [{"product_pct": _r((i + 1) / len(g), 4), "revenue_pct": _r(cum.iat[i], 4)} for i in pareto_points],
        "movers": product_movers(f),
    }


def product_movers(f: Filters, n: int = 8) -> dict:
    """Products whose revenue grew or fell most between the two halves of the period."""
    df = sales(f)
    if df.empty:
        return {"rising": [], "falling": []}
    mid = df["InvoiceDate"].min() + (df["InvoiceDate"].max() - df["InvoiceDate"].min()) / 2
    first = df[df["InvoiceDate"] < mid].groupby("StockCode", observed=True)["Revenue"].sum()
    second = df[df["InvoiceDate"] >= mid].groupby("StockCode", observed=True)["Revenue"].sum()
    both = pd.concat([first.rename("first"), second.rename("second")], axis=1).fillna(0)
    both = both[(both["first"] + both["second"]) > 2000]
    both["delta"] = both["second"] - both["first"]
    desc = df.drop_duplicates("StockCode").set_index("StockCode")["Description"]

    def rows(d: pd.DataFrame) -> list[dict]:
        return [{"stock_code": str(k), "description": str(desc.get(k, "")), "first_half": _r(r["first"]),
                 "second_half": _r(r["second"]), "delta": _r(r["delta"])} for k, r in d.iterrows()]

    return {"rising": rows(both.nlargest(n, "delta")), "falling": rows(both.nsmallest(n, "delta"))}


@lru_cache(maxsize=32)
def cohorts(f: Filters, max_months: int = 12) -> list[dict]:
    """Monthly acquisition cohorts and the share of each cohort that bought again N months later."""
    df = sales(f).dropna(subset=["CustomerID"])
    if df.empty:
        return []
    month = df["InvoiceDate"].dt.year * 12 + df["InvoiceDate"].dt.month - 1
    first = month.groupby(df["CustomerID"]).transform("min")
    t = pd.DataFrame({"cohort": first, "age": month - first, "cust": df["CustomerID"]}).drop_duplicates()
    counts = t.groupby(["cohort", "age"])["cust"].nunique().unstack(fill_value=0)
    last = int(month.max())
    if df["InvoiceDate"].max().day < 28:  # last month is partial: don't show it as a drop in retention
        last -= 1
    out = []
    for cohort, row in counts.iterrows():
        size = row.get(0, 0)
        if size == 0:
            continue
        out.append({
            "cohort": f"{cohort // 12}-{cohort % 12 + 1:02d}", "size": int(size),
            "retention": [_r(row.get(a, 0) / size, 4) if cohort + a <= last else None
                          for a in range(0, max_months + 1)],
        })
    return out
