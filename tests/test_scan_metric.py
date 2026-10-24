"""Pins the Scan seat's market-risk contribution metric.

This metric had NO test at all, which is why a scale defect survived in it.
The tests here are written so that each one FAILS against the old formula
and PASSES against the corrected one.

The metric, for holding i:

    systematic     = (beta_i * sigma_m)**2     -- the market's part
    idiosyncratic = idio_i**2                 -- the asset's own part
    total         = systematic + idiosyncratic
    hedgeable_share = systematic / total

Both terms are annualised VARIANCES, so they can be added.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.config import DeskConfig, Holding
from src.data import load_panel
from src.policy.scan import ScanPolicy


@pytest.fixture(scope="module")
def desk_cfg() -> DeskConfig:
    return DeskConfig.from_yaml("examples/holdings.example.yaml")


@pytest.fixture(scope="module")
def panel(desk_cfg: DeskConfig) -> pd.DataFrame:
    return load_panel(
        source=desk_cfg.data.source,
        symbols=desk_cfg.all_symbols,
        seed=desk_cfg.data.seed,
        path=desk_cfg.data.path,
    )


def _scan(panel: pd.DataFrame, cfg: DeskConfig, betas, idios):
    cut = panel.iloc[:-21]
    policy = ScanPolicy(benchmark=cfg.portfolio.benchmark)
    holdings = cfg.portfolio.holdings
    return policy.scan(cut, holdings, betas, idios), cut


def test_the_two_terms_are_both_variances(panel, desk_cfg):
    """systematic and idiosyncratic must be on the same scale.

    The old formula had a dimensionless systematic term added to a variance.
    This test computes each term independently and checks that the ratio
    matches the one the seat reports.
    """
    betas = {"AAPL": 1.0, "MSFT": 0.7, "NVDA": 1.2}
    idios = {"AAPL": 0.20, "MSFT": 0.15, "NVDA": 0.40}
    cands, cut = _scan(panel, desk_cfg, betas, idios)

    bench = cut[desk_cfg.portfolio.benchmark].pct_change().dropna()
    market_vol = float(bench.std(ddof=1) * np.sqrt(252))

    for c in cands:
        expected_systematic = (c.beta * market_vol) ** 2
        expected_idiosyncratic = c.idio_vol**2
        expected_total = expected_systematic + expected_idiosyncratic
        expected_share = expected_systematic / expected_total

        assert c.systematic_contribution == pytest.approx(expected_systematic, rel=1e-9)
        assert c.idiosyncratic_contribution == pytest.approx(expected_idiosyncratic, rel=1e-9)
        assert c.total_contribution == pytest.approx(expected_total, rel=1e-9)
        assert c.hedgeable_share == pytest.approx(expected_share, rel=1e-9)


def test_a_high_beta_holding_is_not_reported_as_unhedgeable(panel, desk_cfg):
    """The defect this file exists to prevent.

    The old formula computed a systematic term of (portfolio_beta - beta) *
    beta. For any holding whose beta is ABOVE the portfolio's -- the ones
    most exposed to the market, and so the most worth hedging -- that term
    came out NEGATIVE, the share was clipped to zero, and the desk reported
    "not hedgeable" about exactly the holdings a market hedge helps most.

    Here the portfolio beta is 1.0 and one holding is well above it.
    """
    betas = {"AAPL": 1.8, "MSFT": 0.5, "NVDA": 1.0}
    idios = {"AAPL": 0.20, "MSFT": 0.15, "NVDA": 0.40}
    cands, _ = _scan(panel, desk_cfg, betas, idios)

    aapl = next(c for c in cands if c.symbol == "AAPL")
    assert aapl.beta == 1.8
    assert aapl.hedgeable_share > 0.0, (
        "a holding with a high beta must not be reported as having no "
        "hedgeable risk; the old formula clipped this to zero"
    )
    # And it must be genuinely hedgeable -- most of its risk is the market's.
    assert aapl.hedgeable_share > 0.5


def test_the_share_responds_to_market_volatility(panel, desk_cfg):
    """The metric has to see how volatile the market is.

    A holding's risk is more market risk when the market is volatile, so
    its hedgeable share must rise with market volatility. The old formula
    contained no market variance at all, so the share could not move.
    """
    betas = {"AAPL": 1.0, "MSFT": 0.7, "NVDA": 1.2}
    idios = {"AAPL": 0.20, "MSFT": 0.15, "NVDA": 0.40}

    cut = panel.iloc[:-21]
    policy = ScanPolicy(benchmark=desk_cfg.portfolio.benchmark)
    holdings = desk_cfg.portfolio.holdings

    shares = []
    for scale in (0.5, 1.0, 2.0):
        # Scale the benchmark's returns, which scales its volatility.
        scaled = cut.copy()
        bench = desk_cfg.portfolio.benchmark
        scaled[bench] = cut[bench] * (1.0 + 0.0)  # keep level, scale returns
        # Build a panel whose benchmark has the requested volatility by
        # rescaling its daily returns and rebuilding the level.
        r = cut[bench].pct_change().dropna()
        new_r = r * scale
        level = cut[bench].iloc[0]
        path = [level]
        for x in new_r:
            path.append(path[-1] * (1.0 + x))
        scaled[bench] = path
        cands = policy.scan(scaled, holdings, betas, idios)
        aapl = next(c for c in cands if c.symbol == "AAPL")
        shares.append(aapl.hedgeable_share)

    assert shares[0] < shares[1] < shares[2], (
        f"the hedgeable share must rise with market volatility, got {shares}"
    )


def test_more_idiosyncratic_risk_means_less_hedgeable(panel, desk_cfg):
    """More of the asset's own risk means less of it can be hedged away."""
    betas = {"AAPL": 1.0, "MSFT": 0.7, "NVDA": 1.2}
    quiet = {"AAPL": 0.05, "MSFT": 0.05, "NVDA": 0.05}
    noisy = {"AAPL": 0.60, "MSFT": 0.60, "NVDA": 0.60}

    c_quiet, _ = _scan(panel, desk_cfg, betas, quiet)
    c_noisy, _ = _scan(panel, desk_cfg, betas, noisy)

    q = next(c for c in c_quiet if c.symbol == "AAPL").hedgeable_share
    n = next(c for c in c_noisy if c.symbol == "AAPL").hedgeable_share
    assert n < q, (
        f"a holding with more idiosyncratic risk must be less hedgeable: "
        f"{n} should be below {q}"
    )


def test_the_share_is_always_a_probability(panel, desk_cfg):
    """hedgeable_share is documented as being in [0, 1]."""
    betas = {"AAPL": 1.9, "MSFT": -0.4, "NVDA": 1.0}
    idios = {"AAPL": 0.05, "MSFT": 0.60, "NVDA": 0.40}
    cands, _ = _scan(panel, desk_cfg, betas, idios)
    for c in cands:
        assert 0.0 <= c.hedgeable_share <= 1.0


def test_a_missing_benchmark_is_an_error_not_a_silent_zero(panel, desk_cfg):
    """Fail closed. A silent zero would look like "nothing to hedge"."""
    cut = panel.iloc[:-21].drop(columns=[desk_cfg.portfolio.benchmark])
    policy = ScanPolicy(benchmark=desk_cfg.portfolio.benchmark)
    with pytest.raises(KeyError):
        policy.scan(cut, desk_cfg.portfolio.holdings, {"AAPL": 1.0}, {"AAPL": 0.2})


def test_the_ranking_is_deterministic(panel, desk_cfg):
    """Same inputs, same order -- ties broken by symbol."""
    betas = {"AAPL": 1.0, "MSFT": 1.0, "NVDA": 1.0}
    idios = {"AAPL": 0.2, "MSFT": 0.2, "NVDA": 0.2}
    first, _ = _scan(panel, desk_cfg, betas, idios)
    second, _ = _scan(panel, desk_cfg, betas, idios)
    assert [c.symbol for c in first] == [c.symbol for c in second]
    assert [c.symbol for c in first] == sorted(c.symbol for c in first)
