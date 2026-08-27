"""Write an immutable, de-identified research run archive for the local Demo."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


STAGE_IDS = [
    "data_extract_store",
    "single_factor_research",
    "factor_improvement",
    "risk_rebalance",
    "strategy_iteration",
    "backtest_report",
    "version_record",
]


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def archive_research_run(payload: dict[str, Any], request: dict[str, Any], root: str | Path) -> dict[str, Any]:
    """Persist every stage's input/output plus a replayable run manifest.

    The archive contains derived demo results only. It intentionally does not
    write raw licensed data, access tokens, or browser state.
    """
    root_path = Path(root)
    run_id = f"local-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    run_dir = root_path / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    payload.setdefault("versioning", {})["run_id"] = run_id
    payload["versioning"]["archive_policy"] = "每次运行独立归档，不覆盖历史结果；仅保存脱敏输入、派生结果和阶段契约。"

    strategies = payload.get("strategies", {})
    factor_research = payload.get("factor_research", {})
    stages = {
        "data_extract_store": {
            "input": {"source": "synthetic", "asset_type": request.get("asset_type", "index"), "universe_id": request.get("universe_id", "synthetic_sector_8"), "start": request.get("start"), "end": request.get("end")},
            "output": {"data_manifest": payload.get("data_manifest", {}), "assets": payload.get("assets", [])},
        },
        "single_factor_research": {
            "input": {"factor_ids": list(factor_research), "sample_split": payload.get("config", {}).get("sample_split", {}), "factor_decisions": request.get("factor_decisions", {})},
            "output": {"factor_research": factor_research},
        },
        "factor_improvement": {
            "input": {
                "formula": payload.get("research_workflow", {}).get("composite_design", {}).get("formula"),
                "factor_weights": request.get("factor_weights", {}),
                "orthogonalization": payload.get("research_workflow", {}).get("composite_design", {}).get("orthogonalization"),
                "approved": request.get("composite_approved", False),
            },
            "output": {"composite": factor_research.get("composite_v1", {}), "strategy": strategies.get("composite", {})},
        },
        "risk_rebalance": {
            "input": {
                "cost_assumptions": payload.get("config", {}).get("cost_assumptions", {}),
                "risk_controls": {
                    "allow_short": False,
                    "max_gross_exposure": 1.0,
                    "top_n": request.get("top_n", 3),
                    "defensive_exposure": request.get("defensive_exposure", 0.5),
                    "signal_lag": request.get("signal_lag", 1),
                },
            },
            "output": {"strategy_evidence": {key: value.get("evidence", {}) for key, value in strategies.items()}},
        },
        "strategy_iteration": {
            "input": {"hypotheses": payload.get("strategy_iterations", []), "strategy_decision": request.get("strategy_decision")},
            "output": {"candidate_strategies": [{"id": key, "label": value.get("label"), "logic": value.get("logic")} for key, value in strategies.items()]},
        },
        "backtest_report": {
            "input": {"config": payload.get("config", {}), "strategy_ids": list(strategies)},
            "output": {"strategies": strategies, "quality": payload.get("research_workflow", {}).get("backtest_quality", {}), "independent_validation": payload.get("independent_validation", {})},
        },
        "version_record": {
            "input": {"config": payload.get("config", {}), "data_manifest": payload.get("data_manifest", {}), "parent_version": payload.get("versioning", {}).get("parent")},
            "output": {"versioning": payload.get("versioning", {})},
        },
    }
    stage_manifest: dict[str, Any] = {}
    for stage_id in STAGE_IDS:
        stage_dir = run_dir / stage_id
        stage_dir.mkdir()
        record = stages[stage_id]
        _write_json(stage_dir / "input.json", record["input"])
        _write_json(stage_dir / "output.json", record["output"])
        stage_manifest[stage_id] = {"input": str(Path(stage_id) / "input.json"), "output": str(Path(stage_id) / "output.json"), "status": "completed"}
    _write_json(run_dir / "run-output.json", payload)
    manifest = {
        "schema_version": "research-run-archive-v1",
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": request,
        "stages": stage_manifest,
        "output": "run-output.json",
        "disclaimer": "本归档仅用于本地 Demo 验证，数据为合成示例，不代表真实收益。",
    }
    _write_json(run_dir / "run-manifest.json", manifest)
    return {"run_id": run_id, "path": str(run_dir), "manifest": str(run_dir / "run-manifest.json"), "stage_count": len(STAGE_IDS)}


def archive_decision(record: dict[str, Any], root: str | Path) -> dict[str, str]:
    """Persist a human decision as a separate append-only local record."""
    root_path = Path(root) / "decisions"
    root_path.mkdir(parents=True, exist_ok=True)
    decision_id = f"decision-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    path = root_path / f"{decision_id}.json"
    _write_json(path, {"schema_version": "research-decision-v1", "decision_id": decision_id, "created_at": datetime.now(timezone.utc).isoformat(), **record})
    return {"decision_id": decision_id, "path": str(path)}


def list_research_history(root: str | Path, *, limit: int = 50) -> dict[str, Any]:
    """Return a bounded, newest-first index of local runs and decisions."""
    root_path = Path(root)
    runs: list[dict[str, Any]] = []
    for path in sorted(root_path.glob("local-*/run-manifest.json"), reverse=True)[:limit]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            runs.append({
                "run_id": value.get("run_id"),
                "created_at": value.get("created_at"),
                "input": value.get("input", {}),
                "stage_count": len(value.get("stages", {})),
            })
        except (OSError, json.JSONDecodeError):
            continue
    decisions: list[dict[str, Any]] = []
    decision_root = root_path / "decisions"
    for path in sorted(decision_root.glob("decision-*.json"), reverse=True)[:limit]:
        try:
            decisions.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return {"runs": runs, "decisions": decisions}


def load_archived_run(root: str | Path, run_id: str) -> dict[str, Any]:
    """Load one archived run without allowing traversal outside the run root."""
    if not re.fullmatch(r"local-[0-9TZ]+-[0-9a-f]{8}", run_id):
        raise ValueError("运行号格式无效")
    run_dir = Path(root) / run_id
    path = run_dir / "run-output.json"
    if not path.is_file():
        raise FileNotFoundError(run_id)
    payload = json.loads(path.read_text(encoding="utf-8"))
    manifest_path = run_dir / "run-manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["archived_input"] = manifest.get("input", {})
    payload["archive"] = {"run_id": run_id, "path": str(run_dir), "manifest": str(manifest_path)}
    return payload
