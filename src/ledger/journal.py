"""Append-only journal writer.

Storage format: JSON Lines. One JSON object per line.

Why JSONL and not parquet or sqlite for the write path?

* Append-only is one ``open(..., "a")`` and one ``write``. No rewrite risk.
* A human can read it with ``less``. The point of this repo is that you can
  check what the system did, so the primary artefact has to be inspectable.
* It survives a crash mid-write: you lose at most the last line.

Parquet is used for the *derived* analysis tables (one row per trade, one row
per decision), written by ``export_parquet``. Parquet is a better container
for analytics but a worse container for an audit trail.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


class Journal:
    """Append-only writer for the desk's decisions."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._decisions = self.root / "decisions.jsonl"
        self._proposals = self.root / "proposals.jsonl"
        self._verdicts = self.root / "verdicts.jsonl"
        self._intents = self.root / "order_intents.jsonl"
        self._fills = self.root / "fills.jsonl"
        self._seen_keys: set[str] = set()
        self._load_seen_keys()

    # ------------------------------------------------------------------ paths
    @property
    def decisions_path(self) -> Path:
        return self._decisions

    @property
    def intents_path(self) -> Path:
        return self._intents

    @property
    def fills_path(self) -> Path:
        return self._fills

    # ------------------------------------------------------------------ write
    def _append(self, path: Path, row: dict[str, Any]) -> None:
        line = json.dumps(row, sort_keys=True, default=str) + "\n"
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())

    def write_decision(self, decision) -> bool:
        """Append a seat decision.

        Idempotent: if a decision with the same idempotency key is already in
        the journal, nothing is written and ``False`` is returned. That is the
        entire point of an idempotency key - re-running a day must produce the
        same journal, not a second copy of it.

        Returns True when the row was written.
        """
        key = decision.idempotency_key
        if key in self._seen_keys:
            return False
        self._seen_keys.add(key)
        self._append(self._decisions, decision.to_row())
        return True

    def write_proposal(self, proposal) -> None:
        self._append(self._proposals, proposal.to_row())

    def write_verdict(self, verdict) -> None:
        self._append(self._verdicts, verdict.to_row())

    def write_intent(self, intent) -> None:
        self._append(self._intents, intent.to_row())

    def write_fill(self, fill) -> None:
        self._append(self._fills, fill.to_row())

    def has_decision(self, idempotency_key: str) -> bool:
        return idempotency_key in self._seen_keys

    def _load_seen_keys(self) -> None:
        if not self._decisions.exists():
            return
        with open(self._decisions, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    self._seen_keys.add(json.loads(line)["idempotency_key"])
                except (json.JSONDecodeError, KeyError):
                    continue

    # ------------------------------------------------------------------- read
    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows = []
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows

    def decisions(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self._decisions)

    def proposals(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self._proposals)

    def verdicts(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self._verdicts)

    def intents(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self._intents)

    def fills(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self._fills)

    # ----------------------------------------------------------------- export
    def export_parquet(self, name: str) -> Path:
        """Write one of the journals out as parquet for analysis."""
        mapping = {
            "decisions": self._decisions,
            "proposals": self._proposals,
            "verdicts": self._verdicts,
            "order_intents": self._intents,
            "fills": self._fills,
        }
        if name not in mapping:
            raise KeyError(f"unknown journal {name!r}; expected one of {sorted(mapping)}")
        rows = self._read_jsonl(mapping[name])
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        out = self.root / f"{name}.parquet"
        df.to_parquet(out, index=False)
        return out

    # ------------------------------------------------------------------ misc
    def stats(self) -> dict[str, int]:
        return {
            "decisions": len(self.decisions()),
            "proposals": len(self.proposals()),
            "verdicts": len(self.verdicts()),
            "order_intents": len(self.intents()),
            "fills": len(self.fills()),
        }

    def clear(self) -> None:
        """Delete every journal file. For tests and for a clean demo run."""
        for path in (
            self._decisions,
            self._proposals,
            self._verdicts,
            self._intents,
            self._fills,
        ):
            if path.exists():
                path.unlink()
        self._seen_keys.clear()
