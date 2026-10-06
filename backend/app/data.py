"""Loading the cleaned dataset and applying dashboard filters."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_PATH = Path(os.environ.get(
    "RETAIL_DATA_PATH",
    Path(__file__).resolve().parents[2] / "data" / "online_retail_ii.parquet",
))


@dataclass(frozen=True)
class Filters:
    """Global dashboard filters. Hashable so results can be cached per filter."""

    start: date | None = None
    end: date | None = None
    countries: tuple[str, ...] = ()

    @classmethod
    def parse(cls, start: str | None, end: str | None, countries: str | None) -> "Filters":
        return cls(
            start=date.fromisoformat(start) if start else None,
            end=date.fromisoformat(end) if end else None,
            countries=tuple(sorted(c.strip() for c in countries.split(",") if c.strip())) if countries else (),
        )

    def without_dates(self) -> "Filters":
        return Filters(countries=self.countries)


@lru_cache(maxsize=1)
def load_all() -> pd.DataFrame:
    """Every row of the dataset, including cancellations and non-product lines."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"{DATA_PATH} not found. Run `python scripts/prepare_data.py` first."
        )
    df = pd.read_parquet(DATA_PATH)
    df["Date"] = df["InvoiceDate"].dt.normalize()
    return df


def _apply(df: pd.DataFrame, f: Filters) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    if f.start:
        mask &= df["InvoiceDate"] >= pd.Timestamp(f.start)
    if f.end:
        mask &= df["InvoiceDate"] < pd.Timestamp(f.end) + pd.Timedelta(days=1)
    if f.countries:
        mask &= df["Country"].isin(f.countries)
    return df[mask]


@lru_cache(maxsize=64)
def sales(f: Filters = Filters()) -> pd.DataFrame:
    """Valid product sales (no cancellations, fees, duplicates or bad prices)."""
    df = load_all()
    return _apply(df[df["IsValidSale"]], f)


@lru_cache(maxsize=64)
def cancellations(f: Filters = Filters()) -> pd.DataFrame:
    df = load_all()
    return _apply(df[df["IsCancellation"] & df["IsProduct"]], f)


def date_bounds() -> tuple[pd.Timestamp, pd.Timestamp]:
    df = sales()
    return df["InvoiceDate"].min(), df["InvoiceDate"].max()


def countries() -> list[dict]:
    rev = sales().groupby("Country", observed=True)["Revenue"].sum().sort_values(ascending=False)
    return [{"name": str(k), "revenue": round(float(v), 2)} for k, v in rev.items()]
