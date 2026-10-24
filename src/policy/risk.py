"""The Risk seat: the only veto, the only signature.

Everything else in the desk can propose. Only Risk can authorise.

The design principle is **fail-safe by construction**: the path from a seat to
an order runs through exactly one gate, and the default state of that gate
is "no". A seat that crashes, a journal write that fails, an execution
adapter that wakes up confused — none of them can produce an order, because
an unsigned intent is not executable.

The kill switch is a file on disk. That is deliberate: it survives a crashed
process, a rebooted machine, and a human who needs to stop the desk *right
now* without waiting for a health check.

Checks the Risk seat performs, in order:

1. Kill switch present? Stop everything.
2. Is there a judge verdict at all, and did it pass?
3. Do the judge votes agree? A 1-of-3 approval is not a consensus.
4. Is the reward-to-risk above the floor?
5. Is each leg within the per-trade risk budget?
6. Is gross hedge exposure within the cap?
7. Are there too many legs?
8. Does the expected benefit beat the transaction cost?

Every rejection is recorded with the reason. A system that publishes its
veto reasons is auditable; one that quietly does nothing is not.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..ledger.schema import OrderIntent, snapshot_hash

KILL_SWITCH_NAME = "risk.kill_switch"


@dataclass
class RiskDecision:
    """The Risk seat's answer."""

    approved: bool
    intent: OrderIntent | None = None
    reasons: list[str] = field(default_factory=list)
    veto_reasons: list[str] = field(default_factory=list)
    signature: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class RiskPolicy:
    """Applies hard limits and signs the order intents that pass."""

    def __init__(
        self,
        max_gross_hedge_pct: float = 1.0,
        risk_per_trade_pct: float = 0.02,
        min_reward_to_risk: float = 1.5,
        max_legs: int = 5,
        journal_root: str | Path = "journal",
        require_judge_agreement: bool = True,
        min_judge_agreement: float = 0.67,
    ):
        self.max_gross_hedge_pct = float(max_gross_hedge_pct)
        self.risk_per_trade_pct = float(risk_per_trade_pct)
        self.min_reward_to_risk = float(min_reward_to_risk)
        self.max_legs = int(max_legs)
        self.journal_root = Path(journal_root)
        self.require_judge_agreement = require_judge_agreement
        self.min_judge_agreement = float(min_judge_agreement)

    # ------------------------------------------------------------ kill switch
    @property
    def kill_switch_path(self) -> Path:
        return self.journal_root / KILL_SWITCH_NAME

    def kill_switch_engaged(self) -> bool:
        return self.kill_switch_path.exists()

    def engage_kill_switch(self, reason: str = "manual") -> Path:
        """Engage the kill switch. Stops the desk before the next cycle."""
        self.journal_root.mkdir(parents=True, exist_ok=True)
        self.kill_switch_path.write_text(reason + "\n", encoding="utf-8")
        return self.kill_switch_path

    def release_kill_switch(self) -> bool:
        if self.kill_switch_path.exists():
            self.kill_switch_path.unlink()
            return True
        return False

    # ------------------------------------------------------------------ sign
    @staticmethod
    def sign(payload: dict[str, Any]) -> str:
        """Deterministic signature over the intent payload."""
        blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]

    # --------------------------------------------------------------- evaluate
    def evaluate(
        self,
        date: str,
        proposals: list,
        judge_summary: dict[str, Any],
        equity: float,
        costs: Any,
        existing_gross_hedge_pct: float = 0.0,
        open_legs: int = 0,
    ) -> RiskDecision:
        """Decide whether any proposal may become an order intent."""
        reasons: list[str] = []
        vetoes: list[str] = []

        if self.kill_switch_engaged():
            vetoes.append(f"kill switch engaged ({self.kill_switch_path})")
            return RiskDecision(
                approved=False,
                reasons=reasons,
                veto_reasons=vetoes,
                details={"stage": "kill_switch"},
            )

        if not proposals:
            vetoes.append("no hedge proposal on this date")
            return RiskDecision(approved=False, reasons=reasons, veto_reasons=vetoes,
                                details={"stage": "no_proposal"})

        if judge_summary.get("n", 0) == 0:
            vetoes.append("no judge verdict: nothing may be traded without a second opinion")
            return RiskDecision(approved=False, reasons=reasons, veto_reasons=vetoes,
                                details={"stage": "no_judge"})

        if judge_summary.get("verdict") != "approve":
            vetoes.append(
                f"judge rejected the proposal "
                f"({judge_summary.get('approvals', 0)}/{judge_summary.get('n', 0)} approvals)"
            )
            return RiskDecision(approved=False, reasons=reasons, veto_reasons=vetoes,
                                details={"stage": "judge_reject", "judge": judge_summary})

        if self.require_judge_agreement:
            agreement = float(judge_summary.get("agreement", 0.0))
            if agreement < self.min_judge_agreement:
                vetoes.append(
                    f"judges disagreed too much (agreement {agreement:.2f} < {self.min_judge_agreement:.2f})"
                )
                return RiskDecision(approved=False, reasons=reasons, veto_reasons=vetoes,
                                    details={"stage": "judge_split", "judge": judge_summary})

        # The proposal to trade is the first one that passes; the desk trades
        # one hedge leg at a time by default.
        proposal = proposals[0]

        if proposal.reward_to_risk < self.min_reward_to_risk:
            vetoes.append(
                f"reward-to-risk {proposal.reward_to_risk:.2f} below floor {self.min_reward_to_risk:.2f}"
            )
            return RiskDecision(approved=False, reasons=reasons, veto_reasons=vetoes,
                                details={"stage": "rrr"})

        notional = abs(float(proposal.target_notional))
        gross_pct = (existing_gross_hedge_pct + notional / equity) if equity > 0 else float("inf")
        if gross_pct > self.max_gross_hedge_pct:
            vetoes.append(
                f"gross hedge {gross_pct:.1%} exceeds cap {self.max_gross_hedge_pct:.1%}"
            )
            return RiskDecision(approved=False, reasons=reasons, veto_reasons=vetoes,
                                details={"stage": "gross_cap"})

        if open_legs + 1 > self.max_legs:
            vetoes.append(f"too many open legs ({open_legs} + 1 > {self.max_legs})")
            return RiskDecision(approved=False, reasons=reasons, veto_reasons=vetoes,
                                details={"stage": "max_legs"})

        # Expected benefit must beat the transaction cost, in dollars.
        cost_dollars = notional * float(costs.round_trip_fraction)
        if proposal.est_reward_usd <= cost_dollars:
            vetoes.append(
                f"expected benefit ${proposal.est_reward_usd:,.0f} does not exceed "
                f"transaction cost ${cost_dollars:,.0f}"
            )
            return RiskDecision(approved=False, reasons=reasons, veto_reasons=vetoes,
                                details={"stage": "cost"})

        # Per-trade risk budget: the loss this leg could cause must fit the budget.
        leg_risk = abs(float(proposal.est_risk_usd))
        budget = equity * self.risk_per_trade_pct
        if leg_risk > budget:
            vetoes.append(
                f"leg risk ${leg_risk:,.0f} exceeds budget ${budget:,.0f} "
                f"({self.risk_per_trade_pct:.1%} of equity)"
            )
            return RiskDecision(approved=False, reasons=reasons, veto_reasons=vetoes,
                                details={"stage": "risk_budget"})

        side = "sell" if proposal.target_notional < 0 else "buy"
        payload = {
            "date": date,
            "symbol": proposal.hedge_symbol,
            "side": side,
            "notional": float(proposal.target_notional),
            "proposal_id": proposal.proposal_id,
            "equity": float(equity),
            "judge": judge_summary,
        }
        signature = self.sign(payload)

        intent = OrderIntent(
            intent_id=f"intent-{date}-{proposal.hedge_symbol}",
            date=date,
            symbol=proposal.hedge_symbol,
            side=side,
            notional=float(proposal.target_notional),
            reason=proposal.rationale,
            proposal_id=proposal.proposal_id,
            risk_signature=signature,
            risk_signed_by="risk-seat",
            live_allowed=False,
        )
        reasons.append(
            f"approved: vol reduction {proposal.est_vol_reduction_pct:.2f}%, "
            f"rrr {proposal.reward_to_risk:.2f}, cost ${cost_dollars:,.0f} "
            f"vs benefit ${proposal.est_reward_usd:,.0f}"
        )
        return RiskDecision(
            approved=True,
            intent=intent,
            reasons=reasons,
            veto_reasons=vetoes,
            signature=signature,
            details={"judge": judge_summary, "cost_dollars": cost_dollars},
        )
