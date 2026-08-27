# -*- coding: utf-8 -*-
"""Small, explicit transaction-cost models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd


@dataclass(frozen=True)
class LinearCostModel:
    """Charge separate proportional rates on bought and sold portfolio weight."""

    buy_rate: float = 0.0
    sell_rate: float = 0.0
    model_id: str = "linear"

    def __post_init__(self) -> None:
        if self.buy_rate < 0 or self.sell_rate < 0:
            raise ValueError("cost rates must be non-negative")

    def calculate(self, weight_changes: pd.DataFrame) -> pd.Series:
        buys = weight_changes.clip(lower=0).sum(axis=1)
        sells = -weight_changes.clip(upper=0).sum(axis=1)
        return (buys * self.buy_rate + sells * self.sell_rate).rename("cost")

    @classmethod
    def from_runtime_config(cls, config: Mapping[str, Any]) -> "LinearCostModel":
        if not config.get("enabled", False):
            return cls(model_id="disabled")
        asset_class = str(config.get("asset_class", "etf"))
        asset = config.get(asset_class, {})
        commission = float(asset.get("commission_rate", 0.0))
        stamp = float(asset.get("stamp_duty", 0.0))
        slippage = float(config.get("slippage", {}).get("fixed_bp", 0.0)) / 10_000.0
        return cls(
            buy_rate=commission + slippage,
            sell_rate=commission + stamp + slippage,
            model_id=f"linear_{asset_class}",
        )

