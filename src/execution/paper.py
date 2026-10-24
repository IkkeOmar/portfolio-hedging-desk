"""Paper broker: fills intents against a given date, with costs.

The fill rule is the important part. The intent says *how much* to trade; the
broker decides *when* and *at what price* it could have happened. The broker
takes an explicit ``fill_date`` and refuses any fill dated *before* the
intent's own date: a fill may never use a price the decision could not have
known. That floor is enforced here, loudly, rather than trusted to callers.

Note that the two callers use different — and both correct — conventions:

- the **backtest** decides at the close of day t-1 and fills at the close of
  day t, so the fill lands on the day *after* the decision;
- the **live desk** decides using data strictly before day t and fills at the
  close of day t, so the fill lands *on* the decision date.

Both satisfy the same rule: the fill is at a close at or after the decision.
The broker enforces that floor only. Choosing the exact close is the
caller's job, and a caller that passes a wrong date gets a loud error rather
than a plausible-looking wrong answer.

Costs model, per side:

    fee      = notional * fee_bps / 10_000
    slippage = notional * slippage_bps / 10_000
    spread   = notional * spread_bps / 10_000

A backtest that fills at the signal price with no costs is a picture of a
strategy, not a measurement of one.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Any

import pandas as pd

from ..ledger.schema import Fill, OrderIntent


class LiveTradingRefused(RuntimeError):
    """Raised when something tries to place a live order without authorisation."""


@dataclass
class PaperBroker:
    """Simulated broker. Costs and an explicit fill date."""

    costs: Any
    live: bool = False

    def _fill_price(self, prices: pd.Series, fill_date: str) -> float:
        """The close on ``fill_date``."""
        series = prices.dropna()
        try:
            return float(series.loc[pd.Timestamp(fill_date)])
        except KeyError as exc:
            raise LookupError(f"no price for {fill_date}") from exc

    def submit(self, intent: OrderIntent, panel: pd.DataFrame, fill_date: str | None = None) -> Fill:
        """Execute a signed intent and return the fill.

        Refuses unsigned intents. Refuses live mode without ``LIVE=1``.
        Refuses a ``fill_date`` earlier than the intent's own date.
        """
        if not intent.risk_signature:
            raise LiveTradingRefused(
                f"intent {intent.intent_id} has no Risk signature; the execution adapter will not act on it"
            )
        if self.live and os.environ.get("LIVE", "0") != "1":
            raise LiveTradingRefused(
                "live mode requires LIVE=1 in the environment. Refusing to send an order."
            )
        if intent.symbol not in panel.columns:
            raise KeyError(f"no price series for {intent.symbol}")

        fill_date = fill_date or intent.date
        # A fill may not use a price from before the decision. The broker
        # enforces this floor itself: the no-look-ahead property of the desk
        # should not depend on every caller remembering to pass the right
        # date. A caller that passes the wrong one gets a loud error here
        # instead of a plausible-looking wrong answer.
        if pd.Timestamp(fill_date) < pd.Timestamp(intent.date):
            raise ValueError(
                f"intent {intent.intent_id} is dated {intent.date} but was asked to fill on "
                f"{fill_date}; a fill may not use a price from before the decision"
            )
        price = self._fill_price(panel[intent.symbol], fill_date)
        qty = abs(intent.notional) / price
        signed_qty = qty if intent.side == "buy" else -qty
        notional = abs(signed_qty) * price

        fee = notional * float(self.costs.fee_bps_per_side) / 10_000.0
        slippage = notional * float(self.costs.slippage_bps_per_side) / 10_000.0
        spread = notional * float(self.costs.spread_bps_per_side) / 10_000.0

        fill_id = hashlib.sha256(
            f"{intent.intent_id}|{fill_date}|{price:.6f}|{notional:.2f}".encode()
        ).hexdigest()[:16]

        return Fill(
            fill_id=fill_id,
            intent_id=intent.intent_id,
            date=fill_date,
            symbol=intent.symbol,
            side=intent.side,
            quantity=float(signed_qty),
            price=price,
            notional=float(notional),
            commission=fee,
            slippage=slippage,
            spread_cost=spread,
            total_cost=float(fee + slippage + spread),
        )
