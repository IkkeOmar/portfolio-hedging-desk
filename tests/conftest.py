"""Shared test fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import DeskConfig  # noqa: E402
from src.data.synthetic import synthetic_panel  # noqa: E402


@pytest.fixture(scope="session")
def panel() -> pd.DataFrame:
    """A deterministic 15-year synthetic price panel."""
    return synthetic_panel(symbols=["AAPL", "MSFT", "NVDA", "SPY"], seed=20261024)


@pytest.fixture(scope="session")
def config() -> DeskConfig:
    raw = {
        "portfolio": {
            "account_id": "test",
            "benchmark": "SPY",
            "holdings": [
                {"symbol": "AAPL", "shares": 100},
                {"symbol": "MSFT", "shares": 60},
                {"symbol": "NVDA", "shares": 40},
            ],
        },
        "hedging": {
            "hedge_instrument": "SPY",
            "lookback_days": 252,
            "shrinkage_k": 60.0,
            "max_hedge_pct_equity": 0.60,
            "rebalance": "monthly",
        },
        "risk": {
            "max_gross_hedge_pct": 1.0,
            "risk_per_trade_pct": 0.02,
            "min_reward_to_risk": 1.5,
            "max_legs": 5,
        },
        "costs": {
            "fee_bps_per_side": 2.0,
            "slippage_bps_per_side": 1.0,
            "spread_bps_per_side": 0.5,
        },
        "data": {"source": "synthetic", "seed": 20261024},
    }
    return DeskConfig.from_dict(raw, source_path="<test>")


@pytest.fixture
def iid_returns() -> pd.Series:
    """A plain i.i.d. daily return series."""
    rng = np.random.default_rng(42)
    idx = pd.bdate_range("2020-01-01", periods=750)
    return pd.Series(rng.standard_normal(750) * 0.01 + 0.0002, index=idx)
