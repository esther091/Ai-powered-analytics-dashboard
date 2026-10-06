"""FastAPI service behind the React dashboard."""

from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import analytics, assistant, insights, ml
from .data import Filters, countries, date_bounds, load_all



def warm_cache() -> None:
    """Load data and pre-compute the default views so the first page load is fast."""
    def work():
        load_all()
        lo, hi = date_bounds()
        # All time, plus the dashboard's default view (the latest full calendar year onwards).
        for f in (Filters(start=hi.replace(month=1, day=1).date()), Filters()):
            for fn in (analytics.kpis, analytics.products, analytics.cohorts, ml.segments, ml.forecast,
                       ml.churn, ml.anomalies, ml.basket_rules, insights.generate):
                fn(f)
    threading.Thread(target=work, daemon=True).start()


@asynccontextmanager
async def lifespan(_: FastAPI):
    warm_cache()
    yield


app = FastAPI(title="AI-Powered Retail Analytics API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


def filters(
    start: str | None = Query(None, description="YYYY-MM-DD"),
    end: str | None = Query(None, description="YYYY-MM-DD"),
    countries: str | None = Query(None, description="Comma-separated country names"),
) -> Filters:
    return Filters.parse(start, end, countries)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/meta")
def meta(x_anthropic_key: str | None = Header(None)):
    lo, hi = date_bounds()
    return {
        "dataset": "Online Retail II (UCI Machine Learning Repository)",
        "min_date": str(lo.date()), "max_date": str(hi.date()),
        "countries": countries(),
        "ai_assistant": assistant.available(x_anthropic_key),
        "server_key": assistant.available(None),
        "model": assistant.MODEL,
    }


@app.get("/api/kpis")
async def kpis(f: Filters = Depends(filters)):
    return await run_in_threadpool(analytics.kpis, f)


@app.get("/api/timeseries")
async def timeseries(f: Filters = Depends(filters), freq: str = Query("M", pattern="^[DWM]$")):
    return await run_in_threadpool(analytics.timeseries, f, freq)


@app.get("/api/yoy")
async def yoy(f: Filters = Depends(filters)):
    return await run_in_threadpool(analytics.yoy_monthly, f)


@app.get("/api/countries")
async def countries_view(f: Filters = Depends(filters)):
    return await run_in_threadpool(analytics.countries_breakdown, f, 15)


@app.get("/api/heatmap")
async def heatmap(f: Filters = Depends(filters)):
    return await run_in_threadpool(analytics.weekday_hour_heatmap, f)


@app.get("/api/products")
async def products(f: Filters = Depends(filters)):
    return await run_in_threadpool(analytics.products, f, 20)


@app.get("/api/cohorts")
async def cohorts(f: Filters = Depends(filters)):
    return await run_in_threadpool(analytics.cohorts, f)


@app.get("/api/segments")
async def segments(f: Filters = Depends(filters)):
    return await run_in_threadpool(ml.segments, f)


@app.get("/api/forecast")
async def forecast(f: Filters = Depends(filters)):
    return await run_in_threadpool(ml.forecast, f.without_dates())


@app.get("/api/anomalies")
async def anomalies(f: Filters = Depends(filters)):
    return await run_in_threadpool(ml.anomalies, f)


@app.get("/api/churn")
async def churn(f: Filters = Depends(filters)):
    return await run_in_threadpool(ml.churn, f.without_dates())


@app.get("/api/basket")
async def basket(f: Filters = Depends(filters)):
    return await run_in_threadpool(ml.basket_rules, f)


@app.get("/api/insights")
async def auto_insights(f: Filters = Depends(filters)):
    return await run_in_threadpool(insights.generate, f)


class Turn(BaseModel):
    role: str
    content: str


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[Turn] = []


@app.post("/api/ask")
async def ask(body: AskBody, x_anthropic_key: str | None = Header(None)):
    return await run_in_threadpool(assistant.ask, body.question, [t.model_dump() for t in body.history], x_anthropic_key)


# Serve the built React app (frontend/dist) when it exists, so one process runs everything.
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        file = DIST / path
        if path and file.is_file() and DIST in file.resolve().parents:
            return FileResponse(file)
        return FileResponse(DIST / "index.html")
