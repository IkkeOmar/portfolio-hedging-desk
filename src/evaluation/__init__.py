"""The evaluation gates.

Four gates, in order, short-circuiting on the first failure. Each lives in
its own module and returns a dataclass with a ``passed`` flag and the numbers
behind it.

For a HEDGING agent these are deliberately different from the usual
information/cost/compounding/stability stack. See ``gates.py`` for the
reason: a perfect hedge has zero forward-return correlation by construction,
so a return-based information gate rejects the best possible hedge.

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
    ``OLS(..., cov_type="HAC")`` for Newey-West (1987) standard errors.

``scipy.stats``
    Spearman rank correlation and the t-distribution.

``sklearn.covariance.LedoitWolf``
    Ledoit and Wolf (2004) shrinkage for the covariance estimate.

Conventions
-----------
* ``periods_per_year`` defaults to 252 (trading days).
* ``risk_free`` arguments are **per period**, never annual.
* Sharpe-style ratios use the *arithmetic mean* of excess returns, never
  CAGR. Dividing CAGR by volatility and calling the result a Sharpe ratio is
  a mislabelled statistic, and it is the single most common error in retail
  backtests.
"""

from .gates import (
    GATE_ORDER,
    GateResult,
    run_gates,
    hedgeability_gate,
    regime_information_gate,
    compensation_gate,
    stability_gate,
)
from .metrics import (
    cagr,
    annualised_vol,
    sharpe,
    sortino,
    max_drawdown,
    calmar,
    arithmetic_minus_geometric,
    volatility_drag,
    deflated_sharpe,
    spearman_ic,
    newey_west_tstat,
    ledoit_wolf_covariance,
    probability_of_backtest_overfitting,
    effective_number_of_trials,
    minimum_track_record_length,
)

__all__ = [
    "GateResult",
    "run_gates",
    "hedgeability_gate",
    "regime_information_gate",
    "compensation_gate",
    "stability_gate",
    "cagr",
    "annualised_vol",
    "sharpe",
    "sortino",
    "max_drawdown",
    "calmar",
    "arithmetic_minus_geometric",
    "volatility_drag",
    "deflated_sharpe",
    "spearman_ic",
    "newey_west_tstat",
    "ledoit_wolf_covariance",
    "probability_of_backtest_overfitting",
    "effective_number_of_trials",
    "minimum_track_record_length",
]
