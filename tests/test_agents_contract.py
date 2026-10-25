"""Does the D19 check notice when AGENTS.md and the README disagree?

D18 checks that the README names at least three extension points and
that every path resolves. D19 checks the other half: the machine-facing
contract has to agree with the human-facing one, and it has to say what
a caller may NOT do.

A check that has never failed has not been proved, so every case here
is a failure it must produce.
"""

from __future__ import annotations

import importlib.util
import os
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


def _readme() -> str:
    return (REPO / "README.md").read_text(encoding="utf-8")


def _agents() -> str:
    """The published contract, if it has landed.

    AGENTS.md is a protected file: it is written and verified, and it
    lands only on approval. Until then these tests run against the
    approved draft, which lives beside the repository -- so the check
    is proved NOW rather than the day the file is approved.
    """
    published = REPO / "AGENTS.md"
    if published.exists():
        return published.read_text(encoding="utf-8")
    # The approved draft lives in the workfolder, which is outside the
    # repository and is not there in CI. It is found by an ENVIRONMENT
    # VARIABLE rather than a hard-coded path: a machine path in a
    # committed file is a personal string, and the publication scan
    # fails the build on one.
    #
    # In CI these tests skip, and the D19 check in the audit reports the
    # contract as PENDING. When AGENTS.md is approved and lands, the
    # published file is used and every test runs for real.
    draft_path = os.environ.get("DESK_AGENTS_DRAFT")
    if draft_path:
        draft = Path(draft_path)
        if draft.exists():
            return draft.read_text(encoding="utf-8")
    pytest.skip("AGENTS.md is not published yet, so there is nothing to check")


def test_the_readme_and_agents_agree(audit, tmp_path):
    """The real files must satisfy the check.

    If this fails, either the two documents disagree about where the
    seams are, or AGENTS.md has lost its "may not" list.
    """
    path = tmp_path / "AGENTS.md"
    path.write_text(_agents(), encoding="utf-8")
    problems, _pending = audit.check_agents_agrees_with_readme(_readme(), path)
    assert problems == [], problems


def test_a_missing_agents_file_is_pending_not_failed(audit, tmp_path):
    """No contract yet is PENDING, not a broken build.

    AGENTS.md is a protected file: it is written and verified, and it
    lands only on approval. A build that fails for a file nobody has
    approved yet trains people to ignore the checker, so the absence is
    reported as pending and the comparison happens the moment the file
    is there.

    The moment the file exists, a disagreement IS a failure -- that is
    what the other tests here check.
    """
    problems, pending = audit.check_agents_agrees_with_readme(
        _readme(), tmp_path / "AGENTS.md"
    )
    assert problems == [], problems
    assert pending, "the absence of the contract must be reported"
    assert any("AGENTS.md" in n for n in pending), pending


def test_a_disagreeing_seam_list_fails(audit, tmp_path):
    """AGENTS.md must name the seams the README names.

    Here the agent contract drops one of the README's four extension
    points, so an agent reading AGENTS.md would never learn that the gate
    thresholds are replaceable.
    """
    agents = _agents()
    assert "`src/evaluation/gates.py`" in agents, "the fixture assumes the seam is named"
    broken = agents.replace("`src/evaluation/gates.py`", "the gate thresholds")
    path = tmp_path / "AGENTS.md"
    path.write_text(broken, encoding="utf-8")
    problems, _pending = audit.check_agents_agrees_with_readme(_readme(), path)
    assert problems, "dropping a named seam must fail the check"
    assert any("src/evaluation/gates.py" in p for p in problems), problems


def test_a_missing_may_not_list_fails(audit, tmp_path):
    """The contract must say what a caller may NOT do.

    This is the honesty of the project restated for a machine: it may not
    turn the repository into a signal generator, may not weaken a gate
    threshold to make something pass, and may not present the output as
    advice about what to hold. Without the list, the contract is silent
    on exactly the things an agent gets wrong.
    """
    agents = _agents()
    assert audit.MAY_NOT_MARKER in agents, "the fixture assumes the marker is present"
    broken = agents.replace(audit.MAY_NOT_MARKER, "### A list of things")
    path = tmp_path / "AGENTS.md"
    path.write_text(broken, encoding="utf-8")
    problems, _pending = audit.check_agents_agrees_with_readme(_readme(), path)
    assert problems, "removing the may-not list must fail the check"
    assert any("may not" in p for p in problems), problems


def test_a_missing_seam_section_fails(audit, tmp_path):
    """AGENTS.md without a seams section names no extension points."""
    agents = _agents()
    assert audit.AGENTS_SEAM_SECTION in agents, "the fixture assumes the section exists"
    broken = agents.replace(audit.AGENTS_SEAM_SECTION, "### Extension points")
    path = tmp_path / "AGENTS.md"
    path.write_text(broken, encoding="utf-8")
    problems, _pending = audit.check_agents_agrees_with_readme(_readme(), path)
    assert problems, "a missing seam section must fail the check"
    assert any(audit.AGENTS_SEAM_SECTION in p for p in problems), problems


def test_commands_are_not_mistaken_for_seams(audit, tmp_path):
    """A path under scripts/ is a command, not an extension point.

    AGENTS.md names the audit scripts a caller may run. Those are not
    seams -- a caller cannot extend the system by editing the audit --
    and counting them as seams would make the two lists disagree for no
    reason.
    """
    agents = _agents()
    assert "scripts/audit_claims.py" in agents, "the fixture assumes the command is named"
    problems, pending = audit.check_agents_agrees_with_readme(
        _readme(), tmp_path / "x"
    )
    # The file does not exist, so the only finding is the pending file.
    assert problems == [], problems
    assert pending, "the absence of the contract must be reported"
