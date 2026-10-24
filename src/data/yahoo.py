"""yfinance adapter: end-of-day closes for US-listed symbols.

Free, no API key, not guaranteed to be correct. Notes that matter:

* ``auto_adjust=True`` gives you split- and dividend-adjusted closes, which is
  what you want for backtesting and what you do not want for filling a trade.
  We use adjusted closes everywhere and say so in the report.
* Yahoo throttles. The adapter caches to a parquet file and re-uses it.
* A symbol with no history raises. We do not silently substitute.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """yfinance returns MultiIndex columns on some versions. Flatten to level 0."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    return df


def yahoo_panel(symbols=None, start=None, end=None, cache_dir: str | Path | None = None) -> pd.DataFrame:
    """Fetch daily closes for ``symbols`` and return a wide DataFrame."""
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise ImportError(
            "the yahoo adapter needs yfinance: pip install yfinance "
            "(or set data.source: synthetic to run without it)"
        ) from exc

    if isinstance(symbols, str):
        symbols = [symbols]
    if not symbols:
        raise ValueError("yahoo_panel needs at least one symbol")

    cache_path = None
    if cache_dir is not None:
        cache_path = Path(cache_dir) / "yahoo_panel.parquet"
        if cache_path.exists():
            try:
                cached = pd.read_parquet(cache_path)
                if set(symbols).issubset(set(cached.columns)):
                    if start is not None:
                        cached = cached[cached.index >= pd.Timestamp(start)]
                    if end is not None:
                        cached = cached[cached.index <= pd.Timestamp(end)]
                    return cached
            except Exception:  # pragma: no cover - corrupt cache, just refetch
                pass

    frames = {}
    for symbol in symbols:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                raw = yf.download(
                    symbol,
                    start=start,
                    end=end,
                    auto_adjust=True,
                    progress=False,
                    actions=False,
                )
                if raw.empty:
                    raise RuntimeError(f"no rows returned for {symbol}")
                raw = _flatten_columns(raw)
                col = "Close" if "Close" in raw.columns else "Adj Close"
                if col not in raw.columns:
                    raise RuntimeError(f"no close column for {symbol}: {list(raw.columns)}")
                frames[symbol] = raw[col].dropna()
                break
            except Exception as exc:  # pragma: no cover - network dependent
                last_error = exc
                time.sleep(1.5 * (attempt + 1))
        if symbol not in frames:
            raise RuntimeError(f"could not fetch {symbol} from yahoo: {last_error}")

    panel = pd.DataFrame(frames).sort_index()
    panel.index.name = "Date"
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            panel.to_parquet(cache_path)
        except Exception:  # pragma: no cover - parquet engine may be missing
            pass
    return panel
