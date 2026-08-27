# -*- coding: utf-8 -*-
"""A small vectorized runner with explicit signal and execution alignment."""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtest.costs import LinearCostModel
from backtest.result import BacktestResult
from core.contracts import BacktestConfig, DataBundle, StrategyContext, StrategyProtocol
from core.metrics import cal_all_metrics


def _validate_weights(weights: pd.DataFrame, config: BacktestConfig, assets: pd.Index) -> pd.DataFrame:
    if not isinstance(weights, pd.DataFrame) or weights.empty:
        raise ValueError("strategy must return a non-empty target-weights DataFrame")
    if not isinstance(weights.index, pd.DatetimeIndex):
        weights.index = pd.to_datetime(weights.index)
    if not weights.index.is_monotonic_increasing or weights.index.has_duplicates:
        raise ValueError("target-weight dates must be monotonic and unique")
    if weights.columns.has_duplicates:
        raise ValueError("target-weight assets must be unique")
    unknown = weights.columns.difference(assets)
    if len(unknown):
        raise ValueError(f"target weights contain unknown assets: {list(unknown)}")
    if not np.isfinite(weights.to_numpy(dtype=float)).all():
        raise ValueError("target weights contain NaN or Inf")
    if not config.allow_short and (weights < -1e-12).any().any():
        raise ValueError("negative weights require allow_short=True")
    gross = weights.abs().sum(axis=1)
    if (gross > config.max_gross_exposure + 1e-12).any():
        raise ValueError("target weights exceed max_gross_exposure")
    if not config.allow_short and (weights.sum(axis=1) > 1.0 + 1e-12).any():
        raise ValueError("long-only target weights imply negative cash")
    return weights.reindex(columns=assets, fill_value=0.0).astype(float)


def _truncate_bundle_to_end(bundle: DataBundle, end: str) -> DataBundle:
    """Hide data after the requested end date from strategy code."""
    cutoff = pd.Timestamp(end)

    def clip(frame: pd.DataFrame | None) -> pd.DataFrame | None:
        if frame is None or not isinstance(frame.index, pd.DatetimeIndex):
            return frame
        return frame.loc[frame.index <= cutoff].copy(deep=True)

    benchmark = bundle.benchmark_returns
    if benchmark is not None:
        benchmark = benchmark.loc[benchmark.index <= cutoff].copy(deep=True)
    return DataBundle(
        asset_returns=clip(bundle.asset_returns),
        prices=clip(bundle.prices),
        factors={name: frame for name, frame in ((name, clip(value)) for name, value in bundle.factors.items()) if frame is not None},
        benchmark_returns=benchmark,
        dataset_manifest=bundle.dataset_manifest,
    )


def run_backtest(
    strategy: StrategyProtocol,
    data: DataBundle,
    config: BacktestConfig,
    *,
    cost_model: LinearCostModel | None = None,
) -> BacktestResult:
    """Run target weights through lag, execution, costs and canonical metrics."""
    config.validate()
    data.validate()
    bundle = _truncate_bundle_to_end(data.safe_copy(), config.end)
    returns = bundle.asset_returns.loc[config.start:config.end].copy()
    if returns.empty:
        raise ValueError("no asset returns in requested backtest window")
    target = strategy.generate_target_weights(StrategyContext(bundle, config))
    target = _validate_weights(target, config, returns.columns)
    target = target.loc[target.index <= returns.index.max()]
    if target.empty or target.index.max() < returns.index.min() - pd.DateOffset(years=10):
        raise ValueError("no relevant target weights for requested backtest window")

    # Include pre-window signals so the first in-window execution is reproducible.
    alignment_index = target.index.union(returns.index).sort_values()
    scheduled_all = target.reindex(alignment_index).ffill().fillna(0.0)
    executed = scheduled_all.shift(config.signal_lag).reindex(returns.index).fillna(0.0)
    active_missing = returns.isna() & executed.ne(0.0)
    if active_missing.any().any():
        bad = active_missing.stack()[lambda x: x].index[0]
        raise ValueError(f"missing return for active position: {bad}")
    safe_returns = returns.fillna(0.0)
    changes = executed.diff().fillna(executed)
    turnover = changes.abs().sum(axis=1).rename("turnover")
    model = cost_model or LinearCostModel(model_id=config.cost_model_id)
    costs = model.calculate(changes)
    gross = (executed * safe_returns).sum(axis=1).rename("gross_return")
    net = (gross - costs).rename("net_return")
    nav = (1.0 + net).cumprod().rename("nav")
    cash = (1.0 - executed.sum(axis=1)).rename("cash_weight")

    if bundle.benchmark_returns is not None:
        benchmark = bundle.benchmark_returns.reindex(returns.index)
        if benchmark.isna().any():
            raise ValueError("benchmark returns do not cover the backtest window")
        benchmark = benchmark.astype(float).rename("benchmark_return")
    elif config.benchmark_id == "equal_weight":
        benchmark = safe_returns.mean(axis=1).rename("benchmark_return")
    else:
        raise ValueError(f"benchmark data missing for {config.benchmark_id}")

    holdings = executed.where(executed.ne(0.0))
    timeline = pd.DataFrame(
        {
            "signal_date": pd.Series(returns.index, index=returns.index).shift(config.signal_lag),
            "rebalance_date": returns.index,
            "return_period": returns.index,
        },
        index=returns.index,
    )
    metrics = cal_all_metrics(net.to_numpy(), benchmark.to_numpy())
    return BacktestResult(
        config, target, executed, cash, turnover, gross, costs, net,
        benchmark, nav, holdings, timeline, metrics,
    )
