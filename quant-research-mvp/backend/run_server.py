"""Serve the local Demo site and expose a small real run/archive API."""
from __future__ import annotations

import argparse
import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

# 支持把 portfolio_demo 单独拷贝到另一台电脑运行。
DEMO_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = DEMO_ROOT / "vendor"
if str(VENDOR_ROOT) not in sys.path:
    sys.path.insert(0, str(VENDOR_ROOT))

from core.contracts import BacktestConfig, SplitConfig

from .archive import archive_decision, archive_research_run, list_research_history, load_archived_run
from .demo_pipeline import build_synthetic_bundle, run_bundle_pipeline
from .validation_agent import validate_research_contract


ROOT = DEMO_ROOT
SITE = ROOT / "site"
RUNS = ROOT / "runs"
ALLOWED_STRATEGIES = {"momentum", "low_vol", "value", "composite", "momentum_timing", "equal_weight"}


def _json_response(handler: SimpleHTTPRequestHandler, status: int, value: dict) -> None:
    body = json.dumps(value, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _request_payload(handler: SimpleHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length > 100_000:
        raise ValueError("请求内容过大")
    raw = handler.rfile.read(length)
    value = json.loads(raw.decode("utf-8") or "{}")
    if not isinstance(value, dict):
        raise ValueError("请求必须是 JSON 对象")
    return value


class DemoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SITE), **kwargs)

    def log_message(self, format: str, *args) -> None:
        print(f"[demo] {self.address_string()} - {format % args}")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            _json_response(self, 200, {"status": "ok", "service": "local-quant-demo", "archive_root": str(RUNS)})
            return
        if path == "/api/research/history":
            _json_response(self, 200, {"status": "completed", **list_research_history(RUNS)})
            return
        if path.startswith("/api/research/run/"):
            run_id = path.rsplit("/", 1)[-1]
            try:
                _json_response(self, 200, {"status": "completed", "payload": load_archived_run(RUNS, run_id)})
            except ValueError as error:
                _json_response(self, 400, {"status": "failed", "error": str(error)})
            except FileNotFoundError:
                _json_response(self, 404, {"status": "failed", "error": "未找到该运行记录"})
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/research/decision":
            try:
                record = _request_payload(self)
                if record.get("decision") not in {"adopt", "adjust", "discard"}:
                    raise ValueError("决策必须是采纳、调整或废弃")
                for field, label in (("stage", "研究阶段"), ("object_id", "研究对象"), ("reason", "判断依据"), ("version", "版本号")):
                    if not str(record.get(field) or "").strip():
                        raise ValueError(f"{label}不能为空")
                result = archive_decision(record, RUNS)
                _json_response(self, 200, {"status": "completed", **result})
            except (ValueError, json.JSONDecodeError) as error:
                _json_response(self, 400, {"status": "failed", "error": str(error)})
            return
        if path != "/api/research/run":
            _json_response(self, 404, {"error": "接口不存在"})
            return
        try:
            request = _request_payload(self)
            strategies = request.get("strategy_ids") or ["composite", "momentum_timing", "equal_weight"]
            if not isinstance(strategies, list) or not strategies or not set(strategies).issubset(ALLOWED_STRATEGIES):
                raise ValueError("策略选择不在 Demo 支持范围内")
            start = str(request.get("start") or "2019-01-31")
            end = str(request.get("end") or "2025-12-31")
            signal_lag_raw = request.get("signal_lag")
            signal_lag = int(1 if signal_lag_raw is None else signal_lag_raw)
            if signal_lag < 1:
                raise ValueError("信号滞后至少为 1 期")
            train_end = str(request.get("train_end") or "2022-12-31")
            validation_end = str(request.get("validation_end") or "2024-12-31")
            split_config = SplitConfig(
                train_start=start,
                train_end=train_end,
                validation_start=str(request.get("validation_start") or "2023-01-31"),
                validation_end=validation_end,
                name="wealth_demo_train_validation_holdout",
                exposure_note="留出集只用于最终复核，不参与因子权重调整",
            )
            split_config.validate()
            weights = request.get("factor_weights") or {
                "momentum_6m": 0.5,
                "low_vol_orthogonal": 0.3,
                "value_orthogonal": 0.2,
            }
            if not isinstance(weights, dict) or set(weights) != {
                "momentum_6m", "low_vol_orthogonal", "value_orthogonal"
            }:
                raise ValueError("综合因子权重字段不完整")
            top_n_raw = request.get("top_n")
            top_n = int(3 if top_n_raw is None else top_n_raw)
            if top_n < 1:
                raise ValueError("持仓数量至少为 1")
            defensive_exposure = float(request.get("defensive_exposure") if request.get("defensive_exposure") is not None else 0.5)
            bundle = build_synthetic_bundle()
            manifest = dict(bundle.dataset_manifest)
            manifest["asset_type"] = str(request.get("asset_type") or "index")
            manifest["universe_id"] = str(request.get("universe_id") or "synthetic_sector_8")
            bundle.dataset_manifest = manifest
            config = BacktestConfig(
                start=start,
                end=end,
                rebalance_frequency=str(request.get("frequency") or "monthly"),
                signal_lag=signal_lag,
                benchmark_id="equal_weight",
                cost_model_id=str(request.get("cost_model") or "demo_linear_5bp_buy_10bp_sell"),
            )
            payload = run_bundle_pipeline(
                bundle,
                strategy_ids=strategies,
                run_config=config,
                split_config=split_config,
                composite_weights={key: float(value) for key, value in weights.items()},
                top_n=top_n,
                defensive_exposure=defensive_exposure,
            )
            validation = validate_research_contract(request, payload)
            payload["independent_validation"] = validation
            if validation["blocking"]:
                _json_response(self, 422, {"status": "blocked", "error": validation["summary"], "validation": validation})
                return
            archive = archive_research_run(payload, request, RUNS)
            payload["archive"] = archive
            _json_response(self, 200, {"status": "completed", "archive": archive, "payload": payload})
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            _json_response(self, 400, {"status": "failed", "error": str(error)})
        except Exception as error:  # pragma: no cover - defensive API boundary
            _json_response(self, 500, {"status": "failed", "error": f"运行失败：{error}"})


def parse_port(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="启动本地量化研究 Demo 服务")
    parser.add_argument("legacy_port", nargs="?", type=int, help="兼容旧的位置端口参数")
    parser.add_argument("--port", dest="named_port", type=int, help="服务端口，默认 8765")
    args = parser.parse_args(argv)
    port = args.named_port if args.named_port is not None else args.legacy_port
    return port if port is not None else 8765


def main() -> None:
    port = parse_port()
    RUNS.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", port), DemoHandler)
    print(f"Demo server: http://127.0.0.1:{port}/")
    print(f"Archive root: {RUNS}")
    server.serve_forever()


if __name__ == "__main__":
    main()
