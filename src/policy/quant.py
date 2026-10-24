"""The Quant seat: what kind of market are we in?

Two numbers, computed from the trailing window, no black boxes.

1. **Realised volatility.** Annualised standard deviation of daily returns
   over the lookback. Modern risk models care about the *level* of vol and its
   *direction*. Both are visible here.

2. **The trend state.** Where is the benchmark relative to its own moving
   average? This is the same family of idea as the classic 200-day rule that
   we audited in ``notes/``. We do not claim it is a forecast. We claim it
   describes the current regime, and that regimes change the job of a hedge.

The seat also produces the "dial": a number in [0, 1] saying how much
reducing risk is worth doing right now. It is deliberately simple and
deliberately explainable:

    dial = 1.0                      in a stress regime (vol high, trend down)
          = 0.5                      mixed
          = 0.2                      calm and trending up (hedge less)

A dial that a person can argue with is worth more than a dial that is
technically superior and opaque.

Look-ahead discipline
----------------------
``evaluate`` takes a **cut-off panel**: prices strictly before the decision
date. It never filters by date itself, because a seat that is handed the
future will eventually use it. The caller decides what the seat may see.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class RegimeSnapshot:
    """The Quant seat's answer for one day."""

    date: str
    benchmark: str
    realised_vol: float          # annualised, fraction (0.12 = 12%)
    vol_percentile: float        # where today's vol sits in its own history, 0..1
    trend_state: str             # "above" | "below" | "flat"
    trend_strength: float        # distance from MA in units of realised daily vol
    dial: float                  # 0..1, how much hedging to do
    regime: str                  # "stress" | "defensive" | "neutral" | "calm"
    detail: dict[str, Any] = field(default_factory=dict)


class QuantPolicy:
    """Computes the regime snapshot. Stateless apart from the price history."""

    def __init__(self, benchmark: str, lookback_days: int = 252, ma_days: int = 200):
        self.benchmark = benchmark
        self.lookback_days = int(lookback_days)
        self.ma_days = int(ma_days)

    # ------------------------------------------------------------------ maths
    @staticmethod
    def realised_vol(returns: pd.Series, annualisation: int = 252) -> float:
        """Annualised standard deviation of daily returns.

        Uses the sample standard deviation (ddof=1) and multiplies the daily
        standard deviation by sqrt(252). Simple, standard, and stated.
        """
        clean = returns.dropna()
        if len(clean) < 2:
            return float("nan")
        return float(clean.std(ddof=1) * np.sqrt(annualisation))

    @staticmethod
    def trend_state(price: float, ma: float, daily_vol: float) -> tuple[str, float]:
        """Classify price relative to its moving average.

        ``trend_strength`` measures the distance from the moving average in
        units of daily volatility. That makes the number comparable across
        assets and across time, instead of a raw percentage that mostly
        measures how volatile the asset happens to be.
        """
        if not np.isfinite(ma) or ma <= 0 or not np.isfinite(daily_vol) or daily_vol <= 0:
            return "flat", 0.0
        strength = (price - ma) / (ma * daily_vol)
        if strength > 0.5:
            return "above", float(strength)
        if strength < -0.5:
            return "below", float(strength)
        return "flat", float(strength)

    def dial(self, vol_percentile: float, trend_state: str) -> float:
        """How much hedging is worth doing, in [0, 1].

        Two ingredients, each defensible on its own:

        * Volatility percentile. Hedging is more valuable when the thing you
          are hedging against is moving more. Percentile, not level, so the
          dial does not change meaning over the life of a market.
        * Trend state. A falling market is where drawdowns live.

        The dial is a *policy knob*, not a probability. It says "do more of the
        risk reduction we already decided is worth doing".
        """
        vol_component = float(np.clip(vol_percentile, 0.0, 1.0))
        if trend_state == "below":
            trend_component = 1.0
        elif trend_state == "above":
            trend_component = 0.0
        else:
            trend_component = 0.5
        return float(np.clip(0.5 * vol_component + 0.5 * trend_component, 0.0, 1.0))

    # ------------------------------------------------------------------ run
    def evaluate(self, cutoff_panel: pd.DataFrame, date: str | None = None) -> RegimeSnapshot:
        """Compute the regime snapshot from a cut-off panel.

        ``cutoff_panel`` must contain only prices from before the decision
        date. The function does not check that, and cannot: only the caller
        knows what the desk was allowed to see. The backtest and the live desk
        both pass a strictly-earlier panel.
        """
        if self.benchmark not in cutoff_panel.columns:
            raise KeyError(
                f"benchmark {self.benchmark!r} not in panel columns: {list(cutoff_panel.columns)}"
            )
        prices = cutoff_panel[self.benchmark].dropna()
        if len(prices) < self.ma_days + 5:
            raise ValueError(
                f"need at least {self.ma_days + 5} observations of {self.benchmark}, got {len(prices)}"
            )

        window = prices.tail(self.lookback_days + self.ma_days)
        returns = window.pct_change().dropna()

        # Realised vol over the lookback window only (not the MA window).
        lookback_returns = returns.tail(self.lookback_days)
        vol = self.realised_vol(lookback_returns)
        daily_vol = float(lookback_returns.std(ddof=1))

        # Percentile of the current vol within the trailing vol history.
        rolling_vol = returns.rolling(20).std(ddof=1) * np.sqrt(252)
        rolling_vol = rolling_vol.dropna()
        if len(rolling_vol) >= 20 and np.isfinite(vol):
            vol_percentile = float((rolling_vol <= vol).mean())
        else:
            vol_percentile = 0.5

        ma = float(prices.tail(self.ma_days).mean())
        last_price = float(prices.iloc[-1])
        state, strength = self.trend_state(last_price, ma, daily_vol)
        dial = self.dial(vol_percentile, state)

        if vol_percentile >= 0.8 and state == "below":
            regime = "stress"
        elif state == "below" or vol_percentile >= 0.8:
            regime = "defensive"
        elif vol_percentile <= 0.3 and state == "above":
            regime = "calm"
        else:
            regime = "neutral"

        return RegimeSnapshot(
            date=str(date or prices.index[-1].date()),
            benchmark=self.benchmark,
            realised_vol=vol,
            vol_percentile=vol_percentile,
            trend_state=state,
            trend_strength=strength,
            dial=dial,
            regime=regime,
            detail={
                "lookback_days": self.lookback_days,
                "ma_days": self.ma_days,
                "last_price": last_price,
                "ma": ma,
                "daily_vol": daily_vol,
                "observations": int(len(prices)),
            },
        )
