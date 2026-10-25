"""Does the audit notice when the desk did nothing?

The desk swallows exceptions from its seats, records them, and carries on.
That is deliberate: the run is more useful with a partial answer and an
error log than with a crash. But it has a consequence that the gates do
not protect against.

A seat that raises on every call produces:

    the same gates      (hedgeability True, regime_information False)
    the same verdict    (False)
    the same R^2        (0.5850042453516432)

because the gates are computed from the hedging equation and not from the
seats. The two things that DO differ are the ones the run swallowed:

    n_seat_errors  172 instead of 0
    n_trades         0 instead of 121

So a report can say "hedgeability passes" while the scan seat failed on
every single day. These tests pin the check that tells those apart.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _load_audit_module():
    """Import scripts/audit_claims.py by path.

    It is a script, not a package module, and importing it runs its
    top-level code -- so it is loaded by path rather than by name.
    """
    path = REPO / "scripts" / "audit_claims.py"
    spec = importlib.util.spec_from_file_location("desk_audit_claims", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def audit():
    return _load_audit_module()


def _write_report(tmp_path: Path, summary: dict) -> Path:
    path = tmp_path / "evaluation.json"
    path.write_text(json.dumps({"summary": summary}), encoding="utf-8")
    return path


def test_a_healthy_report_passes(audit, tmp_path):
    """The real report: 121 trades, no seat errors."""
    path = _write_report(tmp_path, {
        "n_trades": 121, "n_seat_errors": 0, "n_signal_errors": 0,
        "r_squared": 0.5850042453516432,
    })
    problems, notes = audit.check_the_desk_did_work(path)
    assert problems == [], problems
    assert any("121 trade(s)" in n for n in notes)


def test_a_crashed_seat_is_caught(audit, tmp_path):
    """The failure this check exists for.

    These are the numbers a seat that raises on every call produces. The
    gates, the verdict and the R^2 are all IDENTICAL to the healthy run
    above -- that is the whole point -- so nothing else in the report
    distinguishes them.
    """
    path = _write_report(tmp_path, {
        "n_trades": 0, "n_seat_errors": 172, "n_signal_errors": 0,
        "r_squared": 0.5850042453516432,
    })
    problems, notes = audit.check_the_desk_did_work(path)
    assert problems, "a report describing 172 seat errors must fail the audit"
    joined = " ".join(problems)
    assert "172 seat error(s)" in joined
    assert "0 trades" in joined


def test_a_report_without_trades_fails_even_without_seat_errors(audit, tmp_path):
    """Zero trades is its own problem.

    A run that placed no trades produces the same R^2 and the same gates
    as a run that was told to place none. If the seats did not raise, the
    only remaining evidence that the desk worked is that it traded.
    """
    path = _write_report(tmp_path, {
        "n_trades": 0, "n_seat_errors": 0, "n_signal_errors": 0,
        "r_squared": 0.5850042453516432,
    })
    problems, _ = audit.check_the_desk_did_work(path)
    assert any("0 trades" in p for p in problems), problems


def test_a_report_that_hides_its_failures_fails(audit, tmp_path):
    """A report that does not publish the counters cannot be checked.

    This is the subtle version of the same hole: if the report simply
    omits n_seat_errors, then there is nothing to compare against zero,
    and a broken run is indistinguishable from a working one.
    """
    path = _write_report(tmp_path, {"n_trades": 121})
    problems, _ = audit.check_the_desk_did_work(path)
    assert any("does not publish n_seat_errors" in p for p in problems), problems


def test_signal_errors_are_caught_too(audit, tmp_path):
    """The signal path is a separate failure mode with the same shape."""
    path = _write_report(tmp_path, {
        "n_trades": 121, "n_seat_errors": 0, "n_signal_errors": 3,
        "r_squared": 0.5850042453516432,
    })
    problems, _ = audit.check_the_desk_did_work(path)
    assert any("3 signal error(s)" in p for p in problems), problems


def test_the_published_report_passes(audit):
    """The committed report must satisfy the check it motivated.

    If this fails, the shipped report describes a run that did not work,
    and every number in it is unsound.
    """
    path = REPO / "reports" / "evaluation.json"
    if not path.exists():
        pytest.skip("no committed report to check")
    problems, _ = audit.check_the_desk_did_work(path)
    assert problems == [], problems
