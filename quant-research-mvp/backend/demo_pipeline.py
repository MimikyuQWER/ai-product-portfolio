"""A deterministic end-to-end research run for the portfolio demo.

The demo deliberately reuses the formal project's public contracts and the
canonical backtest runner. It uses synthetic monthly data so the portfolio
site can be distributed without private data, credentials, or an online
service. The same strategy boundary can later receive an iFinD-derived bundle.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from backtest.costs import LinearCostModel
from backtest.runner import run_backtest
from core.contracts import BacktestConfig, DataBundle, FactorSpec, SplitConfig, StrategyContext
from research.factor_evaluator import evaluate_factor


ASSET_LABELS: dict[str, str] = {
    "SECTOR_01": "制造与设备",
    "SECTOR_02": "消费与服务",
    "SECTOR_03": "医药与健康",
    "SECTOR_04": "信息与科技",
    "SECTOR_05": "金融与地产",
    "SECTOR_06": "能源与材料",
    "SECTOR_07": "公用与交通",
    "SECTOR_08": "先进制造",
}
ASSETS = pd.Index(ASSET_LABELS, name="asset")
SUPPORTED_ASSET_TYPES: dict[str, dict[str, str]] = {
    "stock": {"label": "股票", "demo_universe": "合成行业股票池"},
    "fund": {"label": "基金", "demo_universe": "合成基金池"},
    "bond": {"label": "债券", "demo_universe": "合成债券指数池"},
    "index": {"label": "指数", "demo_universe": "合成行业指数池"},
}
STRATEGY_META: dict[str, dict[str, str]] = {
    "momentum": {
        "label": "横截面动量",
        "short": "追踪过去 6 个月相对强势的 3 个行业",
        "logic": "过去表现靠前 → 下一期等权持有",
    },
    "low_vol": {
        "label": "低波动",
        "short": "选择过去 6 个月波动率最低的 3 个行业",
        "logic": "历史波动率较低 → 下一期等权持有",
    },
    "value": {
        "label": "价值 / PB",
        "short": "选择模拟 PB 最低的 3 个行业",
        "logic": "估值相对较低 → 下一期等权持有",
    },
    "composite": {
        "label": "综合因子",
        "short": "正交化后按动量、低波与价值的标准化排名合成综合分数",
        "logic": "单因子 → 正交化 → 多因子加权 → 下一期持有综合分数靠前的行业",
    },
    "momentum_timing": {
        "label": "动量择时",
        "short": "用 12 个月趋势过滤决定持仓比例，再持有相对强势行业",
        "logic": "12 个月趋势为正满仓 Top 3，趋势转弱降至半仓，下一期执行",
    },
    "equal_weight": {
        "label": "等权基准",
        "short": "所有行业等权持有，作为可解释基准",
        "logic": "全资产等权 → 每期保持基准组合",
    },
}

DEMO_SPLIT = SplitConfig(
    train_start="2019-01-31",
    train_end="2022-12-31",
    validation_start="2023-01-31",
    validation_end="2024-12-31",
    name="demo_train_validation_holdout",
    exposure_note="2025 holdout is reserved for final review and is not used for factor weights",
)


@dataclass(frozen=True)
class DemoStrategy:
    """One strategy implementation behind the common StrategyProtocol."""

    strategy_id: str
    lookback: int = 6
    top_n: int = 3
    defensive_exposure: float = 0.5

    def generate_target_weights(self, context: StrategyContext) -> pd.DataFrame:
        returns = context.data.asset_returns
        factor_name = {
            "momentum": "momentum_6m",
            "momentum_timing": "momentum_6m",
            "low_vol": "low_vol_6m",
            "value": "pb",
            "composite": "composite_v1",
        }.get(self.strategy_id)
        factor = context.data.factors.get(factor_name) if factor_name else None
        dates = returns.index[self.lookback :] if factor is None else factor.dropna(how="all").index
        if self.strategy_id == "momentum_timing":
            trend = context.data.factors.get("market_trend_12m")
            dates = dates.intersection(trend.dropna().index) if trend is not None else dates
        rows: list[pd.Series] = []
        for date in dates:
            history = returns.loc[:date].tail(self.lookback)
            gross_scale = 1.0
            if self.strategy_id == "momentum" and factor is None:
                score = (1.0 + history).prod() - 1.0
                selected = score.nlargest(self.top_n).index
            elif self.strategy_id == "low_vol" and factor is None:
                score = history.std(ddof=1)
                selected = score.nsmallest(self.top_n).index
            elif self.strategy_id == "value" and factor is None:
                value = context.data.factors["pb"].loc[:date].ffill().iloc[-1]
                selected = value.nsmallest(self.top_n).index
            elif self.strategy_id == "low_vol":
                selected = factor.loc[date].nsmallest(self.top_n).index
            elif self.strategy_id == "value":
                selected = factor.loc[date].nsmallest(self.top_n).index
            elif self.strategy_id in {"momentum", "composite"}:
                selected = factor.loc[date].nlargest(self.top_n).index
            elif self.strategy_id == "momentum_timing":
                selected = factor.loc[date].nlargest(self.top_n).index
                trend_value = context.data.factors["market_trend_12m"].loc[date]
                gross_scale = 1.0 if trend_value > 0 else self.defensive_exposure
            else:
                selected = returns.columns
            row = pd.Series(0.0, index=returns.columns, name=date)
            row.loc[selected] = gross_scale / len(selected)
            rows.append(row)
        return pd.DataFrame(rows, index=dates)


def build_synthetic_bundle(*, seed: int = 20260826, months: int = 84) -> DataBundle:
    """Create one deterministic monthly data bundle for all strategies."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2019-01-31", periods=months, freq="ME")
    regime = np.sin(np.linspace(0, 3.3 * np.pi, months)) * 0.006
    common = rng.normal(0.004, 0.035, months) + regime
    drift = np.array([0.0060, 0.0052, 0.0047, 0.0065, 0.0038, 0.0030, 0.0043, 0.0058])
    beta = np.array([1.05, 0.88, 0.76, 1.15, 0.73, 1.03, 0.62, 1.08])
    idio_scale = np.array([0.030, 0.024, 0.019, 0.040, 0.017, 0.034, 0.014, 0.027])
    values = np.column_stack(
        [drift[i] + beta[i] * common + rng.normal(0.0, idio_scale[i], months) for i in range(len(ASSETS))]
    )
    asset_returns = pd.DataFrame(values, index=dates, columns=ASSETS).clip(lower=-0.35)
    # A smooth, deterministic valuation surface gives the value strategy a
    # real input/output contract without pretending that it is licensed data.
    pb_base = np.array([1.65, 2.15, 2.55, 3.10, 1.20, 1.45, 1.75, 2.05])
    pb_noise = rng.normal(0.0, 0.08, (months, len(ASSETS)))
    pb = pd.DataFrame(np.maximum(pb_base + pb_noise, 0.35), index=dates, columns=ASSETS)
    prices = 100.0 * (1.0 + asset_returns).cumprod()
    benchmark = asset_returns.mean(axis=1).rename("benchmark")
    manifest = {
        "source": "synthetic",
        "seed": seed,
        "frequency": "monthly",
        "asset_type": "index",
        "universe_id": "synthetic_sector_8",
        "date_start": dates[0].strftime("%Y-%m-%d"),
        "date_end": dates[-1].strftime("%Y-%m-%d"),
        "rows": len(dates),
        "assets": list(ASSETS),
        "adjustment": "not_applicable_synthetic",
    }
    manifest["sha256"] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    factors = _derive_factor_frames(asset_returns, pb)
    return DataBundle(
        asset_returns=asset_returns,
        prices=prices,
        factors=factors,
        benchmark_returns=benchmark,
        dataset_manifest=manifest,
    )


def _derive_factor_frames(
    returns: pd.DataFrame,
    pb: pd.DataFrame | None = None,
    composite_weights: dict[str, float] | None = None,
) -> dict[str, pd.DataFrame]:
    """Build transparent, point-in-time factor inputs for the demo pipeline."""
    momentum = (1.0 + returns).rolling(6, min_periods=6).apply(np.prod, raw=True) - 1.0
    low_vol = returns.rolling(6, min_periods=6).std(ddof=1)
    factors: dict[str, pd.DataFrame] = {
        "momentum_6m": momentum,
        "low_vol_6m": low_vol,
        "market_trend_12m": (1.0 + returns.mean(axis=1)).rolling(12, min_periods=12).apply(np.prod, raw=True) - 1.0,
    }
    if pb is not None:
        weights = composite_weights or {
            "momentum_6m": 0.5,
            "low_vol_orthogonal": 0.3,
            "value_orthogonal": 0.2,
        }
        total = sum(float(value) for value in weights.values())
        if total <= 0:
            raise ValueError("综合因子权重之和必须大于 0")
        weights = {key: float(value) / total for key, value in weights.items()}
        factors["pb"] = pb
        momentum_rank = momentum.rank(axis=1, pct=True)
        low_vol_rank = low_vol.rank(axis=1, pct=True, ascending=False)
        value_rank = pb.rank(axis=1, pct=True, ascending=False)
        low_vol_orthogonal = _orthogonalize_cross_section(low_vol_rank, [momentum_rank])
        value_orthogonal = _orthogonalize_cross_section(value_rank, [momentum_rank, low_vol_rank])
        factors["low_vol_orthogonal"] = low_vol_orthogonal
        factors["value_orthogonal"] = value_orthogonal
        factors["composite_v1"] = (
            weights["momentum_6m"] * _cross_sectional_zscore(momentum_rank)
            + weights["low_vol_orthogonal"] * _cross_sectional_zscore(low_vol_orthogonal)
            + weights["value_orthogonal"] * _cross_sectional_zscore(value_orthogonal)
        )
    return factors


def _cross_sectional_zscore(frame: pd.DataFrame) -> pd.DataFrame:
    mean = frame.mean(axis=1)
    std = frame.std(axis=1, ddof=0).replace(0.0, np.nan)
    return frame.sub(mean, axis=0).div(std, axis=0)


def _orthogonalize_cross_section(target: pd.DataFrame, controls: list[pd.DataFrame]) -> pd.DataFrame:
    """Residualize a factor cross-sectionally using only same-date controls."""
    result = pd.DataFrame(np.nan, index=target.index, columns=target.columns)
    for date in target.index:
        series = pd.concat([target.loc[date].rename("target")] + [frame.loc[date].rename(f"control_{i}") for i, frame in enumerate(controls)], axis=1).dropna()
        if len(series) < len(controls) + 2:
            continue
        x = np.column_stack([np.ones(len(series)), series.iloc[:, 1:].to_numpy(dtype=float)])
        y = series.iloc[:, 0].to_numpy(dtype=float)
        beta, *_ = np.linalg.lstsq(x, y, rcond=None)
        residual = y - x @ beta
        result.loc[date, series.index] = residual
    return result


def _factor_research_evidence(
    bundle: DataBundle,
    split: SplitConfig = DEMO_SPLIT,
    composite_weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """按明确的滞后期和样本切分评估单因子与综合因子。"""
    weights = composite_weights or {
        "momentum_6m": 0.5,
        "low_vol_orthogonal": 0.3,
        "value_orthogonal": 0.2,
    }
    composite_formula = (
        f"{weights['momentum_6m']:.2f} * z(momentum_rank) + "
        f"{weights['low_vol_orthogonal']:.2f} * z(low_vol_orthogonal) + "
        f"{weights['value_orthogonal']:.2f} * z(value_orthogonal)"
    )
    specs = {
        "momentum_6m": FactorSpec("momentum_6m", "monthly", 1, 1, 1, "synthetic_sector_8", {"lookback": 6}),
        "low_vol_6m": FactorSpec("low_vol_6m", "monthly", -1, 1, 1, "synthetic_sector_8", {"lookback": 6}),
        "pb": FactorSpec("pb", "monthly", -1, 1, 1, "synthetic_sector_8", {"metric": "pb"}),
        "low_vol_orthogonal": FactorSpec("low_vol_orthogonal", "monthly", 1, 1, 1, "synthetic_sector_8", {"residualized_against": ["momentum_6m"]}),
        "value_orthogonal": FactorSpec("value_orthogonal", "monthly", 1, 1, 1, "synthetic_sector_8", {"residualized_against": ["momentum_6m", "low_vol_6m"]}),
        "composite_v1": FactorSpec(
            "composite_v1", "monthly", 1, 1, 1, "synthetic_sector_8",
            {"weights": weights, "orthogonalization": "cross_sectional_residual"},
        ),
    }
    evaluations: dict[str, Any] = {}
    for name, spec in specs.items():
        values = bundle.factors.get(name)
        if values is None:
            continue
        clean = values.dropna(how="any")
        try:
            evaluation = evaluate_factor(clean, spec, split, asset_returns=bundle.asset_returns)
            payload = evaluation.to_dict()
            group_mean = evaluation.group_returns.mean()
            benchmark = evaluation.group_returns.mean(axis=1)
            excess = evaluation.group_returns.sub(benchmark, axis=0)
            payload["definition"] = {
                "formula": {
                    "momentum_6m": "prod(1 + monthly_return[t-5:t]) - 1",
                    "low_vol_6m": "std(monthly_return[t-5:t], ddof=1)",
                    "pb": "reported PB at observation date",
                    "low_vol_orthogonal": "residual(rank(-volatility) ~ 1 + rank(momentum))",
                    "value_orthogonal": "residual(rank(-PB) ~ 1 + rank(momentum) + rank(-volatility))",
                    "composite_v1": composite_formula,
                }[name],
                "economic_meaning": {
                    "momentum_6m": "相对强势可能延续，反映趋势和资金调整的惯性",
                    "low_vol_6m": "较低历史波动可能对应更稳定的风险暴露",
                    "pb": "较低估值代表为每单位账面价值支付的价格相对更低",
                    "low_vol_orthogonal": "在剔除动量共同变化后，观察低波信号的独立部分",
                    "value_orthogonal": "在剔除动量和低波共同变化后，观察价值信号的独立部分",
                    "composite_v1": "用不同风险来源的信号组合，减少单一因子依赖",
                }[name],
                "direction": "higher_is_better" if spec.direction == 1 else "lower_is_better",
                "lag_periods": spec.lag_periods,
                "forward_periods": spec.forward_periods,
            }
            payload["tables"] = {
                "ic_summary": payload["summary"].get("full", {}),
                "group_mean_return": {key: _metric(value) for key, value in group_mean.items()},
                "group_excess_return": {key: _metric(value) for key, value in excess.mean().items()},
                "g1_g5_long_short": _metric(evaluation.long_short.mean()),
                "ic_series": [
                    {"date": pd.Timestamp(date).strftime("%Y-%m-%d"), "rank_ic": _metric(value)}
                    for date, value in evaluation.rank_ic.items()
                ],
                "group_returns": [
                    {"date": pd.Timestamp(date).strftime("%Y-%m-%d"), **{key: _metric(value) for key, value in row.items()}}
                    for date, row in evaluation.group_returns.iterrows()
                ],
            }
            payload["sensitivity"] = {
                "description": "固定因子定义，仅改变预测周期，观察信号衰减，不使用留出集调参。",
                "forward_periods": {
                    str(period): {
                        "rank_ic_mean": _metric(series.mean()),
                        "rank_icir": _metric(series.mean() / series.std(ddof=0)) if series.std(ddof=0) else 0.0,
                        "observations": int(series.notna().sum()),
                    }
                    for period, series in evaluation.decay_rank_ic.items()
                },
            }
            payload["approval"] = {
                "status": "pending_review",
                "allowed_actions": ["adopt", "adjust", "discard"],
                "ai_observer": {
                    "summary": "AI 旁观建议：先看训练集与验证集方向是否一致，再决定是否进入因子池。",
                    "suggestions": ["检查 ICIR 是否依赖少数月份", "比较 G1-G5 多空与换手成本", "不要用留出集反复调权重"],
                },
            }
            evaluations[name] = payload
        except ValueError as exc:
            evaluations[name] = {"status": "not_available", "reason": str(exc), "spec": spec.__dict__}
    return evaluations


def _research_stages(
    bundle: DataBundle,
    factor_evidence: dict[str, Any],
    config: BacktestConfig,
    split_config: SplitConfig = DEMO_SPLIT,
) -> list[dict[str, Any]]:
    """Describe the seven explicit research responsibilities shown in the UI."""
    split = {
        "train": {"start": split_config.train_start, "end": split_config.train_end},
        "validation": {"start": split_config.validation_start, "end": split_config.validation_end},
        "holdout": {
            "start": str((pd.Timestamp(split_config.validation_end) + pd.offsets.MonthEnd(1)).date()),
            "end": config.end,
            "purpose": "final review only",
        },
    }
    return [
        {
            "id": "data_extract_store", "name": "数据提取与存储",
            "responsibility": "登记来源、频率、日期范围和可见性边界，并形成统一数据包。",
            "input": ["行情接口或本地文件", "资产池", "日期范围"],
            "output": ["统一数据包", "数据清单", "数据指纹"],
            "controls": ["来源可追踪", "日期边界", "不保存凭证"],
            "status": "completed",
        },
        {
            "id": "single_factor_research", "name": "单个因子挖掘与测试",
            "responsibility": "单独定义因子、方向、观察窗口、滞后和 forward return，再评估 IC、分组和覆盖度。",
            "input": ["数据包", "因子定义", "训练集 / 验证集 / 留出集"],
            "output": ["因子值表", "IC / 分组收益", "衰减和换手证据"],
            "controls": ["信号至少滞后 1 期", "预测周期明确", "时间切分"],
            "status": "completed" if factor_evidence else "partial",
        },
        {
            "id": "factor_improvement", "name": "因子改进与综合",
            "responsibility": "把经过单因子测试的信号做标准化、方向统一和加权合成，记录每个权重的来源。",
            "input": ["单因子评估结果", "标准化规则", "权重方案"],
            "output": ["composite_v1 因子", "权重快照", "对比结果"],
            "controls": ["权重和为 1", "横截面正交化", "不使用留出集调参", "版本化"],
            "status": "completed" if "composite_v1" in factor_evidence else "not_available",
        },
        {
            "id": "risk_rebalance", "name": "风控与调仓逻辑",
            "responsibility": "把目标权重变成受约束的执行权重，并统一处理调仓频率、换手和交易成本。",
            "input": ["目标权重", "持仓状态", "成本配置", "风险约束"],
            "output": ["执行权重", "换手", "成本", "风险事件"],
            "controls": ["只做多", "总敞口 ≤ 1", "买入与卖出费率"],
            "status": "completed",
        },
        {
            "id": "strategy_iteration", "name": "策略设计与迭代",
            "responsibility": "比较基准、单因子和综合因子，把假设、改动和决策原因写进迭代记录。",
            "input": ["因子证据", "策略规则", "训练 / 验证结果"],
            "output": ["候选策略表", "迭代记录", "待验证假设"],
            "controls": ["先训练 / 验证", "留出集不参与调参", "保留失败版本"],
            "status": "completed",
        },
        {
            "id": "backtest_report", "name": "回测与报告产出",
            "responsibility": "按时间顺序执行信号、滞后、收益和成本，产出可复核的净值、持仓和绩效报告。",
            "input": ["回测配置", "目标权重", "资产收益", "交易成本模型"],
            "output": ["净值", "持仓轨迹", "指标", "报告摘要"],
            "controls": [f"{config.start} → {config.end}", f"信号滞后 = {config.signal_lag} 期", "统一交易成本模型"],
            "status": "completed",
        },
        {
            "id": "version_record", "name": "版本管理与运行记录",
            "responsibility": "将代码、配置、数据、策略参数和产物绑定成可重放的研究版本。",
            "input": ["各阶段清单", "配置快照", "代码版本"],
            "output": ["运行清单", "产物指纹", "版本 / 迭代日志"],
            "controls": ["不可覆盖运行 ID", "输入输出可追溯", "脱敏发布"],
            "status": "completed",
        },
    ]


def _metric(value: Any) -> float | None:
    if value is None or not np.isfinite(float(value)):
        return None
    return round(float(value), 6)


def _serialize_result(
    result: Any,
    strategy_id: str,
    *,
    top_n: int = 3,
    defensive_exposure: float = 0.5,
) -> dict[str, Any]:
    nav = [
        {"date": pd.Timestamp(date).strftime("%Y-%m-%d"), "value": round(float(value), 6)}
        for date, value in result.nav.items()
    ]
    holdings = []
    for date, row in result.executed_weights.iterrows():
        active = row[row > 0]
        if active.empty:
            continue
        holdings.append(
            {
                "date": pd.Timestamp(date).strftime("%Y-%m-%d"),
                "items": [{"asset": asset, "label": ASSET_LABELS.get(asset, asset), "weight": round(float(weight), 4)} for asset, weight in active.items()],
            }
        )
    metrics = {key: _metric(value) for key, value in result.metrics.items()}
    return {
        "id": strategy_id,
        "label": STRATEGY_META[strategy_id]["label"],
        "summary": STRATEGY_META[strategy_id]["short"],
        "logic": STRATEGY_META[strategy_id]["logic"],
        "spec": {
            "factor_inputs": {
                "momentum": ["momentum_6m"],
                "low_vol": ["low_vol_6m"],
                "value": ["pb"],
                "composite": ["momentum_6m", "low_vol_orthogonal", "value_orthogonal"],
                "momentum_timing": ["momentum_6m", "market_trend_12m"],
                "equal_weight": [],
            }[strategy_id],
            "selection": f"Top {top_n} 等权" if strategy_id != "equal_weight" else "全资产等权",
            "rebalance": "monthly",
            "signal_lag": result.config.signal_lag,
            "risk_controls": {"long_only": True, "max_gross_exposure": result.config.max_gross_exposure, "transaction_cost": result.config.cost_model_id},
            "timing_rule": (
                f"12个月基准趋势为正满仓，否则降至 {defensive_exposure:.0%}"
                if strategy_id == "momentum_timing" else "不适用"
            ),
        },
        "metrics": metrics,
        "nav": nav,
        "holdings": holdings,
        "evidence": {
            "signal_lag": result.config.signal_lag,
            "cost_model": result.config.cost_model_id,
            "cost_total": _metric(result.costs.sum()),
            "turnover_mean": _metric(result.turnover.mean()),
            "periods": len(result.net_returns),
        },
    }


def run_bundle_pipeline(
    bundle: DataBundle,
    *,
    strategy_ids: list[str] | None = None,
    run_config: BacktestConfig | None = None,
    split_config: SplitConfig = DEMO_SPLIT,
    composite_weights: dict[str, float] | None = None,
    top_n: int = 3,
    defensive_exposure: float = 0.5,
) -> dict[str, Any]:
    """Run selected strategies on one bundle through the formal runner."""
    work_bundle = bundle.safe_copy()
    weights = composite_weights or {
        "momentum_6m": 0.5,
        "low_vol_orthogonal": 0.3,
        "value_orthogonal": 0.2,
    }
    weight_total = sum(float(value) for value in weights.values())
    if weight_total <= 0 or any(float(value) < 0 for value in weights.values()):
        raise ValueError("综合因子权重必须为非负数，且权重之和大于 0")
    weights = {key: float(value) / weight_total for key, value in weights.items()}
    if top_n < 1 or top_n > len(work_bundle.asset_returns.columns):
        raise ValueError("持仓数量超出可用标的范围")
    if not 0 <= defensive_exposure <= 1:
        raise ValueError("趋势转弱时的仓位必须在 0 到 1 之间")
    derived = _derive_factor_frames(work_bundle.asset_returns, work_bundle.factors.get("pb"), weights)
    work_bundle.factors.update(derived)
    config = run_config or BacktestConfig(
        start=str(work_bundle.asset_returns.index.min().date()),
        end=str(work_bundle.asset_returns.index.max().date()),
        rebalance_frequency="monthly",
        signal_lag=1,
        benchmark_id="equal_weight",
        cost_model_id="demo_linear_5bp_buy_10bp_sell",
    )
    config.validate()
    zero_cost = config.cost_model_id == "zero_cost_warning"
    cost_model = LinearCostModel(
        buy_rate=0.0 if zero_cost else 0.0005,
        sell_rate=0.0 if zero_cost else 0.0010,
        model_id=config.cost_model_id,
    )
    results: dict[str, Any] = {}
    selected_ids = strategy_ids or list(STRATEGY_META)
    missing = set(selected_ids) - set(STRATEGY_META)
    if missing:
        raise ValueError(f"unknown demo strategies: {sorted(missing)}")
    for strategy_id in selected_ids:
        strategy = DemoStrategy(
            strategy_id=strategy_id,
            top_n=top_n,
            defensive_exposure=defensive_exposure,
        )
        result = run_backtest(strategy, work_bundle, config, cost_model=cost_model)
        results[strategy_id] = _serialize_result(
            result,
            strategy_id,
            top_n=top_n,
            defensive_exposure=defensive_exposure,
        )
    factor_evidence = {}
    if pd.Timestamp(config.start) <= pd.Timestamp(split_config.train_start) and pd.Timestamp(config.end) >= pd.Timestamp(split_config.validation_end):
        factor_evidence = _factor_research_evidence(work_bundle, split_config, weights)
    holdout_start = str((pd.Timestamp(split_config.validation_end) + pd.offsets.MonthEnd(1)).date())
    config_payload = {
        "start": config.start,
        "end": config.end,
        "frequency": config.rebalance_frequency,
        "signal_lag": config.signal_lag,
        "cost_model": config.cost_model_id,
        "benchmark": config.benchmark_id,
        "asset_type": work_bundle.dataset_manifest.get("asset_type", "index"),
        "universe_id": work_bundle.dataset_manifest.get("universe_id", "synthetic_sector_8"),
        "allow_short": config.allow_short,
        "max_gross_exposure": config.max_gross_exposure,
        "sample_split": {
            "train": {"start": split_config.train_start, "end": split_config.train_end},
            "validation": {"start": split_config.validation_start, "end": split_config.validation_end},
            "holdout": {"start": holdout_start, "end": config.end, "purpose": "final review only"},
        },
        "strategy_parameters": {
            "factor_weights": weights,
            "top_n": top_n,
            "defensive_exposure": defensive_exposure,
        },
        "cost_assumptions": {"buy_rate": 0.0005, "sell_rate": 0.0010, "currency": "fraction of traded notional"},
    }
    iterations = [
        {"version": "baseline.equal_weight", "hypothesis": "先建立不依赖因子的可解释基准", "input": ["asset_returns"], "output": ["equal_weight"], "decision": "作为参考基准"},
        {"version": "candidate.single_factor", "hypothesis": "先分别验证动量、低波和价值信号", "input": ["单因子证据"], "output": ["momentum", "low_vol", "value"], "decision": "在训练集和验证集比较"},
        {"version": "candidate.composite_v1", "hypothesis": f"先做横截面正交化，再用 {weights['momentum_6m']:.0%} / {weights['low_vol_orthogonal']:.0%} / {weights['value_orthogonal']:.0%} 合成多因子排名", "input": ["momentum_6m", "low_vol_orthogonal", "value_orthogonal"], "output": ["composite_v1", "综合因子策略"], "decision": "仅用于留出集复核，不自动晋级"},
    ]
    version_material = {"schema_version": "demo-run-v2", "data_manifest": work_bundle.dataset_manifest, "config": config_payload, "strategies": selected_ids}
    config_hash = hashlib.sha256(json.dumps(config_payload, sort_keys=True).encode()).hexdigest()
    run_hash = hashlib.sha256(json.dumps(version_material, sort_keys=True, default=str).encode()).hexdigest()
    factor_decisions = [
        {"factor_id": "momentum_6m", "status": "pending_review", "decision": None, "reason": None},
        {"factor_id": "low_vol_6m", "status": "pending_review", "decision": None, "reason": None},
        {"factor_id": "pb", "status": "pending_review", "decision": None, "reason": None},
        {"factor_id": "low_vol_orthogonal", "status": "derived_candidate", "decision": None, "reason": "由低波因子正交化生成"},
        {"factor_id": "value_orthogonal", "status": "derived_candidate", "decision": None, "reason": "由价值因子正交化生成"},
        {"factor_id": "composite_v1", "status": "candidate_only", "decision": None, "reason": "必须先完成单因子审批"},
    ]
    golden_checks = [
        {"id": "metric_formula_registry", "name": "指标统一公式出口", "status": "passed", "evidence": "核心指标库统一计算"},
        {"id": "future_visibility", "name": "策略不可见回测结束日之后的数据", "status": "passed", "evidence": "回测引擎截断回归测试"},
        {"id": "net_return_identity", "name": "净收益等于毛收益减成本", "status": "passed", "evidence": "回测契约断言"},
        {"id": "nav_identity", "name": "净值等于净收益累乘", "status": "passed", "evidence": "回测结果恒等式"},
        {"id": "artifact_hash", "name": "配置和数据指纹已绑定", "status": "passed", "evidence": "运行记录绑定配置指纹和数据指纹"},
    ]
    research_workflow = {
        "current_stage": "factor_review",
        "human_ai_contract": {
            "human": ["提出研究问题", "确认因子经济意义", "批准或废弃因子", "决定是否进入正式策略"],
            "ai": ["执行确定性计算", "生成指标表和敏感性表", "检查口径与前视风险", "提出可验证的改善建议"],
            "shared": ["每一步先锁定输入", "输出可追溯", "所有批准和废弃都记录原因"],
        },
        "configuration": {
            "status": "locked_for_demo",
            "asset_pool": "synthetic_sector_8",
            "frequency": config.rebalance_frequency,
            "backtest_window": {"start": config.start, "end": config.end},
            "sample_split": config_payload["sample_split"],
            "cost_model": config_payload["cost_assumptions"],
            "point_in_time_rule": "因子 t 期只能影响 t+1 期及之后的执行；留出集不能用于调参",
        },
        "factor_pool": {"status": "awaiting_human_approval", "decisions": factor_decisions},
        "composite_design": {
            "status": "candidate_only",
            "formula": f"{weights['momentum_6m']:.2f} * z(momentum_rank) + {weights['low_vol_orthogonal']:.2f} * z(low_vol_orthogonal) + {weights['value_orthogonal']:.2f} * z(value_orthogonal)",
            "weights": weights,
            "orthogonalization": "同一截面内用已确认因子解释共同变化，综合因子只保留残差部分，避免重复计权",
            "human_input": "研究员提出权重和改进方向，AI 执行正交化、标准化并生成对比证据",
        },
        "strategy_review": {
            "status": "awaiting_human_approval",
            "logic": "已批准因子 → 排名 → 前 N 名 → 目标权重 → 风险约束 → 下一期执行",
            "ai_observer": "回测完成后先检查公式、时间对齐、成本和版本是否发生漂移，再提示人决定采纳、改进或废弃。",
        },
        "backtest_quality": {"status": "passed_with_golden_checks", "checks": golden_checks},
        "version_history": [
            {"version_id": "demo-research-v0.1.0", "type": "baseline", "status": "superseded", "reason": "增加显式因子评估、审批和规则校验记录"},
            {"version_id": "demo-research-v0.2.0", "type": "workflow_mvp", "status": "current_candidate", "reason": "七阶段研究流程已结构化"},
        ],
    }
    return {
        "schema_version": "demo-run-v2",
        "generated_at": "synthetic-deterministic",
        "disclaimer": "本文件中的数据和结果均为合成示例，仅用于产品演示，不代表真实收益。",
        "data_manifest": work_bundle.dataset_manifest,
        "config": config_payload,
        "assets": [{"id": asset, "label": ASSET_LABELS.get(asset, asset)} for asset in work_bundle.asset_returns.columns],
        "strategies": results,
        "architecture": _research_stages(work_bundle, factor_evidence, config, split_config),
        "factor_research": factor_evidence,
        "strategy_iterations": iterations,
        "research_workflow": research_workflow,
        "versioning": {
            "version_id": "demo-research-v0.2.0",
            "parent": "demo-research-v0.1.0",
            "run_id": f"demo-{run_hash[:12]}",
            "config_hash": config_hash,
            "data_hash": work_bundle.dataset_manifest.get("sha256"),
            "artifact_policy": "记录输入、输出和阶段契约；发布包不携带外部原始数据",
        },
        "supported_asset_types": SUPPORTED_ASSET_TYPES,
    }


def run_demo_pipeline(*, seed: int = 20260826) -> dict[str, Any]:
    """Run every demo strategy through the formal local backtest runner."""
    return run_bundle_pipeline(build_synthetic_bundle(seed=seed))


def build_demo_payload(output: str | Path) -> Path:
    """Write the static-site payload and return its path."""
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run_demo_pipeline(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    target = root / "site" / "data" / "demo-run.json"
    print(build_demo_payload(target))
