"""The desk: one trading day, run end to end.

    Scan -> Quant -> Hedger -> Judge (xN) -> Risk -> Execution

Every seat reads its inputs from the journal and writes its output to the
journal. No seat keeps state between runs. That means a day can be replayed
exactly, and a crash leaves a readable record of how far the desk got.

The order of operations is fixed and enforced:

* Quant and Hedger write proposals and diagnostics.
* Judge writes N verdicts.
* Risk writes a signed order intent, or a veto with a reason.
* Only a signed intent reaches the execution adapter.

Fail-safe by construction: no signature, no order.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .config import DeskConfig
from .data import load_panel
from .execution.paper import PaperBroker
from .ledger.journal import Journal
from .ledger.schema import Decision, snapshot_hash
from .policy.hedger import HedgePolicy
from .policy.judge import LLMJudge, RuleBasedJudge, aggregate_verdicts
from .policy.quant import QuantPolicy
from .policy.risk import RiskPolicy
from .policy.scan import ScanPolicy


@dataclass
class Desk:
    """A live desk for one account."""

    config: DeskConfig
    journal: Journal
    judge_runs: int = 3

    def __post_init__(self) -> None:
        cfg = self.config
        self.quant = QuantPolicy(cfg.portfolio.benchmark, lookback_days=cfg.hedging.lookback_days)
        self.scan = ScanPolicy(cfg.portfolio.benchmark, max_candidates=cfg.risk.max_legs)
        self.hedger = HedgePolicy(
            benchmark=cfg.portfolio.benchmark,
            hedge_instrument=cfg.hedging.hedge_instrument,
            lookback_days=cfg.hedging.lookback_days,
            shrinkage_k=cfg.hedging.shrinkage_k,
        )
        self.risk = RiskPolicy(
            max_gross_hedge_pct=cfg.risk.max_gross_hedge_pct,
            risk_per_trade_pct=cfg.risk.risk_per_trade_pct,
            min_reward_to_risk=cfg.risk.min_reward_to_risk,
            max_legs=cfg.risk.max_legs,
            journal_root=self.journal.root,
        )
        self.broker = PaperBroker(costs=cfg.costs)

    # ------------------------------------------------------------------ panel
    def load_panel(self, symbols: list[str] | None = None) -> pd.DataFrame:
        cfg = self.config
        return load_panel(
            source=cfg.data.source,
            symbols=symbols or cfg.all_symbols,
            seed=cfg.data.seed,
            path=cfg.data.path,
        )

    # ------------------------------------------------------------------- run
    def run_day(self, date: str | None = None, panel: pd.DataFrame | None = None) -> dict[str, Any]:
        """Run one cycle. Returns a summary dict; everything is also journalled."""
        cfg = self.config
        if panel is None:
            panel = self.load_panel()

        if date is None:
            date = str(panel.index[-1].date())
        date = str(date)

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        # The information cutoff is the last close strictly before the decision
        # date. Everything the desk sees is behind this line.
        cutoff_index = panel.index[panel.index < pd.Timestamp(date)]
        if len(cutoff_index) == 0:
            raise ValueError(f"no data before {date}")
        cutoff = str(cutoff_index[-1].date())
        cutoff_panel = panel[panel.index < pd.Timestamp(date)]

        result: dict[str, Any] = {
            "date": date,
            "information_cutoff": cutoff,
            "seats": {},
            "order": None,
            "veto": None,
        }

        # ---- kill switch: checked before anything else runs ------------------
        if self.risk.kill_switch_engaged():
            self.journal.write_decision(
                Decision(
                    decision_id=f"risk-{date}-kill-switch",
                    date=date,
                    seat="risk",
                    idempotency_key=f"risk:{date}:kill_switch",
                    timestamp=now,
                    information_cutoff=cutoff,
                    input_snapshot_hash=snapshot_hash({"kill": True, "date": date}),
                    action="veto",
                    detail={"reason": "kill switch engaged"},
                )
            )
            result["veto"] = "kill switch engaged"
            return result

        holdings = cfg.portfolio.holdings
        if not holdings:
            raise ValueError("no holdings configured")

        prices = panel.loc[cutoff_index[-1]]
        equity = sum(h.shares * float(prices.get(h.symbol, 0.0)) for h in holdings)
        if equity <= 0:
            raise ValueError("portfolio value is zero; check the holdings and the price data")

        # ---- Quant seat -------------------------------------------------------
        regime = self.quant.evaluate(cutoff_panel, date=date)
        self.journal.write_decision(
            Decision(
                decision_id=f"quant-{date}",
                date=date,
                seat="quant",
                idempotency_key=f"quant:{date}",
                timestamp=now,
                information_cutoff=cutoff,
                input_snapshot_hash=snapshot_hash(
                    {"benchmark": cfg.portfolio.benchmark, "vol": regime.realised_vol, "dial": regime.dial}
                ),
                action="hold",
                signal=float(regime.dial),
                confidence=float(regime.vol_percentile),
                detail={
                    "regime": regime.regime,
                    "realised_vol": regime.realised_vol,
                    "vol_percentile": regime.vol_percentile,
                    "trend_state": regime.trend_state,
                    "trend_strength": regime.trend_strength,
                    "dial": regime.dial,
                },
            )
        )
        result["seats"]["quant"] = regime

        # ---- Scan seat + Hedger seat -----------------------------------------
        estimates = self.hedger.estimate_all(cutoff_panel, [h.symbol for h in holdings])
        betas = {s: e.beta_shrunk for s, e in estimates.items()}
        idio = {s: e.idio_vol for s, e in estimates.items()}
        candidates = self.scan.scan(cutoff_panel, holdings, betas, idio)

        self.journal.write_decision(
            Decision(
                decision_id=f"scan-{date}",
                date=date,
                seat="scan",
                idempotency_key=f"scan:{date}",
                timestamp=now,
                information_cutoff=cutoff,
                input_snapshot_hash=snapshot_hash(
                    {"candidates": [(c.symbol, round(c.total_contribution, 8)) for c in candidates]}
                ),
                action="hold" if candidates else "skip",
                signal=float(candidates[0].total_contribution) if candidates else 0.0,
                detail={
                    "candidates": [
                        {
                            "symbol": c.symbol,
                            "weight": c.weight,
                            "beta": c.beta,
                            "idio_vol": c.idio_vol,
                            "systematic": c.systematic_contribution,
                            "idiosyncratic": c.idiosyncratic_contribution,
                            "hedgeable_share": c.hedgeable_share,
                        }
                        for c in candidates
                    ],
                    "betas": {s: float(e.beta) for s, e in estimates.items()},
                    "betas_shrunk": {s: float(e.beta_shrunk) for s, e in estimates.items()},
                    "shrinkage_weights": {s: float(e.shrinkage_weight) for s, e in estimates.items()},
                    "t_stats": {s: float(e.t_stat) for s, e in estimates.items()},
                },
            )
        )
        result["seats"]["scan"] = candidates

        proposal = self.hedger.build_proposal(
            date=date,
            cutoff_panel=cutoff_panel,
            candidates=candidates,
            equity=equity,
            costs=cfg.costs,
            dial=regime.dial,
            max_hedge_pct_equity=cfg.hedging.max_hedge_pct_equity,
        )

        if proposal is None:
            self.journal.write_decision(
                Decision(
                    decision_id=f"risk-{date}-no-proposal",
                    date=date,
                    seat="risk",
                    idempotency_key=f"risk:{date}:no_proposal",
                    timestamp=now,
                    information_cutoff=cutoff,
                    input_snapshot_hash=snapshot_hash({"proposal": None, "date": date}),
                    action="skip",
                    detail={"reason": "no hedge proposal justified on this date"},
                )
            )
            result["veto"] = "no hedge proposal"
            return result

        self.journal.write_proposal(proposal)
        self.journal.write_decision(
            Decision(
                decision_id=f"hedger-{date}",
                date=date,
                seat="hedger",
                idempotency_key=f"hedger:{date}",
                timestamp=now,
                information_cutoff=cutoff,
                input_snapshot_hash=proposal.detail.get("input_hash", ""),
                action="hedge",
                signal=float(proposal.est_vol_reduction_pct) / 100.0,
                confidence=float(min(1.0, max(0.0, proposal.reward_to_risk / 3.0))),
                horizon_days=self.hedger.horizon_days,
                detail=proposal.to_row(),
            )
        )
        result["seats"]["hedger"] = proposal

        # ---- Judge seat: N votes ---------------------------------------------
        judge = RuleBasedJudge()
        verdicts = [
            judge.judge(proposal, {"regime": regime.regime, "dial": regime.dial}, run=i)
            for i in range(self.judge_runs)
        ]
        for v in verdicts:
            self.journal.write_verdict(v)
        summary = aggregate_verdicts(verdicts)

        self.journal.write_decision(
            Decision(
                decision_id=f"judge-{date}",
                date=date,
                seat="judge",
                idempotency_key=f"judge:{date}",
                timestamp=now,
                information_cutoff=cutoff,
                input_snapshot_hash=proposal.detail.get("input_hash", ""),
                action="approve" if summary["verdict"] == "approve" else "skip",
                signal=float(summary["score"]),
                confidence=float(summary["agreement"]),
                detail=summary,
            )
        )
        result["seats"]["judge"] = summary

        # ---- Risk seat: the only veto and the only signature ------------------
        decision = self.risk.evaluate(
            date=date,
            proposals=[proposal],
            judge_summary=summary,
            equity=equity,
            costs=cfg.costs,
        )
        self.journal.write_decision(
            Decision(
                decision_id=f"risk-{date}",
                date=date,
                seat="risk",
                idempotency_key=f"risk:{date}",
                timestamp=now,
                information_cutoff=cutoff,
                input_snapshot_hash=snapshot_hash(
                    {"intent": decision.intent.to_row() if decision.intent else None, "date": date}
                ),
                action="approve" if decision.approved else "veto",
                signal=1.0 if decision.approved else -1.0,
                detail={
                    "approved": decision.approved,
                    "reasons": decision.reasons,
                    "veto_reasons": decision.veto_reasons,
                    "signature": decision.signature,
                    "stage": decision.details.get("stage"),
                },
            )
        )

        if not decision.approved or decision.intent is None:
            result["veto"] = "; ".join(decision.veto_reasons) or "not approved"
            return result

        # ---- Execution --------------------------------------------------------
        self.journal.write_intent(decision.intent)
        fill = self.broker.submit(decision.intent, panel, fill_date=date)
        self.journal.write_fill(fill)
        result["order"] = {
            "intent": decision.intent.to_row(),
            "fill": fill.to_row(),
            "signature": decision.signature,
        }
        return result


# --------------------------------------------------------------------- CLI
def _print_result(result: dict[str, Any]) -> None:
    print(f"\n=== desk run {result['date']} (information cutoff {result['information_cutoff']}) ===")
    quant = result["seats"].get("quant")
    if quant is not None:
        print(
            f"  quant : regime={quant.regime} vol={quant.realised_vol:.2%} "
            f"pct={quant.vol_percentile:.2f} trend={quant.trend_state} dial={quant.dial:.2f}"
        )
    scan = result["seats"].get("scan")
    if scan:
        print("  scan  : " + ", ".join(
            f"{c.symbol} w={c.weight:.1%} beta={c.beta:.2f} hedgeable={c.hedgeable_share:.0%}"
            for c in scan
        ))
    hedger = result["seats"].get("hedger")
    if hedger is not None:
        print(
            f"  hedger: {hedger.hedge_symbol} {hedger.target_notional:+,.0f} "
            f"vol {hedger.est_vol_reduction_pct:+.2f}% rrr={hedger.reward_to_risk:.2f}"
        )
    judge = result["seats"].get("judge")
    if judge is not None:
        print(f"  judge : {judge['verdict']} ({judge['approvals']}/{judge['n']} approvals)")
    if result.get("veto"):
        print(f"  risk  : VETO - {result['veto']}")
    if result.get("order"):
        fill = result["order"]["fill"]
        print(
            f"  fill  : {fill['side']} {abs(fill['quantity']):.2f} {fill['symbol']} "
            f"@ {fill['price']:.2f} cost {fill['total_cost']:.2f}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hedging-desk",
        description="Run one cycle of the hedging desk and print what it decided.",
    )
    parser.add_argument("--config", default="examples/holdings.example.yaml")
    parser.add_argument("--journal", default="journal")
    parser.add_argument("--date", default=None, help="ISO date to run. Default: last available.")
    parser.add_argument("--json", action="store_true", help="print the raw result as JSON")
    args = parser.parse_args(argv)

    config = DeskConfig.from_yaml(args.config)
    journal = Journal(args.journal)
    desk = Desk(config=config, journal=journal)
    result = desk.run_day(date=args.date)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        _print_result(result)
        print(f"\n  journal: {journal.root}")
        print(f"  {journal.stats()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
