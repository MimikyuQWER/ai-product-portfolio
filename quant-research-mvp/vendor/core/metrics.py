# -*- coding: utf-8 -*-
"""核心金融指标计算函数 — 全系统唯一实现。

⚖️ 口径约定（不可在函数内部隐式修改）：
  - 收益率输入：月度收益率序列（非累计、非年化）
  - 年化方法：几何年化（cum → 12/n 次方）
  - 夏普比率：算术年化法，超额收益 = 策略收益 - 无风险利率
  - 标准差 ddof 规则：
      时序（时间序列波动率）：ddof=1（样本标准差，无偏估计）
      截面（同月31个行业的z-score排名）：ddof=0（总体标准差，已有全量数据）
  - 最大回撤：nav / peak - 1，返回标量
  - 无风险利率：默认 2.5%/12（10年国债近似）
  - Rank IC 最少有效样本：5 个行业（n≥5），低于此数返回 NaN

⚠️ 禁改规则：
  已发布函数只能新增不能修改签名或计算逻辑。
  要改口径 → 新增版本化函数名（如 sharpe_ratio_v2），旧函数保留。
  未走 golden test 验证之前不得合并到本文件。

METRICS_VERSION 用于归档 hash 比对，任何修改后必须同步更新 golden test 标准答案。
"""

import hashlib
import numpy as np
from pathlib import Path

METRICS_VERSION = "1.0.0"


def metrics_file_hash() -> str:
    """返回本文件的 SHA256 前 16 位，用于归档溯源。"""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]


# ═══════════════════════════════════════════════════════
# 基础指标
# ═══════════════════════════════════════════════════════

def geo_annual(rets):
    """几何年化收益率。

    输入：月度收益率序列（非累计）。
    公式：(1 + ∏(1+月收益))^(12/n) - 1

    Parameters
    ----------
    rets : list or np.ndarray
        月度收益率序列，允许含 NaN（自动过滤）。

    Returns
    -------
    float
    """
    arr = np.array([r for r in rets if r == r])  # r == r filters NaN
    if len(arr) == 0:
        return 0.0
    cumulative = float(np.prod(1 + arr) - 1)
    return float((1 + cumulative) ** (12 / len(arr)) - 1)


def max_drawdown(arr):
    """最大回撤。

    输入：月度收益率序列。
    公式：min(nav / peak - 1)

    Parameters
    ----------
    arr : list or np.ndarray
        月度收益率序列。

    Returns
    -------
    float
        最大回撤值（负数）。
    """
    nav = np.cumprod(1 + np.array(arr))
    peak = np.maximum.accumulate(nav)
    return float(np.min((nav - peak) / peak))


def max_drawdown_detail(arr):
    """最大回撤（含起止日期）。

    输入：月度收益率序列，index 为日期。

    Returns
    -------
    dict: {max_dd, peak_date, trough_date}
    """
    import pandas as pd
    nav = (1 + pd.Series(arr)).cumprod()
    peak = nav.cummax()
    dd = nav / peak - 1
    trough_idx = dd.idxmin()
    peak_idx = nav.loc[:trough_idx].idxmax()
    return {
        "max_dd": float(dd.min()),
        "peak_date": str(peak_idx),
        "trough_date": str(trough_idx),
    }


def pl_ratio(arr):
    """盈亏比。

    输入：月度收益率序列。
    公式：正收益月均值 / |负收益月均值|

    Returns
    -------
    float
    """
    arr = np.asarray(arr, dtype=float)
    pos = arr[arr > 0]
    neg = arr[arr < 0]
    if len(pos) == 0 or len(neg) == 0:
        return 0.0
    return float(np.mean(pos) / abs(np.mean(neg)))


def sharpe_ratio(monthly_rets, rf_monthly_arr):
    """夏普比率（算术年化法）。

    输入：月度策略收益 + 月度无风险利率。
    公式：mean(月超额) × 12 / [std(月超额, ddof=1) × √12]

    Parameters
    ----------
    monthly_rets : list or np.ndarray
        策略月度收益率序列。
    rf_monthly_arr : list or np.ndarray
        无风险月度利率序列（如 0.025/12）。

    Returns
    -------
    float
    """
    excess = np.array(monthly_rets) - np.array(rf_monthly_arr)
    excess = excess[~np.isnan(excess)]  # 防御: NaN 无风险利率过滤
    if len(excess) == 0:
        return np.nan  # 全量 NaN → 明确不可用, 避免静默遮断数据缺失
    ann_excess = np.mean(excess) * 12
    ann_vol = np.std(excess, ddof=1) * np.sqrt(12)
    if ann_vol == 0:
        return 0.0
    return float(ann_excess / ann_vol)


def information_ratio(strategy_rets, benchmark_rets):
    """信息比率。

    输入：策略月度收益 + 基准月度收益（长度须一致）。
    公式：mean(月超额) × 12 / [std(月超额, ddof=1) × √12]

    Returns
    -------
    float
    """
    excess = np.array(strategy_rets) - np.array(benchmark_rets)
    ann_excess = np.mean(excess) * 12
    te = np.std(excess, ddof=1) * np.sqrt(12)
    if te == 0:
        return 0.0
    return float(ann_excess / te)


def turnover(top_codes):
    """月均换手率。

    输入：每期持仓列表的列表。
    公式：mean(每月更换行业数 / 持仓行业数)

    Parameters
    ----------
    top_codes : list of list
        每期 Top N 的行业代码列表。

    Returns
    -------
    float
    """
    if len(top_codes) < 2:
        return 0.0
    changes = []
    for i in range(1, len(top_codes)):
        n_changed = len(set(top_codes[i]) - set(top_codes[i - 1]))
        changes.append(n_changed / len(top_codes[i]))
    return float(np.mean(changes))


# ═══════════════════════════════════════════════════════
# 聚合指标
# ═══════════════════════════════════════════════════════

def cal_all_metrics(rets, benchmark_rets=None, rf_arr=None):
    """计算全部回测指标（一站式输出）。

    Parameters
    ----------
    rets : list or np.ndarray
        策略月度收益率序列。
    benchmark_rets : list or np.ndarray, optional
        基准月度收益率（用于计算超额和 IR）。
    rf_arr : np.ndarray, optional
        月度无风险利率，默认 2.5%/12。

    Returns
    -------
    dict: {cum, ann, vol, sharpe, max_dd, wr, pl, ir, excess_ann,
           down_vol, sortino, calmar}
    """
    arr = np.array(rets)
    if rf_arr is None:
        rf_arr = np.full(len(arr), 0.025 / 12)

    cum = float(np.prod(1 + arr) - 1)
    ann = geo_annual(arr)
    vol = float(np.std(arr, ddof=1) * np.sqrt(12))
    sh = sharpe_ratio(arr, rf_arr)
    mdd = max_drawdown(arr)
    wr = float(np.mean(arr > 0))
    pl = pl_ratio(arr)

    ir = 0.0
    excess_ann = 0.0
    if benchmark_rets is not None:
        ir = information_ratio(arr, np.array(benchmark_rets))
        excess_ann = ann - geo_annual(benchmark_rets)

    # 下行波动率 & 索提诺比率 (NaN 安全: 清洗 rf_arr 后统一用于 downside 和年化)
    rf_arr_np = np.asarray(rf_arr, dtype=float)
    rf_ok = ~np.isnan(rf_arr_np)
    rf_annual = float(np.mean(rf_arr_np[rf_ok])) * 12 if rf_ok.any() else 0.025
    rf_safe = np.where(rf_ok, rf_arr_np, rf_annual / 12)
    downside = np.minimum(arr - rf_safe, 0)
    down_vol = float(np.std(downside, ddof=1) * np.sqrt(12)) if len(downside) > 0 else 0.0
    sortino = (ann - rf_annual) / down_vol if down_vol > 0 else 0.0

    # 卡玛比率
    calmar = ann / abs(mdd) if abs(mdd) > 0 else 0.0

    return {
        'cum': cum, 'ann': ann, 'vol': vol, 'sharpe': sh,
        'max_dd': mdd, 'wr': wr, 'pl': pl, 'ir': ir,
        'excess_ann': excess_ann,
        'down_vol': down_vol, 'sortino': sortino, 'calmar': calmar,
    }


# ═══════════════════════════════════════════════════════
# 报告统一出口（报告只调这里，禁止报告内联逐年/分段重算）
# ═══════════════════════════════════════════════════════

def report_metrics(rets, dates, benchmark_rets=None, is_end=None):
    """回测报告统一指标出口（唯一口径）。

    全区间 / 训练集 / 验证集 / 逐年 指标全部委托 cal_all_metrics 计算，
    报告脚本不得再内联 (1+prod)^(12/n)-1、(mean*12-rf)/(std*√12)、
    min(nav/peak-1) 等公式——一律从本函数返回值取数。

    Parameters
    ----------
    rets : list or np.ndarray
        策略月度收益率序列。
    dates : list
        与 rets 等长的日期序列（pd.Timestamp / str），用于训练/验证分割与逐年分组。
    benchmark_rets : list or np.ndarray, optional
        基准月度收益率（如等权行业），用于超额与 IR。
    is_end : pd.Timestamp or str, optional
        训练/验证分割点；None 表示不分割（train/val 返回 None）。

    Returns
    -------
    dict: {
        'full':   cal_all_metrics(...),
        'train':  cal_all_metrics(...) 或 None,
        'val':    cal_all_metrics(...) 或 None,
        'yearly': { 'YYYY': cal_all_metrics(...), ... },
    }
    """
    import pandas as pd
    arr = np.asarray(rets, dtype=float)
    bench = None if benchmark_rets is None else np.asarray(benchmark_rets, dtype=float)
    ds = pd.to_datetime(pd.Series(list(dates)))
    if len(ds) != len(arr):
        raise ValueError("dates 与 rets 长度不一致")

    out = {'full': cal_all_metrics(arr, bench)}

    if is_end is not None:
        is_end = pd.Timestamp(is_end)
        tr = (ds <= is_end).to_numpy()
        va = ~tr
        out['train'] = cal_all_metrics(arr[tr], bench[tr] if bench is not None else None) if tr.any() else None
        out['val'] = cal_all_metrics(arr[va], bench[va] if bench is not None else None) if va.any() else None
    else:
        out['train'] = None
        out['val'] = None

    years = ds.dt.year.to_numpy()
    yearly = {}
    for yr in sorted(set(years.tolist())):
        m = years == yr
        yearly[str(int(yr))] = cal_all_metrics(arr[m], bench[m] if bench is not None else None)
    out['yearly'] = yearly
    return out


# ═══════════════════════════════════════════════════════
# 因子评估指标
# ═══════════════════════════════════════════════════════

def cross_sectional_zscore(df: "pd.DataFrame") -> "pd.DataFrame":
    """截面 z-score 标准化（唯一标准实现）。

    口径：每月末取值 → 截面去均值 ÷ 截面标准差（ddof=0，总体标准差）。
    原因：每月 31 个行业是全量数据，非抽样，因此用总体标准差。

    Parameters
    ----------
    df : pd.DataFrame
        日频因子值，index=日期，columns=行业代码。

    Returns
    -------
    pd.DataFrame
        月频截面 z-score，index=月末日期，columns=行业代码。
    """
    import pandas as pd
    m = df.resample('ME').last()
    return m.subtract(m.mean(axis=1), axis=0).div(m.std(axis=1, ddof=0), axis=0)


def rank_ic(factor: np.ndarray, forward_return: np.ndarray) -> float:
    """Rank IC（Spearman 秩相关系数）。

    调用方必须自行确保 factor 已经 shift(1) 做好时间对齐，
    本函数只做纯数学计算，不做任何时间轴处理。

    ⛔ 硬约束：禁止从临时脚本或命令行直接调用 rank_ic 算 IC。
       所有因子 IC 评估必须通过 engine.eval_factor_ic() 完成。
       从 python -c / 临时脚本 / 非白名单模块调用本函数将直接报错。

    Parameters
    ----------
    factor : np.ndarray
        因子值序列（已对齐到同一时间点）。
    forward_return : np.ndarray
        对应未来收益序列。

    Returns
    -------
    float
    """
    # ── 运行时守卫：首次调用时判断来源，结果缓存避免热循环开销 ──
    if not hasattr(rank_ic, '_caller_checked'):
        rank_ic._caller_checked = True
        rank_ic._caller_allowed = False
        try:
            import os
            _allowed = {
                'engine.py', 'factor_evaluator.py', 'abnormal_turnover.py',
                'report_v1_full.py', 'report_v1_top5.py',
                '02_📁_因子研究.py',
            }
            for fi in __import__('inspect').stack()[1:]:
                fn = os.path.basename(fi.filename)
                if fn in _allowed:
                    rank_ic._caller_allowed = True
                    break
                if fn in ('<string>', '<stdin>', '<input>') or fn.startswith('<'):
                    break
        except Exception:
            rank_ic._caller_allowed = True  # 放行，不误杀

        if not rank_ic._caller_allowed:
            raise RuntimeError(
                "⛔ rank_ic() 被非白名单代码调用。\n"
                "   禁止从命令行 (python -c) 或临时脚本直接计算 IC。\n"
                "   所有因子 IC 评估必须通过 engine.eval_factor_ic() 完成。\n"
                "   如需评估因子，请运行 python factor/xxx.py（已内置 IC 输出）。"
            )
    # ── 守卫结束 ──

    from scipy import stats
    mask = ~(np.isnan(factor) | np.isnan(forward_return))
    if mask.sum() < 5:       # 最少 5 个有效行业（与报告 IC 循环守卫一致）
        return np.nan
    return float(stats.spearmanr(factor[mask], forward_return[mask])[0])


def ic_summary(ic_series) -> dict:
    """IC 序列聚合统计（唯一口径）。

    供报告使用，禁止报告内联 mean/std/ICIR/胜率 的重复计算。

    口径约定（与历史报告一致）：
      - 均值/标准差：总体口径 ddof=0（np.std 默认）
      - ICIR = mean / std
      - IC胜率 = 大于 0 的月份占比

    Parameters
    ----------
    ic_series : list or np.ndarray
        逐月 Rank IC 序列（可含 NaN，自动过滤）。

    Returns
    -------
    dict: {mean, std, icir, win_rate, n}
    """
    arr = np.asarray(ic_series, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) == 0:
        return {'mean': 0.0, 'std': 0.0, 'icir': 0.0, 'win_rate': 0.0, 'n': 0}
    mean = float(np.mean(arr))
    std = float(np.std(arr))
    return {
        'mean': mean,
        'std': std,
        'icir': float(mean / std) if std > 0 else 0.0,
        'win_rate': float(np.mean(arr > 0)),
        'n': int(len(arr)),
    }


# ═══════════════════════════════════════════════════════
# 可用指标清单（供 AI 自查）
# ═══════════════════════════════════════════════════════

AVAILABLE_METRICS = [
    # 基础指标
    {"name": "geo_annual",               "input": "月度收益率序列", "output": "float 几何年化收益率"},
    {"name": "max_drawdown",             "input": "月度收益率序列", "output": "float 最大回撤"},
    {"name": "max_drawdown_detail",      "input": "月度收益率 Series(date index)", "output": "dict{max_dd, peak_date, trough_date}"},
    {"name": "pl_ratio",                 "input": "月度收益率序列", "output": "float 盈亏比"},
    {"name": "sharpe_ratio",             "input": "月度策略收益 + 月度无风险利率", "output": "float 夏普比率"},
    {"name": "information_ratio",        "input": "策略收益 + 基准收益", "output": "float 信息比率"},
    {"name": "turnover",                 "input": "每期持仓列表的列表", "output": "float 月均换手率"},
    # 聚合指标
    {"name": "cal_all_metrics",          "input": "月度收益 + 可选基准收益 + 可选无风险利率", "output": "dict 全部回测指标"},
    # 因子评估
    {"name": "rank_ic",                  "input": "因子 array + 未来收益 array（调用方自行shift）", "output": "float Rank IC"},
]
