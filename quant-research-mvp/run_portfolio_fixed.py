# -*- coding: utf-8 -*-
"""脱敏 demo 的最终入口，隔离宿主仓库 git 元数据。"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "vendor"
for import_root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from portfolio_demo.run_demo import SyntheticMomentumStrategy, build_synthetic_bundle
from backtest.costs import LinearCostModel
from backtest.runner import run_backtest
from core.contracts import BacktestConfig
from experiments.recorder import RunRecorder


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the desensitized portfolio demo")
    demo_root = Path(__file__).resolve().parent
    parser.add_argument("--output", type=Path, default=demo_root / "output_portfolio_fixed")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    output = args.output.resolve()
    bundle = build_synthetic_bundle(seed=args.seed)
    config = BacktestConfig(
        start=str(bundle.asset_returns.index[0].date()),
        end=str(bundle.asset_returns.index[-1].date()),
        rebalance_frequency="monthly", signal_lag=1,
        benchmark_id="provided_synthetic_benchmark", cost_model_id="linear_demo",
    )
    result = run_backtest(
        SyntheticMomentumStrategy(top_n=3), bundle, config,
        cost_model=LinearCostModel(buy_rate=0.0005, sell_rate=0.0005, model_id="linear_demo"),
    )
    isolated_root = Path(tempfile.mkdtemp(prefix="qr_portfolio_"))
    recorder = RunRecorder(output / "runs", project_root=isolated_root)
    run_id = recorder.make_run_id(config.__dict__, bundle.dataset_manifest, timestamp="demo")
    existing_run = output / "runs" / run_id
    if existing_run.is_dir():
        run_dir = existing_run
    else:
        run_dir = recorder.record_backtest(
            result,
            effective_config={"strategy": "synthetic_top3_momentum", "lookback_months": 3,
                              "signal_lag": 1, "seed": args.seed},
            data_manifest=bundle.dataset_manifest, run_id=run_id,
            entrypoint="portfolio_demo.run_portfolio_fixed",
        )
    try:
        display_run_dir = run_dir.relative_to(demo_root).as_posix()
    except ValueError:
        display_run_dir = str(run_dir)
    summary = {
        "run_dir": display_run_dir, "seed": args.seed,
        "months": len(result.net_returns), "final_nav": float(result.nav.iloc[-1]),
        "total_cost": float(result.costs.sum()), "max_turnover": float(result.turnover.max()),
        "metrics": result.metrics, "data_is_synthetic": True,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "demo_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
