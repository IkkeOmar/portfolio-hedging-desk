"""CSV adapter: read a price panel from disk.

Expected shape: first column is a date (any parseable format), remaining
columns are symbols with close prices. This is the adapter to use if you want
to point the desk at your own data.

    date,AAPL,MSFT
    2020-01-02,125.06,160.37
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def csv_panel(path: str | Path, symbols=None, start=None, end=None) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"price CSV not found: {path}")
    df = pd.read_csv(path, index_col=0)
    df.index = pd.to_datetime(df.index)
    df.index.name = "Date"
    df = df.sort_index().apply(pd.to_numeric, errors="coerce")
    if symbols:
        wanted = [s.upper() for s in symbols]
        missing = [s for s in wanted if s not in df.columns]
        if missing:
            raise KeyError(f"CSV {path} is missing columns: {missing}")
        df = df[wanted]
    if start is not None:
        df = df[df.index >= pd.Timestamp(start)]
    if end is not None:
        df = df[df.index <= pd.Timestamp(end)]
    return df
