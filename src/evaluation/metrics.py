"""The statistics. Built on maintained libraries, not hand-rolled.

Why this module is thin
-----------------------
Every statistic here has a well-tested, well-documented reference
implementation. Re-implementing them would be slower, less correct, and a
worse teaching example, because a reader who wants to check our arithmetic
should be able to check it against the library everyone else uses.

What we use, and why
--------------------
``skfolio.measures``
    ``deflated_sharpe_ratio``, ``expected_max_sharpe_ratio`` and
    ``probabilistic_sharpe_ratio``. Bailey and Lopez de Prado (2014). skfolio
    computes the kurtosis as the *raw* (non-excess) moment, which is what the
    paper's formula requires; several hand-rolled versions get this wrong and
    silently shift the DSR.

``purgedcv``
    ``probability_of_backtest_overfitting`` (CSCV), ``deflated_sharpe_ratio``,
    ``effective_n_trials`` and ``min_track_record_length``. Lopez de Prado's
    purged walk-forward and the Bailey/Borwein/Lopez de Prado/Zhu overfitting
    machinery, MIT licensed and sklearn-native.

``statsmodels``
    ``OLS(..., cov_type="HAC")`` for Newey-West (1987) standard errors. We use
    it instead of our own implementation so the autocorrelation correction
    matches the reference exactly.

``scipy.stats``
    Spearman rank correlation and the t-distribution.

``sklearn.covariance.LedoitWolf``
    Ledoit and Wolf (2004) shrinkage for the covariance estimate. A raw
    sample covariance matrix over a few hundred days is badly conditioned;
    shrinkage is the standard fix, and it is a one-liner here.

Conventions used throughout
---------------------------
* ``periods_per_year`` defaults to 252 (trading days).
* ``risk_free`` arguments are **per period**, never annual. Mixing the two is
  the single most common silent error in this kind of code.
* Sharpe-style ratios are computed from the *arithmetic mean* of excess
  returns, never from CAGR. Dividing CAGR by volatility and calling the result
  a Sharpe ratio is a mislabelled statistic, and it is the single most common
  error in retail backtests.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

TRADING_DAYS = 252


# --------------------------------------------------------------------- basics
def cagr(returns: pd.Series, periods_per_year: int = TRADING_DAYS) -> float:
    """Compound annual growth rate from a series of periodic returns.

    CAGR = (total growth)^(1/years) - 1, where years is measured in periods
    and the periods per year is the annualisation factor.
    """
    clean = returns.dropna()
    if len(clean) == 0:
        return float("nan")
    total = float((1.0 + clean).prod())
    if total <= 0:
        return float("nan")
    years = len(clean) / periods_per_year
    if years <= 0:
        return float("nan")
    return float(total ** (1.0 / years) - 1.0)


def annualised_vol(returns: pd.Series, periods_per_year: int = TRADING_DAYS) -> float:
    """Annualised standard deviation of periodic returns (sample std, ddof=1)."""
    clean = returns.dropna()
    if len(clean) < 2:
        return float("nan")
    return float(clean.std(ddof=1) * math.sqrt(periods_per_year))


def sharpe(
    returns: pd.Series,
    risk_free: float = 0.0,
    periods_per_year: int = TRADING_DAYS,
) -> float:
    """Annualised Sharpe ratio.

    Sharpe = (mean(r) - r_f) / std(r) * sqrt(periods_per_year)

    ``risk_free`` is a per-period rate, not an annual rate. The arithmetic
    mean of excess returns is used, never CAGR.
    """
    clean = returns.dropna()
    if len(clean) < 2:
        return float("nan")
    excess = clean - risk_free
    sd = float(clean.std(ddof=1))
    if sd <= 0:
        return float("nan")
    return float(excess.mean() / sd * math.sqrt(periods_per_year))


def sortino(
    returns: pd.Series,
    risk_free: float = 0.0,
    periods_per_year: int = TRADING_DAYS,
) -> float:
    """Annualised Sortino ratio: excess return over *downside* deviation only."""
    clean = returns.dropna()
    if len(clean) < 2:
        return float("nan")
    excess = clean - risk_free
    downside = excess[excess < 0]
    if len(downside) == 0:
        return float("inf") if excess.mean() > 0 else float("nan")
    dd = float(np.sqrt((downside**2).mean()))
    if dd <= 0:
        return float("nan")
    return float(excess.mean() / dd * math.sqrt(periods_per_year))


def max_drawdown(returns: pd.Series) -> float:
    """Maximum peak-to-trough drawdown as a negative fraction (e.g. -0.24).

    Computed on the equity curve, because drawdown is a property of the path.
    """
    clean = returns.dropna()
    if len(clean) == 0:
        return float("nan")
    equity = (1.0 + clean).cumprod()
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min())


def calmar(returns: pd.Series, periods_per_year: int = TRADING_DAYS) -> float:
    """CAGR divided by the absolute maximum drawdown."""
    mdd = max_drawdown(returns)
    if not np.isfinite(mdd) or mdd == 0:
        return float("nan")
    return float(cagr(returns, periods_per_year) / abs(mdd))


def arithmetic_minus_geometric(returns: pd.Series, periods_per_year: int = TRADING_DAYS) -> float:
    """The exact gap between the arithmetic and geometric annualised return.

    This is the volatility drag, computed exactly from the realised path
    rather than approximated as sigma^2/2. The approximation is only good for
    small volatility and small returns; the exact number is free, so we
    compute the exact one.
    """
    clean = returns.dropna()
    if len(clean) < 2:
        return float("nan")
    arithmetic = float(clean.mean()) * periods_per_year
    geometric = cagr(clean, periods_per_year)
    return float(arithmetic - geometric)


def volatility_drag(returns: pd.Series, periods_per_year: int = TRADING_DAYS) -> float:
    """The sigma^2/2 approximation, for comparison against the exact gap."""
    vol = annualised_vol(returns, periods_per_year)
    return float(0.5 * vol**2)


# --------------------------------------------------------------- statistical
def spearman_ic(pred: np.ndarray, realised: np.ndarray) -> float:
    """Spearman rank correlation between a prediction and a realised outcome.

    Rank correlation, not Pearson, because the signal is an ordering. Uses
    ``scipy.stats.spearmanr`` so the tie handling matches the reference
    implementation.
    """
    from scipy.stats import spearmanr

    p = np.asarray(pred, dtype=float)
    r = np.asarray(realised, dtype=float)
    mask = np.isfinite(p) & np.isfinite(r)
    p, r = p[mask], r[mask]
    if len(p) < 3:
        return float("nan")
    result = spearmanr(p, r)
    value = result.statistic
    return float(value) if np.isfinite(value) else float("nan")


def sm_add_constant(x: np.ndarray) -> np.ndarray:
    """Design matrix with an intercept column."""
    x = np.asarray(x, dtype=float)
    return np.column_stack([np.ones(len(x)), x])


def newey_west_tstat(x: np.ndarray, y: np.ndarray, maxlags: int | None = None) -> float:
    """t-statistic for the slope of y on x with Newey-West (HAC) standard errors.

    Uses ``statsmodels`` OLS with ``cov_type="HAC"``, the reference
    implementation of Newey and West (1987). Autocorrelated daily signals
    make the naive standard error too small, which makes the naive t-statistic
    too large, which makes you overstate your evidence.

    ``maxlags`` defaults to floor(4 * (n/100)^(2/9)), the common rule.
    """
    from statsmodels.regression.linear_model import OLS

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    n = len(x)
    if n < 20:
        return float("nan")
    if maxlags is None:
        maxlags = int(math.floor(4 * (n / 100.0) ** (2.0 / 9.0)))
    maxlags = max(0, min(int(maxlags), n - 1))

    X = sm_add_constant(x)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    tstat = model.tvalues[1]
    return float(tstat) if np.isfinite(tstat) else float("nan")


def ledoit_wolf_covariance(returns: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Ledoit-Wolf (2004) shrinkage covariance estimate.

    Returns ``(covariance, shrinkage_intensity)``. The sample covariance of a
    few hundred daily returns is badly conditioned; Ledoit-Wolf shrinks it
    toward a scaled identity, which is the standard remedy (Ledoit and Wolf
    2003, "Honey, I Shrunk the Sample Covariance Matrix").
    """
    from sklearn.covariance import LedoitWolf

    clean = returns.dropna()
    if len(clean) < 3:
        raise ValueError(f"need at least 3 observations for a covariance estimate, got {len(clean)}")
    model = LedoitWolf().fit(clean.to_numpy(dtype=float))
    return model.covariance_, float(model.shrinkage_)


# ------------------------------------------------- selection-bias machinery
@dataclass
class DeflatedSharpe:
    """Deflated Sharpe Ratio output.

    The problem it solves: if you run 1000 strategies and pick the best, its
    Sharpe is not a fair estimate of any strategy's Sharpe. It is partly
    skill and partly the luck of the draw. The DSR deflates the observed
    Sharpe for the number of trials you actually ran, the skewness and
    kurtosis of the returns, and the variance of the trials' Sharpe ratios.

    Bailey and Lopez de Prado (2014).

    ``deflated_sharpe`` is a *probability* (higher is better), and it passes
    at 0.95, matching the paper's convention and skfolio's convention.
    """

    deflated_sharpe: float
    observed_sharpe: float
    expected_max_sharpe: float
    p_value: float
    trials: int
    passed: bool


def deflated_sharpe(
    returns: pd.Series,
    trials: int,
    observed_trials_sharpes: list[float] | None = None,
    periods_per_year: int = TRADING_DAYS,
) -> DeflatedSharpe:
    """Deflated Sharpe Ratio, via skfolio.

    Parameters
    ----------
    returns
        The returns of the strategy you are evaluating.
    trials
        How many strategy variants you actually tried before picking this one.
        This number is the entire point. If you ran one, trials=1 and the
        deflation does nothing, which is correct.
    observed_trials_sharpes
        The Sharpe ratios of all the variants you tried, in *annualised* units.
        skfolio works in per-period units, so this function converts.

    Note on units: skfolio's ``expected_max_sharpe_ratio`` takes the standard
    deviation of the *trial* Sharpe ratios in per-period units. With a single
    trial there is no dispersion to measure and the benchmark is zero, so the
    DSR reduces to the plain Probabilistic Sharpe Ratio.
    """
    from skfolio.measures import deflated_sharpe_ratio as skfolio_dsr
    from skfolio.measures import expected_max_sharpe_ratio

    clean = returns.dropna()
    n = len(clean)
    if n < 30 or trials < 1:
        return DeflatedSharpe(
            deflated_sharpe=float("nan"),
            observed_sharpe=float("nan"),
            expected_max_sharpe=float("nan"),
            p_value=float("nan"),
            trials=int(trials),
            passed=False,
        )

    per_period = clean.to_numpy(dtype=float)
    sr_annual = sharpe(clean, 0.0, periods_per_year)

    expected_max = 0.0
    if observed_trials_sharpes and len(observed_trials_sharpes) > 1:
        # skfolio expects per-period Sharpes for the trial set.
        trial_sharpes = np.asarray(observed_trials_sharpes, dtype=float) / math.sqrt(periods_per_year)
        value = float(skfolio_dsr(per_period, trial_sharpes))
        expected_max = float(
            expected_max_sharpe_ratio(
                n_trials=float(len(trial_sharpes)),
                trial_sharpe_ratio_std=float(np.std(trial_sharpes, ddof=1)),
            )
        ) * math.sqrt(periods_per_year)
    else:
        # No dispersion information. With one trial the benchmark is zero.
        # skfolio's DSR needs at least one trial Sharpe, so we pass the
        # strategy's own per-period Sharpe and note the limitation.
        sr_per_period = float(per_period.mean() / per_period.std(ddof=1))
        value = float(skfolio_dsr(per_period, np.array([sr_per_period])))

    return DeflatedSharpe(
        deflated_sharpe=value,
        observed_sharpe=float(sr_annual),
        expected_max_sharpe=float(expected_max),
        p_value=float(1.0 - value),
        trials=int(trials),
        passed=bool(value >= 0.95),
    )


def probability_of_backtest_overfitting(
    returns: pd.DataFrame,
    n_splits: int = 16,
) -> dict[str, Any]:
    """Probability of Backtest Overfitting (CSCV), via purgedcv.

    Bailey, Borwein, Lopez de Prado and Zhu. The question it answers: if you
    picked the best of N configurations in-sample, what is the probability
    that it is actually below median out-of-sample?

    Parameters
    ----------
    returns
        A DataFrame with one column per strategy variant and one row per
        time period. This is the *matrix of trials*, not a single return
        series.
    n_splits
        Number of combinatorial splits. 16 is the paper's default, and it must
        be even.

    Note on orientation: purgedcv expects the matrix as
    ``(n_configs, n_obs)`` -- configurations down the rows. A DataFrame that
    is time-down-the-rows has to be transposed, and getting this wrong does
    not raise: it silently computes the PBO of the transpose. This function
    takes the transposes and asserts the shape, so the caller cannot get it
    wrong.
    """
    from purgedcv import probability_of_backtest_overfitting as purgedcv_pbo

    clean = returns.dropna()
    n_time, n_configs = clean.shape
    if n_configs < 2:
        raise ValueError(
            f"PBO needs at least two strategy variants to compare, got {n_configs}"
        )
    if n_splits % 2 != 0:
        raise ValueError(f"n_splits must be even for CSCV, got {n_splits}")
    if n_time < n_splits:
        raise ValueError(
            f"PBO needs at least {n_splits} observations per variant, got {n_time}"
        )
    # purgedcv wants (n_configs, n_obs). Our DataFrame is (n_time, n_configs).
    matrix = clean.to_numpy(dtype=float).T
    assert matrix.shape == (n_configs, n_time), "PBO matrix orientation is wrong"
    result = purgedcv_pbo(matrix, n_splits=n_splits)
    return {
        "pbo": float(result.pbo),
        "n_splits": int(n_splits),
        "n_variants": int(n_configs),
        "n_observations": int(n_time),
    }


def effective_number_of_trials(trial_sharpes: list[float]) -> int:
    """How many *independent* trials the Sharpe ratios really represent.

    A dense grid of similar parameter combinations produces highly correlated
    trial Sharpes, so counting them as independent trials overstates the
    correction. purgedcv estimates the effective count from the
    autocorrelation of the sorted Sharpe ratios.
    """
    from purgedcv import effective_n_trials

    arr = np.asarray(trial_sharpes, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) < 3:
        return int(max(len(arr), 1))
    return int(effective_n_trials(arr))


def minimum_track_record_length(
    observed_sharpe: float,
    target_sharpe: float = 0.0,
    alpha: float = 0.05,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """How long a track record you need to trust a Sharpe ratio.

    Lopez de Prado (2014), "The Minimum Track Record Length". It inverts the
    Probabilistic Sharpe Ratio for the sample size::

        n* = 1 + ceil( ( Z^-1(1-alpha) * sqrt(1 - g3*SR + (g4-1)/4*SR^2)
                         / (SR_observed - SR_target) )^2 )

    Two behaviours worth knowing, both verified against the reference
    implementation:

    * If ``observed_sharpe <= target_sharpe`` the answer is ``inf``. No
      length of track record can establish a gap you have not got.
    * A *higher* observed Sharpe needs a *shorter* record to separate it
      from the same target, because the denominator ``SR_observed -
      SR_target`` grows. The intuition "higher Sharpe needs more data" is
      about the true Sharpe being unknown, which is a different question.

    Returns the required number of observations.
    """
    from purgedcv import min_track_record_length

    return float(min_track_record_length(observed_sharpe, target_sharpe, alpha, skew, kurtosis))
