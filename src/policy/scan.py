"""The Scan seat: which holdings are worth hedging?

A scan is a *screen*, not a decision. It ranks the portfolio's holdings by
how much market risk each one contributes, and passes the top few to the
Hedger.

The contribution metric is the key concept, and it is worth understanding:

    market risk contribution of holding i
        = (portfolio_beta - beta_i) * beta_i + (beta_i * sigma_i^2)

The first term is the risk that comes from moving *with* the market (systematic
risk). The second is risk that comes from the asset's own behaviour
(idiosyncratic risk). You cannot hedge idiosyncratic risk with a market
instrument, so only the first term is worth hedging.

That is the whole reason the Scan seat exists: it separates the risk a hedge
can actually remove from the risk it cannot.

Look-ahead discipline
----------------------
``scan`` takes a cut-off panel and does no date filtering of its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


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

        last = cutoff_panel.ffill().iloc[-1]
        values: dict[str, float] = {}
        for h in holdings:
            price = last.get(h.symbol, np.nan)
            values[h.symbol] = float(h.shares) * float(price) if np.isfinite(price) else 0.0

        total_value = sum(v for v in values.values() if np.isfinite(v) and v > 0)
        if total_value <= 0:
            return []

        portfolio_beta = 0.0
        for h in holdings:
            v = values.get(h.symbol, 0.0)
            if not np.isfinite(v) or v <= 0:
                continue
            portfolio_beta += (v / total_value) * betas.get(h.symbol, 0.0)

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
            systematic = (portfolio_beta - beta) * beta
            idiosyncratic = beta * idio**2
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
