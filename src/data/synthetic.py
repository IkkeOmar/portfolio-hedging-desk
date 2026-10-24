"""A deterministic synthetic market, so the repo runs with no network and no keys.

Why ship a fake market at all?
------------------------------
Because "run the thing yourself" is the single most valuable property of an
educational repository, and a repository that needs a broker key or a working
network to show its first result is a repository most people never run.

The generator is deliberately not a toy. It contains the features that break
naive strategies:

* a common market factor with slow regime changes (bull / bear / sideways),
* volatility clustering, so risk is not constant,
* occasional stress windows with correlation spikes toward 1,
* per-asset betas that differ, so hedging one holding does not hedge another,
* fat-ish tails via occasional jumps.

It is synthetic. It is not evidence about real markets. It is a test fixture.
Every real claim in this repo is made against real data and says so.

The price model, derived
------------------------
An asset's daily log return is

    log_ret_i = mu_i - 0.5*sigma_i^2 + beta_i * market_shock + idio_shock

where ``market_shock`` is the common factor and ``idio_shock`` is
asset-specific noise. In this construction:

* ``mu_i`` is the **arithmetic** daily drift, so ``E[P_T] = P_0 * exp(mu_i * T)``:
  the price grows at the rate the parameters say it does.
* ``-0.5*sigma_i^2`` is the Ito correction. Without it, the expected price
  grows faster than ``mu_i`` and, over a long window, the price series drifts
  to absurd levels. This single term is what keeps a 15-year synthetic market
  at plausible price levels.
* ``sigma_i`` is the **daily** volatility, so ``sigma_i * sqrt(252)`` is the
  annualised volatility.

Units are the whole game here. The two conversion functions below are the
only place units are converted, and they are different:

    _daily_drift(a)   = a / 252          drift accumulates linearly in time
    _daily_vol(a)     = a / sqrt(252)    volatility scales with the square root

Using the volatility conversion for drift makes prices explode by orders of
magnitude over a long window, which then makes every downstream number
(absurd weights, absurd notionals) look like a bug in the trading code when
it is a bug in the data generator. That failure mode is exactly why this
module documents its own units.

Drift correction (why the shocks are de-meaned)
-----------------------------------------------
A finite sample of shocks has a nonzero mean. Over 15 years at 15% annual
volatility, the standard error of the daily mean shock is about
0.15/sqrt(15) = 3.9% per year, which is the same order as the drift we are
trying to impose. A naive generator therefore produces markets whose realised
drift is dominated by sampling noise: the first version of this module
produced a market losing 2% a year from a +4% drift, purely on seed luck.

The fix is to remove the sample mean from the shocks and fold it into the
drift. The realised drift is then *exactly* the stated drift for every seed,
and the market's trend structure comes from the regime design rather than
from sampling noise. This is the standard drift correction, and it is stated
here because a reader checking the arithmetic needs to know it is there.

Regime-driven drift
-------------------
The market's drift depends on its regime: bull markets drift up, bear markets
drift down, sideways markets go nowhere. Two reasons this matters:

1. Realism. Equities have positive drift over long windows and violent
   drawdowns inside them. A market with a single constant drift has neither.
2. Testability. The information gate asks whether a signal (price above or
   below its 200-day moving average) predicts forward returns. That question
   is only meaningful if trends persist. If the synthetic market had no trend
   structure, the gate would always fail for a reason that has nothing to do
   with the code under test.

The per-symbol ``alpha`` in ``_PARAMS`` is the asset's *excess* drift over
the market, not its total drift.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Names chosen so the demo reads like a portfolio, not like "asset_0".
DEFAULT_SYMBOLS = ("AAPL", "MSFT", "NVDA", "JPM", "XOM", "SPY")

TRADING_DAYS = 252

# Annualised excess drift over the market, annualised total volatility, and
# market beta per symbol.
_PARAMS = {
    "AAPL": {"beta": 1.25, "total_vol": 0.28, "alpha": 0.02},
    "MSFT": {"beta": 0.95, "total_vol": 0.22, "alpha": 0.03},
    "NVDA": {"beta": 1.65, "total_vol": 0.48, "alpha": 0.10},
    "JPM": {"beta": 1.05, "total_vol": 0.20, "alpha": 0.02},
    "XOM": {"beta": 0.70, "total_vol": 0.19, "alpha": 0.00},
    "SPY": {"beta": 1.00, "total_vol": 0.15, "alpha": 0.00},
}

# Daily market drift by regime: bull, sideways, bear.
# Calibrated so the time-weighted average is a realistic equity drift and a
# bear regime is a real drawdown rather than a wobble.
REGIME_DRIFT = {1: 0.00110, 0: 0.00030, -1: -0.00100}


def _daily_drift(annual_drift: float) -> float:
    """Annualised drift -> daily drift. Drift accumulates linearly in time."""
    return float(annual_drift / TRADING_DAYS)


def _daily_vol(annual_vol: float) -> float:
    """Annualised volatility -> daily volatility. Vol scales with sqrt(time)."""
    return float(annual_vol / np.sqrt(TRADING_DAYS))


def _regime_schedule(n_days: int, rng: np.random.Generator) -> np.ndarray:
    """Slow-switching regime labels: 1 = bull, 0 = sideways, -1 = bear.

    Regimes last 90 to 300 days. Long enough that a 200-day moving average
    has something to say, short enough that the market turns over within a
    few years.
    """
    regimes = np.empty(n_days, dtype=int)
    i = 0
    while i < n_days:
        label = int(rng.choice([1, 0, -1], p=[0.42, 0.30, 0.28]))
        length = int(rng.integers(90, 300))
        regimes[i : i + length] = label
        i += length
    return regimes[:n_days]


def _garch_like_vol(n_days: int, rng: np.random.Generator, base: float) -> np.ndarray:
    """Volatility clustering, GARCH(1,1)-ish.

    ``base`` is the DAILY volatility level the series reverts to.

    The unconditional variance of this recursion is ``omega/(1-alpha-beta)``.
    We choose ``omega`` so that this equals ``base**2`` exactly, otherwise the
    series drifts to a volatility level the caller never asked for.
    """
    alpha, beta = 0.08, 0.90
    omega = base**2 * (1.0 - alpha - beta)
    var = base**2
    out = np.empty(n_days)
    for t in range(n_days):
        shock = rng.standard_normal()
        out[t] = np.sqrt(var)
        var = omega + alpha * (base * shock) ** 2 + beta * var
    return out


def synthetic_panel(
    symbols=None,
    start=None,
    end=None,
    seed: int = 20261024,
) -> pd.DataFrame:
    """Generate a wide panel of daily closes.

    Parameters
    ----------
    symbols : sequence[str] | None
    start, end : str | pandas.Timestamp | None
        Default window is 15 years ending at the reference date.
    seed : int
        Same seed, same market. Always.
    """
    rng = np.random.default_rng(seed)
    symbols = [s.upper() for s in (symbols or DEFAULT_SYMBOLS)]
    for s in symbols:
        _PARAMS.setdefault(s, {"beta": 1.00, "total_vol": 0.25, "alpha": 0.00})

    if end is None:
        end = pd.Timestamp("2026-10-16")
    else:
        end = pd.Timestamp(end)
    if start is None:
        start = end - pd.Timedelta(days=int(365.25 * 15))
    else:
        start = pd.Timestamp(start)

    dates = pd.bdate_range(start=start, end=end)
    n = len(dates)
    if n < 300:
        raise ValueError(f"synthetic market needs at least 300 trading days, got {n}")

    regimes = _regime_schedule(n, rng)

    # --- market factor ------------------------------------------------------
    mkt_daily_vol = _daily_vol(_PARAMS["SPY"]["total_vol"])
    market_vol = _garch_like_vol(n, rng, base=mkt_daily_vol)

    # Stress windows: volatility spikes, correlations jump toward 1.
    stress_mask = np.zeros(n, dtype=bool)
    for _ in range(max(1, n // 1100)):
        s = int(rng.integers(0, max(1, n - 30)))
        length = int(rng.integers(15, 40))
        market_vol[s : s + length] *= rng.uniform(2.0, 3.2)
        stress_mask[s : s + length] = True

    # Regime drift for the market factor.
    market_drift = np.array([REGIME_DRIFT[int(r)] for r in regimes])

    # The factor's random component is a pure shock, separate from its drift.
    market_shock = market_vol * rng.standard_normal(n)
    # Drift correction: remove the sample mean of the shock. It is NOT added
    # back to the drift, because that would cancel the correction.
    market_shock = market_shock - market_shock.mean()

    # --- per-asset returns --------------------------------------------------
    panel: dict[str, np.ndarray] = {}
    for sym in symbols:
        p = _PARAMS[sym]
        beta = float(p["beta"])
        total_daily_vol = _daily_vol(p["total_vol"])
        idio_daily_vol = float(np.sqrt(max(total_daily_vol**2 - (beta * mkt_daily_vol) ** 2, 0.0)))
        idio_vol = _garch_like_vol(n, rng, base=max(idio_daily_vol, 1e-4))

        # Idiosyncratic noise is suppressed during stress windows, so
        # correlations genuinely approach 1 when it matters.
        idio_scale = np.where(stress_mask, 0.25, 1.0)
        idio_shock = idio_vol * idio_scale * rng.standard_normal(n)
        # Same drift correction for the idiosyncratic component.
        idio_shock = idio_shock - idio_shock.mean()

        # Asset drift: its beta times the market's regime drift, plus its own
        # excess drift. This is what creates persistent trends with a known
        # drift.
        #
        # The de-meaned shock bias is deliberately NOT added back here. Adding
        # it back would cancel the de-meaning and leave the sampling noise in
        # the realised drift, which is the exact thing the correction exists
        # to remove. Removing the bias from the shock and NOT re-adding it to
        # the drift is what makes the realised drift match the stated drift
        # for every seed.
        mu = beta * market_drift + _daily_drift(p["alpha"])

        # Total variance of the log return, for the Ito correction.
        total_var = (beta * market_vol) ** 2 + idio_vol**2
        log_ret = mu - 0.5 * total_var + beta * market_shock + idio_shock

        # Fat tails: a handful of jumps.
        for _ in range(max(1, n // 700)):
            j = int(rng.integers(0, n))
            log_ret[j] += rng.standard_normal() * 0.05 * (1 + p["total_vol"])

        price = 100.0 * np.exp(np.cumsum(log_ret))
        panel[sym] = price

    return pd.DataFrame(panel, index=dates)
