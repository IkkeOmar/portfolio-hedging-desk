#!/usr/bin/env python3
"""Walk-forward backtest of the whole desk, then run the four gates.

    python scripts/backtest.py --config examples/holdings.example.yaml

Writes ``reports/evaluation.json`` and ``reports/evaluation.md``.

This is the script that produces the evidence. It uses the same seats, the
same config and the same journal format as the live desk, so what it measures
is what the desk would do.

The four gates are HEDGING gates, not trading gates:

1. ``hedgeability``       -- is there anything to hedge? (R^2 >= 25%)
2. ``regime_information`` -- does the dial anticipate forward volatility?
3. ``compensation``       -- did the risk reduction pay for itself?
4. ``stability``          -- does it hold across regimes and out-of-sample?

A return-based information gate would be structurally wrong here: a perfect
hedge has ZERO forward-return correlation by construction. See
``src/evaluation/gates.py`` for the full argument and the citation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backtest import Backtester  # noqa: E402
from src.config import DeskConfig  # noqa: E402
from src.data import load_panel  # noqa: E402
from src.evaluation.gates import run_gates  # noqa: E402
from src.evaluation.metrics import (  # noqa: E402
    annualised_vol,
    cagr,
    max_drawdown,
    sharpe,
)
from src.ledger.journal import Journal  # noqa: E402
from src.report import (  # noqa: E402
    write_equity_csv,
    write_json_report,
    write_markdown_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backtest the desk and run the four gates.")
    parser.add_argument("--config", default="examples/holdings.example.yaml")
    parser.add_argument("--journal", default="reports/journal_backtest")
    parser.add_argument("--out", default="reports")
    parser.add_argument("--horizon", type=int, default=21, help="forward-return horizon in days")
    parser.add_argument("--trials", type=int, default=1,
                        help="how many strategy variants were tried. Honesty: count them all.")
    parser.add_argument("--json", action="store_true",
                        help="print the evaluation payload as JSON on stdout, "
                             "for a program to consume instead of a human to "
                             "read. The report files are written either way.")
    args = parser.parse_args(argv)

    config = DeskConfig.from_yaml(args.config)
    journal = Journal(args.journal)
    panel = load_panel(
        source=config.data.source,
        symbols=config.all_symbols,
        seed=config.data.seed,
        path=config.data.path,
    )

    bt = Backtester(config=config, journal=journal)
    result = bt.run(panel, horizon_days=args.horizon)

    # ---- the four gates ------------------------------------------------
    # The gate stack short-circuits: a hedge that fails gate 1 does not need
    # to be tested on gate 3. Every gate that DID run is still reported.
    gates, passed = run_gates(
        r_squared=result.r_squared,
        dial=result.dial.to_numpy(dtype=float),
        forward_vol=result.forward_vol.to_numpy(dtype=float),
        hedged_returns=result.hedged_returns,
        unhedged_returns=result.unhedged_returns,
        regimes=result.regimes,
        walkforward_sharpes=result.walkforward_sharpes,
        total_cost=float(result.total_cost),
        hedge_instrument=config.hedging.hedge_instrument,
    )

    hedged_cagr = cagr(result.hedged_returns)
    unhedged_cagr = cagr(result.unhedged_returns)

    payload = {
        "verdict": "pass" if passed else "fail",
        "short_circuited_at": next((g.name for g in gates if not g.passed), None),
        "config": {
            "source": config.source_path,
            "data_source": config.data.source,
            "seed": config.data.seed,
            "benchmarks": config.portfolio.benchmark,
            "hedge_instrument": config.hedging.hedge_instrument,
            "lookback_days": config.hedging.lookback_days,
            "shrinkage_k": config.hedging.shrinkage_k,
            "rebalance": config.hedging.rebalance,
            "costs_round_trip_bps": config.costs.round_trip_bps,
            "horizon_days": args.horizon,
            # The Sharpe in this report is mean(excess returns) / std,
            # annualised by sqrt(252). The risk-free rate it subtracts is
            # ZERO, and it is stated here so a reader can check the
            # assumption instead of having to infer it. A zero risk-free
            # rate is a choice, not an oversight: this desk measures a
            # hedge overlay on a synthetic equity panel, and a stated
            # assumption beats an unstated one.
            "risk_free_rate_per_period": 0.0,
            "sharpe_definition": "mean(excess)/std(ddof=1)*sqrt(252)",
        },
        "summary": {
            "n_days": int(len(result.hedged_returns)),
            "n_trades": int(result.n_trades),
            "n_proposals": len(result.proposals),
            "n_vetoes": len(result.vetoes),
            "n_seat_errors": len(result.seat_errors),
            "n_signal_errors": len(result.signal_errors),
            "r_squared": float(result.r_squared),
            "hedged_cagr": float(hedged_cagr),
            "unhedged_cagr": float(unhedged_cagr),
            "hedged_sharpe": sharpe(result.hedged_returns),
            "unhedged_sharpe": sharpe(result.unhedged_returns),
            "hedged_annualised_vol": annualised_vol(result.hedged_returns),
            "unhedged_annualised_vol": annualised_vol(result.unhedged_returns),
            "hedged_max_drawdown": max_drawdown(result.hedged_returns),
            "unhedged_max_drawdown": max_drawdown(result.unhedged_returns),
            "total_cost": float(result.total_cost),
            "trials_declared": int(args.trials),
        },
        "gates": [g.to_dict() for g in gates],
        "vetoes": result.vetoes,
        "seat_errors": result.seat_errors,
        "signal_errors": result.signal_errors,
        "trades": result.trades,
        "walkforward": [
            {"window": w, "sharpe": s} for w, s in zip(result.windows, result.walkforward_sharpes)
        ],
    }

    out = Path(args.out)
    write_json_report(out / "evaluation.json", payload)
    write_markdown_report(out / "evaluation.md", payload)
    write_equity_csv(out / "equity.csv", result)

    if args.json:
        # A machine consumer wants the payload, not a table. The report
        # files are still written, so the dashboard and the claim audit
        # read exactly the same run.
        print(json.dumps(payload, indent=2, default=str))
        return 0 if passed else 1

    s = payload["summary"]
    print(f"\n=== walk-forward backtest: {s['n_days']} days, {s['n_trades']} trades, "
          f"{s['n_proposals']} proposals ===")
    print(f"  R^2 (hedging equation)      {s['r_squared']:.4f}   <- gate 1")
    print(f"  hedged   CAGR {hedged_cagr:+.2%}  Sharpe {s['hedged_sharpe']:.3f}  "
          f"vol {s['hedged_annualised_vol']:.2%}  maxDD {s['hedged_max_drawdown']:.2%}")
    print(f"  unhedged CAGR {unhedged_cagr:+.2%}  Sharpe {s['unhedged_sharpe']:.3f}  "
          f"vol {s['unhedged_annualised_vol']:.2%}  maxDD {s['unhedged_max_drawdown']:.2%}")
    print(f"  costs {s['total_cost']:,.2f}  vetoes {s['n_vetoes']}  "
          f"seat_errors {s['n_seat_errors']}  signal_errors {s['n_signal_errors']}")
    for gate in gates:
        mark = "PASS" if gate.passed else "FAIL"
        print(f"  [{mark}] {gate.name}: {gate.headline}")
    if payload["short_circuited_at"]:
        print(f"  (short-circuited at {payload['short_circuited_at']})")
    if s["n_seat_errors"]:
        print(f"  WARNING: {s['n_seat_errors']} seat errors -- the desk did not run cleanly.")
        for err in result.seat_errors[:3]:
            print(f"    {err['date']}: {err['reason']}")
    print(f"\n  wrote {out / 'evaluation.json'}, {out / 'evaluation.md'} "
          f"and {out / 'equity.csv'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
