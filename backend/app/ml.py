"""Machine-learning features. None of these need an API key.

- Customer segmentation: RFM features clustered with K-means.
- Revenue forecast: gradient-boosted trees on calendar features, with
  quantile models for an 80% interval and a hold-out backtest.
- Anomaly detection: Isolation Forest over daily trading metrics.
- Churn risk: a classifier trained on a historical cut-off, then used to score
  every active customer today.
- Market basket: product-pair association rules (support, confidence, lift).
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.cluster import KMeans
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor, IsolationForest
from sklearn.inspection import permutation_importance
from sklearn.metrics import average_precision_score, roc_auc_score, silhouette_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from .analytics import _r
from .data import Filters, cancellations, sales

SEED = 42


# ---------------------------------------------------------------- segmentation

def rfm_table(df: pd.DataFrame, as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    df = df.dropna(subset=["CustomerID"])
    as_of = as_of or df["InvoiceDate"].max() + pd.Timedelta(days=1)
    g = df.groupby("CustomerID").agg(
        last=("InvoiceDate", "max"), first=("InvoiceDate", "min"),
        frequency=("Invoice", "nunique"), monetary=("Revenue", "sum"),
    )
    g["recency"] = (as_of - g["last"]).dt.days
    g["tenure"] = (as_of - g["first"]).dt.days
    return g[g["monetary"] > 0]


# Segment names come from each cluster's centroid profile, so they stay stable
# whatever order K-means happens to return clusters in.
def _name_segments(centers: pd.DataFrame, overall: pd.DataFrame) -> dict[int, str]:
    c = centers.copy()
    c["score"] = -c["recency"].rank() + c["frequency"].rank() + c["monetary"].rank()
    order = c.sort_values("score", ascending=False).index.tolist()
    names = {order[0]: "Champions", order[-1]: "Hibernating"}
    rec_med, freq_med = overall["recency"].median(), overall["frequency"].median()
    for idx in order[1:-1]:
        recent = c.loc[idx, "recency"] <= rec_med
        frequent = c.loc[idx, "frequency"] > freq_med
        if recent:
            names[idx] = "Loyal" if frequent else "New & promising"
        else:
            names[idx] = "At risk" if frequent else "Needs attention"
    seen: dict[str, int] = {}
    for idx in order:  # disambiguate if two clusters share a profile
        n = names[idx]
        seen[n] = seen.get(n, 0) + 1
        if seen[n] > 1:
            names[idx] = f"{n} ({seen[n]})"
    return names


SEGMENT_ACTIONS = {
    "Champions": "Reward them: early access, loyalty perks, referral asks. Avoid discounting.",
    "Loyal": "Upsell higher-value ranges and bundles; invite to a loyalty tier.",
    "Promising": "Nurture with recommendations based on what they bought.",
    "New & promising": "Onboard: a second-order incentive within 30 days locks in the habit.",
    "Needs attention": "Personalised re-engagement before they drift into Hibernating.",
    "At risk": "Win-back campaign now: they used to buy often but have gone quiet.",
    "Hibernating": "Low-cost reactivation only; exclude from expensive campaigns.",
}


@lru_cache(maxsize=32)
def segments(f: Filters, k: int | None = None) -> dict:
    rfm = rfm_table(sales(f))
    if len(rfm) < 20:
        return {"k": 0, "segments": [], "scatter": [], "silhouette": None, "customers": 0}
    X = np.log1p(rfm[["recency", "frequency", "monetary"]].clip(lower=0))
    Xs = StandardScaler().fit_transform(X)

    # Choose k by silhouette score on a sample (4 to 6 clusters keeps it actionable).
    scores = {}
    rng = np.random.default_rng(SEED)
    sample = rng.choice(len(Xs), size=min(3000, len(Xs)), replace=False)
    for kk in ([k] if k else [4, 5, 6]):
        km = KMeans(n_clusters=kk, n_init=10, random_state=SEED).fit(Xs)
        scores[kk] = (silhouette_score(Xs[sample], km.labels_[sample]), km)
    best_k = max(scores, key=lambda kk: scores[kk][0])
    sil, km = scores[best_k]
    rfm["cluster"] = km.labels_
    centers = rfm.groupby("cluster")[["recency", "frequency", "monetary"]].median()
    names = _name_segments(centers, rfm)
    rfm["segment"] = rfm["cluster"].map(names)

    total_rev = rfm["monetary"].sum()
    seg = rfm.groupby("segment").agg(
        customers=("monetary", "size"), revenue=("monetary", "sum"),
        recency=("recency", "median"), frequency=("frequency", "median"), monetary=("monetary", "median"),
    ).sort_values("revenue", ascending=False)
    pts = rfm.sample(n=min(1500, len(rfm)), random_state=SEED)
    return {
        "k": int(best_k),
        "silhouette": _r(sil, 3),
        "customers": int(len(rfm)),
        "segments": [
            {"segment": s, "customers": int(r.customers), "customer_share": _r(r.customers / len(rfm), 4),
             "revenue": _r(r.revenue), "revenue_share": _r(r.revenue / total_rev, 4),
             "median_recency_days": int(r.recency), "median_orders": _r(r.frequency, 1),
             "median_spend": _r(r.monetary), "action": SEGMENT_ACTIONS.get(s, "")}
            for s, r in seg.iterrows()
        ],
        "scatter": [
            {"customer_id": int(cid), "recency": int(r.recency), "frequency": int(r.frequency),
             "monetary": _r(r.monetary), "segment": r.segment}
            for cid, r in pts.iterrows()
        ],
    }


# -------------------------------------------------------------------- forecast

def _calendar(idx: pd.DatetimeIndex) -> pd.DataFrame:
    doy = idx.dayofyear.to_numpy()
    xmas = pd.to_datetime([f"{y}-12-25" for y in idx.year])
    return pd.DataFrame({
        "dow": idx.dayofweek, "month": idx.month, "dom": idx.day,
        "doy_sin": np.sin(2 * np.pi * doy / 365.25), "doy_cos": np.cos(2 * np.pi * doy / 365.25),
        "days_to_xmas": np.clip((xmas - idx).days.to_numpy(), -10, 120),
    }, index=idx)


def _daily(f: Filters) -> pd.Series:
    df = sales(f.without_dates())
    s = df.groupby("Date")["Revenue"].sum()
    full = pd.date_range(s.index.min(), s.index.max(), freq="D")
    return s.reindex(full, fill_value=0.0)


def _weekly(s: pd.Series) -> pd.Series:
    return s.resample("W-MON", label="left", closed="left").sum()


def _predict(history: pd.Series, idx: pd.DatetimeIndex) -> pd.Series:
    """Blend of two models, which beat either alone in backtests:
    1. gradient-boosted trees on calendar features (learns weekday and holiday shape);
    2. seasonal naive: the same weekday 52 weeks earlier, scaled by the trailing
       91-day year-over-year growth rate.
    """
    gbm = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=15,
                                        min_samples_leaf=10, random_state=SEED)
    gbm.fit(_calendar(history.index), history)
    p_gbm = gbm.predict(_calendar(idx)).clip(min=0)
    full = history.reindex(pd.date_range(history.index.min(), idx.max(), freq="D"))
    last_year = full.shift(364).reindex(idx).to_numpy()
    recent, prior = history.iloc[-91:].sum(), history.shift(364).iloc[-91:].sum()
    growth = recent / prior if prior > 0 else 1.0
    p_naive = np.where(np.isnan(last_year), p_gbm, last_year * growth)
    return pd.Series((p_gbm + p_naive) / 2, index=idx)


@lru_cache(maxsize=16)
def forecast(f: Filters, horizon: int = 90, holdout: int = 91) -> dict:
    """Weekly revenue forecast. Ignores the date filter: a forecast needs full history."""
    y = _daily(f)
    if len(y) < 400:
        return {"available": False}

    # Backtest: fit on everything before the last `holdout` days, predict them.
    train, test = y.iloc[:-holdout], y.iloc[-holdout:]
    bt = _predict(train, test.index)
    days = test.resample("W-MON", label="left", closed="left").count()
    full_weeks = days[days >= 5].index
    wk_true, wk_pred = _weekly(test)[full_weeks], _weekly(bt)[full_weeks]
    wk_naive = _weekly(pd.Series(train.reindex(test.index - pd.Timedelta(days=364)).to_numpy(), index=test.index))[full_weeks]
    pct_err = (wk_pred - wk_true) / wk_true.replace(0, np.nan)
    mape = float(pct_err.abs().mean())
    naive_mape = float(((wk_naive - wk_true).abs() / wk_true.replace(0, np.nan)).mean())
    spread = 1.28 * float(np.sqrt((pct_err ** 2).mean()))  # ~80% band from backtest error

    future_idx = pd.date_range(y.index.max() + pd.Timedelta(days=1), periods=horizon, freq="D")
    fut_daily = _predict(y, future_idx)
    fut = _weekly(fut_daily)
    fut = fut[fut.index >= future_idx[0]]  # skip the stub week that overlaps actuals
    hist = _weekly(y.iloc[-182:])
    return {
        "available": True,
        "granularity": "week",
        "history": [{"date": str(d.date()), "actual": _r(v)} for d, v in hist.items()],
        "forecast": [{"date": str(d.date()), "forecast": _r(v), "lower": _r(v * max(0, 1 - spread)),
                      "upper": _r(v * (1 + spread))} for d, v in fut.items()],
        "backtest": {
            "weeks": int(len(full_weeks)),
            "mape": _r(mape, 4),
            "naive_last_year_mape": _r(naive_mape, 4),
            "series": [{"date": str(d.date()), "actual": _r(wk_true[d]), "predicted": _r(wk_pred[d])} for d in full_weeks],
        },
        "total_next_30d": _r(fut_daily.iloc[:30].sum()),
        "total_horizon": _r(fut_daily.sum()),
        "horizon_days": horizon,
        "forecast_start": str(future_idx[0].date()),
        "model": "Blend of gradient-boosted trees on calendar features and a growth-adjusted seasonal naive; "
                 "band is +/-1.28x the backtest's RMS weekly % error (about 80%).",
    }


# ------------------------------------------------------------------- anomalies

@lru_cache(maxsize=32)
def anomalies(f: Filters, contamination: float = 0.03) -> dict:
    df = sales(f)
    if df.empty:
        return {"days": [], "series": []}
    canc = cancellations(f)
    d = df.groupby("Date").agg(revenue=("Revenue", "sum"), orders=("Invoice", "nunique"),
                               customers=("CustomerID", "nunique"), units=("Quantity", "sum"))
    d["aov"] = d["revenue"] / d["orders"]
    d["cancelled"] = canc.groupby("Date")["Revenue"].sum().abs().reindex(d.index).fillna(0)
    # Compare each day with the typical level for that weekday over the surrounding weeks.
    base = d.groupby(d.index.dayofweek)["revenue"].transform(lambda s: s.rolling(9, center=True, min_periods=3).median())
    d["rev_vs_typical"] = d["revenue"] / base
    feats = ["revenue", "orders", "aov", "units", "cancelled", "rev_vs_typical"]
    X = np.log1p(d[feats].clip(lower=0).fillna(0))
    if len(d) < 30:
        return {"days": [], "series": []}
    iso = IsolationForest(contamination=contamination, random_state=SEED).fit(X)
    d["score"] = -iso.score_samples(X)
    d["anomaly"] = iso.predict(X) == -1
    z = (X - X.mean()) / X.std(ddof=0)

    labels = {"revenue": "revenue", "orders": "order count", "aov": "average order value",
              "units": "units sold", "cancelled": "cancellations", "rev_vs_typical": "revenue vs typical weekday"}
    out = []
    for day, r in d[d["anomaly"]].sort_values("score", ascending=False).iterrows():
        zz = z.loc[day]
        driver = zz.abs().idxmax()
        direction = "unusually high" if zz[driver] > 0 else "unusually low"
        out.append({
            "date": str(day.date()), "weekday": day.strftime("%a"), "score": _r(r.score, 3),
            "revenue": _r(r.revenue), "orders": int(r.orders), "aov": _r(r.aov), "cancelled": _r(r.cancelled),
            "typical_revenue": _r(r.revenue / r.rev_vs_typical) if r.rev_vs_typical else None,
            "driver": labels[driver], "direction": direction,
            "explanation": f"{labels[driver].capitalize()} was {direction} ({zz[driver]:+.1f} SD).",
        })
    return {
        "days": out,
        "series": [{"date": str(day.date()), "revenue": _r(r.revenue), "anomaly": bool(r.anomaly)} for day, r in d.iterrows()],
        "method": "Isolation Forest over daily revenue, orders, AOV, units, cancellations and revenue vs typical weekday",
    }


# ----------------------------------------------------------------------- churn

CHURN_WINDOW = 90
CHURN_FEATURES = ["recency", "frequency", "monetary", "tenure", "aov", "avg_gap", "products", "cancel_rate", "recent_90d_spend"]
FEATURE_LABELS = {
    "recency": "Days since last order", "frequency": "Number of orders", "monetary": "Total spend",
    "tenure": "Days since first order", "aov": "Average order value", "avg_gap": "Average days between orders",
    "products": "Distinct products bought", "cancel_rate": "Share of value cancelled",
    "recent_90d_spend": "Spend in the last 90 days",
}


def _churn_features(df: pd.DataFrame, canc: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    df = df[df["InvoiceDate"] < as_of].dropna(subset=["CustomerID"])
    canc = canc[canc["InvoiceDate"] < as_of].dropna(subset=["CustomerID"])
    g = rfm_table(df, as_of)
    inv = df.groupby(["CustomerID", "Invoice"])["InvoiceDate"].min().reset_index().sort_values("InvoiceDate")
    gaps = inv.groupby("CustomerID")["InvoiceDate"].apply(lambda s: s.diff().dt.days.mean())
    g["aov"] = g["monetary"] / g["frequency"]
    g["avg_gap"] = gaps.reindex(g.index).fillna(g["tenure"])
    g["products"] = df.groupby("CustomerID")["StockCode"].nunique().reindex(g.index)
    cval = canc.groupby("CustomerID")["Revenue"].sum().abs().reindex(g.index).fillna(0)
    g["cancel_rate"] = cval / (g["monetary"] + cval)
    recent = df[df["InvoiceDate"] >= as_of - pd.Timedelta(days=90)]
    g["recent_90d_spend"] = recent.groupby("CustomerID")["Revenue"].sum().reindex(g.index).fillna(0)
    return g


@lru_cache(maxsize=16)
def churn(f: Filters) -> dict:
    """Probability each customer makes no purchase in the next 90 days."""
    df, canc = sales(f.without_dates()), cancellations(f.without_dates())
    end = df["InvoiceDate"].max().normalize() + pd.Timedelta(days=1)
    cutoff = end - pd.Timedelta(days=CHURN_WINDOW)

    train = _churn_features(df, canc, cutoff)
    future_buyers = set(df.loc[(df["InvoiceDate"] >= cutoff), "CustomerID"].dropna().unique())
    train["churned"] = (~train.index.isin(future_buyers)).astype(int)
    if len(train) < 200 or train["churned"].nunique() < 2:
        return {"available": False}

    Xtr, Xte, ytr, yte = train_test_split(train[CHURN_FEATURES], train["churned"], test_size=0.25,
                                          random_state=SEED, stratify=train["churned"])
    model = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.05, max_leaf_nodes=15, random_state=SEED)
    model.fit(Xtr, ytr)
    p = model.predict_proba(Xte)[:, 1]
    auc, ap = roc_auc_score(yte, p), average_precision_score(yte, p)
    imp = permutation_importance(model, Xte, yte, scoring="roc_auc", n_repeats=5, random_state=SEED)

    final = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.05, max_leaf_nodes=15, random_state=SEED)
    final.fit(train[CHURN_FEATURES], train["churned"])

    now = _churn_features(df, canc, end)
    # Only score customers still plausibly active (bought within the last year).
    now = now[now["recency"] <= 365].copy()
    now["churn_prob"] = final.predict_proba(now[CHURN_FEATURES])[:, 1]
    now["value_at_risk"] = now["churn_prob"] * now["monetary"] / max(now["tenure"].median(), 1) * 365 / 2
    countries = df.dropna(subset=["CustomerID"]).groupby("CustomerID")["Country"].agg(lambda s: s.iat[-1])
    bands = pd.cut(now["churn_prob"], [0, 0.3, 0.6, 1.0], labels=["Low", "Medium", "High"], include_lowest=True)

    top = now.sort_values("value_at_risk", ascending=False).head(25)
    return {
        "available": True,
        "window_days": CHURN_WINDOW,
        "trained_on_cutoff": str(cutoff.date()),
        "base_rate": _r(train["churned"].mean(), 4),
        "metrics": {"roc_auc": _r(auc, 3), "average_precision": _r(ap, 3), "test_customers": int(len(yte))},
        "importance": sorted(
            [{"feature": FEATURE_LABELS[c], "importance": _r(max(m, 0), 4)} for c, m in zip(CHURN_FEATURES, imp.importances_mean)],
            key=lambda d: -d["importance"]),
        "bands": [{"band": str(b), "customers": int(n), "spend": _r(now.loc[bands == b, "monetary"].sum())}
                  for b, n in bands.value_counts().reindex(["Low", "Medium", "High"]).items()],
        "scored_customers": int(len(now)),
        "at_risk": [
            {"customer_id": int(cid), "country": str(countries.get(cid, "")), "churn_prob": _r(r.churn_prob, 3),
             "recency": int(r.recency), "orders": int(r.frequency), "spend": _r(r.monetary),
             "avg_gap_days": _r(r.avg_gap, 1), "value_at_risk": _r(r.value_at_risk)}
            for cid, r in top.iterrows()
        ],
    }


# ---------------------------------------------------------------------- basket

@lru_cache(maxsize=16)
def basket_rules(f: Filters, top_products: int = 400, min_support: float = 0.008, n: int = 40) -> dict:
    df = sales(f)
    if df.empty:
        return {"rules": [], "invoices": 0}
    keep = df["StockCode"].value_counts().head(top_products).index
    d = df[df["StockCode"].isin(keep)][["Invoice", "StockCode"]].drop_duplicates()
    inv_codes, inv_idx = np.unique(d["Invoice"].to_numpy(), return_inverse=True)
    prod_codes, prod_idx = np.unique(d["StockCode"].astype(str).to_numpy(), return_inverse=True)
    M = sparse.csr_matrix((np.ones(len(d), dtype=np.float32), (inv_idx, prod_idx)),
                          shape=(len(inv_codes), len(prod_codes)))
    n_inv = df["Invoice"].nunique()
    co = (M.T @ M).toarray()
    support_single = np.diag(co) / n_inv
    np.fill_diagonal(co, 0)
    pair_support = co / n_inv
    i, j = np.where(pair_support >= min_support)
    conf = pair_support[i, j] / support_single[i]
    lift = conf / support_single[j]
    desc = df.drop_duplicates("StockCode").set_index(df.drop_duplicates("StockCode")["StockCode"].astype(str))["Description"]
    rules = pd.DataFrame({"a": prod_codes[i], "b": prod_codes[j], "support": pair_support[i, j],
                          "confidence": conf, "lift": lift})
    rules = rules.sort_values(["lift", "confidence"], ascending=False)
    # Keep one direction per pair (the higher-confidence one) for the top list.
    rules["pair"] = rules.apply(lambda r: tuple(sorted((r.a, r.b))), axis=1)
    top = rules.sort_values("confidence", ascending=False).drop_duplicates("pair").sort_values("lift", ascending=False).head(n)
    return {
        "invoices": int(n_inv),
        "min_support": min_support,
        "rules": [
            {"if_bought": str(desc.get(r.a, r.a)), "if_code": r.a, "then_buy": str(desc.get(r.b, r.b)), "then_code": r.b,
             "support": _r(r.support, 4), "confidence": _r(r.confidence, 3), "lift": _r(r.lift, 2)}
            for r in top.itertuples()
        ],
    }
