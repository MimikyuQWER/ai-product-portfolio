# -*- coding: utf-8 -*-
"""脱敏的本地量化研究 demo。

只使用随机生成的行业标签和合成收益，不读取项目真实数据、账号配置或 API。
运行后会生成一个可复现的动量轮动回测，并用项目内的轻量 runner 记录审计产物。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "vendor"
for import_root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from backtest.costs import LinearCostModel
from backtest.runner import run_backtest
from core.contracts import BacktestConfig, DataBundle, StrategyContext
from experiments.recorder import RunRecorder


class SyntheticMomentumStrategy:
    """按过去三个月动量选 Top-N；执行滞后由 runner 统一处理。"""

    def __init__(self, top_n: int = 3) -> None:
        self.top_n = top_n

    def generate_target_weights(self, context: StrategyContext) -> pd.DataFrame:
        factor = context.data.factors["momentum"]
        rows: dict[pd.Timestamp, pd.Series] = {}
        assets = context.data.asset_returns.columns
        for date, values in factor.iterrows():
            ranked = values.dropna().sort_values(ascending=False).head(self.top_n)
            if len(ranked) < self.top_n:
                continue
            weights = pd.Series(0.0, index=assets)
            weights.loc[ranked.index] = 1.0 / self.top_n
            rows[pd.Timestamp(date)] = weights
        return pd.DataFrame.from_dict(rows, orient="index").sort_index()


def build_synthetic_bundle(seed: int = 42, periods: int = 60, assets: int = 8) -> DataBundle:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2021-01-31", periods=periods, freq="ME")
    names = [f"IND_{i:02d}" for i in range(1, assets + 1)]

    # 只模拟“行业轮动 + 市场共同因子 + 噪声”，不对应任何真实标的。
    market = rng.normal(0.006, 0.035, periods)
    cycle = np.sin(np.linspace(0, 4 * np.pi, periods))
    strength = np.array([
        np.roll(cycle, i * (periods // assets)) for i in range(assets)
    ]).T
    returns = 0.45 * market[:, None] + 0.012 * strength + rng.normal(
        0.0, 0.045, (periods, assets)
    )
    frame = pd.DataFrame(returns, index=dates, columns=names)
    momentum = frame.rolling(3, min_periods=3).sum()
    benchmark = frame.mean(axis=1).rename("benchmark")
    return DataBundle(
        asset_returns=frame,
        factors={"momentum": momentum},
        benchmark_returns=benchmark,
        dataset_manifest={
            "dataset_id": "synthetic_industry_returns_v1",
            "source": "generated locally",
            "seed": seed,
            "periods": periods,
            "assets": assets,
            "sensitive_data": False,
        },
    )


def run(output: Path, seed: int = 42) -> Path:
    bundle = build_synthetic_bundle(seed=seed)
    start = bundle.asset_returns.index[0]
    end = bundle.asset_returns.index[-1]
    config = BacktestConfig(
        start=str(start.date()),
        end=str(end.date()),
        rebalance_frequency="monthly",
        signal_lag=1,
        benchmark_id="provided_synthetic_benchmark",
        cost_model_id="linear_demo",
    )
    result = run_backtest(
        SyntheticMomentumStrategy(top_n=3),
        bundle,
        config,
        cost_model=LinearCostModel(buy_rate=0.0005, sell_rate=0.0005, model_id="linear_demo"),
    )

    recorder = RunRecorder(output / "runs", project_root=PROJECT_ROOT)
    run_id = recorder.make_run_id(config.__dict__, bundle.dataset_manifest, timestamp="demo")
    run_dir = recorder.record_backtest(
        result,
        effective_config={
            "strategy": "synthetic_top3_momentum",
            "lookback_months": 3,
            "signal_lag": 1,
            "seed": seed,
        },
        data_manifest=bundle.dataset_manifest,
        run_id=run_id,
        entrypoint="portfolio_demo.run_demo",
    )
    summary = {
        "run_dir": str(run_dir),
        "seed": seed,
        "months": len(result.net_returns),
        "final_nav": float(result.nav.iloc[-1]),
        "total_cost": float(result.costs.sum()),
        "max_turnover": float(result.turnover.max()),
        "metrics": result.metrics,
        "data_is_synthetic": True,
    }
    (output / "demo_summary.json").parent.mkdir(parents=True, exist_ok=True)
    (output / "demo_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the desensitized local quant research demo")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "output",
        help="directory for generated demo artifacts",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    run(args.output.resolve(), seed=args.seed)


if __name__ == "__main__":
    main()
