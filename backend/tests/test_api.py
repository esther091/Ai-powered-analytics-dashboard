"""Smoke and correctness tests. Run from backend/: `pytest -q`."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import assistant
from app.data import Filters, load_all, sales
from app.main import app

client = TestClient(app)


def test_dataset_matches_uci_row_count():
    assert len(load_all()) == 1_067_371


def test_valid_sales_exclude_cancellations_fees_and_bad_rows():
    df = sales(Filters())
    assert not df["Invoice"].str.startswith("C").any()
    assert (df["Quantity"] > 0).all() and (df["Price"] > 0).all()
    assert not df["StockCode"].isin(["POST", "M", "DOT", "BANK CHARGES"]).any()
    assert df["Revenue"].sum() == pytest.approx(19_399_950, rel=1e-4)


@pytest.mark.parametrize("path", [
    "meta", "kpis", "timeseries?freq=W", "yoy", "countries", "heatmap", "products", "cohorts",
    "segments", "forecast", "anomalies", "churn", "basket", "insights",
])
def test_endpoints_respond(path):
    r = client.get(f"/api/{path}")
    assert r.status_code == 200, r.text
    assert r.json()


def test_filters_narrow_results():
    all_time = client.get("/api/kpis").json()["current"]["revenue"]
    de = client.get("/api/kpis?countries=Germany&start=2011-01-01&end=2011-06-30").json()
    assert 0 < de["current"]["revenue"] < all_time
    assert de["previous_period"]["basis"] == "same period last year"


def test_models_are_better_than_chance():
    churn = client.get("/api/churn").json()
    assert churn["metrics"]["roc_auc"] > 0.7
    fc = client.get("/api/forecast").json()
    assert fc["backtest"]["mape"] < 0.3
    seg = client.get("/api/segments").json()
    assert {"Champions", "Hibernating"} <= {s["segment"] for s in seg["segments"]}


def test_query_sales_tool():
    out = assistant.query_sales({"metric": "revenue", "group_by": "country", "top_n": 3})
    assert [r["country"] for r in out["rows"]][0] == "United Kingdom"
    assert len(out["rows"]) == 3 and out["truncated"]
    total = assistant.query_sales({"metric": "orders", "group_by": "none", "start": "2011-11-01", "end": "2011-11-30"})
    assert total["rows"][0]["orders"] > 1000


def test_ask_without_key_is_disabled(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = client.post("/api/ask", json={"question": "hi"}).json()
    assert r["error"] == "no_key"


def test_ask_runs_tool_loop(monkeypatch):
    """The assistant executes Claude's tool calls and returns the final text."""
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            block = SimpleNamespace(type="tool_use", id="t1", name="query_sales",
                                    input={"metric": "revenue", "group_by": "year"})
            return SimpleNamespace(stop_reason="tool_use", content=[block], model="test")
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="2011 was bigger.")], model="test")

    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    monkeypatch.setattr(assistant, "_client", lambda key: fake)
    out = assistant.ask("Which year sold more?")
    assert out["answer"] == "2011 was bigger."
    assert out["tools"][0]["tool"] == "query_sales"
    tool_result = calls[1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and "2011" in tool_result["content"]
    assert calls[0]["model"] == assistant.MODEL
