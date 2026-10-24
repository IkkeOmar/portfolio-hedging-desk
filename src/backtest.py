"""The walk-forward backtest: run the whole desk over history, then judge it.

This is the engine that turns the desk into evidence. It walks forward
through time and, at each rebalance date, does exactly what the live desk
would do, with one rule that cannot be broken:

    **Every decision on date t may only use data from before date t.**

The fill convention is deliberately conservative:

    signal   : computed from closes up to and including day t-1
    decision : made at the close of day t-1
    fill     : at the close of day t

So you never get to trade at a price you only learned afterwards, and you
never earn a return on a position you could not have held.

Accounting
----------
Two equity curves are maintained:

* **gross** - the portfolio marked to market, ignoring transaction costs.
* **net**   - the same portfolio, less the cumulative transaction costs.

Because costs are subtracted from the compounding base rather than from a
single day's return, the net curve compounds the way a real account does.
This is what makes the gross-vs-net comparison honest.

What the backtest produces
---------------------------
* the hedged portfolio's daily return series, gross and net,
* the unhedged portfolio's daily return series (the benchmark that matters),
* the signal series and forward returns for the information gate,
* the regime label per day, for the stability gate,
* consecutive out-of-sample windows, for the walk-forward half of the
  stability gate,
* a journal, written exactly as the live desk writes it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .config import DeskConfig
from .evaluation.metrics import sharpe
from .execution.paper import PaperBroker
from .ledger.journal import Journal
from .policy.hedger import HedgePolicy
from .policy.judge import RuleBasedJudge, aggregate_verdicts
from .policy.quant import QuantPolicy
from .policy.risk import RiskPolicy
from .policy.scan import ScanPolicy

REBALANCE_STEPS = {"daily": 1, "weekly": 5, "monthly": 21}
TRADING_DAYS = 252


@dataclass
class BacktestResult:
    """Everything the evaluation needs, in one object."""

    dates: pd.Index
    hedged_returns: pd.Series          # net of costs
    hedged_returns_gross: pd.Series    # before costs
    unhedged_returns: pd.Series
    signal: pd.Series
    forward_returns: pd.Series
    regimes: pd.Series
    dial: pd.Series                  # the desk's decision variable, per day
    forward_vol: pd.Series          # forward realised vol of the portfolio
    r_squared: float                # hedging-equation R^2 vs the hedge instrument
    r_squared_series: pd.Series     # rolling R^2, for reporting
    n_trades: int
    total_cost: float
    equity: pd.Series
    equity_unhedged: pd.Series
    walkforward_sharpes: list[float] = field(default_factory=list)
    vetoes: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    proposals: list[dict[str, Any]] = field(default_factory=list)
    judge_summaries: list[dict[str, Any]] = field(default_factory=list)
    windows: list[tuple[str, int, int]] = field(default_factory=list)
    # Every swallowed exception is recorded here. A desk that quietly does
    # nothing looks exactly like a desk that has nothing to do, and the only
    # way to tell them apart is to keep the failures.
    seat_errors: list[dict[str, Any]] = field(default_factory=list)
    signal_errors: list[dict[str, Any]] = field(default_factory=list)


class Backtester:
    """Runs the desk over a price panel, forward in time."""

    def __init__(self, config: DeskConfig, journal: Journal | None = None, judge_runs: int = 3):
        self.config = config
        self.journal = journal
        self.judge_runs = int(judge_runs)
        # The hedge instrument the desk trades to neutralise market risk.
        # Stored on the instance because the R^2 helper below (and the
        # signal/label block) needs it by name. It was previously only
        # passed into HedgePolicy, so ``self.hedge_instrument`` raised
        # AttributeError on every decision day -- and the bare
        # ``except Exception`` around the seat block swallowed it into a
        # ``seat_error`` veto, so the desk silently never traded.
        self.hedge_instrument = config.hedging.hedge_instrument
        self.quant = QuantPolicy(config.portfolio.benchmark, lookback_days=config.hedging.lookback_days)
        self.scan = ScanPolicy(config.portfolio.benchmark, max_candidates=config.risk.max_legs)
        self.hedger = HedgePolicy(
            benchmark=config.portfolio.benchmark,
            hedge_instrument=config.hedging.hedge_instrument,
            lookback_days=config.hedging.lookback_days,
            shrinkage_k=config.hedging.shrinkage_k,
        )
        self.risk = RiskPolicy(
            max_gross_hedge_pct=config.risk.max_gross_hedge_pct,
            risk_per_trade_pct=config.risk.risk_per_trade_pct,
            min_reward_to_risk=config.risk.min_reward_to_risk,
            max_legs=config.risk.max_legs,
            journal_root=journal.root if journal is not None else "journal",
            require_judge_agreement=False,   # the rule-based judge is deterministic
        )
        self.judge = RuleBasedJudge()
        self.broker = PaperBroker(costs=config.costs)

    # ------------------------------------------------------------- utilities
    @staticmethod
    def _cutoff_panel(panel: pd.DataFrame, date: str) -> pd.DataFrame:
        """Everything the desk is allowed to see when it decides on ``date``.

        Strictly before ``date``.
        """
        return panel[panel.index < pd.Timestamp(date)]

    def _rebalance_dates(self, index: pd.Index) -> set[str]:
        step = REBALANCE_STEPS.get(self.config.hedging.rebalance, 21)
        return {str(index[i].date()) for i in range(0, len(index), step)}

    # -------------------------------------------------------------- the loop
    def run(self, panel: pd.DataFrame, horizon_days: int = 21) -> BacktestResult:
        cfg = self.config
        index = panel.index
        if len(index) < cfg.hedging.lookback_days + 60:
            raise ValueError(
                f"need at least {cfg.hedging.lookback_days + 60} rows to backtest, got {len(index)}"
            )

        holdings = cfg.portfolio.holdings
        if not holdings:
            raise ValueError("no holdings configured")
        symbols = [h.symbol for h in holdings]
        shares = np.array([h.shares for h in holdings], dtype=float)

        # --- unhedged portfolio, vectorised ---------------------------------
        prices = panel[symbols].ffill()
        prev_prices = prices.shift(1)
        holdings_value = (prices * shares).sum(axis=1, min_count=1)
        prev_value = (prev_prices * shares).sum(axis=1, min_count=1)
        unhedged_returns = (holdings_value / prev_value - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)

        # --- state ------------------------------------------------------------
        hedge_units = 0.0              # signed units of the hedge instrument
        hedge_cash = 0.0               # cash from short proceeds / spent on longs
        cumulative_cost = 0.0
        n_trades = 0
        trades: list[dict[str, Any]] = []
        proposals: list[dict[str, Any]] = []
        judge_summaries: list[dict[str, Any]] = []
        vetoes: list[dict[str, Any]] = []
        signal_errors: list[dict[str, Any]] = []
        seat_errors: list[dict[str, Any]] = []
        pending_order = None           # intent decided yesterday, fills today

        gross_values = pd.Series(index=index, dtype=float)
        cost_today = pd.Series(0.0, index=index, dtype=float)
        signal_series = pd.Series(index=index, dtype=float)
        regime_series = pd.Series(index=index, dtype=object)
        dial_series = pd.Series(index=index, dtype=float)
        r2_series = pd.Series(index=index, dtype=float)

        rebal = self._rebalance_dates(index)
        bench = cfg.portfolio.benchmark
        hedge_sym = cfg.hedging.hedge_instrument

        for dt in index:
            date_str = str(dt.date())
            px = panel.loc[dt]
            hv = float(holdings_value.loc[dt])
            # Mark the hedge leg to market. `hedge_cash` holds the proceeds of
            # a short sale (or the cash spent on a long). It MUST be included:
            #
            #     equity = holdings_value + hedge_units*price + hedge_cash
            #
            # Without the cash term, opening a short of N dollars appears to
            # destroy N dollars of equity, because the short position's market
            # value is -N while the offsetting cash is missing. That bug
            # booked a spurious loss equal to the traded notional on every
            # rebalance, and made the hedged portfolio show a -85% drawdown
            # against a -62% unhedged one. It was an accounting error, not a
            # result.
            hedge_value = 0.0
            if hedge_units != 0.0 and hedge_sym in panel.columns:
                hedge_value = hedge_units * float(px.get(hedge_sym, 0.0))
            gross_values.loc[dt] = hv + hedge_value + hedge_cash

            # ---- 1. Execute yesterday's pending order at today's close -----
            if pending_order is not None:
                intent = pending_order
                pending_order = None
                fill = self.broker.submit(intent, panel, fill_date=date_str)
                # Close the old hedge leg at the new fill price, then open the
                # new one. Both legs' cash effects are captured.
                if hedge_units != 0.0:
                    # Closing the old leg converts its market value into cash.
                    # The position was worth hedge_units * price, so closing it
                    # changes cash by +hedge_units * price.
                    #
                    # Sign check, because getting this wrong is invisible in a
                    # single-symbol test and catastrophic in a backtest: for a
                    # short (hedge_units < 0) this REDUCES cash, which is
                    # correct - buying a short back costs money. The earlier
                    # version had the sign reversed and therefore credited the
                    # buy-back, adding roughly twice the traded notional to
                    # equity on every rebalance. That produced a hedged CAGR
                    # of +38% against +6% unhedged, which is not a strategy
                    # anyone should believe.
                    hedge_cash += hedge_units * fill.price
                hedge_cash += fill.notional
                hedge_units = fill.quantity
                cumulative_cost += fill.total_cost
                cost_today.loc[dt] = fill.total_cost
                n_trades += 1
                trades.append(
                    {
                        "date": fill.date,
                        "symbol": fill.symbol,
                        "side": fill.side,
                        "quantity": fill.quantity,
                        "price": fill.price,
                        "notional": fill.notional,
                        "cost": fill.total_cost,
                        "equity_at_trade": gross_values.loc[dt] - cumulative_cost,
                    }
                )

            # ---- 2. Decide, using only data before today --------------------
            if date_str in rebal:
                cutoff = self._cutoff_panel(panel, date_str)
                regime = None
                proposal = None
                # Warm-up: before there is enough history to estimate a beta
                # and a regime, there is nothing to decide. This is not an
                # error, it is the start of the sample.
                if len(cutoff) < cfg.hedging.lookback_days + 60:
                    pending_order = None
                    continue
                try:
                    regime = self.quant.evaluate(cutoff, date=date_str)
                    dial_series.loc[dt] = regime.dial
                    # The hedging equation's R^2: how much of the portfolio's
                    # variance does the hedge instrument explain? Healy and
                    # Lo (2010) require this to clear 25% before an overlay
                    # is worth running at all.
                    r2_series.loc[dt] = self._hedge_r_squared(cutoff, holdings, shares)
                    estimates = self.hedger.estimate_all(cutoff, symbols)
                    betas = {s: e.beta_shrunk for s, e in estimates.items()}
                    idio = {s: e.idio_vol for s, e in estimates.items()}
                    candidates = self.scan.scan(cutoff, holdings, betas, idio)
                    equity_now = float(hv + hedge_value)
                    proposal = self.hedger.build_proposal(
                        date=date_str,
                        cutoff_panel=cutoff,
                        candidates=candidates,
                        equity=equity_now,
                        costs=cfg.costs,
                        dial=regime.dial,
                        max_hedge_pct_equity=cfg.hedging.max_hedge_pct_equity,
                    )
                except Exception as exc:  # a seat must never take the desk down
                    # Recorded in BOTH places: `vetoes` so the report shows it
                    # where a reader looks, and `seat_errors` so a run can
                    # assert that the desk actually executed rather than
                    # failing quietly on every single day.
                    reason = f"{type(exc).__name__}: {exc}"
                    seat_errors.append({"date": date_str, "reason": reason})
                    vetoes.append({"date": date_str, "stage": "seat_error", "reason": reason})

                if proposal is not None:
                    proposals.append(proposal.to_row())
                    verdicts = [
                        self.judge.judge(proposal, {"regime": getattr(regime, "regime", None)}, run=i)
                        for i in range(self.judge_runs)
                    ]
                    summary = aggregate_verdicts(verdicts)
                    judge_summaries.append({"date": date_str, **summary})

                    decision = self.risk.evaluate(
                        date=date_str,
                        proposals=[proposal],
                        judge_summary=summary,
                        equity=float(hv + hedge_value),
                        costs=cfg.costs,
                        existing_gross_hedge_pct=(
                            abs(hedge_value) / hv if hv > 0 else 0.0
                        ),
                        open_legs=1 if hedge_units != 0.0 else 0,
                    )
                    if decision.approved and decision.intent is not None:
                        pending_order = decision.intent
                    else:
                        vetoes.append(
                            {
                                "date": date_str,
                                "stage": decision.details.get("stage", "unknown"),
                                "reason": "; ".join(decision.veto_reasons) or "not approved",
                            }
                        )

            # ---- 3. Signal and regime label for the information gate ---------
            sig = np.nan
            label = "unknown"
            try:
                cutoff = self._cutoff_panel(panel, date_str)
                if len(cutoff) > 220:
                    pb = cutoff[bench].dropna()
                    ma = float(pb.tail(200).mean())
                    dv = float(pb.pct_change().dropna().tail(60).std(ddof=1))
                    last_px = float(pb.iloc[-1])
                    if ma > 0 and dv > 0:
                        sig = (last_px - ma) / (ma * dv)
                    label = "up" if sig > 0 else "down"
            except Exception as exc:  # noqa: BLE001
                # Do NOT swallow this silently. A bare ``except: pass`` here
                # hides genuine breakage behind an empty signal column, which
                # then shows up as "the information gate found nothing". Record
                # it so the failure is visible in the report.
                signal_errors.append({"date": date_str, "reason": f"{type(exc).__name__}: {exc}"})
            signal_series.loc[dt] = sig
            regime_series.loc[dt] = label

        # --- returns ---------------------------------------------------------
        base = float(gross_values.iloc[0])
        cumulative_costs = cost_today.reindex(index).fillna(0.0).cumsum()
        equity_gross = gross_values / base
        equity_net = (gross_values - cumulative_costs) / base
        hedged_gross_returns = equity_gross.pct_change().fillna(0.0)
        hedged_net_returns = equity_net.pct_change().fillna(0.0)

        # The unhedged series is aligned to the same index.
        unhedged = unhedged_returns.reindex(index).fillna(0.0)

        # --- forward outcomes for the gates ----------------------------------
        forward = forward_compound(unhedged, horizon_days)
        # The hedging agent's outcome is RISK, not return: a perfect hedge has
        # zero forward-return correlation by construction. The dial is tested
        # against forward realised volatility instead.
        forward_vol = forward_volatility(unhedged, horizon_days)

        # --- walk-forward windows -------------------------------------------
        windows = self._walkforward_windows(hedged_net_returns, n_windows=6)
        wf_sharpes = [sharpe(hedged_net_returns.iloc[a:b]) for _, a, b in windows]

        equity_unhedged = (1.0 + unhedged).cumprod()

        return BacktestResult(
            dates=index,
            hedged_returns=hedged_net_returns,
            hedged_returns_gross=hedged_gross_returns,
            unhedged_returns=unhedged,
            signal=signal_series,
            forward_returns=forward,
            regimes=regime_series,
            dial=dial_series,
            forward_vol=forward_vol,
            r_squared=float(r2_series.dropna().mean()) if r2_series.notna().any() else float("nan"),
            r_squared_series=r2_series,
            n_trades=n_trades,
            total_cost=float(cumulative_cost),
            equity=equity_net,
            equity_unhedged=equity_unhedged,
            walkforward_sharpes=wf_sharpes,
            vetoes=vetoes,
            trades=trades,
            proposals=proposals,
            judge_summaries=judge_summaries,
            seat_errors=seat_errors,
            signal_errors=signal_errors,
            windows=windows,
        )

    def _hedge_r_squared(
        self, cutoff_panel: pd.DataFrame, holdings, shares: np.ndarray
    ) -> float:
        """R^2 of the portfolio's returns regressed on the hedge instrument.

        This is the "hedging equation" of Healy and Lo (2010). It answers:
        what fraction of the portfolio's return variance does the hedge
        instrument explain? Below about 25%, hedging cannot pay for itself.

        Computed on the portfolio series built from the holdings, over the
        same trailing window used for the beta estimates.
        """
        syms = [h.symbol for h in holdings]
        # ``prices_available`` is a predicate (a bool), not a container, so it
        # cannot be used with ``not in``. The hedge instrument must be present
        # AND every holding must be present.
        if not prices_available(cutoff_panel, syms):
            return float("nan")
        if self.hedge_instrument not in cutoff_panel.columns:
            return float("nan")
        window = cutoff_panel.tail(self.config.hedging.lookback_days + 10)
        px = window[syms].ffill()
        prev = px.shift(1)
        hv = (px * shares).sum(axis=1, min_count=1)
        prev_hv = (prev * shares).sum(axis=1, min_count=1)
        port_ret = (hv / prev_hv - 1.0).replace([np.inf, -np.inf], np.nan)
        hedge_ret = window[self.hedge_instrument].pct_change()
        joined = pd.concat([port_ret.rename("p"), hedge_ret.rename("h")], axis=1).dropna()
        if len(joined) < 30:
            return float("nan")
        y = joined["p"].to_numpy(dtype=float)
        x = joined["h"].to_numpy(dtype=float)
        x_dev = x - x.mean()
        sxx = float((x_dev**2).sum())
        if sxx <= 0:
            return float("nan")
        beta = float(((y - y.mean()) * x_dev).sum() / sxx)
        resid = y - (y.mean() + beta * x_dev)
        sst = float(((y - y.mean()) ** 2).sum())
        if sst <= 0:
            return float("nan")
        return float(1.0 - (resid**2).sum() / sst)

    @staticmethod
    def _walkforward_windows(returns: pd.Series, n_windows: int = 6) -> list[tuple[str, int, int]]:
        """Split into consecutive out-of-sample windows."""
        n = len(returns)
        if n < n_windows * 30:
            return []
        size = n // n_windows
        out = []
        for i in range(n_windows):
            a = i * size
            b = n if i == n_windows - 1 else (i + 1) * size
            out.append((f"W{i + 1}", a, b))
        return out


def prices_available(panel: pd.DataFrame, symbols: list[str]) -> bool:
    """True when every requested symbol has a column in the panel."""
    return all(s in panel.columns for s in symbols)


def forward_volatility(returns: pd.Series, horizon: int, periods_per_year: int = 252) -> pd.Series:
    """Annualised realised volatility over the NEXT ``horizon`` periods.

    For a hedging agent this is the outcome that matters: the dial is meant
    to anticipate volatility, not returns. A hedge's payoff is a reduction
    in the dispersion of outcomes.

    Uses the standard deviation of the forward window, so the value at t
    describes days t+1..t+horizon.
    """
    if horizon <= 1:
        return pd.Series(np.nan, index=returns.index)
    clean = returns.dropna()
    vol = clean.rolling(horizon).std(ddof=1) * np.sqrt(periods_per_year)
    # Align so that vol[t] describes the window STARTING at t.
    vol = vol.shift(-(horizon - 1))
    return vol.reindex(returns.index)


def forward_compound(returns: pd.Series, horizon: int) -> pd.Series:
    """Compounded return over the next ``horizon`` periods, aligned to today.

    ``result[t]`` is the compounded return of periods ``t+1 .. t+horizon``,
    i.e. strictly AFTER today. A signal computed at the close of t must be
    matched to an outcome that starts after t, never including it.

    Uses log returns so the compounding is exact and cheap: the sum of
    log(1+r) over the forward window, exponentiated.

    Index arithmetic, stated so it can be checked:

        rev[i] = sum_{j >= i} log_r[j]        (a suffix sum)
        fwd[i] = sum_{j = i+1}^{i+H} log_r[j]
               = rev[i+1] - rev[i+H+1]

    which in pandas is ``rev.shift(-1) - rev.shift(-(H+1))``.

    An earlier version of this function used ``shift(-(H-1)) - 1`` offsets,
    which summed the wrong window and produced a forward series correlated
    at -0.79 with the direct computation. The test
    ``tests/test_backtest.py::test_forward_compound_matches_direct_computation``
    now pins this against a naive loop.
    """
    if horizon <= 0:
        return pd.Series(np.nan, index=returns.index)
    log_r = np.log1p(returns.replace([np.inf, -np.inf], np.nan).fillna(0.0))
    values = log_r.to_numpy(dtype=float)
    n = len(values)

    # rev[i] = sum_{j >= i} log_r[j]  (a suffix sum), computed by reversing.
    rev = np.cumsum(values[::-1])[::-1]
    # rev_ext[n] = 0, the empty suffix, so that a window ending exactly at the
    # last observation is still computable.
    rev_ext = np.append(rev, 0.0)

    # fwd[i] = sum_{j = i+1}^{i+H} log_r[j] = rev[i+1] - rev[i+H+1].
    # Valid for i <= n-1-H, i.e. n-H rows. The last H rows have no complete
    # forward window and stay NaN.
    valid = max(n - horizon, 0)
    out = np.full(n, np.nan)
    if valid > 0:
        idx = np.arange(valid)
        fwd_log = rev_ext[idx + 1] - rev_ext[idx + horizon + 1]
        out[:valid] = np.expm1(fwd_log)
    return pd.Series(out, index=returns.index)
