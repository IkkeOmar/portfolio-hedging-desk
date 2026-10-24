"""Row types for the journal.

Design rule: a row must be self-describing. If you hand someone one line of
the journal and nothing else, they should be able to tell what was decided,
on what information, at what time, and with how much confidence.

The field names follow the prediction-ledger schema in the project methodology
(see ``docs/METHODOLOGY.md``). Fields that do not apply to a given seat are
left empty rather than filled with a placeholder number.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any


def snapshot_hash(payload: Any) -> str:
    """Stable hash of the exact information a decision was based on.

    This is what makes a decision auditable. If two runs of the desk disagree
    on the same day, the hashes differ and you can find out which input
    moved. SHA-256 over a canonical JSON rendering, so key order does not
    matter.
    """
    blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


@dataclass
class Decision:
    """One seat's output for one day."""

    # identity
    decision_id: str
    date: str                    # ISO date, the trading day
    seat: str                    # hedger | quant | scan | judge | risk
    idempotency_key: str        # re-running the same day must not duplicate the row

    # information
    timestamp: str               # when the seat ran
    information_cutoff: str      # latest market data the seat was allowed to see
    input_snapshot_hash: str     # hash of the exact inputs
    model_version: str = "rule-based-v1"
    strategy_version: str = "hedge-v1"
    prompt_version: str = "n/a"

    # what was decided
    action: str = "hold"        # hold | hedge | skip | veto | approve
    signal: float | None = None  # continuous score in [-1, 1]
    confidence: float | None = None
    horizon_days: int = 1

    # the numbers behind the decision
    detail: dict[str, Any] = field(default_factory=dict)
    predicted_return: float | None = None
    predicted_probability_up: float | None = None

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HedgeProposal:
    """The Hedger seat's request. Never traded directly; it must be judged."""

    proposal_id: str
    date: str
    hedge_symbol: str
    target_notional: float       # signed: negative = short
    hedge_beta: float            # the instrument's beta to the benchmark
    portfolio_beta: float        # the portfolio's beta before the hedge
    hedged_beta: float           # the portfolio's beta after the hedge
    est_vol_reduction_pct: float  # percent reduction in portfolio volatility
    est_cost_bps: float          # round-trip cost of this leg
    est_reward_usd: float        # expected dollar benefit over the horizon
    est_risk_usd: float          # expected dollar at risk over the horizon
    reward_to_risk: float        # est_reward_usd / est_risk_usd
    rationale: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Verdict:
    """One judge vote. Several of these are aggregated into a final verdict."""

    verdict_id: str
    proposal_id: str
    date: str
    judge_run: int              # which of the N ensemble runs this is
    verdict: str                # approve | reject
    score: float                # [-1, 1]
    reasons: list[str] = field(default_factory=list)
    judge_model: str = "rule-based-v1"

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OrderIntent:
    """An approved, sized, risk-signed order. The only thing an adapter may execute."""

    intent_id: str
    date: str
    symbol: str
    side: str                   # buy | sell
    notional: float             # signed dollar amount, positive = buy
    quantity_hint: float | None = None
    reason: str = ""
    proposal_id: str | None = None
    risk_signature: str | None = None   # sha256 of the risk decision
    risk_signed_by: str | None = None
    live_allowed: bool = False

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Fill:
    """A simulated or real fill."""

    fill_id: str
    intent_id: str
    date: str
    symbol: str
    side: str
    quantity: float
    price: float
    notional: float
    commission: float
    slippage: float
    spread_cost: float
    total_cost: float

    def to_row(self) -> dict[str, Any]:
        return asdict(self)
