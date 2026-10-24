#!/usr/bin/env python3
"""Run one cycle of the desk.

    python scripts/run_desk.py --config examples/holdings.example.yaml

Prints what each seat decided and where the journal landed. The journal is
the real output; the printout is a convenience.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.desk import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
