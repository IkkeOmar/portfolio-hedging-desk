"""The seats. Each one owns one decision and writes one journal row.

    quant.py    what kind of market are we in? (regime)
    scan.py     what is worth looking at? (candidates)
    hedger.py   what should the hedge be? (proposal)
    judge.py    is this proposal any good? (verdict, ensemble of N)
    risk.py     may this be traded at all? (the only veto, and the only signature)

The dependency direction is strict: judge reads the hedger's output, risk reads
everyone's output, and only risk can produce an order intent. There is no path
from a seat to an order that skips risk.
"""

from .hedger import HedgePolicy, HedgeEstimate
from .quant import QuantPolicy, RegimeSnapshot
from .scan import ScanPolicy, ScanCandidate
from .judge import Judge, RuleBasedJudge, LLMJudge, aggregate_verdicts
from .risk import RiskPolicy, RiskDecision

__all__ = [
    "HedgePolicy",
    "HedgeEstimate",
    "QuantPolicy",
    "RegimeSnapshot",
    "ScanPolicy",
    "ScanCandidate",
    "Judge",
    "RuleBasedJudge",
    "LLMJudge",
    "aggregate_verdicts",
    "RiskPolicy",
    "RiskDecision",
]
