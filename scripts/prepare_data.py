"""Download Online Retail II and write a cleaned, typed Parquet file.

Sources, tried in order:
  1. The UCI Machine Learning Repository zip (the original Excel workbook).
  2. The `onlineretail2` R package on GitHub, which bundles the same 1,067,371
     rows with the donor's permission (used when UCI is unreachable).

Usage:
    python scripts/prepare_data.py            # download and build
    python scripts/prepare_data.py --src FILE # build from a local .zip/.xlsx/.rda
"""

from __future__ import annotations

import argparse
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "online_retail_ii.parquet"

UCI_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
MIRROR_URL = "https://raw.githubusercontent.com/allanvc/onlineretail2/master/data/onlineretail2.rda"
EXPECTED_ROWS = 1_067_371

# Stock codes that are fees, adjustments or postage rather than products.
NON_PRODUCT_CODES = {
    "POST", "DOT", "M", "D", "C2", "C3", "CRUK", "BANK CHARGES", "AMAZONFEE",
    "ADJUST", "ADJUST2", "TEST001", "TEST002", "S", "B", "PADS", "SP1002",
    "GIFT", "m",
}


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as resp:  # noqa: S310 (fixed URLs)
        return resp.read()


def _read_excel(raw: bytes) -> pd.DataFrame:
    sheets = pd.read_excel(io.BytesIO(raw), sheet_name=None, dtype={"Invoice": str, "StockCode": str})
    return pd.concat(sheets.values(), ignore_index=True)


def _read_zip(raw: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".xlsx"))
        return _read_excel(zf.read(name))


def _read_rda(path: Path) -> pd.DataFrame:
    import pyreadr  # optional dependency, only needed for the mirror

    return next(iter(pyreadr.read_r(str(path)).values()))


def load_raw(src: str | None) -> pd.DataFrame:
    if src:
        p = Path(src)
        if p.suffix == ".zip":
            return _read_zip(p.read_bytes())
        if p.suffix == ".xlsx":
            return _read_excel(p.read_bytes())
        return _read_rda(p)
    try:
        print("Downloading from UCI ...")
        return _read_zip(_download(UCI_URL))
    except Exception as exc:  # network policy, outage, etc.
        print(f"UCI unavailable ({exc}); using the onlineretail2 GitHub mirror ...")
        tmp = ROOT / "data" / "_onlineretail2.rda"
        tmp.write_bytes(_download(MIRROR_URL))
        try:
            return _read_rda(tmp)
        finally:
            tmp.unlink(missing_ok=True)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={"Customer ID": "CustomerID"})
    df = df[["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "CustomerID", "Country"]].copy()

    df["Invoice"] = df["Invoice"].astype(str).str.strip()
    df["StockCode"] = df["StockCode"].astype(str).str.strip().str.upper()
    df["Description"] = df["Description"].astype("string").str.strip().str.upper()
    df["Quantity"] = df["Quantity"].astype("int32")
    df["Price"] = df["Price"].astype("float64")
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"]).astype("datetime64[s]")
    df["CustomerID"] = df["CustomerID"].astype("Int64")
    df["Country"] = df["Country"].astype(str).str.strip().replace({"EIRE": "Ireland", "RSA": "South Africa", "USA": "United States"})

    df["IsCancellation"] = df["Invoice"].str.startswith("C")
    df["IsProduct"] = ~df["StockCode"].isin({c.upper() for c in NON_PRODUCT_CODES})
    df["Revenue"] = (df["Quantity"] * df["Price"]).round(2)
    df["IsDuplicate"] = df.duplicated(keep="first")

    # A "valid sale" is what every revenue metric in the dashboard counts.
    df["IsValidSale"] = (
        ~df["IsCancellation"] & df["IsProduct"] & ~df["IsDuplicate"]
        & (df["Quantity"] > 0) & (df["Price"] > 0)
    )

    # Two famous erroneous bulk orders (80,995 and 74,215 units) were each
    # cancelled straight away; drop the pairs so they don't distort averages.
    huge = df["Quantity"].abs() >= 74_215
    df.loc[huge, "IsValidSale"] = False

    for col in ("StockCode", "Country", "Description"):
        df[col] = df[col].astype("category")
    return df.reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", help="local .zip, .xlsx or .rda to build from")
    args = ap.parse_args()

    raw = load_raw(args.src)
    if len(raw) != EXPECTED_ROWS:
        print(f"warning: expected {EXPECTED_ROWS:,} rows, got {len(raw):,}", file=sys.stderr)
    df = clean(raw)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False, compression="zstd")

    valid = df[df["IsValidSale"]]
    print(f"Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e6:.1f} MB)")
    print(f"  raw rows        {len(df):>10,}")
    print(f"  valid sales     {len(valid):>10,}")
    print(f"  cancellations   {int(df['IsCancellation'].sum()):>10,}")
    print(f"  duplicates      {int(df['IsDuplicate'].sum()):>10,}")
    print(f"  missing cust.   {int(df['CustomerID'].isna().sum()):>10,}")
    print(f"  revenue (valid) £{valid['Revenue'].sum():>13,.0f}")
    print(f"  date range      {df['InvoiceDate'].min()} .. {df['InvoiceDate'].max()}")
    print(f"  countries       {df['Country'].nunique():>10}")


if __name__ == "__main__":
    main()
