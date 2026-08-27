# -*- coding: utf-8 -*-
"""Fixed and walk-forward split helpers."""
from __future__ import annotations

from collections.abc import Iterator

import pandas as pd

from core.contracts import SplitConfig


def split_masks(index: pd.DatetimeIndex, split: SplitConfig) -> dict[str, pd.Series]:
    split.validate()
    dates = pd.DatetimeIndex(index)
    return {
        "train": pd.Series((dates >= pd.Timestamp(split.train_start)) & (dates <= pd.Timestamp(split.train_end)), index=dates),
        "validation": pd.Series((dates >= pd.Timestamp(split.validation_start)) & (dates <= pd.Timestamp(split.validation_end)), index=dates),
    }


def expanding_walk_forward(
    start: str, end: str, *, train_periods: int, validation_periods: int, frequency: str = "ME"
) -> Iterator[SplitConfig]:
    if train_periods < 1 or validation_periods < 1:
        raise ValueError("walk-forward periods must be positive")
    dates = pd.date_range(start, end, freq=frequency)
    cursor = train_periods
    fold = 1
    while cursor + validation_periods <= len(dates):
        yield SplitConfig(
            str(dates[0].date()), str(dates[cursor - 1].date()),
            str(dates[cursor].date()), str(dates[cursor + validation_periods - 1].date()),
            name=f"walk_forward_{fold}", exposure_note="new-strategy walk-forward fold",
        )
        cursor += validation_periods
        fold += 1

