# -*- coding: utf-8 -*-
"""Small public contracts shared by research, strategy and backtest layers."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Protocol, runtime_checkable

import pandas as pd


@dataclass(frozen=True)
class SplitConfig:
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    name: str = "default"
    exposure_note: str = "validation data may have been observed during legacy research"

    def validate(self) -> None:
        ts = [pd.Timestamp(x) for x in (
            self.train_start, self.train_end,
            self.validation_start, self.validation_end,
        )]
        if not (ts[0] <= ts[1] < ts[2] <= ts[3]):
            raise ValueError("split dates must satisfy train_start <= train_end < validation_start <= validation_end")


@dataclass(frozen=True)
class FactorSpec:
    name: str
    frequency: Literal["daily", "monthly"]
    direction: Literal[1, -1]
    lag_periods: int
    forward_periods: int
    universe_id: str
    params: Mapping[str, Any] = field(default_factory=dict)
    allow_same_period: bool = False

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("factor name must not be empty")
        if self.direction not in (-1, 1):
            raise ValueError("factor direction must be 1 or -1")
        if self.lag_periods < 0 or (self.lag_periods == 0 and not self.allow_same_period):
            raise ValueError("lag_periods must be >=1 unless allow_same_period is explicit")
        if self.forward_periods < 1:
            raise ValueError("forward_periods must be >=1")
        if not self.universe_id.strip():
            raise ValueError("universe_id must not be empty")


@dataclass(frozen=True)
class BacktestConfig:
    start: str
    end: str
    rebalance_frequency: Literal["daily", "monthly"] = "monthly"
    signal_lag: int = 1
    benchmark_id: str = "equal_weight"
    cost_model_id: str = "default"
    initial_cash: float | None = None
    allow_same_period: bool = False
    allow_short: bool = False
    max_gross_exposure: float = 1.0

    def validate(self) -> None:
        if pd.Timestamp(self.start) > pd.Timestamp(self.end):
            raise ValueError("backtest start must not be after end")
        if self.signal_lag < 0 or (self.signal_lag == 0 and not self.allow_same_period):
            raise ValueError("signal_lag must be >=1 unless allow_same_period is explicit")
        if self.max_gross_exposure <= 0:
            raise ValueError("max_gross_exposure must be positive")
        if self.initial_cash is not None and self.initial_cash <= 0:
            raise ValueError("initial_cash must be positive")


@dataclass
class DataBundle:
    """Inputs frozen conceptually at run start; safe_copy isolates mutations."""

    asset_returns: pd.DataFrame
    prices: pd.DataFrame | None = None
    factors: Mapping[str, pd.DataFrame] = field(default_factory=dict)
    benchmark_returns: pd.Series | None = None
    dataset_manifest: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.asset_returns.empty:
            raise ValueError("asset_returns must not be empty")
        if not self.asset_returns.index.is_monotonic_increasing:
            raise ValueError("asset_returns index must be monotonic")
        if self.asset_returns.index.has_duplicates or self.asset_returns.columns.has_duplicates:
            raise ValueError("asset_returns dates and columns must be unique")

    def safe_copy(self) -> "DataBundle":
        return DataBundle(
            asset_returns=self.asset_returns.copy(deep=True),
            prices=None if self.prices is None else self.prices.copy(deep=True),
            factors={k: v.copy(deep=True) for k, v in self.factors.items()},
            benchmark_returns=None if self.benchmark_returns is None else self.benchmark_returns.copy(deep=True),
            dataset_manifest=deepcopy(dict(self.dataset_manifest)),
        )


@dataclass(frozen=True)
class StrategyContext:
    data: DataBundle
    config: BacktestConfig


@runtime_checkable
class StrategyProtocol(Protocol):
    def generate_target_weights(self, context: StrategyContext) -> pd.DataFrame:
        """Return signal-date target weights, index=date and columns=asset."""
