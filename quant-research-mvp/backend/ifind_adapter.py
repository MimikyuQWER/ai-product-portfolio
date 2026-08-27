"""Small, non-persisting iFinD adapter used by the demo smoke test."""
from __future__ import annotations

from typing import Any

import pandas as pd

from core.contracts import DataBundle
from utils.ifind_api import CPS_RAW, IFindAPI

from .demo_pipeline import run_bundle_pipeline


def response_to_close_frame(response: dict[str, Any]) -> pd.DataFrame:
    """Normalize cmd_history_quotation tables to date x code closes."""
    series: dict[str, pd.Series] = {}
    for table in response.get("tables", []):
        code = str(table.get("thscode", "")).strip()
        times = pd.to_datetime(table.get("time", []))
        values = pd.DataFrame(table.get("table", []), index=times)
        if not code or values.empty:
            continue
        close = values.iloc[:, 0].apply(pd.to_numeric, errors="coerce")
        close.index.name = "date"
        series[code] = close
    if not series:
        raise ValueError("iFinD response did not contain close tables")
    result = pd.concat(series, axis=1).sort_index()
    result.columns.name = "code"
    return result


def fetch_ifind_bundle(
    *,
    codes: list[str],
    start: str,
    end: str,
    api: IFindAPI | None = None,
) -> DataBundle:
    """Fetch closes in memory and convert them to a monthly DataBundle."""
    client = api or IFindAPI()
    response = client.get_history_prices(codes, start, end, indicators="close", fill="Blank", cps=CPS_RAW)
    close_daily = response_to_close_frame(response)
    close_monthly = close_daily.resample("ME").last()
    returns = close_monthly.pct_change(fill_method=None).dropna(how="all")
    returns = returns.dropna(axis=1, how="any")
    if returns.empty or len(returns) < 8:
        raise ValueError("iFinD smoke sample is too short after monthly normalization")
    manifest = {
        "source": "iFinD",
        "endpoint": "cmd_history_quotation",
        "asset_type": "index",
        "universe_id": "ifind_index_smoke_pool",
        "codes": list(returns.columns),
        "frequency": "monthly_after_resample",
        "date_start": returns.index.min().strftime("%Y-%m-%d"),
        "date_end": returns.index.max().strftime("%Y-%m-%d"),
        "rows": len(returns),
        "adjustment": "raw_index_close_CPS_1",
    }
    return DataBundle(
        asset_returns=returns,
        prices=close_monthly.reindex(returns.index),
        benchmark_returns=returns.mean(axis=1).rename("benchmark"),
        dataset_manifest=manifest,
    )


def run_ifind_smoke(*, codes: list[str], start: str, end: str) -> dict[str, Any]:
    """Fetch a small live sample and run representative factor strategies."""
    bundle = fetch_ifind_bundle(codes=codes, start=start, end=end)
    strategy_ids = ["momentum", "low_vol", "momentum_timing", "equal_weight"]
    if "pb" in bundle.factors:
        strategy_ids[2:2] = ["value", "composite"]
    return run_bundle_pipeline(bundle, strategy_ids=strategy_ids)
