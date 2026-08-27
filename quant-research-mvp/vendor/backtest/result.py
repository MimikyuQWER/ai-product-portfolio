# -*- coding: utf-8 -*-
"""Standard result object returned by the lightweight runner."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from core.contracts import BacktestConfig


@dataclass(frozen=True)
class BacktestResult:
    config: BacktestConfig
    target_weights: pd.DataFrame
    executed_weights: pd.DataFrame
    cash_weights: pd.Series
    turnover: pd.Series
    gross_returns: pd.Series
    costs: pd.Series
    net_returns: pd.Series
    benchmark_returns: pd.Series
    nav: pd.Series
    holdings: pd.DataFrame
    timeline: pd.DataFrame
    metrics: dict[str, Any]

    @property
    def portfolio_value(self) -> pd.Series:
        multiplier = self.config.initial_cash if self.config.initial_cash is not None else 1.0
        return (self.nav * multiplier).rename("portfolio_value")

