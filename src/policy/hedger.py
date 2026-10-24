"""The Hedger seat: what should the hedge be, and how big?

This is where the actual finance lives. Four ideas, in order of importance.

1. **Beta.** How much does this holding move when the market moves? Estimated
   by ordinary least squares of the asset's daily returns on the benchmark's
   daily returns, over a trailing window. No look-ahead: the window ends
   before the decision date.

2. **Shrinkage.** A raw beta estimated from 252 noisy observations is
   unreliable. We pull it toward zero by a factor that depends on how
   statistically convincing the estimate is:

       w       = t^2 / (t^2 + k)        t = t-statistic of the beta estimate
       beta*   = w * beta

   This is a precision-weighted shrinkage: the weight is the signal-to-noise
   ratio of the estimate. When the estimate is precise (large t), w is near 1
   and we trust it. When it is noise (small t), w is near 0 and we hedge
   nothing. The shrinkage constant ``k`` is in the config file, not in the
   code.

   A professional will note that this shrinks toward zero, while the textbook
   beta estimators shrink elsewhere: Blume (1971) shrinks toward ONE, and
   Vasicek (1973) shrinks toward the CROSS-SECTIONAL MEAN of betas. We
   shrink toward zero on purpose: for a *hedge*, the conservative claim is
   "this holding does not move with the market", and we only hedge what we
   can defend. Lally (1998), "An Examination of Blume and Vasicek Betas",
   Financial Review 33(3), 183-198, doi:10.1111/j.1540-6288.1998.tb01390.x,
   supports the choice directly: "Blume's implicit forecast of any tendency
   for true betas to regress towards one may not be desirable".

   See docs/METHODOLOGY.md section 4.1 for the full attribution, including
   what we could NOT verify.

3. **Minimum-variance hedge ratio.** Given a portfolio return series and a
   hedge instrument return series, the dollar hedge per dollar of portfolio
   that minimises portfolio variance is

       f* = -cov(r_p, r_h) / var(r_h)

   Derivation: portfolio variance with a hedge of ``f`` dollars per dollar of
   portfolio is

       Var(r_p + f*r_h) = Var(r_p) + 2*f*cov(r_p, r_h) + f^2*Var(r_h)

   Differentiate with respect to ``f`` and set to zero:

       2*cov + 2*f*Var(r_h) = 0   =>   f* = -cov(r_p, r_h) / Var(r_h)

   For a long-equity portfolio hedged with a market instrument, cov is
   positive, so ``f*`` is negative: short the hedge. Correct.

   Note this is *not* the same as "hedge to beta zero". Beta-neutral means
   "the portfolio should not move with the market". Minimum variance means
   "the portfolio should be as calm as possible". They differ whenever the
   hedge instrument has its own specific risk. Minimum variance is the
   statistically optimal answer; beta-neutral is the one you can explain in
   one sentence. We compute both and record both.

4. **The dial.** The optimal ratio is multiplied by the regime dial, so the
   desk does the *full* optimal hedge in a stress regime and a fraction of it
   in a calm one. This is a policy choice, not a statistical result, and it is
   stated as such.

Important framing
-----------------
The numbers this seat produces (volatility reduction, reward-to-risk) are
**screening estimates, not forecasts**. They answer "is this hedge large
enough to be worth its cost, and is it in the right direction". They do NOT
answer "will this make money". The answer to that question comes from the
four evaluation gates, run on realised, walk-forward, cost-inclusive data.
The whole point of this repository is that the analytic estimate is the
hypothesis and the backtest is the test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from ..ledger.schema import HedgeProposal, snapshot_hash

TRADING_DAYS = 252


@dataclass
class HedgeEstimate:
    """Everything the Hedger needs to know about one asset."""

    symbol: str
    beta: float                  # raw OLS beta
    beta_shrunk: float           # after shrinkage
    t_stat: float                # t-statistic of the beta estimate
    shrinkage_weight: float      # w in w = t^2/(t^2+k)
    r_squared: float
    n_obs: int
    idio_vol: float              # annualised residual volatility
    detail: dict[str, Any] = field(default_factory=dict)


class HedgePolicy:
    """Estimates betas, sizes hedges, and produces proposals."""

    def __init__(
        self,
        benchmark: str,
        hedge_instrument: str,
        lookback_days: int = 252,
        shrinkage_k: float = 60.0,
        horizon_days: int = 21,
    ):
        self.benchmark = benchmark
        self.hedge_instrument = hedge_instrument
        self.lookback_days = int(lookback_days)
        self.shrinkage_k = float(shrinkage_k)
        self.horizon_days = int(horizon_days)

    # ----------------------------------------------------------- beta + shrink
    def estimate_beta(
        self, asset_returns: pd.Series, bench_returns: pd.Series
    ) -> HedgeEstimate:
        """OLS beta of ``asset_returns`` on ``bench_returns``, then shrunk."""
        joined = pd.concat([asset_returns, bench_returns], axis=1).dropna()
        joined.columns = ["asset", "bench"]
        n = len(joined)
        if n < 30:
            raise ValueError(f"need at least 30 overlapping observations to estimate a beta, got {n}")

        x = joined["bench"].to_numpy(dtype=float)
        y = joined["asset"].to_numpy(dtype=float)
        x_dev = x - x.mean()
        y_dev = y - y.mean()
        sxx = float((x_dev**2).sum())
        if sxx <= 0:
            raise ValueError("benchmark has zero variance over the window")
        beta = float((x_dev * y_dev).sum() / sxx)

        # Residual variance and the standard error of the slope.
        resid = y_dev - beta * x_dev
        dof = max(n - 2, 1)
        sigma2 = float((resid**2).sum() / dof)
        se_beta = float(np.sqrt(sigma2 / sxx))
        t_stat = float(beta / se_beta) if se_beta > 0 else 0.0
        sst = float((y_dev**2).sum())
        r_squared = float(1.0 - (resid**2).sum() / sst) if sst > 0 else 0.0

        # Shrinkage weight. t^2/(t^2+k). Defined for negative betas too: we
        # shrink the magnitude, not the sign.
        t2 = t_stat**2
        w = t2 / (t2 + self.shrinkage_k) if (t2 + self.shrinkage_k) > 0 else 0.0

        idio_vol = float(np.sqrt(sigma2) * np.sqrt(TRADING_DAYS))
        return HedgeEstimate(
            symbol="",
            beta=beta,
            beta_shrunk=float(beta * w),
            t_stat=t_stat,
            shrinkage_weight=float(w),
            r_squared=r_squared,
            n_obs=int(n),
            idio_vol=idio_vol,
        )

    def estimate_all(
        self, cutoff_panel: pd.DataFrame, symbols: list[str]
    ) -> dict[str, HedgeEstimate]:
        """Estimate a beta for each symbol against the benchmark.

        ``cutoff_panel`` must contain only prices from before the decision
        date.
        """
        if self.benchmark not in cutoff_panel.columns:
            raise KeyError(f"benchmark {self.benchmark!r} not in panel columns")
        window = cutoff_panel.tail(self.lookback_days + 10)
        returns = window.pct_change().dropna(how="all")
        bench = returns[self.benchmark]
        out: dict[str, HedgeEstimate] = {}
        for sym in symbols:
            if sym not in returns.columns:
                continue
            est = self.estimate_beta(returns[sym], bench)
            est.symbol = sym
            out[sym] = est
        return out

    # ----------------------------------------------------------------- sizing
    @staticmethod
    def minimum_variance_hedge(
        portfolio_returns: pd.Series,
        hedge_returns: pd.Series,
    ) -> tuple[float, float]:
        """Return ``(f*, cov)``: the hedge dollars per dollar of portfolio that
        minimises portfolio variance, and the covariance it came from.

        ``f* = -cov(r_p, r_h) / var(r_h)``. Positive ``f*`` means "go long
        the hedge per dollar of portfolio", negative means "go short it".

        The covariance is returned because it tells you whether the hedge is
        worth anything at all: if the covariance is near zero, there is no
        market risk to remove.
        """
        joined = pd.concat([portfolio_returns, hedge_returns], axis=1).dropna()
        if len(joined) < 30:
            raise ValueError("not enough overlapping observations for the hedge ratio")
        rp = joined.iloc[:, 0].to_numpy(dtype=float)
        rh = joined.iloc[:, 1].to_numpy(dtype=float)
        var_h = float(((rh - rh.mean()) ** 2).sum() / max(len(rh) - 1, 1))
        if var_h <= 0:
            raise ValueError("hedge instrument has zero variance over the window")
        cov = float(((rp - rp.mean()) * (rh - rh.mean())).sum() / max(len(rp) - 1, 1))
        return -cov / var_h, cov

    def build_proposal(
        self,
        date: str,
        cutoff_panel: pd.DataFrame,
        candidates: list,
        equity: float,
        costs: Any,
        dial: float,
        max_hedge_pct_equity: float,
    ) -> HedgeProposal | None:
        """Build the hedge proposal for one day, or ``None`` if none is justified.

        ``cutoff_panel`` holds prices up to and including the decision date.
        """
        if equity <= 0 or not candidates:
            return None
        if self.hedge_instrument not in cutoff_panel.columns:
            return None

        returns = cutoff_panel.pct_change().dropna(how="all")
        if len(returns) < 40:
            return None

        symbols = [c.symbol for c in candidates]
        sub = returns[symbols].dropna()
        if len(sub) < 40:
            return None

        weights = np.array([c.weight for c in candidates], dtype=float)
        if weights.sum() <= 0:
            return None
        weights = weights / weights.sum()

        # Portfolio return series, reconstructed from the candidate weights.
        portfolio_returns = pd.Series(sub.to_numpy(dtype=float) @ weights, index=sub.index)

        hedge_returns = returns[self.hedge_instrument].reindex(sub.index)
        # Keep only the dates where the assets AND the hedge instrument all
        # have prices, so every series below is on one common index.
        common = sub.index.intersection(hedge_returns.dropna().index)
        if len(common) < 40:
            return None
        asset_returns = sub.loc[common].to_numpy(dtype=float)
        portfolio_returns = pd.Series(asset_returns @ weights, index=common)
        rh = hedge_returns.loc[common]
        rp = portfolio_returns

        f_star, cov = self.minimum_variance_hedge(rp, rh)

        # Portfolio beta from the (already shrunk) candidate betas.
        portfolio_beta = float(np.sum(weights * np.array([c.beta for c in candidates])))

        # Beta of the hedge instrument to the benchmark, for the beta-neutral
        # comparison. The *total* volatility of the hedge leg is what carries
        # the risk: if you are short SPY and SPY rallies 20%, you lose 20% of
        # that leg whatever else is true. The OLS residual of the hedge on the
        # benchmark is zero when the hedge instrument IS the benchmark, so it
        # is only used as a diagnostic, never as the risk term.
        hedge_beta = 1.0
        hedge_total_vol = float(np.std(rh, ddof=1))
        hedge_specific_vol = float("nan")
        if self.benchmark in returns.columns:
            hb = self.estimate_beta(returns[self.hedge_instrument], returns[self.benchmark])
            hedge_beta = hb.beta
            hedge_specific_vol = hb.idio_vol

        # Size the hedge: the optimal ratio, scaled by the dial, clipped to cap.
        target_fraction = float(np.clip(f_star * dial, -max_hedge_pct_equity, max_hedge_pct_equity))
        target_notional = target_fraction * equity

        # ---- volatility before and after, exactly ----------------------------
        cov_matrix = np.cov(asset_returns, rowvar=False, ddof=1)
        var_p = float(weights @ cov_matrix @ weights)
        rh_arr = rh.to_numpy(dtype=float)
        var_h = float(np.var(rh_arr, ddof=1))
        cov_ph = float(np.mean((rp.to_numpy() - rp.mean()) * (rh_arr - rh_arr.mean())))
        f = target_fraction
        var_hedged = var_p + 2.0 * f * cov_ph + f * f * var_h
        vol_before = float(np.sqrt(max(var_p, 0.0)))
        vol_after = float(np.sqrt(max(var_hedged, 0.0)))
        vol_reduction_pct = float(100.0 * (1.0 - vol_after / vol_before)) if vol_before > 0 else 0.0

        # ---- benefit and risk, both stated as what they are ------------------
        horizon = self.horizon_days
        # Benefit: the reduction in the *dispersion* of portfolio outcomes over
        # the horizon, in dollars. This is a risk measure, not expected P&L.
        #
        # Both the benefit and the risk below must use the SAME scaling:
        # a daily volatility becomes a horizon volatility by multiplying by
        # sqrt(horizon). An earlier version used sqrt(horizon/252) here and
        # sqrt(horizon) in the risk term, which understated the ratio by a
        # factor of sqrt(252) - about 16x - and made every proposal look
        # worse than it was.
        est_reward_usd = max(vol_before - vol_after, 0.0) * equity * np.sqrt(horizon)
        # Risk: the one-sigma loss the hedge leg itself can cause over the
        # horizon, in dollars. This uses the hedge instrument's TOTAL
        # volatility, not its residual against the benchmark: if you are short
        # SPY and SPY rallies 20%, you lose 20% of that leg whatever else is
        # true. Using the residual would score a beta-1 hedge instrument as
        # riskless, which is false.
        est_risk_usd = (
            abs(f) * equity * hedge_total_vol / np.sqrt(TRADING_DAYS) * np.sqrt(horizon)
        )
        rrr = (est_reward_usd / est_risk_usd) if est_risk_usd > 0 else 0.0

        est_cost_bps = float(costs.round_trip_bps)

        proposal = HedgeProposal(
            proposal_id=f"prop-{date}-{self.hedge_instrument}",
            date=date,
            hedge_symbol=self.hedge_instrument,
            target_notional=float(target_notional),
            hedge_beta=float(hedge_beta),
            portfolio_beta=portfolio_beta,
            hedged_beta=float(portfolio_beta + f * hedge_beta),
            est_vol_reduction_pct=float(vol_reduction_pct),
            est_cost_bps=est_cost_bps,
            est_reward_usd=float(est_reward_usd),
            est_risk_usd=float(est_risk_usd),
            reward_to_risk=float(rrr),
            rationale=(
                f"portfolio beta {portfolio_beta:.2f}; min-variance ratio {f_star:.2f}; "
                f"dial {dial:.2f}; annualised vol {vol_before:.1%} -> {vol_after:.1%}"
            ),
            detail={
                "min_variance_ratio": float(f_star),
                "beta_neutral_fraction": float(-portfolio_beta / hedge_beta) if hedge_beta else 0.0,
                "cov_portfolio_hedge": float(cov_ph),
                "vol_before_annual": vol_before * np.sqrt(TRADING_DAYS),
                "vol_after_annual": vol_after * np.sqrt(TRADING_DAYS),
                "hedge_specific_vol_annual": float(hedge_specific_vol),
                "hedge_fraction": float(f),
                "dial": float(dial),
                "equity": float(equity),
                "horizon_days": int(horizon),
                "symbols": symbols,
                "weights": [float(x) for x in weights],
                "input_hash": snapshot_hash(
                    {"date": date, "symbols": symbols, "dial": float(dial)}
                ),
            },
        )
        return proposal
