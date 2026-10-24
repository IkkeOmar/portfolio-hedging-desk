"""Market data adapters.

One file per source. Every adapter returns the same thing: a wide DataFrame of
end-of-day closes, indexed by date, one column per symbol.

    index: DatetimeIndex (trading days, ascending)
    columns: symbol -> close price (float)

Adapters never fill forward a price they do not have. A missing day is a
missing day.
"""

from __future__ import annotations

from ..config import ConfigError

__all__ = ["load_panel", "available_sources"]


def available_sources() -> tuple[str, ...]:
    return ("synthetic", "yahoo", "csv")


def load_panel(source: str = "synthetic", symbols=None, start=None, end=None, seed: int = 20261024, path=None):
    """Load a price panel from the named source.

    Parameters
    ----------
    source : {"synthetic", "yahoo", "csv"}
    symbols : list[str] | None
        Which symbols to load. ``None`` means "let the adapter decide".
    start, end : date-like | None
    seed : int
        Only used by the synthetic source.
    path : str | Path | None
        Only used by the csv source.
    """
    source = source.lower()
    if source == "synthetic":
        from .synthetic import synthetic_panel

        return synthetic_panel(symbols=symbols, start=start, end=end, seed=seed)
    if source == "yahoo":
        from .yahoo import yahoo_panel

        return yahoo_panel(symbols=symbols, start=start, end=end)
    if source == "csv":
        from .csv_source import csv_panel

        if path is None:
            raise ConfigError("data.source='csv' needs data.path in the config file")
        return csv_panel(path=path, symbols=symbols, start=start, end=end)
    raise ConfigError(f"unknown data source {source!r}; expected one of {available_sources()}")
