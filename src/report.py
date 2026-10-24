"""Write the evaluation report: JSON for machines, Markdown for humans.

Both are always written, even when a gate short-circuits. A report that only
exists on success is a report that hides its own failures.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .evaluation.gates import GateResult


def write_json_report(path: str | Path, payload: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def write_equity_csv(path: str | Path, result: Any) -> Path:
    """Write the daily equity and drawdown series as CSV.

    The JSON report holds the headline numbers; this holds the *path* behind
    them, one row per trading day, so a chart can be drawn without re-running
    the backtest.

    The drawdown column is computed from the equity curve with the same
    definition ``src.evaluation.metrics.max_drawdown`` uses, so the worst
    value in this file is the same number the report quotes.
    """
    import pandas as pd

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    dates = pd.DatetimeIndex(result.dates)
    hedged = pd.Series(result.equity).reindex(dates)
    unhedged = pd.Series(result.equity_unhedged).reindex(dates)

    def _dd(series: pd.Series) -> pd.Series:
        return series / series.cummax() - 1.0

    # Rounded to 10 significant decimals. The full repr of a float is 17
    # digits, which triples the file size and tells a reader nothing: the
    # numbers come from a synthetic fixture, not from a measurement that
    # needs 17 digits.
    frame = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "hedged_equity": hedged.round(10).to_numpy(),
        "unhedged_equity": unhedged.round(10).to_numpy(),
        "hedged_drawdown": _dd(hedged).round(10).to_numpy(),
        "unhedged_drawdown": _dd(unhedged).round(10).to_numpy(),
    })
    for name, attr in (("dial", "dial"), ("forward_vol", "forward_vol"),
                       ("r_squared", "r_squared_series")):
        series = getattr(result, attr, None)
        if series is None:
            continue
        frame[name] = pd.Series(series).reindex(dates).to_numpy()
    regimes = getattr(result, "regimes", None)
    if regimes is not None:
        frame["regime"] = pd.Series(regimes).reindex(dates).astype(str).to_numpy()

    frame.to_csv(path, index=False)
    return path


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        if value != value:  # NaN
            return "n/a"
        return f"{value:.{digits}f}"
    return str(value)


def render_markdown(payload: dict[str, Any]) -> str:
    """Turn the report payload into readable Markdown."""
    lines: list[str] = []
    lines.append("# Evaluation report")
    lines.append("")
    lines.append(f"**Verdict: {payload.get('verdict', 'unknown').upper()}**")
    if payload.get("short_circuited_at"):
        lines.append("")
        lines.append(f"> Short-circuited at gate {payload['short_circuited_at']}. "
                     "Later gates were not evaluated, on purpose: a strategy that fails "
                     "an earlier gate does not need to be tested on the later ones.")
    lines.append("")

    summary = payload.get("summary", {})
    if summary:
        lines.append("## Headline numbers")
        lines.append("")
        lines.append("| Quantity | Value |")
        lines.append("|---|---|")
        for key, value in summary.items():
            if isinstance(value, float):
                lines.append(f"| {key} | {_fmt(value)} |")
            elif isinstance(value, (int, str)):
                lines.append(f"| {key} | {value} |")
        lines.append("")

    gates = payload.get("gates", [])
    if gates:
        lines.append("## The four gates")
        lines.append("")
        for gate in gates:
            mark = "PASS" if gate["passed"] else "FAIL"
            lines.append(f"### Gate {gate['name']} — {mark}")
            lines.append("")
            lines.append(f"*{gate['headline']}*")
            lines.append("")
            metrics = gate.get("metrics") or {}
            if metrics:
                lines.append("| Metric | Value |")
                lines.append("|---|---|")
                for key, value in metrics.items():
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value, default=str)
                    lines.append(f"| {key} | {_fmt(value)} |")
                lines.append("")
            for note in gate.get("notes", []):
                lines.append(f"- {note}")
            lines.append("")

    vetoes = payload.get("vetoes", [])
    if vetoes:
        lines.append("## What the Risk seat refused")
        lines.append("")
        lines.append(
            "The Risk seat is the only seat that can approve an order, and it "
            "declines more often than it approves. A desk that never vetoes is "
            "not managing risk, it is trading."
        )
        lines.append("")
        lines.append("| Date | Stage | Reason |")
        lines.append("|---|---|---|")
        for veto in vetoes[:60]:
            lines.append(f"| {veto.get('date', '')} | {veto.get('stage', '')} | {veto.get('reason', '')} |")
        if len(vetoes) > 60:
            lines.append(f"| ... | | {len(vetoes) - 60} more |")
        lines.append("")

    seat_errors = payload.get("seat_errors", [])
    signal_errors = payload.get("signal_errors", [])
    if seat_errors or signal_errors:
        lines.append("## Errors")
        lines.append("")
        lines.append(
            "A seat that raises is recorded here rather than swallowed. A desk that "
            "fails quietly looks exactly like a desk that has nothing to do."
        )
        lines.append("")
        if seat_errors:
            lines.append(f"**{len(seat_errors)} seat errors** (a seat raised during a decision):")
            lines.append("")
            lines.append("| Date | Reason |")
            lines.append("|---|---|")
            for err in seat_errors[:30]:
                lines.append(f"| {err.get('date', '')} | {err.get('reason', '')} |")
            lines.append("")
        if signal_errors:
            lines.append(f"**{len(signal_errors)} signal errors**:")
            lines.append("")
            for err in signal_errors[:30]:
                lines.append(f"- {err.get('date', '')}: {err.get('reason', '')}")
            lines.append("")

    trades = payload.get("trades", [])
    if trades:
        lines.append("## Trades")
        lines.append("")
        lines.append("| Date | Symbol | Side | Notional | Cost |")
        lines.append("|---|---|---|---|---|")
        for t in trades:
            lines.append(
                f"| {t.get('date')} | {t.get('symbol')} | {t.get('side')} | "
                f"{float(t.get('notional', 0)):,.0f} | {float(t.get('cost', 0)):,.2f} |"
            )
        lines.append("")

    lines.append("## How to read this")
    lines.append("")
    lines.append(
        "This is a HEDGING desk, so read the gates in the hedging sense, not the "
        "trading sense."
    )
    lines.append("")
    lines.append("- **A hedge is a trade in risk, not a trade in profit.** Its job is to "
                 "reduce the dispersion of outcomes. A hedge that does not lower "
                 "volatility is a cost with no benefit.")
    lines.append("- **Gate 1 (hedgeability, R^2) is the first gate and the most "
                 "important.** If the hedge instrument explains less than 25% of the "
                 "portfolio's variance, no overlay can be worth its cost. This threshold "
                 "is Healy and Lo (2010), condition (B).")
    lines.append("- **Gate 2 asks about volatility, not returns.** The dial is supposed to "
                 "anticipate future volatility. A return-correlation gate would be "
                 "structurally wrong: a perfect hedge has zero forward-return "
                 "correlation by construction, so it would reject the best possible hedge.")
    lines.append("- **A Sharpe ratio here is the real one:** mean excess return over "
                 "standard deviation, annualised. It is not CAGR divided by volatility. "
                 "Those differ, and the difference is the whole point of checking.")
    lines.append("- **Every backtest in this repo charges the configured transaction "
                 "costs on every trade.**")
    lines.append("- **The walk-forward windows are consecutive out-of-sample slices.** "
                 "A strategy that only works in one of them has learned the sample.")
    lines.append("- **The gates short-circuit on purpose.** A hedge that fails gate 1 "
                 "does not need to be tested on gate 3, and pretending otherwise "
                 "manufactures evidence.")
    lines.append("- **This data is synthetic.** It is a test fixture for the machinery, "
                 "not evidence about real markets. No claim about real markets is "
                 "made anywhere in this repository.")
    lines.append("")
    return "\n".join(lines)


def write_markdown_report(path: str | Path, payload: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(payload), encoding="utf-8")
    return path
