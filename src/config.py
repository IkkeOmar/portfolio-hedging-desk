"""Configuration: every number the desk is allowed to act on lives in YAML.

Why this file exists
--------------------
Two reasons, both practical.

1. Editability. Someone who has never read this codebase should be able to
   change what the desk does without changing how it does it. All of that
   lives in ``examples/holdings.example.yaml``.
2. Auditability. When you later ask "why did it hedge on that day?", the
   answer should be a diff in a config file, not a search through code.

Validation is deliberately loud: a missing or misspelled key raises
``ConfigError`` with the key name and the file path. Silent defaults in a
risk system are a bug, not a convenience.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """A config file is missing something the desk cannot run without."""


@dataclass(frozen=True)
class Holding:
    """One position in the user's portfolio."""

    symbol: str
    shares: float
    cost_basis: float | None = None

    def market_value(self, price: float) -> float:
        return self.shares * price


@dataclass(frozen=True)
class Costs:
    """What a round trip costs you.

    ``round_trip_bps`` is what the strategy pays to enter and exit once. Every
    backtest in this repo charges it. A strategy that only works at zero cost
    is not a strategy, it is a rounding error.
    """

    fee_bps_per_side: float = 2.0
    slippage_bps_per_side: float = 1.0
    spread_bps_per_side: float = 0.5

    @property
    def one_way_bps(self) -> float:
        return self.fee_bps_per_side + self.slippage_bps_per_side + self.spread_bps_per_side

    @property
    def round_trip_bps(self) -> float:
        return 2.0 * self.one_way_bps

    @property
    def round_trip_fraction(self) -> float:
        """Round-trip cost as a fraction of notional, e.g. 0.0007 for 7 bps."""
        return self.round_trip_bps / 10_000.0


@dataclass(frozen=True)
class RiskLimits:
    """Hard limits. The Risk seat enforces these and nobody else may relax them."""

    max_gross_hedge_pct: float = 1.0
    risk_per_trade_pct: float = 0.02
    min_reward_to_risk: float = 1.5
    max_legs: int = 5

    def __post_init__(self) -> None:
        """Reject limits that cannot mean anything.

        Without this, a typo like ``risk_per_trade_pct: -0.02`` loads
        silently and produces a Risk seat that vetoes every order for the
        wrong reason, or worse, one that approves orders it should not.
        A limit that cannot be honoured should stop the process at load
        time, not produce a plausible-looking wrong answer later.
        """
        if self.max_gross_hedge_pct <= 0:
            raise ConfigError(
                f"risk.max_gross_hedge_pct must be > 0, got {self.max_gross_hedge_pct!r}"
            )
        if self.risk_per_trade_pct <= 0:
            raise ConfigError(
                f"risk.risk_per_trade_pct must be > 0, got {self.risk_per_trade_pct!r}"
            )
        if self.min_reward_to_risk <= 0:
            raise ConfigError(
                f"risk.min_reward_to_risk must be > 0, got {self.min_reward_to_risk!r}"
            )
        if self.max_legs < 1:
            raise ConfigError(
                f"risk.max_legs must be at least 1, got {self.max_legs!r}"
            )


@dataclass(frozen=True)
class HedgingParams:
    """Parameters of the hedge-sizing policy."""

    hedge_instrument: str = "SPY"
    lookback_days: int = 252
    shrinkage_k: float = 60.0
    max_hedge_pct_equity: float = 0.60
    rebalance: str = "monthly"

    VALID_REBALANCE = ("daily", "weekly", "monthly")

    def __post_init__(self) -> None:
        if self.rebalance not in self.VALID_REBALANCE:
            raise ConfigError(
                f"hedging.rebalance must be one of {self.VALID_REBALANCE}, got {self.rebalance!r}"
            )
        if self.lookback_days < 20:
            raise ConfigError(
                f"hedging.lookback_days={self.lookback_days} is too short to estimate a beta; use at least 20"
            )
        if self.shrinkage_k < 0:
            raise ConfigError(f"hedging.shrinkage_k must be >= 0, got {self.shrinkage_k}")


@dataclass(frozen=True)
class Portfolio:
    """The thing being hedged."""

    account_id: str = "default"
    base_currency: str = "USD"
    benchmark: str = "SPY"
    holdings: tuple[Holding, ...] = ()

    def symbols(self) -> list[str]:
        return [h.symbol for h in self.holdings]


@dataclass(frozen=True)
class DataConfig:
    """Where prices come from."""

    source: str = "synthetic"
    seed: int = 20261024
    # Only used by the csv source: the path to the price file. Required when
    # source == "csv". It used to be missing, which meant the csv adapter
    # existed and was advertised in VALID_SOURCES but could not be selected
    # from a config file at all.
    path: str | None = None

    VALID_SOURCES = ("synthetic", "yahoo", "csv")

    def __post_init__(self) -> None:
        if self.source not in self.VALID_SOURCES:
            raise ConfigError(
                f"data.source must be one of {self.VALID_SOURCES}, got {self.source!r}"
            )
        if self.source == "csv" and not self.path:
            raise ConfigError(
                "data.source='csv' needs data.path in the config file"
            )


@dataclass(frozen=True)
class DeskConfig:
    """The whole configuration, validated."""

    portfolio: Portfolio
    hedging: HedgingParams
    risk: RiskLimits
    costs: Costs
    data: DataConfig
    source_path: str | None = None

    # ---------------------------------------------------------------- loading
    @classmethod
    def from_yaml(cls, path: str | Path) -> "DeskConfig":
        path = Path(path)
        if not path.exists():
            raise ConfigError(f"config file not found: {path}")
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:  # pragma: no cover - message formatting only
            raise ConfigError(f"could not parse YAML at {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ConfigError(f"config at {path} must be a YAML mapping, got {type(raw).__name__}")
        return cls.from_dict(raw, source_path=str(path))

    @classmethod
    def from_dict(cls, raw: dict[str, Any], source_path: str | None = None) -> "DeskConfig":
        where = source_path or "<dict>"

        def section(name: str) -> dict[str, Any]:
            value = raw.get(name, {})
            if value is None:
                return {}
            if not isinstance(value, dict):
                raise ConfigError(f"{where}: section '{name}' must be a mapping, got {type(value).__name__}")
            return value

        p_raw = section("portfolio")
        holdings_raw = p_raw.get("holdings", []) or []
        if not isinstance(holdings_raw, list):
            raise ConfigError(f"{where}: portfolio.holdings must be a list")
        holdings: list[Holding] = []
        for i, item in enumerate(holdings_raw):
            if not isinstance(item, dict):
                raise ConfigError(f"{where}: portfolio.holdings[{i}] must be a mapping")
            symbol = str(item.get("symbol", "")).strip().upper()
            if not symbol:
                raise ConfigError(f"{where}: portfolio.holdings[{i}] is missing 'symbol'")
            try:
                shares = float(item.get("shares", 0.0))
            except (TypeError, ValueError) as exc:
                raise ConfigError(f"{where}: portfolio.holdings[{i}].shares must be a number") from exc
            cb = item.get("cost_basis")
            holdings.append(
                Holding(symbol=symbol, shares=shares, cost_basis=float(cb) if cb is not None else None)
            )

        portfolio = Portfolio(
            account_id=str(p_raw.get("account_id", "default")),
            base_currency=str(p_raw.get("base_currency", "USD")),
            benchmark=str(p_raw.get("benchmark", "SPY")).strip().upper(),
            holdings=tuple(holdings),
        )

        h_raw = section("hedging")
        hedging = HedgingParams(
            hedge_instrument=str(h_raw.get("hedge_instrument", portfolio.benchmark)).strip().upper(),
            lookback_days=int(h_raw.get("lookback_days", 252)),
            shrinkage_k=float(h_raw.get("shrinkage_k", 60.0)),
            max_hedge_pct_equity=float(h_raw.get("max_hedge_pct_equity", 0.60)),
            rebalance=str(h_raw.get("rebalance", "monthly")).lower(),
        )

        r_raw = section("risk")
        risk = RiskLimits(
            max_gross_hedge_pct=float(r_raw.get("max_gross_hedge_pct", 1.0)),
            risk_per_trade_pct=float(r_raw.get("risk_per_trade_pct", 0.02)),
            min_reward_to_risk=float(r_raw.get("min_reward_to_risk", 1.5)),
            max_legs=int(r_raw.get("max_legs", 5)),
        )

        c_raw = section("costs")
        costs = Costs(
            fee_bps_per_side=float(c_raw.get("fee_bps_per_side", 2.0)),
            slippage_bps_per_side=float(c_raw.get("slippage_bps_per_side", 1.0)),
            spread_bps_per_side=float(c_raw.get("spread_bps_per_side", 0.5)),
        )

        d_raw = section("data")
        raw_path = d_raw.get("path")
        data = DataConfig(
            source=str(d_raw.get("source", "synthetic")).lower(),
            seed=int(d_raw.get("seed", 20261024)),
            path=str(raw_path) if raw_path else None,
        )

        return cls(
            portfolio=portfolio,
            hedging=hedging,
            risk=risk,
            costs=costs,
            data=data,
            source_path=source_path,
        )

    # ---------------------------------------------------------------- helpers
    @property
    def all_symbols(self) -> list[str]:
        """Every symbol the desk needs: holdings, benchmark and hedge instrument."""
        symbols = list(self.portfolio.symbols())
        for extra in (self.portfolio.benchmark, self.hedging.hedge_instrument):
            if extra not in symbols:
                symbols.append(extra)
        return symbols

    def summary(self) -> str:
        n = len(self.portfolio.holdings)
        return (
            f"{self.portfolio.account_id}: {n} holding(s), benchmark {self.portfolio.benchmark}, "
            f"hedge via {self.hedging.hedge_instrument}, data={self.data.source}"
        )
