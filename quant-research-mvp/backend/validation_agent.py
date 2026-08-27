"""Independent, deterministic checks for the portfolio Demo research contract.

The validator receives only structured inputs and computed artifacts.  It does
not reuse the research assistant's narrative, so a proposal cannot validate
itself by repeating its own conclusion.
"""
from __future__ import annotations

from datetime import date
from typing import Any


LEVEL_ORDER = {"green": 0, "yellow": 1, "red": 2}


def _finding(level: str, check_id: str, title: str, message: str) -> dict[str, str]:
    return {"level": level, "id": check_id, "title": title, "message": message}


def validate_research_contract(request: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Return a UI-ready validation report; red findings block progression."""
    findings: list[dict[str, str]] = []
    signal_lag = int(request.get("signal_lag", 1))
    if signal_lag < 1:
        findings.append(_finding("red", "same_period_execution", "同期开仓", "信号滞后必须至少为 1 期，不能用本期收盘信号按本期收盘成交。"))
    else:
        findings.append(_finding("green", "same_period_execution", "时间顺序", f"信号滞后 {signal_lag} 期，未发现同期开仓。"))

    date_keys = ["start", "train_end", "validation_start", "validation_end", "end"]
    try:
        points = [date.fromisoformat(str(request[key])) for key in date_keys]
        if not (points[0] < points[1] < points[2] <= points[3] < points[4]):
            raise ValueError
        findings.append(_finding("green", "sample_split", "样本隔离", "训练、验证与留出区间按时间顺序分离。"))
    except (KeyError, TypeError, ValueError):
        findings.append(_finding("red", "sample_split", "样本切分错误", "训练、验证与留出区间缺失、重叠或顺序不合法。"))

    cost_model = str(request.get("cost_model") or "")
    if cost_model == "zero_cost_warning":
        findings.append(_finding("yellow", "zero_cost", "交易成本为 0", "允许作为敏感性测试继续，但不能静默作为正式候选版本。"))
    elif not cost_model:
        findings.append(_finding("red", "cost_model", "成本口径缺失", "必须绑定交易成本模型后才能回测。"))
    else:
        findings.append(_finding("green", "cost_model", "成本已计入", "运行记录已绑定交易成本模型。"))

    orthogonalization = payload.get("research_workflow", {}).get("composite_design", {}).get("orthogonalization")
    findings.append(_finding(
        "green" if orthogonalization else "yellow",
        "orthogonalization",
        "正交化口径" if orthogonalization else "正交化信息不足",
        str(orthogonalization or "未找到正交化顺序，建议在综合因子审批前补充。"),
    ))

    checks = payload.get("research_workflow", {}).get("backtest_quality", {}).get("checks", [])
    failed = [item for item in checks if item.get("status") != "passed"]
    if failed:
        findings.append(_finding("red", "golden_checks", "固定结果检查失败", f"{len(failed)} 项规则或基准结果检查未通过。"))
    else:
        findings.append(_finding("green", "golden_checks", "固定结果一致", f"{len(checks)} 项规则与基准结果检查通过。"))

    versioning = payload.get("versioning", {})
    if not versioning.get("config_hash") or not versioning.get("data_hash"):
        findings.append(_finding("red", "artifact_identity", "运行身份不完整", "配置指纹或数据指纹缺失，结果不可作为候选版本。"))
    else:
        findings.append(_finding("green", "artifact_identity", "运行身份已绑定", "配置指纹和数据指纹已进入运行记录。"))

    level = max((item["level"] for item in findings), key=lambda item: LEVEL_ORDER[item], default="green")
    blockers = [item for item in findings if item["level"] == "red"]
    warnings = [item for item in findings if item["level"] == "yellow"]
    summary = "存在阻断问题，不能进入下一阶段。" if blockers else ("验证通过，但有研究风险需要确认。" if warnings else "独立验证通过，可以进入下一阶段。")
    return {"agent": "independent_validator_v1", "level": level, "blocking": bool(blockers), "summary": summary, "findings": findings}
