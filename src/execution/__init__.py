"""Execution adapters: how an approved intent becomes a fill.

Only one adapter ships: a paper simulator. It models the parts of execution
that actually decide whether a backtest was honest:

* the trade happens at the next available price, not the price you saw,
* you pay the fee,
* you pay the slippage,
* you pay the spread.

A backtest that fills at the signal price with no costs is a picture of a
strategy, not a measurement of one.
"""

from .paper import PaperBroker

__all__ = ["PaperBroker"]
