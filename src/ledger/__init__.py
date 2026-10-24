"""The journal: every decision, written before its outcome is known.

Two objects live here.

``Decision``
    One row per seat per day. Written *before* the seat's outcome is known,
    so the record cannot be edited by hindsight. This is the raw material for
    the evaluation gates.

``OrderIntent``
    One row per intended trade. Only the Risk seat may create one, and only
    with a signature. The execution adapter refuses unsigned intents.

Both are append-only. The writer never rewrites a row; corrections are new
rows with a ``supersedes`` pointer.
"""

from .schema import Decision, OrderIntent, Fill, Verdict, HedgeProposal
from .journal import Journal

__all__ = [
    "Decision",
    "OrderIntent",
    "Fill",
    "Verdict",
    "HedgeProposal",
    "Journal",
]
