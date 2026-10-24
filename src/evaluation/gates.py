"""The evaluation gates for a HEDGING agent.

Why these are not the usual four
-------------------------------
The standard four-gate stack for a trading strategy asks: *does the signal
predict forward RETURNS?* (information), *does it survive costs?* (cost),
*does it compound?* (compounding), *is it stable?* (stability).

That framing is structurally wrong for a hedge, and getting it wrong is the
single easiest way to publish a hedge that does not work. The reason is
almost algebraic:

    A PERFECT HEDGE HAS ZERO FORWARD-RETURN CORRELATION.

If a hedge removes exactly the risk you are worried about, the hedged
portfolio's returns are, by construction, uncorrelated with whatever you
were hedging. An information-coefficient gate would therefore reject the
best possible hedge and pass a useless one. This is not a threshold to tune;
it is the wrong question.

So the gates here are re-derived from what a hedge actually claims:

1. **HEDGEABILITY** (Healy & Lo's condition B). Is there anything to hedge?
   The hedging equation's R^2 must clear 25%. Below that, the factor explains
   too little of the portfolio's variance and "implementing a beta-hedging
   overlay can actually increase the overall risk to the investor while
   simultaneously reducing the expected return".
2. **REGIME INFORMATION**. Does the desk's dial anticipate forward realised
   volatility? A dial that is high when the market is calm is backwards.
   Here the expected relationship is POSITIVE: dial up, volatility coming.
3. **COMPENSATION** (Healy & Lo's condition A2). Is the risk reduction worth
   what it costs, counting both transaction costs and the return premium
   given up? The test is the Sharpe ratio, hedged versus unhedged.
4. **STABILITY**. Does the risk reduction hold across regimes and across
   consecutive out-of-sample windows?

Reference for the framework: Healy, A. D. and Lo, A. W. (2010), "Jumping the
Gates: Using Beta-Overlay Strategies to Hedge Liquidity Constraints",
*Hedge Funds*, Chapter 11. DOI 10.1515/9781400835812.303.

Thresholds live at the top of this file as named constants, so every judgement
call is visible in one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .metrics import (
    annualised_vol,
    arithmetic_minus_geometric,
    cagr,
    deflated_sharpe,
    max_drawdown,
    newey_west_tstat,
    sharpe,
    sortino,
    spearman_ic,
    volatility_drag,
)

# --------------------------------------------------------------- thresholds
# Healy and Lo (2010), Section 2: "a very rough guideline for the minimum
# R^2 needed to implement an effective hedging-overlay strategy is 25%".
# The gate stack, in the order it runs. This is the single source of truth
# for the order: ``run_gates`` short-circuits at the first failure, so a
# report can contain fewer than four gates. The dashboard needs to know
# which gates never ran, and it must not guess -- so it reads this.
GATE_ORDER = ("hedgeability", "regime_information", "compensation", "stability")

MIN_R_SQUARED = 0.25

# Does the dial anticipate forward volatility? Expected sign is POSITIVE:
# a high dial means "hedge more", which should mean "volatility is coming".
MIN_VOL_IC = 0.02
MIN_VOL_IC_TSTAT = 1.96

# Compensation: the hedged Sharpe must beat the unhedged Sharpe for the risk
# reduction to have paid for itself.
MIN_SHARPE_IMPROVEMENT = 0.0

# Stability.
MIN_REGIME_PASS_FRACTION = 0.5
MIN_WALKFORWARD_PASS_FRACTION = 0.7


@dataclass
class GateResult:
    """One gate's verdict."""

    name: str
    passed: bool
    headline: str
    metrics: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "headline": self.headline,
            "metrics": self.metrics,
            "notes": self.notes,
        }


# ------------------------------------------------------------------- gate 1
def hedgeability_gate(
    r_squared: float,
    hedge_instrument: str = "the hedge instrument",
) -> GateResult:
    """Is there anything to hedge?

    The R^2 of the hedging equation: the fraction of the portfolio's return
    variance explained by the hedge instrument. Healy and Lo's condition (B).

    Below the threshold, hedging cannot help: the factor captures too little
    of the variance, so the overlay adds cost and tracking error while
    removing almost nothing.
    """
    notes: list[str] = []
    passed = bool(np.isfinite(r_squared) and r_squared >= MIN_R_SQUARED)

    if not np.isfinite(r_squared):
        notes.append("R^2 could not be estimated; there is no evidence the hedge instrument explains anything.")
    elif not passed:
        notes.append(
            f"R^2 = {r_squared:.1%} is below the {MIN_R_SQUARED:.0%} threshold "
            f"(Healy and Lo 2010). Hedging here would add cost and tracking error "
            f"for almost no risk reduction, and could increase total risk."
        )
    else:
        notes.append(
            f"R^2 = {r_squared:.1%} clears the {MIN_R_SQUARED:.0%} threshold, so "
            f"{hedge_instrument} explains enough of the portfolio's variance to be worth hedging."
        )

    # The volatility reduction a full hedge would deliver, per Healy and Lo
    # equation (7): delta = 1 - sqrt(1 - R^2).
    predicted = (
        float(1.0 - np.sqrt(1.0 - r_squared))
        if np.isfinite(r_squared) and 0 <= r_squared <= 1
        else float("nan")
    )

    return GateResult(
        "hedgeability",
        passed,
        f"R^2 {r_squared:.1%}" if np.isfinite(r_squared) else "R^2 unavailable",
        {
            "r_squared": float(r_squared) if np.isfinite(r_squared) else None,
            "threshold": MIN_R_SQUARED,
            "implied_max_vol_reduction_pct": float(predicted * 100.0) if np.isfinite(predicted) else None,
            "source": "Healy and Lo (2010), condition (B) and equation (7)",
        },
        notes,
    )


# ------------------------------------------------------------------- gate 2
def regime_information_gate(
    dial: np.ndarray,
    forward_vol: np.ndarray,
) -> GateResult:
    """Does the desk's dial anticipate forward volatility?

    The dial is the desk's decision variable: how much hedging is worth doing
    now. It is built from the volatility percentile and the trend state. If
    it were uninformative, the desk would be hedging at random times.

    The expected sign is POSITIVE. A high dial means "hedge more", and that
    should mean "volatility is coming", so the dial should rank periods of
    high forward volatility above periods of low forward volatility.

    Two independent pieces of evidence: the Spearman rank correlation, and a
    Newey-West HAC t-statistic on the slope, because daily signals are
    autocorrelated and a naive t-statistic would overstate the evidence.
    """
    d = np.asarray(dial, dtype=float)
    v = np.asarray(forward_vol, dtype=float)
    mask = np.isfinite(d) & np.isfinite(v)
    d, v = d[mask], v[mask]
    n = len(d)

    if n < 20:
        return GateResult(
            "regime_information",
            False,
            f"only {n} usable observations; need at least 20",
            {"n_obs": int(n)},
            ["Not enough decision dates to test whether the dial is informative."],
        )

    ic = spearman_ic(d, v)
    tstat = newey_west_tstat(d, v)

    ic_ok = bool(np.isfinite(ic) and ic >= MIN_VOL_IC)
    t_ok = bool(np.isfinite(tstat) and tstat >= MIN_VOL_IC_TSTAT)
    passed = bool(ic_ok and t_ok)

    notes: list[str] = []
    if not ic_ok:
        notes.append(
            f"rank IC between the dial and forward volatility is {ic:.4f}, below the "
            f"{MIN_VOL_IC:.3f} floor. The dial does not order volatility ahead of time."
        )
    if not t_ok:
        notes.append(
            f"HAC t-statistic is {tstat:.2f}, below {MIN_VOL_IC_TSTAT}; we cannot rule out "
            f"that this is noise."
        )
    if passed:
        notes.append(
            "The dial ranks forward volatility correctly, so the desk is hedging in "
            "the right direction more often than chance."
        )

    return GateResult(
        "regime_information",
        passed,
        f"vol IC {ic:.4f}, HAC t {tstat:.2f}" if np.isfinite(ic) else "no usable observations",
        {
            "n_obs": int(n),
            "ic_dial_vs_forward_vol": float(ic) if np.isfinite(ic) else None,
            "ic_threshold": MIN_VOL_IC,
            "hac_tstat": float(tstat) if np.isfinite(tstat) else None,
            "tstat_threshold": MIN_VOL_IC_TSTAT,
            "expected_sign": "positive",
        },
        notes,
    )


# ------------------------------------------------------------------- gate 3
def compensation_gate(
    hedged_returns: pd.Series,
    unhedged_returns: pd.Series,
    total_cost: float = 0.0,
    r_squared: float = float("nan"),
) -> GateResult:
    """Did the risk reduction pay for itself?

    Healy and Lo's condition (A2): the investor believes the risk reduction is
    worth the price of forgoing the normally positive expected returns of the
    hedged factor. So the question is not "did the hedged portfolio return
    more" - it is "is the hedged portfolio better on a risk-adjusted basis".

    The test is the Sharpe ratio, hedged versus unhedged, with transaction
    costs already deducted from the hedged series. We also report the
    volatility reduction against the theoretical ceiling implied by R^2, so a
    reader can see whether the overlay is delivering what the theory says it
    can.
    """
    hedged_sharpe = sharpe(hedged_returns)
    unhedged_sharpe = sharpe(unhedged_returns)
    improvement = hedged_sharpe - unhedged_sharpe

    hedged_vol = annualised_vol(hedged_returns)
    unhedged_vol = annualised_vol(unhedged_returns)
    realised_reduction = (
        float(1.0 - hedged_vol / unhedged_vol)
        if np.isfinite(unhedged_vol) and unhedged_vol > 0
        else float("nan")
    )

    predicted = (
        float(1.0 - np.sqrt(1.0 - r_squared))
        if np.isfinite(r_squared) and 0 <= r_squared <= 1
        else float("nan")
    )
    realised_vs_predicted = (
        float(realised_reduction / predicted)
        if np.isfinite(predicted) and predicted > 0 and np.isfinite(realised_reduction)
        else float("nan")
    )

    hedged_dd = max_drawdown(hedged_returns)
    unhedged_dd = max_drawdown(unhedged_returns)

    passed = bool(
        np.isfinite(improvement)
        and improvement > MIN_SHARPE_IMPROVEMENT
        and np.isfinite(realised_reduction)
        and realised_reduction > 0
    )

    notes: list[str] = []
    if not np.isfinite(hedged_sharpe) or not np.isfinite(unhedged_sharpe):
        notes.append("Sharpe ratios could not be computed for one of the two portfolios.")
    else:
        notes.append(
            f"Sharpe {hedged_sharpe:.3f} hedged vs {unhedged_sharpe:.3f} unhedged "
            f"({improvement:+.3f})."
        )
        if improvement <= 0:
            notes.append(
                "The hedge did not improve the risk-adjusted return, so it did not pay "
                "for its costs and its forgone risk premium."
            )
    if np.isfinite(realised_reduction) and realised_reduction > 0:
        notes.append(
            f"annualised volatility {unhedged_vol:.2%} -> {hedged_vol:.2%} "
            f"({realised_reduction:+.1%})."
        )
    if np.isfinite(realised_vs_predicted):
        notes.append(
            f"the realised reduction is {realised_vs_predicted:.0%} of the "
            f"{predicted:.1%} the R^2 implies (Healy and Lo equation 7). A ratio below "
            f"100% is normal: the desk hedges selectively, not continuously."
        )
    if np.isfinite(hedged_dd) and np.isfinite(unhedged_dd):
        notes.append(f"max drawdown {unhedged_dd:.1%} -> {hedged_dd:.1%}.")

    return GateResult(
        "compensation",
        passed,
        f"Sharpe {hedged_sharpe:.3f} vs {unhedged_sharpe:.3f} unhedged",
        {
            "hedged_sharpe": float(hedged_sharpe),
            "unhedged_sharpe": float(unhedged_sharpe),
            "sharpe_improvement": float(improvement),
            "hedged_annualised_vol": float(hedged_vol),
            "unhedged_annualised_vol": float(unhedged_vol),
            "realised_vol_reduction_pct": float(realised_reduction * 100.0) if np.isfinite(realised_reduction) else None,
            "implied_max_vol_reduction_pct": float(predicted * 100.0) if np.isfinite(predicted) else None,
            "realised_vs_implied": float(realised_vs_predicted) if np.isfinite(realised_vs_predicted) else None,
            "hedged_max_drawdown": float(hedged_dd),
            "unhedged_max_drawdown": float(unhedged_dd),
            "total_cost": float(total_cost),
            "hedged_cagr": float(cagr(hedged_returns)),
            "unhedged_cagr": float(cagr(unhedged_returns)),
        },
        notes,
    )


# ------------------------------------------------------------------- gate 4
def stability_gate(
    hedged_returns: pd.Series,
    unhedged_returns: pd.Series,
    regimes: pd.Series | None = None,
    walkforward_sharpes: list[float] | None = None,
) -> GateResult:
    """Does the risk reduction hold across regimes and across time?

    Two tests, because they fail differently:

    * **Regime.** Split by market regime and check the per-regime change in
      Sharpe. A hedge that only helps in crises is a crisis hedge, and the
      reader deserves to know that.
    * **Walk-forward.** Consecutive out-of-sample windows. A hedge that only
      works in the first half of the sample has learned the sample.
    """
    metrics: dict[str, Any] = {}
    notes: list[str] = []
    passed = True

    if regimes is not None and len(regimes):
        aligned = pd.concat(
            [hedged_returns.rename("h"), unhedged_returns.rename("u"), regimes.rename("regime")],
            axis=1,
        ).dropna()
        per_regime: dict[str, float] = {}
        for label, group in aligned.groupby("regime"):
            hs = sharpe(group["h"])
            us = sharpe(group["u"])
            if np.isfinite(hs) and np.isfinite(us):
                per_regime[str(label)] = float(hs - us)
        populated = {k: v for k, v in per_regime.items() if np.isfinite(v)}
        positive = sum(1 for v in populated.values() if v > 0)
        fraction = positive / len(populated) if populated else 0.0
        metrics["per_regime_sharpe_improvement"] = per_regime
        metrics["regimes_populated"] = len(populated)
        metrics["regimes_improved"] = positive
        metrics["regime_pass_fraction"] = float(fraction)
        if populated and fraction < MIN_REGIME_PASS_FRACTION:
            passed = False
            notes.append(
                f"the hedge improved the Sharpe in only {positive}/{len(populated)} regimes "
                f"({fraction:.0%} < {MIN_REGIME_PASS_FRACTION:.0%})."
            )
        if len(populated) < 2:
            notes.append(f"only {len(populated)} regime(s) populated; the regime test is weak here.")

    if walkforward_sharpes:
        finite = [s for s in walkforward_sharpes if np.isfinite(s)]
        positive = sum(1 for s in finite if s > 0)
        fraction = positive / len(finite) if finite else 0.0
        metrics["walkforward_sharpes"] = [float(s) for s in walkforward_sharpes]
        metrics["walkforward_windows"] = len(finite)
        metrics["walkforward_positive"] = positive
        metrics["walkforward_pass_fraction"] = float(fraction)
        if finite and fraction < MIN_WALKFORWARD_PASS_FRACTION:
            passed = False
            notes.append(
                f"positive out-of-sample Sharpe in {positive}/{len(finite)} windows "
                f"({fraction:.0%} < {MIN_WALKFORWARD_PASS_FRACTION:.0%})."
            )
    else:
        notes.append("no walk-forward windows supplied; the stability test is incomplete.")

    if not metrics:
        return GateResult("stability", False, "no regime or walk-forward data", metrics, notes)

    bits = []
    if "regime_pass_fraction" in metrics:
        bits.append(f"{metrics['regimes_improved']}/{metrics['regimes_populated']} regimes")
    if "walkforward_pass_fraction" in metrics:
        bits.append(f"{metrics['walkforward_positive']}/{metrics['walkforward_windows']} OOS windows")
    return GateResult("stability", passed, ", ".join(bits) or "insufficient data", metrics, notes)


# ------------------------------------------------------------------ runner
def run_gates(
    r_squared: float,
    dial: np.ndarray,
    forward_vol: np.ndarray,
    hedged_returns: pd.Series,
    unhedged_returns: pd.Series,
    regimes: pd.Series | None = None,
    walkforward_sharpes: list[float] | None = None,
    total_cost: float = 0.0,
    hedge_instrument: str = "the hedge instrument",
) -> tuple[list[GateResult], bool]:
    """Run the four gates in order and stop at the first failure.

    Returns the list of gate results (which may be short) and an overall
    boolean. A report is written either way; see ``report.py``.
    """
    results: list[GateResult] = []

    g1 = hedgeability_gate(r_squared, hedge_instrument=hedge_instrument)
    results.append(g1)
    if not g1.passed:
        return results, False

    g2 = regime_information_gate(dial, forward_vol)
    results.append(g2)
    if not g2.passed:
        return results, False

    g3 = compensation_gate(hedged_returns, unhedged_returns, total_cost=total_cost, r_squared=r_squared)
    results.append(g3)
    if not g3.passed:
        return results, False

    g4 = stability_gate(
        hedged_returns,
        unhedged_returns,
        regimes=regimes,
        walkforward_sharpes=walkforward_sharpes,
    )
    results.append(g4)
    return results, bool(g4.passed)
