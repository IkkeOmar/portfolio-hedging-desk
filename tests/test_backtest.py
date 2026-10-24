"""Tests for the backtest engine's time alignment.

These exist because the forward-return helper was silently wrong and the
information gate reported a number from it. A wrong forward window flips the
sign of an information coefficient, which is exactly the kind of bug that
makes a strategy look like it has no edge when it might.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtest import forward_compound


def test_forward_compound_matches_direct_computation():
    """The vectorised version must equal a naive loop, element for element."""
    rng = np.random.default_rng(1)
    n = 120
    r = pd.Series(rng.standard_normal(n) * 0.01, index=pd.bdate_range("2020-01-01", periods=n))
    horizon = 21

    got = forward_compound(r, horizon)

    direct = pd.Series(np.nan, index=r.index)
    for i in range(n):
        if i + horizon <= n:
            direct.iloc[i] = np.prod(1.0 + r.iloc[i + 1 : i + horizon + 1]) - 1.0

    both = pd.concat([got.rename("got"), direct.rename("direct")], axis=1).dropna()
    assert len(both) > 50, "the comparison should cover most of the series"
    assert float((both["got"] - both["direct"]).abs().max()) < 1e-12


def test_forward_compound_starts_after_today():
    """The window must be t+1..t+H, never including t itself."""
    r = pd.Series([0.10, 0.20, 0.30, 0.40, 0.50], index=pd.bdate_range("2020-01-01", periods=5))
    got = forward_compound(r, horizon=2)
    # At t=0 the forward window is r[1] and r[2]: 1.2 * 1.3 - 1
    assert got.iloc[0] == pytest.approx(1.2 * 1.3 - 1.0)
    # At t=1 the window is r[2] and r[3]: 1.3 * 1.4 - 1
    assert got.iloc[1] == pytest.approx(1.3 * 1.4 - 1.0)


def test_forward_compound_last_rows_are_nan():
    """The final `horizon` rows have no complete forward window."""
    rng = np.random.default_rng(2)
    r = pd.Series(rng.standard_normal(100) * 0.01, index=pd.bdate_range("2020-01-01", periods=100))
    got = forward_compound(r, horizon=21)
    assert got.iloc[-21:].isna().all()
    assert got.iloc[:-21].notna().all()


def test_forward_compound_is_zero_when_returns_are_zero():
    r = pd.Series(0.0, index=pd.bdate_range("2020-01-01", periods=50))
    got = forward_compound(r, horizon=10)
    assert got.dropna().eq(0.0).all()
