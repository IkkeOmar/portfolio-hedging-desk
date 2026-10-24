"""Loading things for the dashboard.

Everything the dashboard shows comes from a file the repository writes, or
from a run the user asks for. Nothing is computed here that the desk does
not already compute.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def report_path() -> Path:
    return REPO_ROOT / "reports" / "evaluation.json"


def markdown_path() -> Path:
    return REPO_ROOT / "reports" / "evaluation.md"


def equity_path() -> Path:
    return REPO_ROOT / "reports" / "equity.csv"


def load_report(path: Path | None = None) -> dict[str, Any] | None:
    path = path or report_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def load_equity(path: Path | None = None):
    """The daily equity series, as a DataFrame with parsed dates."""
    import pandas as pd

    path = path or equity_path()
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


# ------------------------------------------------------------------ running
def run_backtest(config: str, journal: str, out: str, timeout_s: int = 900) -> tuple[bool, str]:
    """Run the backtest. Returns (ok, message).

    The exit code is 1 when a gate fails, which is the honest result and
    not an error, so it is not treated as a failure here.
    """
    command = [
        sys.executable, "scripts/backtest.py",
        "--config", config,
        "--journal", journal,
        "--out", out,
    ]
    try:
        proc = subprocess.run(command, cwd=str(REPO_ROOT), capture_output=True,
                              text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return False, f"The backtest took longer than {timeout_s}s and was stopped."
    except OSError as exc:
        return False, f"Could not start the backtest: {exc}"

    tail = (proc.stdout or "").strip().splitlines()
    summary = ""
    for line in tail:
        if "walk-forward backtest" in line:
            summary = line.strip()
            break
    if proc.returncode not in (0, 1):
        return False, (proc.stderr or proc.stdout or "the backtest failed")[-800:]
    return True, summary or "done"


def run_desk_day(config: str, date: str, journal: str, judge: Any = None) -> dict[str, Any]:
    """Run one trading day and return what each seat said.

    The journal is the output, because the journal is the point: every
    decision is written down before the outcome is known.
    """
    sys.path.insert(0, str(REPO_ROOT))
    from src.config import DeskConfig
    from src.data import load_panel
    from src.desk import Desk
    from src.ledger.journal import Journal

    cfg = DeskConfig.from_yaml(str(REPO_ROOT / config) if not Path(config).is_absolute() else config)
    panel = load_panel(source=cfg.data.source, symbols=cfg.all_symbols,
                       seed=cfg.data.seed, path=cfg.data.path)
    journal_root = Path(journal)
    if not journal_root.is_absolute():
        journal_root = REPO_ROOT / journal_root
    desk = Desk(config=cfg, journal=Journal(journal_root), judge=judge)
    result = desk.run_day(date=date, panel=panel)
    return {
        "result": result,
        "decisions": Journal(journal_root).decisions(),
        "proposals": Journal(journal_root).proposals(),
        "verdicts": Journal(journal_root).verdicts(),
        "intents": Journal(journal_root).intents(),
        "fills": Journal(journal_root).fills(),
    }


def available_dates(limit: int = 400) -> list[str]:
    """Trading days the desk can be run on, most recent first."""
    sys.path.insert(0, str(REPO_ROOT))
    from src.config import DeskConfig
    from src.data import load_panel

    cfg = DeskConfig.from_yaml(REPO_ROOT / "examples" / "holdings.example.yaml")
    panel = load_panel(source=cfg.data.source, symbols=cfg.all_symbols,
                       seed=cfg.data.seed, path=cfg.data.path)
    dates = [str(d.date()) for d in panel.index]
    return list(reversed(dates[-limit:]))
