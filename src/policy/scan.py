"""The Scan seat: which holdings are worth hedging?

A scan is a *screen*, not a decision. It ranks the portfolio's holdings by
how much market risk each one contributes, and passes the top few to the
Hedger.

The contribution metric is the key concept, and it is worth understanding.

A holding's variance splits into a part that comes from the market and a part
that comes from the asset's own behaviour. Using the same one-factor model the
data generator itself uses:

    total variance of holding i
        = (beta_i * sigma_m)**2 + sigma_eps,i**2
        = systematic variance + idiosyncratic variance

The first term is the risk that comes from moving *with* the market (systematic
risk). The second is risk that comes from the asset's own behaviour
(idiosyncratic risk). You cannot hedge idiosyncratic risk with a market
instrument, so only the first term is worth hedging.

That is the whole reason the Scan seat exists: it separates the risk a hedge
can actually remove from the risk it cannot.

Why both terms are variances
----------------------------

The two terms are ADDED, so they have to be on the same scale, and that scale
has to be a variance. The market's variance has to enter, because how much of
a holding's risk is market risk depends on how volatile the market is: in a
calm market most of a holding's risk is its own, and in a violent market most
of it is the market's.

An earlier version of this file computed

    systematic = (portfolio_beta - beta_i) * beta_i     <- dimensionless
    idiosyncratic = beta_i * sigma_i**2                <- a variance

and took their ratio. That is a defect, and it was not a subtle one:

  * the two terms were on different scales, so their sum had no meaning;
  * the market's variance never entered, so a holding's "hedgeable share"
    could not change when the market's volatility changed -- and it must;
  * for any holding whose beta is ABOVE the portfolio's beta (the ones most
    exposed to the market, and therefore the most worth hedging), the
    systematic term came out NEGATIVE, so the share was clipped to zero and
    the desk reported "not hedgeable" about exactly the holdings a market
    hedge can do the most for.

The corrected metric is below, and ``tests/test_scan_metric.py`` pins it.

Look-ahead discipline
----------------------
``scan`` takes a cut-off panel and does no date filtering of its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

TRADING_DAYS = 252


@dataclass
class ScanCandidate:
    """One holding that passed the screen."""

    symbol: str
    market_value: float
    weight: float                # share of portfolio value
    beta: float
    idio_vol: float              # annualised, residual after the market factor
    systematic_contribution: float
    idiosyncratic_contribution: float
    total_contribution: float
    hedgeable_share: float        # systematic / total, in [0, 1]
    detail: dict[str, Any] = field(default_factory=dict)


class ScanPolicy:
    """Ranks holdings by market-risk contribution."""

    def __init__(self, benchmark: str, max_candidates: int = 5, min_weight: float = 0.0):
        self.benchmark = benchmark
        self.max_candidates = int(max_candidates)
        self.min_weight = float(min_weight)

    def scan(
        self,
        cutoff_panel: pd.DataFrame,
        holdings,
        betas: dict[str, float],
        idio_vols: dict[str, float],
    ) -> list[ScanCandidate]:
        """Return the holdings worth hedging, most important first.

        ``cutoff_panel`` must contain only prices from before the decision
        date.
        """
        if cutoff_panel.empty:
            raise ValueError("cut-off panel is empty")

        # The market's annualised volatility over the cut-off window.
        # Estimated from the benchmark's own returns in the panel, so the
        # metric sees the market as it is at the decision date.
        if self.benchmark not in cutoff_panel.columns:
            raise KeyError(
                f"benchmark {self.benchmark!r} not in panel columns; the scan "
                "seat needs it to split a holding's risk into its market part "
                "and its own part"
            )
        bench_returns = cutoff_panel[self.benchmark].pct_change().dropna()
        if len(bench_returns) < 20:
            raise ValueError(
                f"need at least 20 benchmark returns to estimate market "
                f"volatility, got {len(bench_returns)}"
            )
        market_vol = float(bench_returns.std(ddof=1) * np.sqrt(TRADING_DAYS))

        last = cutoff_panel.ffill().iloc[-1]
        values: dict[str, float] = {}
        for h in holdings:
            price = last.get(h.symbol, np.nan)
            values[h.symbol] = float(h.shares) * float(price) if np.isfinite(price) else 0.0

        total_value = sum(v for v in values.values() if np.isfinite(v) and v > 0)
        if total_value <= 0:
            return []

        candidates: list[ScanCandidate] = []
        for h in holdings:
            v = values.get(h.symbol, 0.0)
            if not np.isfinite(v) or v <= 0:
                continue
            weight = v / total_value
            if weight < self.min_weight:
                continue
            beta = float(betas.get(h.symbol, 0.0))
            idio = float(idio_vols.get(h.symbol, 0.0))
            # Both terms are ANNUALISED VARIANCES, so they can be added.
            #
            #   systematic     = (beta * sigma_m)**2  -- the market's part
            #   idiosyncratic = idio**2             -- the asset's own part
            #
            # sigma_m is the market's annualised volatility over the same
            # cut-off window the betas were estimated on. It is read from
            # the panel rather than from the config, because it has to be
            # the volatility of THIS market on THIS window; a constant
            # would make the metric unable to see a regime change.
            systematic = (beta * market_vol) ** 2
            idiosyncratic = idio**2
            total = systematic + idiosyncratic
            hedgeable = systematic / total if total > 0 else 0.0
            candidates.append(
                ScanCandidate(
                    symbol=h.symbol,
                    market_value=v,
                    weight=weight,
                    beta=beta,
                    idio_vol=idio,
                    systematic_contribution=systematic,
                    idiosyncratic_contribution=idiosyncratic,
                    total_contribution=total,
                    hedgeable_share=float(np.clip(hedgeable, 0.0, 1.0)),
                )
            )

        # Rank by total market-risk contribution, descending. Ties broken by
        # symbol so the ordering is deterministic across runs.
        candidates.sort(key=lambda c: (-c.total_contribution, c.symbol))
        return candidates[: self.max_candidates]
