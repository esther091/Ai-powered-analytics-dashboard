# AI-Powered Retail Analytics Dashboard

An analytics dashboard for the [Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii) dataset
(1,067,371 transactions from a UK online gift retailer, Dec 2009 to Dec 2011): a **React** front end on a
**Python (FastAPI)** API that runs the analysis and machine-learning models.

**Analyst write-up:** [reports/findings.md](reports/findings.md) covers data cleaning, the main findings and recommendations.

## What's in it

| Page | What it shows |
|---|---|
| **Overview** | KPIs vs the same period last year, auto-generated AI insights, monthly revenue, top countries |
| **Sales** | Revenue / orders / customers / AOV by day, week or month; year-over-year by month; weekday × hour heatmap; country table |
| **Products** | Best sellers, Pareto curve and ABC classes, rising and falling products, market-basket "bought together" rules |
| **Customers** (AI) | RFM segmentation with K-means, segment map, churn-risk model with drivers, customers to win back, cohort retention |
| **Forecast & anomalies** (AI) | 90-day weekly revenue forecast with an 80% range and backtest, Isolation-Forest unusual-day detection |
| **Ask the data** (AI) | Natural-language questions answered by Claude using read-only tools over the data and the models |

Every page responds to the date-range and country filters.

### The AI features

All of these run locally with scikit-learn; **no API key is needed** except for "Ask the data".

- **Auto insights**: rule-based narrative generated from the KPIs and model outputs on every filter change.
- **Customer segmentation**: recency/frequency/monetary features, log-scaled, K-means with k picked by silhouette score; segments named from their centroid profile, each with a recommended action.
- **Churn prediction**: gradient-boosted classifier trained on behaviour up to 90 days before the data ends and whether each customer bought afterwards (ROC AUC ≈ 0.79 on held-out customers), then applied to today's active customers. Permutation importance explains the drivers.
- **Revenue forecast**: blend of gradient-boosted trees on calendar features and a growth-adjusted seasonal naive, with a 13-week backtest shown next to the "same week last year" baseline.
- **Anomaly detection**: Isolation Forest over daily revenue, orders, AOV, units, cancellations and revenue relative to the typical weekday, with the metric that made each day unusual.
- **Market basket**: pairwise association rules (support, confidence, lift) among the top 400 products.
- **Ask the data**: Claude (`claude-opus-5-5` by default) answers questions by calling a fixed set of read-only tools (`query_sales`, KPIs, segments, churn, forecast, anomalies, basket rules). It never sees raw rows and never writes code that gets executed. Server-side refusal fallbacks are enabled.

## Run it

Requirements: Python 3.11+, Node 20+.

```bash
# 1. API
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 2. Front end (second terminal)
cd frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api to :8000)
```

The cleaned dataset (`data/online_retail_ii.parquet`, 8 MB) is committed, so there is nothing to download.
To rebuild it from source:

```bash
python scripts/prepare_data.py              # downloads from UCI, or a GitHub mirror if UCI is unreachable
python scripts/prepare_data.py --src online_retail_II.xlsx   # or from a local copy
```

### Turning on "Ask the data"

Either set a key on the server before starting it:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

or paste a key on the **Ask the data** page; it is stored in that browser only and sent to your own API with each
question. `CLAUDE_MODEL` overrides the model.

### Single process / Docker

`npm run build` in `frontend/` creates `frontend/dist`, which the API serves at `/`, so one process runs everything:

```bash
docker build -t retail-analytics .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=sk-ant-... retail-analytics   # key optional
```

## Tests

```bash
cd backend && pytest -q        # data checks, every endpoint, model quality floors, the Claude tool loop (mocked)
cd frontend && npm run build   # type-checks and builds
```

## Project layout

```
backend/app/
  data.py        load the Parquet file, apply filters (cached per filter)
  analytics.py   KPIs, time series, countries, heatmap, products/ABC, cohorts
  ml.py          segmentation, forecast, anomalies, churn, market basket
  insights.py    auto-generated findings
  assistant.py   Claude tool-use loop for "Ask the data"
  main.py        FastAPI routes; serves the built front end
frontend/src/
  pages/         Overview, Sales, Products, Customers, Predictions, Ask
  components/    filters, KPI tiles, insight cards, chart helpers
scripts/prepare_data.py   download + clean the raw data
reports/findings.md       analyst write-up
```

## Data and licence

Online Retail II by Daqing Chen, [UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/502/online+retail+ii),
CC BY 4.0. Because UCI blocks some networks, `prepare_data.py`
falls back to the copy bundled in the [`onlineretail2`](https://github.com/allanvc/onlineretail2) R package
(same 1,067,371 rows, included with the donor's permission).
