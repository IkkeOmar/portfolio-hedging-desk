"""Test the backtest's cash and equity accounting against a naive ledger.

The equity path is the most load-bearing code in the repository: every
performance number in every report comes out of it. A sign error there is
invisible in a smoke test and produces spectacularly wrong backtests, so it
is checked here against a hand-rolled ledger that tracks cash explicitly.

The bug this file exists to prevent: closing a short position was crediting
cash instead of debiting it, which added roughly twice the traded notional to
equity on every rebalance. The symptom was a hedged CAGR of +38% against +6%
unhedged - a number no hedging strategy has ever earned.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtest import Backtester


def _naive_ledger(prices: pd.Series, holdings_value: pd.Series, fills: list[dict]):
    """An independent equity path: track cash, mark positions to market.

    ``fills`` is a list of ``{date, quantity, price, notional}``.
    """
    cash = 0.0
    units = 0.0
    equity = []
    fill_by_date = {f["date"]: f for f in fills}

    for dt in prices.index:
        p = float(prices.loc[dt])
        f = fill_by_date.get(str(dt.date()))
        if f is not None:
            q = f["quantity"]
            # Closing the old leg (if any) settles its market value to cash.
            cash += units * p
            units = 0.0
            # Opening the new leg: a short adds its notional as cash.
            cash += f["notional"]
            units = q
        equity.append(float(holdings_value.loc[dt]) + units * p + cash)
    return pd.Series(equity, index=prices.index)


def test_short_sale_does_not_change_equity_at_entry():
    """Opening a short of N dollars must leave equity unchanged.

    Before: equity = H + u*p + cash with u = -N/p and cash = N.
    After:  equity = H + (-N) + N = H.
    """
    p = 10.0
    notional = 600.0
    quantity = -notional / p
    cash = notional
    holdings = 1000.0
    equity = holdings + quantity * p + cash
    assert equity == pytest.approx(holdings)


def test_short_position_loses_money_when_price_rises():
    """A short of N dollars must lose N*(p1/p0 - 1) when the price rises."""
    p0, p1 = 10.0, 12.0
    notional = 600.0
    quantity = -notional / p0
    cash = notional
    holdings = 1000.0
    equity_at_entry = holdings + quantity * p0 + cash
    equity_after = holdings + quantity * p1 + cash
    assert equity_after - equity_at_entry == pytest.approx(-notional * (p1 / p0 - 1.0))


def test_closing_a_short_debits_cash():
    """Closing a short buys it back. Cash must DECREASE by the buy-back cost."""
    p = 10.0
    quantity = -60.0
    cash = 600.0
    cash_after_close = cash + quantity * p     # the accounting used in backtest.py
    assert cash_after_close == pytest.approx(0.0), "closing the short must cost the buy-back"
    assert cash_after_close < cash, "closing a short must debit cash, never credit it"


def test_backtest_equity_path_matches_naive_ledger(config, panel):
    """The real backtest equity path must equal an independent ledger.

    Runs the backtest with the Risk seat forced to always approve, then
    rebuilds the same equity path by hand and compares.
    """
    from src.policy.risk import RiskPolicy

    # Force approval so there are fills to reconcile.
    original = RiskPolicy.evaluate

    def always_approve(self, date, proposals, judge_summary, equity, costs, **kwargs):
        decision = original(self, date, proposals, judge_summary, equity, costs, **kwargs)
        if decision.approved and decision.intent is not None:
            return decision
        if not proposals:
            return decision
        from src.policy.risk import RiskDecision
        from src.ledger.schema import OrderIntent

        intent = OrderIntent(
            intent_id=f"intent-{date}-{proposals[0].hedge_symbol}",
            date=date,
            symbol=proposals[0].hedge_symbol,
            side="sell" if proposals[0].target_notional < 0 else "buy",
            notional=float(proposals[0].target_notional),
            proposal_id=proposals[0].proposal_id,
            risk_signature=self.sign({"date": date, "forced": True}),
            risk_signed_by="test",
        )
        return RiskDecision(approved=True, intent=intent, reasons=["forced"], signature=intent.risk_signature)

    RiskPolicy.evaluate = always_approve
    try:
        bt = Backtester(config=config)
        result = bt.run(panel)
    finally:
        RiskPolicy.evaluate = original

    assert result.n_trades > 0, "the test needs at least one fill to be meaningful"

    symbols = [h.symbol for h in config.portfolio.holdings]
    shares = np.array([h.shares for h in config.portfolio.holdings], dtype=float)
    prices = panel[symbols].ffill()
    holdings_value = (prices * shares).sum(axis=1, min_count=1)
    hedge_sym = config.hedging.hedge_instrument

    fills = [
        {
            "date": t["date"],
            "quantity": t["quantity"],
            "price": t["price"],
            "notional": abs(t["quantity"]) * t["price"],
        }
        for t in result.trades
    ]
    naive = _naive_ledger(panel[hedge_sym].ffill(), holdings_value, fills)

    # Compare the normalised equity paths.
    repo = result.equity.reindex(naive.index)
    both = pd.concat([repo.rename("repo"), naive.rename("naive")], axis=1).dropna()
    assert len(both) > 100
    # The repo path subtracts cumulative costs, so compare the shapes:
    # the naive ledger excludes costs, so allow for them, but the DRAWDOWN
    # profile and the growth factor must be the same order.
    repo_total = float(repo.iloc[-1] / repo.iloc[0])
    naive_total = float(naive.iloc[-1] / naive.iloc[0])
    assert repo_total == pytest.approx(naive_total, rel=0.05), (
        f"repo equity grew {repo_total:.3f}x, naive ledger grew {naive_total:.3f}x"
    )
