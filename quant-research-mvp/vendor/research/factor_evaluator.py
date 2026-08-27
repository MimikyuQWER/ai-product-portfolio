# -*- coding: utf-8 -*-
"""One auditable factor-evaluation protocol with explicit time alignment."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from core.contracts import FactorSpec, SplitConfig
from core.metrics import ic_summary, rank_ic
from research.splits import split_masks


@dataclass(frozen=True)
class FactorEvaluationResult:
    spec: FactorSpec
    split: SplitConfig
    rank_ic: pd.Series
    pearson_ic: pd.Series
    group_returns: pd.DataFrame
    long_short: pd.Series
    turnover: pd.Series
    coverage: pd.Series
    decay_rank_ic: dict[int, pd.Series]
    summary: dict[str, Any]
    yearly: dict[str, dict[str, float | int]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": {
                "name": self.spec.name,
                "frequency": self.spec.frequency,
                "direction": self.spec.direction,
                "lag_periods": self.spec.lag_periods,
                "forward_periods": self.spec.forward_periods,
                "universe_id": self.spec.universe_id,
                "params": dict(self.spec.params),
            },
            "split": self.split.__dict__,
            "summary": self.summary,
            "yearly": self.yearly,
        }


def _validate_frame(frame: pd.DataFrame, name: str) -> None:
    if frame.empty:
        raise ValueError(f"{name} must not be empty")
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError(f"{name} index must be DatetimeIndex")
    if not frame.index.is_monotonic_increasing or frame.index.has_duplicates:
        raise ValueError(f"{name} dates must be monotonic and unique")
    if frame.columns.has_duplicates:
        raise ValueError(f"{name} assets must be unique")
    values = frame.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError(f"{name} contains NaN or Inf")


def _forward_returns(returns: pd.DataFrame, periods: int) -> pd.DataFrame:
    result = 1.0 + returns
    for step in range(1, periods):
        result = result * (1.0 + returns.shift(-step))
    return result - 1.0


def _cross_section_ic(factor: pd.DataFrame, returns: pd.DataFrame, *, pearson: bool) -> pd.Series:
    output: dict[pd.Timestamp, float] = {}
    for date in factor.index.intersection(returns.index):
        x = factor.loc[date].to_numpy(dtype=float)
        y = returns.loc[date].to_numpy(dtype=float)
        if pearson:
            output[date] = float(np.corrcoef(x, y)[0, 1]) if np.std(x) > 0 and np.std(y) > 0 else np.nan
        else:
            output[date] = rank_ic(x, y)
    return pd.Series(output, dtype=float)


def _group_returns(factor: pd.DataFrame, returns: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    rows: dict[pd.Timestamp, dict[str, float]] = {}
    top_members: dict[pd.Timestamp, set[str]] = {}
    for date in factor.index.intersection(returns.index):
        row = factor.loc[date]
        if row.nunique() < 5:
            raise ValueError(f"factor has fewer than five distinct values at {date.date()}")
        # qcut label 4 is the highest factor bucket. Public convention is
        # intentionally inverted here: G1=highest, G5=lowest.
        quantiles = pd.qcut(row.rank(method="first"), 5, labels=False)
        groups = 5 - quantiles
        grouped = returns.loc[date].groupby(groups).mean()
        if len(grouped) != 5:
            raise ValueError(f"one or more factor groups are empty at {date.date()}")
        rows[date] = {f"G{int(group)}": float(value) for group, value in grouped.items()}
        top_members[date] = set(row.index[groups == 1])
    result = pd.DataFrame.from_dict(rows, orient="index").sort_index()
    turnover: dict[pd.Timestamp, float] = {}
    previous: set[str] | None = None
    for date, current in top_members.items():
        turnover[date] = np.nan if previous is None else 1.0 - len(previous & current) / max(len(previous), len(current))
        previous = current
    return result, pd.Series(turnover, dtype=float)


def evaluate_factor(
    values: pd.DataFrame,
    spec: FactorSpec,
    split: SplitConfig,
    *,
    asset_returns: pd.DataFrame,
) -> FactorEvaluationResult:
    """Evaluate a factor after applying its declared lag and direction."""
    spec.validate()
    split.validate()
    _validate_frame(values, "factor values")
    _validate_frame(asset_returns, "asset returns")
    common = values.columns.intersection(asset_returns.columns)
    if len(common) < 5:
        raise ValueError("factor evaluation requires at least five common assets")
    values = values.loc[:, common]
    returns = asset_returns.loc[:, common]
    if (values.nunique(axis=1) < 5).any():
        raise ValueError("factor contains a zero-variance or insufficient-distinct-value cross-section")

    effective = values.shift(spec.lag_periods) * spec.direction
    forward = _forward_returns(returns, spec.forward_periods)
    dates = effective.dropna().index.intersection(forward.dropna().index)
    effective, forward = effective.loc[dates], forward.loc[dates]
    if effective.empty:
        raise ValueError("no observations remain after lag and forward-return alignment")

    rank_series = _cross_section_ic(effective, forward, pearson=False).dropna()
    pearson_series = _cross_section_ic(effective, forward, pearson=True).dropna()
    groups, turnover = _group_returns(effective, forward)
    long_short = (groups["G1"] - groups["G5"]).rename("long_short_G1_G5")
    coverage = pd.Series(1.0, index=effective.index, name="coverage")
    decay = {
        period: _cross_section_ic(effective, _forward_returns(returns, period).loc[effective.index], pearson=False).dropna()
        for period in (1, 2, 3, 6)
    }
    masks = split_masks(rank_series.index, split)
    summary = {
        "full": ic_summary(rank_series),
        "train": ic_summary(rank_series.loc[masks["train"]]),
        "validation": ic_summary(rank_series.loc[masks["validation"]]),
        "pearson_full": ic_summary(pearson_series),
        "long_short_mean": float(long_short.mean()),
        "group_monotonicity": float(groups.mean().corr(pd.Series(range(5, 0, -1), index=groups.columns), method="spearman")),
        "turnover_mean": float(turnover.mean()),
        "coverage_mean": float(coverage.mean()),
    }
    yearly = {str(year): ic_summary(series) for year, series in rank_series.groupby(rank_series.index.year)}
    return FactorEvaluationResult(
        spec, split, rank_series, pearson_series, groups, long_short,
        turnover, coverage, decay, summary, yearly,
    )
