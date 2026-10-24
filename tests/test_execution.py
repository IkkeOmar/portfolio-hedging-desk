"""The paper broker's fill-date rule, checked three ways.

A fill may never use a price from *before* the decision. The broker enforces
that floor itself rather than trusting every caller to pass the right date,
so the no-look-ahead property belongs to the code rather than to the
discipline of whoever calls it next.

The rule is checked here directly, against both of the conventions this repo
actually uses — the desk fills on the decision date, the backtest fills on the
day after — and end to end against the fills the desk writes to its journal.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.execution.paper import LiveTradingRefused, PaperBroker
from src.ledger.schema import OrderIntent


def _intent(date: str, symbol: str = "AAPL", signed: bool = True) -> OrderIntent:
    """A signed sell intent, dated ``date``."""
    return OrderIntent(
        intent_id=f"intent-{date}-{symbol}",
        date=date,
        symbol=symbol,
        side="sell",
        notional=-10_000.0,
        risk_signature="risk-signature" if signed else None,
    )


def test_broker_refuses_a_fill_before_the_decision(panel, config):
    """The floor: a fill may not be dated earlier than the intent."""
    broker = PaperBroker(costs=config.costs)
    intent = _intent(str(panel.index[-3].date()))
    earlier = str(panel.index[-4].date())

    with pytest.raises(ValueError, match="before the decision"):
        broker.submit(intent, panel, fill_date=earlier)


def test_broker_refuses_a_fill_before_the_decision_when_fill_date_is_defaulted(panel, config):
    """An omitted fill_date falls back to the intent's own date, never before it."""
    broker = PaperBroker(costs=config.costs)
    intent = _intent(str(panel.index[-3].date()))
    fill = broker.submit(intent, panel)

    assert fill.date == intent.date


def test_broker_allows_a_fill_on_the_decision_date(panel, config):
    """The desk's convention: decide with data before t, fill at the close of t.

    The fill price is cross-checked against the panel itself, not just
    accepted because no exception was raised.
    """
    broker = PaperBroker(costs=config.costs)
    decision_day = str(panel.index[-3].date())
    intent = _intent(decision_day)

    fill = broker.submit(intent, panel, fill_date=decision_day)

    expected_price = float(panel["AAPL"].dropna().loc[pd.Timestamp(decision_day)])
    assert fill.date == decision_day
    assert fill.price == pytest.approx(expected_price)


def test_broker_allows_a_fill_on_the_next_day(panel, config):
    """The backtest's convention: decide at the close of t-1, fill at the close of t."""
    broker = PaperBroker(costs=config.costs)
    decision_day = str(panel.index[-3].date())
    next_day = str(panel.index[-2].date())
    intent = _intent(decision_day)

    fill = broker.submit(intent, panel, fill_date=next_day)

    expected_price = float(panel["AAPL"].dropna().loc[pd.Timestamp(next_day)])
    assert fill.date == next_day
    assert fill.price == pytest.approx(expected_price)


def test_broker_refuses_an_unsigned_intent(panel, config):
    """No Risk signature, no fill. This is the veto that actually binds."""
    broker = PaperBroker(costs=config.costs)
    intent = _intent(str(panel.index[-3].date()), signed=False)

    with pytest.raises(LiveTradingRefused):
        broker.submit(intent, panel, fill_date=intent.date)


def test_every_journalled_fill_is_not_earlier_than_its_intent(config, panel, tmp_path):
    """End to end: the fills the desk actually writes respect the rule.

    This is the check that would catch a caller passing a wrong date, which
    is exactly the failure the unit tests above cannot see.
    """
    from src.desk import Desk
    from src.ledger.journal import Journal

    journal = Journal(tmp_path / "journal")
    desk = Desk(config=config, journal=journal)

    for i in range(-40, 0):
        desk.run_day(date=str(panel.index[i].date()), panel=panel)

    intents = {row["intent_id"]: row for row in journal.intents()}
    fills = journal.fills()

    assert fills, "the desk produced no fills, so this check would be vacuous"
    for f in fills:
        intent = intents[f["intent_id"]]
        assert pd.Timestamp(f["date"]) >= pd.Timestamp(
            intent["date"]
        ), f"fill {f['fill_id']} on {f['date']} predates its intent on {intent['date']}"
