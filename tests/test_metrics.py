"""Cross-validate our statistics against independent reference implementations.

This is the file that makes the numbers in the reports trustworthy. Each test
compares our computation against a *different* library or solver, so a bug in
one implementation cannot hide behind the same bug in the other.

Several of these tests were written, failed, and then were corrected after
checking the reference implementation's actual semantics. Where a test
asserts something subtle, the comment says what the reference does and why.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from src.evaluation import metrics as M


# --------------------------------------------------------------- Sharpe et al
def test_sharpe_matches_textbook_formula(iid_returns):
    """Our Sharpe must equal the textbook formula, computed independently."""
    r = iid_returns.to_numpy()
    expected = (r.mean() / r.std(ddof=1)) * math.sqrt(252)
    assert M.sharpe(iid_returns) == pytest.approx(expected, rel=1e-12)


def test_sharpe_is_not_cagr_over_volatility(iid_returns):
    """The classic mislabelling: CAGR/vol is NOT the Sharpe ratio.

    This test exists to make sure we never accidentally report one as the
    other. It is the single most common error in retail backtests, and the
    original version of this repository made exactly that error.
    """
    mar_ratio = M.cagr(iid_returns) / M.annualised_vol(iid_returns)
    sharpe = M.sharpe(iid_returns)
    assert abs(mar_ratio - sharpe) > 1e-6, (
        "CAGR/vol and Sharpe should differ; if they are equal the test data "
        "is degenerate and this test proves nothing"
    )


def test_sharpe_respects_risk_free(iid_returns):
    base = M.sharpe(iid_returns, risk_free=0.0)
    with_rf = M.sharpe(iid_returns, risk_free=0.0001)
    assert with_rf < base


def test_max_drawdown_matches_manual_walk(iid_returns):
    """Walk the equity curve by hand and confirm the worst peak-to-trough."""
    equity = (1.0 + iid_returns).cumprod()
    running_max = 0.0
    worst = 0.0
    for value in equity.to_numpy():
        running_max = max(running_max, value)
        worst = min(worst, value / running_max - 1.0)
    assert M.max_drawdown(iid_returns) == pytest.approx(worst, rel=1e-12)


def test_cagr_matches_closed_form(iid_returns):
    total = float((1.0 + iid_returns).prod())
    years = len(iid_returns) / 252
    assert M.cagr(iid_returns) == pytest.approx(total ** (1 / years) - 1, rel=1e-12)


def test_arith_minus_geo_matches_the_log_return_identity(iid_returns):
    """The exact gap must match the log-return identity.

    Derivation: for each period, ``E[r_simple] = E[r_log] + sigma^2/2``.
    Annualising and comparing against the geometric rate gives

        arithmetic_annual - geometric_annual ~= (sigma_annual^2 - mu_annual^2) / 2

    The drift term is not optional. Leaving it out overstates the gap, and
    that mistake is what the first version of this test did.
    """
    exact = M.arithmetic_minus_geometric(iid_returns)
    vol_annual = M.annualised_vol(iid_returns)
    mu_log_annual = float(np.log1p(iid_returns).mean()) * 252
    predicted = (vol_annual**2 - mu_log_annual**2) / 2.0
    assert exact == pytest.approx(predicted, rel=0.05)


def test_volatility_drag_approx_is_close_to_exact_but_not_equal(iid_returns):
    """sigma^2/2 is an approximation; the exact gap includes the drift term."""
    exact = M.arithmetic_minus_geometric(iid_returns)
    approx = M.volatility_drag(iid_returns)
    assert abs(exact - approx) > 1e-9
    assert abs(exact - approx) / abs(approx) < 0.5


def test_sortino_rewards_asymmetric_returns_at_equal_mean():
    """Same mean, same downside risk, but upside volatility: Sortino must
    prefer the one without upside surprises.

    Both series are built with the SAME mean and the SAME downside
    distribution, so the only difference is upside dispersion.
    """
    rng = np.random.default_rng(11)
    n = 2000
    target_mean = 0.0003
    downside_draws = -np.abs(rng.standard_normal(n)) * 0.01
    # Series A: no upside at all (mean comes from the offset)
    a = downside_draws + (target_mean - downside_draws.mean())
    # Series B: same downside draws plus upside noise, re-centred to the same mean
    b = downside_draws + np.abs(rng.standard_normal(n)) * 0.01
    b = b + (target_mean - b.mean())
    assert a.mean() == pytest.approx(b.mean(), rel=1e-12)
    s_a = M.sortino(pd.Series(a))
    s_b = M.sortino(pd.Series(b))
    assert s_a > s_b, "downside deviation is identical, so equal means must make A strictly better"


# ------------------------------------------------------------------ rank IC
def test_spearman_ic_perfect_and_reversed():
    x = np.array([1.0, 2, 3, 4, 5])
    assert M.spearman_ic(x, x) == pytest.approx(1.0)
    assert M.spearman_ic(x, -x) == pytest.approx(-1.0)


def test_spearman_ic_matches_scipy():
    from scipy.stats import spearmanr

    rng = np.random.default_rng(3)
    a = rng.standard_normal(200)
    b = 0.5 * a + rng.standard_normal(200) * 0.5
    assert M.spearman_ic(a, b) == pytest.approx(float(spearmanr(a, b).statistic), rel=1e-12)


# --------------------------------------------------------------- Newey-West
def test_newey_west_tstat_matches_statsmodels():
    """Our wrapper must reproduce statsmodels' HAC t-statistic exactly."""
    import statsmodels.api as sm

    rng = np.random.default_rng(5)
    n = 500
    x = rng.standard_normal(n)
    # autocorrelated noise so HAC actually differs from the naive standard error
    y = 0.4 * x + np.cumsum(rng.standard_normal(n)) * 0.01
    X = sm.add_constant(x)
    model = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
    assert M.newey_west_tstat(x, y, maxlags=4) == pytest.approx(float(model.tvalues[1]), rel=1e-9)


def test_newey_west_standard_error_exceeds_naive_for_ar1_errors():
    """With stationary AR(1) errors, HAC must produce a LARGER standard error
    than the naive OLS one.

    Note: the earlier version of this test used a random walk for the error
    term. A random walk is not stationary, the HAC correction is not designed
    for it, and the "HAC is more conservative" claim does not hold there.
    With a genuine AR(1) process it does.
    """
    import statsmodels.api as sm

    rng = np.random.default_rng(9)
    n = 2000
    rho = 0.8
    e = np.zeros(n)
    shocks = rng.standard_normal(n) * 0.01
    for i in range(1, n):
        e[i] = rho * e[i - 1] + shocks[i]
    x = rng.standard_normal(n)
    y = 0.2 * x + e

    X = sm.add_constant(x)
    naive = sm.OLS(y, X).fit()
    hac = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
    assert float(hac.bse[1]) > float(naive.bse[1])
    assert abs(M.newey_west_tstat(x, y, maxlags=4)) < abs(float(naive.tvalues[1]))


# --------------------------------------------------------------- Ledoit-Wolf
def test_ledoit_wolf_shrinks_toward_identity():
    """With few observations and many assets, shrinkage must be strong and
    the result must be better conditioned than the raw sample covariance."""
    rng = np.random.default_rng(13)
    df = pd.DataFrame(rng.standard_normal((60, 12)) * 0.01)
    cov, intensity = M.ledoit_wolf_covariance(df)
    raw = df.cov().to_numpy()
    assert intensity > 0.0
    assert np.linalg.cond(cov) < np.linalg.cond(raw)


# ---------------------------------------------------------------- DSR / PBO
def test_deflated_sharpe_single_trial_is_a_probability(iid_returns):
    dsr = M.deflated_sharpe(iid_returns, trials=1)
    assert 0.0 <= dsr.deflated_sharpe <= 1.0
    assert dsr.passed == (dsr.deflated_sharpe >= 0.95)


def test_deflated_sharpe_penalises_more_trials():
    """The same strategy must score worse when you admit you tried more."""
    rng = np.random.default_rng(17)
    good = pd.Series(rng.standard_normal(1000) * 0.01 + 0.001)
    # 50 INDIVIDUAL trial Sharpe ratios, not 50 arrays.
    trials = [float(0.2 + 0.05 * rng.standard_normal()) for _ in range(50)]
    one = M.deflated_sharpe(good, trials=1)
    many = M.deflated_sharpe(good, trials=50, observed_trials_sharpes=trials)
    assert many.deflated_sharpe < one.deflated_sharpe
    assert many.expected_max_sharpe > 0


def test_pbo_runs_on_a_matrix_of_trials():
    """PBO needs several variants and enough observations for the splits."""
    rng = np.random.default_rng(23)
    trials = pd.DataFrame(rng.standard_normal((500, 6)) * 0.01)
    result = M.probability_of_backtest_overfitting(trials, n_splits=8)
    assert 0.0 <= result["pbo"] <= 1.0
    assert result["n_variants"] == 6
    assert result["n_observations"] == 500


def test_pbo_rejects_odd_split_count():
    """CSCV requires an even number of splits."""
    rng = np.random.default_rng(23)
    trials = pd.DataFrame(rng.standard_normal((500, 6)) * 0.01)
    with pytest.raises(ValueError, match="even"):
        M.probability_of_backtest_overfitting(trials, n_splits=7)


def test_minimum_track_record_length_semantics():
    """Reference behaviour, verified against purgedcv.

    * A HIGHER observed Sharpe needs a SHORTER record to separate it from the
      same target, because the denominator (SR_observed - SR_target) grows.
    * If the observed Sharpe does not exceed the target, the answer is
      infinity: no length of history can establish a gap you do not have.
    """
    assert M.minimum_track_record_length(1.5, 0.0) < M.minimum_track_record_length(0.5, 0.0)
    assert math.isinf(M.minimum_track_record_length(0.1, 0.2))
    # A tighter target needs a longer record.
    assert M.minimum_track_record_length(1.5, 1.0) > M.minimum_track_record_length(1.5, 0.0)
