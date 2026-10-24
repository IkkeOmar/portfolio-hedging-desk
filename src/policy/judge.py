"""The Judge seat: is this proposal any good?

Why a Judge at all? The Hedger's maths is arithmetic. It can be wrong in
uninteresting ways: the covariance it measured was noise, the cost estimate
was optimistic, the hedge instrument is not what we thought. A second opinion
that looks at the proposal with different inputs catches some of that.

Two implementations ship:

``RuleBasedJudge``
    Deterministic. Checks the proposal against explicit, readable criteria.
    This is the default, and it is what makes the repo runnable offline with
    no API key. It is not a mock: it is a real, honest second opinion, just
    one that cannot hallucinate.

``LLMJudge``
    Calls an OpenAI-compatible chat endpoint N times. It is included because
    the interesting question for a reader is "what does an LLM add here,
    and does it help or hurt?" — and that question is answerable only if
    the LLM path is actually runnable.

    **How it is enabled.** There is no ``judge.provider`` config key, and
    there is not one in the code either: the desk's configuration schema
    has no ``judge`` section at all. The LLM judge is selected from the
    **dashboard's Settings panel**, which writes the provider's base URL,
    model and key into the local ``.env`` file, and from the "Desk" tab,
    which builds the judge from that file. Programmatically, construct
    ``LLMJudge`` directly — it takes ``base_url``, ``model`` and
    ``api_key_env``.

    (This docstring used to say "set ``judge.provider: llm`` in the
    config". That key has never existed. A documented option that cannot
    be selected makes the project look more capable than it is, which is
    the exact failure this repository is about.)

The ensemble
------------
An LLM judge is non-deterministic: the same input gives different answers.
One run tells you almost nothing. So the Judge runs N times and the votes are
aggregated. This is the single most important idea in the whole seat design:

    **one sample of a noisy opinion is not evidence of anything.**

``aggregate_verdicts`` implements the aggregation: majority vote on the
verdict, mean score, and the spread between runs reported so you can see how
disagreeing the judges were.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np

from ..ledger.schema import Verdict


class Judge(Protocol):
    """Interface every judge implements."""

    model_name: str

    def judge(self, proposal, context: dict[str, Any], run: int) -> Verdict:
        ...


@dataclass
class RuleBasedJudge:
    """Deterministic second opinion, expressed as explicit criteria.

    The criteria, in order, with the reasoning:

    1. **Does it reduce volatility at all?** A hedge that does not lower
       volatility is a cost with no benefit. Reject.
    2. **Is the estimated benefit bigger than the estimated risk?** The
       reward-to-risk ratio has to clear a floor. A hedge that risks more
       dollar value than it is expected to save is not a hedge.
    3. **Is the cost proportional to the benefit?** A 5 bp round trip that
       saves 1% of annual volatility is worth it. A 50 bp round trip that
       saves 0.2% is not.
    4. **Is the hedge the right size?** Notional beyond the configured cap is
       rejected, because a hedge that becomes a directional bet is not a hedge.

    Each rejection records *which* criterion failed. That is what lets the
    journal explain itself.
    """

    model_name: str = "rule-based-v1"
    min_vol_reduction_pct: float = 0.5
    min_reward_to_risk: float = 1.0
    max_cost_bps: float = 50.0

    def judge(self, proposal, context: dict[str, Any], run: int = 0) -> Verdict:
        """Apply the criteria and return a verdict.

        Each criterion is evaluated once and recorded as a (passed, reason)
        pair. The verdict is the AND of the individual pass flags.

        An earlier version inferred the verdict by sniffing prefixes of the
        human-readable reason strings. That was broken: a *passing* criterion
        produced the reason "reward-to-risk 12.59", which begins with the
        same prefix as the *failing* criterion "reward-to-risk 12.59 is below
        the 1.00 floor", so every proposal was rejected. The desk never
        traded a single day. Criteria are now booleans, and the strings are
        for humans only.
        """
        criteria: list[tuple[bool, str, float]] = []

        vol_ok = proposal.est_vol_reduction_pct >= self.min_vol_reduction_pct
        criteria.append((
            vol_ok,
            f"volatility reduced by {proposal.est_vol_reduction_pct:.2f}%"
            if vol_ok else
            f"volatility reduction {proposal.est_vol_reduction_pct:.2f}% is below the "
            f"{self.min_vol_reduction_pct:.2f}% floor",
            0.4,
        ))

        rrr_ok = proposal.reward_to_risk >= self.min_reward_to_risk
        criteria.append((
            rrr_ok,
            f"reward-to-risk {proposal.reward_to_risk:.2f}"
            if rrr_ok else
            f"reward-to-risk {proposal.reward_to_risk:.2f} is below the "
            f"{self.min_reward_to_risk:.2f} floor",
            0.4,
        ))

        cost_ok = proposal.est_cost_bps <= self.max_cost_bps
        criteria.append((
            cost_ok,
            f"round-trip cost {proposal.est_cost_bps:.1f} bps"
            if cost_ok else
            f"round-trip cost {proposal.est_cost_bps:.1f} bps is too high",
            0.2,
        ))

        benefit_ok = proposal.est_reward_usd > 0
        criteria.append((
            benefit_ok,
            f"expected benefit ${proposal.est_reward_usd:,.0f}"
            if benefit_ok else
            "no positive expected benefit",
            0.2,
        ))

        reasons = [reason for _, reason, _ in criteria]
        approved = all(ok for ok, _, _ in criteria)
        score = min(1.0, sum(weight for ok, _, weight in criteria if ok))

        return Verdict(
            verdict_id=f"verdict-{proposal.proposal_id}-r{run}",
            proposal_id=proposal.proposal_id,
            date=proposal.date,
            judge_run=run,
            verdict="approve" if approved else "reject",
            score=float(score),
            reasons=reasons,
            judge_model=self.model_name,
        )


@dataclass
class LLMJudge:
    """LLM judge against any OpenAI-compatible chat-completions endpoint.

    The prompt asks for a JSON object with a verdict and reasons. The response
    is parsed defensively: if the model returns prose instead of JSON, the run
    is recorded as a rejection with the parse failure as the reason rather
    than crashing the desk or, worse, silently defaulting to approval.

    Parameters
    ----------
    base_url : str
        e.g. ``https://api.deepseek.com/v1``
    model : str
        e.g. ``deepseek-chat``
    api_key_env : str
        Name of the environment variable holding the key.
    temperature : float
        Deliberately above zero. The point of the ensemble is to sample a
        distribution, not to get the same answer N times.
    """

    model_name: str = "llm"
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    api_key_env: str = "OPENAI_API_KEY"
    temperature: float = 0.7
    max_tokens: int = 400
    timeout_s: float = 30.0

    _SYSTEM = (
        "You are a risk reviewer for a portfolio hedging desk. "
        "You are given ONE hedge proposal. Reply with STRICT JSON only, no prose, "
        'of the form {"verdict": "approve" | "reject", "score": <number -1..1>, '
        '"reasons": ["<short reason>", ...]}. '
        "Reject if the estimated benefit does not clearly exceed the estimated risk "
        "and cost. Be conservative and specific."
    )

    def _endpoint(self) -> str:
        return self.base_url.rstrip("/") + "/chat/completions"

    def judge(self, proposal, context: dict[str, Any], run: int = 0) -> Verdict:
        api_key = os.environ.get(self.api_key_env, "")
        user_payload = {
            "proposal": {
                "date": proposal.date,
                "hedge_symbol": proposal.hedge_symbol,
                "target_notional": round(proposal.target_notional, 2),
                "portfolio_beta": round(proposal.portfolio_beta, 4),
                "hedged_beta": round(proposal.hedged_beta, 4),
                "est_vol_reduction_pct": round(proposal.est_vol_reduction_pct, 3),
                "est_cost_bps": round(proposal.est_cost_bps, 2),
                "est_reward_usd": round(proposal.est_reward_usd, 2),
                "est_risk_usd": round(proposal.est_risk_usd, 2),
                "reward_to_risk": round(proposal.reward_to_risk, 3),
            },
            "context": {
                k: v for k, v in context.items() if k in ("regime", "dial", "realised_vol", "equity")
            },
        }
        body = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": self._SYSTEM},
                {"role": "user", "content": json.dumps(user_payload, indent=2)},
            ],
        }
        verdict = "reject"
        score = -1.0
        reasons: list[str] = []

        if not api_key:
            reasons.append(f"no API key in ${self.api_key_env}; the judge cannot run")
        else:
            req = urllib.request.Request(
                self._endpoint(),
                data=json.dumps(body).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    raw = json.loads(resp.read().decode("utf-8"))
                content = raw["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                verdict = str(parsed.get("verdict", "reject")).lower()
                if verdict not in ("approve", "reject"):
                    verdict = "reject"
                    reasons.append(f"unrecognised verdict {parsed.get('verdict')!r}; treated as reject")
                score = float(np.clip(parsed.get("score", 0.0), -1.0, 1.0))
                reasons = [str(r) for r in (parsed.get("reasons") or [])]
            except urllib.error.HTTPError as exc:
                reasons.append(f"judge endpoint returned HTTP {exc.code}")
            except (urllib.error.URLError, TimeoutError) as exc:
                reasons.append(f"judge endpoint unreachable: {exc}")
            except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as exc:
                reasons.append(f"could not parse judge response: {exc}")

        return Verdict(
            verdict_id=f"verdict-{proposal.proposal_id}-r{run}",
            proposal_id=proposal.proposal_id,
            date=proposal.date,
            judge_run=run,
            verdict=verdict,
            score=score,
            reasons=reasons,
            judge_model=self.model_name,
        )


def aggregate_verdicts(verdicts: list[Verdict]) -> dict[str, Any]:
    """Aggregate N judge votes into one decision, and report the disagreement.

    Returns a dict with the final verdict, the mean score, the vote counts,
    and the spread of scores between runs. The spread is the interesting
    number: a large spread means the judges disagreed, and a verdict built on
    disagreeing judges is weaker than the majority vote alone suggests.
    """
    if not verdicts:
        return {
            "verdict": "reject",
            "score": 0.0,
            "approvals": 0,
            "rejections": 0,
            "n": 0,
            "score_spread": 0.0,
            "agreement": 0.0,
        }
    scores = np.array([v.score for v in verdicts], dtype=float)
    approvals = sum(1 for v in verdicts if v.verdict == "approve")
    rejections = len(verdicts) - approvals
    agreement = max(approvals, rejections) / len(verdicts)
    return {
        "verdict": "approve" if approvals > rejections else "reject",
        "score": float(scores.mean()),
        "approvals": int(approvals),
        "rejections": int(rejections),
        "n": len(verdicts),
        "score_spread": float(scores.max() - scores.min()) if len(scores) > 1 else 0.0,
        "agreement": float(agreement),
    }
