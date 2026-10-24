"""Verify the hedge mathematics against an independent convex solver.

The minimum-variance hedge ratio has a closed form. A closed form that nobody
checked is a liability, so we check it against cvxpy, which solves the
problem numerically with no knowledge of our formula.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.policy.hedger import HedgePolicy


def _correlated_pair(seed: int = 7, n: int = 1500):
    rng = np.random.default_rng(seed)
    market = rng.standard_normal(n) * 0.011 + 0.0003
    hedge = 1.1 * market + rng.standard_normal(n) * 0.004
    portfolio = 0.9 * market + rng.standard_normal(n) * 0.008
    return portfolio, hedge


def test_min_variance_ratio_matches_cvxpy():
    """Our closed form must equal the numerical optimum of the variance."""
    import cvxpy as cp

    p, h = _correlated_pair()
    f_closed = HedgePolicy.minimum_variance_hedge(pd.Series(p), pd.Series(h))[0]

    f = cp.Variable()
    objective = cp.Minimize(cp.sum_squares((p - p.mean()) + f * (h - h.mean())) / (len(p) - 1))
    problem = cp.Problem(objective)
    problem.solve(solver=cp.CLARABEL, tol_gap_abs=1e-14, tol_gap_rel=1e-14, tol_feas=1e-14)

    assert float(f.value) == pytest.approx(f_closed, abs=1e-8)


def test_min_variance_ratio_reduces_variance():
    """The chosen ratio must actually reduce variance, or the derivation is wrong."""
    p, h = _correlated_pair()
    f, _ = HedgePolicy.minimum_variance_hedge(pd.Series(p), pd.Series(h))
    assert np.var(p + f * h, ddof=1) < np.var(p, ddof=1)


def test_min_variance_ratio_sign_is_short_for_long_portfolio():
    """A long portfolio hedged with a correlated instrument must be short."""
    p, h = _correlated_pair()
    f, cov = HedgePolicy.minimum_variance_hedge(pd.Series(p), pd.Series(h))
    assert cov > 0
    assert f < 0


def test_min_variance_ratio_is_zero_for_uncorrelated_pair():
    """No covariance means no market risk to remove, so no hedge."""
    rng = np.random.default_rng(19)
    p = rng.standard_normal(800) * 0.01
    h = rng.standard_normal(800) * 0.01
    f, cov = HedgePolicy.minimum_variance_hedge(pd.Series(p), pd.Series(h))
    assert abs(cov) < 0.01
    assert abs(f) < 0.1


def test_beta_recovers_known_beta():
    """A series built as beta*x + noise must recover that beta from OLS."""
    rng = np.random.default_rng(29)
    n = 2000
    x = rng.standard_normal(n) * 0.01
    y = 1.5 * x + rng.standard_normal(n) * 0.005
    policy = HedgePolicy(benchmark="SPY", hedge_instrument="SPY")
    est = policy.estimate_beta(pd.Series(y), pd.Series(x))
    assert est.beta == pytest.approx(1.5, abs=0.08)


def test_shrinkage_pulls_beta_toward_zero():
    """A noisy beta must be shrunk below its raw value; a precise one less so."""
    rng = np.random.default_rng(31)
    n = 250
    x = rng.standard_normal(n) * 0.01
    # A weak signal: the raw beta is dominated by noise.
    y = 0.8 * x + rng.standard_normal(n) * 0.03
    policy = HedgePolicy(benchmark="SPY", hedge_instrument="SPY", shrinkage_k=60.0)
    est = policy.estimate_beta(pd.Series(y), pd.Series(x))
    assert abs(est.beta_shrunk) < abs(est.beta)
    assert 0.0 < est.shrinkage_weight < 1.0


def test_shrinkage_weight_is_monotone_in_t_stat():
    """A stronger t-statistic must produce less shrinkage."""
    rng = np.random.default_rng(37)
    n = 400
    x = rng.standard_normal(n) * 0.01
    weak = 0.2 * x + rng.standard_normal(n) * 0.05
    strong = 1.2 * x + rng.standard_normal(n) * 0.02
    policy = HedgePolicy(benchmark="SPY", hedge_instrument="SPY", shrinkage_k=60.0)
    w_weak = policy.estimate_beta(pd.Series(weak), pd.Series(x)).shrinkage_weight
    w_strong = policy.estimate_beta(pd.Series(strong), pd.Series(x)).shrinkage_weight
    assert w_strong > w_weak
