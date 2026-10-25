#!/usr/bin/env python3
"""Audit the X thread against the two repositories it describes.

The thread is the one artefact in this project that leaves the repository
and lands in front of strangers, and it is written for a reader who will
never run the code. So the numbers in it need a harder check than the
README's: they are the claims, and a reader takes them at face value.

This script checks, mechanically:

  T1  every tweet is at most 280 characters
  T2  every number in the thread is produced by the code, the trap ledgers or
      the methodology -- or is one of a small, explicitly documented set of
      figures quoted from the post we audited (which we do not claim)
  T3  every number quoted from the audited post is attributed to it
  T4  no emoji, no hashtags, no em-dashes, no engagement bait
  T5  the thread claims neither live trading nor a predictive edge
  T6  the failing gate is reported, and so are our own defects
  T7  both repositories are linked, and the video is linked once
  T8  the thread says it is a starting point and names the continuation

The numbers come from BOTH repositories. The desk half is read out of
`reports/evaluation.json` and `notes/KNOWN-TRAPS.md`, which are in this
repository. The lab half is read out of the lab's published sweep outputs,
its literature file and its trap ledger, which are in the sibling
repository. The lab is located by `--lab-repo`, or by looking for a sibling
checkout. If the lab cannot be found, the lab's numbers are reported as
UNVERIFIED rather than assumed good: a number we cannot check is a number
we are not entitled to publish.

It runs in CI, so a number that drifts out of the post fails the build.

Usage:
    python scripts/audit_thread.py
    python scripts/audit_thread.py --file notes/2026-10-25-x-thread.md
    python scripts/audit_thread.py --lab-repo ../hedging-agent-public
    python scripts/audit_thread.py --strict   # unmatched numbers fail too
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_THREAD = REPO / "notes" / "2026-10-25-x-thread.md"

# The repositories the thread links. Both are public; the thread is checked
# against both.
LAB_REPO_URL = "https://github.com/IkkeOmar/hedging-agent-public"
DESK_REPO_URL = "https://github.com/IkkeOmar/portfolio-hedging-desk"
VIDEO_URL = "https://www.youtube.com/watch?v=p0zSzhBRp3k"
AUDITED_POST_URL = "https://x.com/david_marco45/status/2113957281654259965"

# Numbers that are QUOTED from the post we audited, not claimed by us. The
# post contained a screenshot; these figures come from it. They are not
# independently verifiable, which is the point of the audit -- so they are
# allowed in the thread, but only because they are labelled as quoted, which
# T3 checks.
QUOTED_FROM_THE_AUDITED_POST = {
    "25": "the $25 starting balance in the post we audited",
    "4237": "the $4,237 figure in the post we audited",
    "10000": "the 10,000 wallets scanned in the post we audited",
    "7": "the 7 traders in the post we audited",
    "90": "the 90-day window in the post we audited",
}

# Phrases a thread must not contain. A thread that promises live trading, or
# claims a predictive edge, is a different and dishonest artefact.
FORBIDDEN_PHRASES = [
    "live trading",
    "live-trading",
    "real money",
    "guaranteed",
    "risk-free profit",
    "beat the market",
    "this works on real",
]

# Emoji ranges. Arrows (U+2190-U+21FF) are deliberately NOT here: they are
# typographic, not emoji, and "git clone -> pip install -> run" reads better
# with one.
EMOJI_RANGES = [
    (0x1F300, 0x1FAFF), (0x2600, 0x27BF), (0x2B00, 0x2BFF),
    (0xFE00, 0xFE0F), (0x1F000, 0x1F1FF),
]

# Engagement bait, matched as phrases so that ordinary English ("most people
# posting like that") is not a false positive.
ENGAGEMENT_BAIT = [
    "like this", "share this", "retweet this", "like and retweet",
    "comment below", "follow me", "link in bio", "drop a comment",
    "thoughts?", "who agrees", "let that sink in", "this is huge",
]


def _norm(text: str) -> str:
    """Normalise the dashes and arrows a thread is likely to contain."""
    return (text.replace("−", "-")       # U+2212 minus sign
                .replace("–", "-")       # en dash
                .replace("—", "-")       # em dash
                .replace("’", "'"))


def read_tweets(text: str) -> list[tuple[str, str]]:
    """Every `> ` block under a `### Tweet n/m` heading, as (heading, body)."""
    tweets: list[tuple[str, str]] = []
    heading = ""
    body: list[str] = []
    in_block = False
    for line in text.splitlines():
        if line.startswith("### "):
            if heading and body:
                tweets.append((heading, "\n".join(body)))
            heading = line[4:].strip()
            body = []
            in_block = False
            continue
        if line.startswith("> "):
            in_block = True
            body.append(line[2:].rstrip())
            continue
        if line.strip() == ">":
            if in_block:
                body.append("")
            continue
        if in_block and not line.startswith(">"):
            tweets.append((heading, "\n".join(body)))
            heading, body, in_block = "", [], False
    if heading and body:
        tweets.append((heading, "\n".join(body)))
    return [(h, b) for h, b in tweets if h.lower().startswith("tweet")]


def find_lab_repo(explicit: str | None) -> Path | None:
    """Locate the lab repository, which holds half of the thread's numbers."""
    if explicit:
        p = Path(explicit).expanduser()
        return p if p.is_dir() else None
    env = "HEDGE_LAB_REPO"
    import os
    if os.environ.get(env):
        p = Path(os.environ[env]).expanduser()
        if p.is_dir():
            return p
    candidates = [
        REPO.parent / "hedging-agent-public",
        REPO.parent / "hedging-agent",
        REPO.parent / "hedging-agent-launch",
        REPO / "hedging-agent",
    ]
    for c in candidates:
        if (c / "outputs").is_dir() and (c / "hedging_agent").is_dir():
            return c
    return None


def _keys_for(value) -> set[str]:
    """The string forms a number may legitimately appear as in prose."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return set()
    return {
        f"{f:.0f}", f"{f:.1f}", f"{f:.2f}", f"{f:.3f}", f"{f:.4f}",
        f"{abs(f):.0f}", f"{abs(f):.1f}", f"{abs(f):.2f}", f"{abs(f):.3f}",
        f"{abs(f):.4f}",
        f"{abs(f) * 100:.0f}", f"{abs(f) * 100:.1f}", f"{abs(f) * 100:.2f}",
        f"{abs(f) * 100:.3f}",
        f"{abs(f):,.0f}", f"{abs(f) * 100:,.1f}",
    }


def harvest_desk() -> dict[str, list[str]]:
    """Every number this repository produces, with where it came from."""
    known: dict[str, list[str]] = {}

    def add(value, source):
        for key in _keys_for(value):
            known.setdefault(key, []).append(source)

    report = REPO / "reports" / "evaluation.json"
    if report.exists():
        data = json.loads(report.read_text(encoding="utf-8"))
        for key, value in (data.get("summary") or {}).items():
            add(value, f"evaluation.json summary.{key}")
        for gate in data.get("gates", []):
            for key, value in (gate.get("metrics") or {}).items():
                add(value, f"evaluation.json gate {gate['name']}.{key}")
        for window in data.get("walkforward", []):
            add(window.get("sharpe"), "evaluation.json walkforward")
        # The number of gates the run actually reached, and how many checks
        # each gate carries: both are counts a reader can check.
        add(len(data.get("gates", [])), "evaluation.json gates[] length")
        add(data.get("short_circuited_at") is not None, "evaluation.json short_circuited_at")

    # The trap ledger: numbers that are established facts about what we got
    # wrong, verified by the audit rather than by a run.
    ledger = REPO / "notes" / "KNOWN-TRAPS.md"
    if ledger.exists():
        body = ledger.read_text(encoding="utf-8")
        for m in re.finditer(r"(?<![\w.])([-+]?\d[\d,]*(?:\.\d+)?)", body):
            raw = m.group(1).replace(",", "")
            for key in {f"{float(raw):.0f}", f"{float(raw):.1f}",
                        f"{float(raw):.2f}", f"{float(raw):.3f}"}:
                known.setdefault(key, []).append("notes/KNOWN-TRAPS.md")

    for path in sorted((REPO / "docs").glob("*.md")):
        body = path.read_text(encoding="utf-8")
        for m in re.finditer(r"(?<![\w.])([-+]?\d[\d,]*(?:\.\d+)?)", body):
            raw = m.group(1).replace(",", "")
            for key in {f"{float(raw):.0f}", f"{float(raw):.1f}",
                        f"{float(raw):.2f}", f"{float(raw):.3f}"}:
                known.setdefault(key, []).append(f"docs/{path.name}")

    return known


def harvest_lab(lab: Path) -> tuple[dict[str, list[str]], list[str]]:
    """Every number the lab produces, with where it came from.

    Returns the known numbers and the list of paths that were read, so the
    script can say what it looked at.
    """
    known: dict[str, list[str]] = {}
    read: list[str] = []

    def add(value, source):
        for key in _keys_for(value):
            known.setdefault(key, []).append(source)

    for path in sorted((lab / "outputs").glob("sweep_*.json")):
        read.append(str(path))
        data = json.loads(path.read_text(encoding="utf-8"))
        universe = data.get("universe", path.stem)
        add(data.get("n_trials"), f"{path.name} n_trials")
        gate = data.get("gate") or {}
        add(len(gate.get("checks", [])), f"{path.name} gate.checks length")
        add(len(gate.get("failed_checks", [])), f"{path.name} gate.failed_checks length")
        for key, value in (data.get("best_metrics") or {}).items():
            add(value, f"{path.name} best_metrics.{key}")
        pbo = data.get("pbo") or {}
        add(pbo.get("pbo"), f"{path.name} pbo.pbo")
        add(pbo.get("n_configs"), f"{path.name} pbo.n_configs")
        add(pbo.get("n_observations"), f"{path.name} pbo.n_observations")
        dsr = data.get("dsr") or {}
        add(dsr.get("dsr"), f"{path.name} dsr.dsr")
        add(dsr.get("observed_sharpe"), f"{path.name} dsr.observed_sharpe")
        add(dsr.get("n_trials"), f"{path.name} dsr.n_trials")
        add(data.get("zero_hedge_ratio"), f"{path.name} zero_hedge_ratio")
        add(data.get("action_ratio"), f"{path.name} action_ratio")
        add(data.get("veto_ratio"), f"{path.name} veto_ratio")
        add(universe, f"{path.name} universe")

    for name in ("notes/KNOWN-TRAPS.md", "docs/LITERATURE.md"):
        path = lab / name
        if not path.exists():
            continue
        read.append(str(path))
        body = path.read_text(encoding="utf-8")
        # Markdown wraps lines, so a phrase can be split across a newline.
        # Numbers are compared after collapsing whitespace.
        flat = re.sub(r"\s+", " ", body)
        for m in re.finditer(r"(?<![\w.])([-+]?\d[\d,]*(?:\.\d+)?)", flat):
            raw = m.group(1).replace(",", "")
            try:
                f = float(raw)
            except ValueError:
                continue
            for key in {f"{f:.0f}", f"{f:.1f}", f"{f:.2f}", f"{f:.3f}"}:
                known.setdefault(key, []).append(f"lab {name}")

    return known, read


def collect_test_count() -> tuple[int | None, str]:
    """How many tests does pytest collect?

    Tries the running interpreter first, then `python` on PATH. On this
    machine the Hermes toolchain's Python 3.14 is on PATH without pytest
    installed, so assuming `sys.executable` is the project interpreter is
    not safe -- and silently returning "0" would be worse than returning
    None.
    """
    for exe in (sys.executable, "python"):
        try:
            proc = subprocess.run(
                [exe, "-m", "pytest", "tests/", "--collect-only", "-q"],
                cwd=REPO, capture_output=True, text=True, timeout=300,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        m = re.search(r"(\d+)\s+tests collected", proc.stdout)
        if m:
            return int(m.group(1)), exe
        total = 0
        for line in proc.stdout.splitlines():
            fm = re.match(r"^tests/[^:]+\.py:\s*(\d+)\s*$", line.strip())
            if fm:
                total += int(fm.group(1))
        if total:
            return total, exe
    return None, "none"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit the X thread against the repositories.")
    parser.add_argument("--file", default=str(DEFAULT_THREAD),
                        help="thread file to audit")
    parser.add_argument("--lab-repo", default=None,
                        help="path to the lab repository (the other half of "
                             "the thread's numbers)")
    parser.add_argument("--strict", action="store_true",
                        help="treat an unmatched number as a failure")
    args = parser.parse_args(argv)

    thread_path = Path(args.file)
    if not thread_path.is_absolute():
        thread_path = REPO / args.file
    if not thread_path.exists():
        print(f"no thread at {thread_path}")
        return 1

    text = thread_path.read_text(encoding="utf-8")
    tweets = read_tweets(text)
    problems: list[str] = []
    warnings: list[str] = []

    print(f"auditing {thread_path.name}: {len(tweets)} tweets\n")

    # ---- T1 length ----
    print("T1  tweet length")
    for heading, body in tweets:
        length = len(body.strip())
        if length > 280:
            problems.append(f"{heading}: {length} characters (limit 280)")
            print(f"  OVER {length:4d}  {heading}")
        else:
            print(f"  ok   {length:4d}  {heading}")
    print()

    # ---- T2 numbers ----
    print("T2  numeric claims")
    known = harvest_desk()
    lab = find_lab_repo(args.lab_repo)
    lab_read: list[str] = []
    if lab is not None:
        lab_known, lab_read = harvest_lab(lab)
        for key, sources in lab_known.items():
            known.setdefault(key, []).extend(sources)
        print(f"  lab repository: {lab}")
        for p in lab_read:
            print(f"    read {p}")
    else:
        print("  lab repository: NOT FOUND")
        warnings.append(
            "the lab repository was not found, so the lab's numbers could "
            "not be verified. Pass --lab-repo or set HEDGE_LAB_REPO."
        )

    collected, used = collect_test_count()
    if collected is not None:
        known.setdefault(str(collected), []).append("pytest --collect-only")

    tokens = set()
    for heading, body in tweets:
        # A URL's digits are an identifier, not a claim: the audited post's
        # status id is a 19-digit number. Strip URLs before looking for
        # numbers, so an id is never screened as an unsourced figure.
        scrubbed = re.sub(r"https?://\S+", " ", _norm(body))
        for m in re.finditer(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s*(%|bps)?", scrubbed):
            tokens.add((m.group(1).replace(",", ""), m.group(2)))

    unmatched = []
    for raw, unit in sorted(tokens, key=lambda t: float(t[0])):
        if raw in QUOTED_FROM_THE_AUDITED_POST:
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        candidates = set(_keys_for(value))
        if unit == "%":
            candidates |= {f"{abs(value):.0f}", f"{abs(value):.1f}",
                           f"{abs(value):.2f}"}
        if not (candidates & set(known)):
            unmatched.append((raw, unit))
    print(f"  screened {len(tokens)} numeric token(s) against the desk's "
          f"report and ledgers"
          + (", and the lab's outputs and ledgers" if lab else ""))
    for raw, unit in unmatched:
        warnings.append(f"no source found for {raw}{unit or ''}")
        print(f"  REVIEW  {raw}{unit or ''}")
    if not unmatched:
        print("  PASS  every number matched a source")
    for raw, why in QUOTED_FROM_THE_AUDITED_POST.items():
        if raw in {t[0] for t in tokens}:
            print(f"  NOTE  {raw} is quoted from the audited post, not claimed "
                  f"by us ({why})")
    print()

    # ---- T3 the quoted numbers are attributed ----
    print("T3  the audited post's numbers are attributed")
    all_tweets = "\n".join(b for _, b in tweets).lower()
    quoted_markers = ["his numbers, not ours", "not ours", "quoted"]
    if not any(m in all_tweets for m in quoted_markers):
        problems.append(
            "the thread quotes figures from the audited post but never "
            "attributes them to it"
        )
        print("  FAIL  the quoted numbers are not attributed to the post")
    else:
        print("  PASS  the quoted numbers are attributed to the post")
    if AUDITED_POST_URL.lower() not in all_tweets:
        warnings.append("the thread does not link the post it audits")
        print("  REVIEW  the audited post is not linked")
    else:
        print("  PASS  the audited post is linked")
    print()

    # ---- T4 style ----
    print("T4  style")
    style_problems = []
    for heading, body in tweets:
        for ch in body:
            code = ord(ch)
            if any(lo <= code <= hi for lo, hi in EMOJI_RANGES):
                style_problems.append(f"{heading}: emoji {ch!r} (U+{code:04X})")
        if "#" in body:
            style_problems.append(f"{heading}: contains a hashtag")
        if "—" in body:
            style_problems.append(f"{heading}: contains an em-dash")
        lowered = body.lower()
        for bait in ENGAGEMENT_BAIT:
            if bait in lowered:
                style_problems.append(f"{heading}: engagement bait {bait!r}")
    if style_problems:
        problems.extend(style_problems)
        for p in style_problems:
            print(f"  FAIL  {p}")
    else:
        print("  PASS  no emoji, no hashtags, no em-dashes, no engagement bait")
    print()

    # ---- T5 forbidden claims (the TWEETS only, not the notes) ----
    print("T5  forbidden claims")
    hits = []
    for heading, body in tweets:
        lowered = body.lower()
        for phrase in FORBIDDEN_PHRASES:
            if phrase in lowered:
                hits.append(f"{heading}: {phrase!r}")
    if hits:
        problems.extend(hits)
        for h in hits:
            print(f"  FAIL  {h}")
    else:
        print("  PASS  no live-trading or predictive-edge claim in the tweets")
    print()

    # ---- T6 the honest result is present ----
    print("T6  the result is reported honestly")
    checks = [
        ("the lab's rejection is reported",
         "reject" in all_tweets),
        ("the desk's failing gate is reported",
         "second" in all_tweets and "gate" in all_tweets),
        ("our own defects are reported",
         "0.596" in all_tweets and "0.420" in all_tweets),
        ("the trial count is given", "48" in all_tweets),
        ("the sample size is given",
         "days" in all_tweets or "trades" in all_tweets),
        ("the post's own numbers are attributed",
         "not ours" in all_tweets),
    ]
    for name, ok in checks:
        if ok:
            print(f"  PASS  {name}")
        else:
            problems.append(f"the thread does not disclose {name}")
            print(f"  FAIL  the thread does not disclose {name}")
    print()

    # ---- T7 links ----
    print("T7  links")
    link_checks = [
        ("the lab is linked", LAB_REPO_URL.lower() in all_tweets),
        ("the desk is linked", DESK_REPO_URL.lower() in all_tweets),
        ("the video is linked", VIDEO_URL.lower() in all_tweets),
    ]
    for name, ok in link_checks:
        if ok:
            print(f"  PASS  {name}")
        else:
            problems.append(f"the thread does not satisfy: {name}")
            print(f"  FAIL  {name}")
    video_count = all_tweets.count(VIDEO_URL.lower())
    if video_count > 1:
        problems.append(f"the video is linked {video_count} times, once is enough")
        print(f"  FAIL  the video is linked {video_count} times")
    elif video_count == 1:
        print("  PASS  the video is linked exactly once")
    print()

    # ---- T8 it is a starting point ----
    print("T8  the thread says it is a starting point")
    starting_checks = [
        ("it names the continuation", "further" in all_tweets),
        ("it says the seams are named", "seam" in all_tweets),
        ("it says the repos are free and MIT",
         "mit" in all_tweets and "free" in all_tweets),
    ]
    for name, ok in starting_checks:
        if ok:
            print(f"  PASS  {name}")
        else:
            problems.append(f"the thread does not disclose: {name}")
            print(f"  FAIL  the thread does not disclose: {name}")
    print()

    print("=" * 70)
    for p in problems:
        print(f"PROBLEM  {p}")
    for w in warnings:
        print(f"WARNING  {w}")
    verdict = (f"{len(problems)} problem(s), {len(warnings)} warning(s), "
               f"{len(tweets)} tweets")
    print(f"RESULT: {verdict}")
    if problems or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
