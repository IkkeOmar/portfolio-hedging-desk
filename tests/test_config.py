"""Configuration validation, and the promise the docs make about libraries.

Three things are checked here:

1. `RiskLimits` rejects values that cannot mean anything, at load time.
2. `DataConfig` can actually select the CSV source it advertises — a config
   option that the configuration accepts but the code cannot honour is worse
   than one it rejects.
3. Every library named in `docs/METHODOLOGY.md`'s dependency table is really
   used and really installable.

The third one exists because the methodology table claimed a library was
"used only in tests" when it was not imported anywhere in the repository and
was not in `requirements.txt` either. A reader checking that claim would
have found it false. This test makes the table checkable.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

from src.config import ConfigError, DataConfig, DeskConfig, RiskLimits

REPO = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------- RiskLimits
def test_risk_limits_accepts_the_shipped_values():
    """The example config and the test fixtures must still load."""
    limits = RiskLimits(
        max_gross_hedge_pct=1.0,
        risk_per_trade_pct=0.02,
        min_reward_to_risk=1.5,
        max_legs=5,
    )
    assert limits.max_legs == 5


@pytest.mark.parametrize(
    "field, value",
    [
        ("max_gross_hedge_pct", 0.0),
        ("max_gross_hedge_pct", -1.0),
        ("risk_per_trade_pct", 0.0),
        ("risk_per_trade_pct", -0.02),
        ("min_reward_to_risk", 0.0),
        ("min_reward_to_risk", -1.5),
        ("max_legs", 0),
        ("max_legs", -3),
    ],
)
def test_risk_limits_rejects_values_that_cannot_mean_anything(field, value):
    """A limit that cannot be honoured must fail at load time, not later."""
    kwargs = {
        "max_gross_hedge_pct": 1.0,
        "risk_per_trade_pct": 0.02,
        "min_reward_to_risk": 1.5,
        "max_legs": 5,
    }
    kwargs[field] = value
    with pytest.raises(ConfigError):
        RiskLimits(**kwargs)


# ---------------------------------------------------------------- DataConfig
def test_data_config_rejects_csv_without_a_path():
    """`csv` is advertised, so selecting it must come with the file it needs."""
    with pytest.raises(ConfigError, match="path"):
        DataConfig(source="csv")


def test_data_config_accepts_csv_with_a_path():
    cfg = DataConfig(source="csv", path="prices.csv")
    assert cfg.source == "csv"
    assert cfg.path == "prices.csv"


def test_data_config_still_rejects_an_unknown_source():
    with pytest.raises(ConfigError):
        DataConfig(source="quandl")


def test_csv_source_works_end_to_end_from_a_config_file(tmp_path):
    """The real check: a config file naming the CSV source actually loads it.

    Writing a price file, pointing a config at it, and reading the panel
    back. If the `path` were not threaded through, this would raise.
    """
    import pandas as pd

    dates = pd.bdate_range("2023-01-02", periods=40)
    frame = pd.DataFrame(
        {
            "AAPL": [100.0 + i for i in range(40)],
            "MSFT": [200.0 + i for i in range(40)],
            "NVDA": [50.0 + i for i in range(40)],
            "SPY": [300.0 + i for i in range(40)],
        },
        index=dates,
    )
    frame.index.name = "date"
    csv_path = tmp_path / "prices.csv"
    frame.to_csv(csv_path)

    config_path = tmp_path / "desk.yaml"
    config_path.write_text(
        "portfolio:\n"
        "  account_id: csv-test\n"
        "  benchmark: SPY\n"
        "  holdings:\n"
        "    - symbol: AAPL\n"
        "      shares: 10\n"
        "hedging:\n"
        "  hedge_instrument: SPY\n"
        "  lookback_days: 20\n"
        "data:\n"
        "  source: csv\n"
        f"  path: {csv_path.as_posix()}\n",
        encoding="utf-8",
    )

    config = DeskConfig.from_yaml(config_path)
    assert config.data.source == "csv"
    assert config.data.path == csv_path.as_posix()

    from src.data import load_panel

    panel = load_panel(
        source=config.data.source,
        symbols=config.all_symbols,
        seed=config.data.seed,
        path=config.data.path,
    )
    assert list(panel.columns) == config.all_symbols
    assert len(panel) == 40
    assert panel["AAPL"].iloc[0] == pytest.approx(100.0)


# ----------------------------------------------- the docs' library table
# PyPI name -> import name, where they differ.
_IMPORT_NAMES = {
    "scikit-learn": "sklearn",
    "PyPortfolioOpt": "pypfopt",
}


def _methodology_libraries() -> dict[str, str]:
    """The library column of the dependency table in docs/METHODOLOGY.md.

    Scoped to the table whose header names a "Library" and a "Licence"
    column. METHODOLOGY.md has several other pipe tables -- the gate table
    among them -- and an unscoped parse picks their rows up as if they were
    dependencies.
    """
    text = (REPO / "docs" / "METHODOLOGY.md").read_text(encoding="utf-8")
    lines = text.splitlines()

    start = None
    for i, line in enumerate(lines):
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if len(cells) >= 4 and cells[1].lower() == "library" and cells[2].lower() == "licence":
            start = i + 2  # skip the header and its separator row
            break
    if start is None:
        return {}

    libs: dict[str, str] = {}
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            break
        # the first cell is the statistic, the second the library. Take the
        # FIRST backticked token: a cell may name a class too, as in
        # "[`scikit-learn`](...) `LedoitWolf`", and LedoitWolf is not a
        # package.
        tokens = re.findall(r"`([^`]+)`", cells[1])
        if tokens and re.fullmatch(r"[A-Za-z0-9_.\-]+", tokens[0]):
            libs[tokens[0]] = cells[3]
    return libs


def test_every_library_the_methodology_claims_is_installed_and_importable():
    """The docs' dependency table must be true, or a reader checking it finds a lie.

    This is the check that would have caught the table row claiming
    PyPortfolioOpt was "used only in tests" when it was imported nowhere.
    """
    requirements = (REPO / "requirements.txt").read_text(encoding="utf-8").lower()
    libs = _methodology_libraries()

    assert libs, "no library rows found in the methodology table -- the parse is wrong"

    for name, note in libs.items():
        module = _IMPORT_NAMES.get(name, name)
        assert name.lower() in requirements or module.lower() in requirements, (
            f"docs/METHODOLOGY.md names {name!r} but requirements.txt does not "
            f"include it (note says: {note!r})"
        )
        assert importlib.util.find_spec(module) is not None, (
            f"docs/METHODOLOGY.md names {name!r} but {module!r} is not importable"
        )


def _imported_modules() -> set[str]:
    """Every top-level module imported anywhere in src/ or tests/.

    Derived from the source rather than from a hardcoded list, so a library
    the docs name cannot be missed by forgetting to list it here -- which is
    exactly how "scipy" got missed the first time this check was written.
    """
    imported: set[str] = set()
    for path in list((REPO / "src").rglob("*.py")) + list((REPO / "tests").rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", text, re.M):
            imported.add(m.group(1))
    return imported


def test_every_library_the_methodology_claims_is_actually_used():
    """Named-and-installed is not enough. It has to be imported somewhere."""
    imported = _imported_modules()

    for name in _methodology_libraries():
        module = _IMPORT_NAMES.get(name, name)
        assert module in imported, (
            f"docs/METHODOLOGY.md names {name!r} but nothing in src/ or tests/ "
            f"imports {module!r}"
        )
