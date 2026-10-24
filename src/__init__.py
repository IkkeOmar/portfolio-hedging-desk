"""portfolio-hedging-desk.

A small, readable implementation of a portfolio hedging desk.

The package is organised as six slots so that any part can be replaced
without touching the rest:

    src/data/        market data adapters (one file per source)
    src/ledger/      the journal schema and the append-only writer
    src/policy/      the seats: what each one decides and why
    src/execution/   how an approved order becomes a fill
    src/evaluation/  the four gates a strategy has to pass
    src/desk.py      the run entry point that wires it together

Import convention: project root on sys.path, then ``from src.data import ...``.
"""

__version__ = "0.2.0"
