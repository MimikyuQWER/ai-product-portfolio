# -*- coding: utf-8 -*-
"""Dependency-light local run recorder; no service or database required."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

import numpy as np
import pandas as pd
import yaml

from backtest.result import BacktestResult
from core.metrics import METRICS_VERSION


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=_json_default, separators=(",", ":")).encode("utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class RunRecorder:
    def __init__(self, root: str | Path = "artifacts/runs", *, project_root: str | Path | None = None) -> None:
        self.root = Path(root).resolve()
        self.project_root = Path(project_root or Path(__file__).resolve().parents[1]).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def make_run_id(config: Mapping[str, Any], data_manifest: Mapping[str, Any], *, timestamp: str | None = None) -> str:
        stamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        digest = hashlib.sha256(_canonical_json({"config": config, "data": data_manifest})).hexdigest()[:12]
        return f"{stamp}_{digest}"

    def _git(self, *args: str) -> str:
        try:
            result = subprocess.run(
                ["git", *args], cwd=self.project_root, capture_output=True,
                text=True, encoding="utf-8", errors="replace", check=False,
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except OSError:
            return ""

    @staticmethod
    def _dependencies() -> dict[str, str]:
        result: dict[str, str] = {}
        for name in ("numpy", "pandas", "pyarrow", "scipy", "PyYAML"):
            try:
                result[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                continue
        return result

    @staticmethod
    def _write_json(path: Path, value: Any) -> None:
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=_json_default) + "\n", encoding="utf-8")

    def record_backtest(
        self,
        result: BacktestResult,
        *,
        effective_config: Mapping[str, Any],
        data_manifest: Mapping[str, Any],
        run_id: str | None = None,
        entrypoint: str = "backtest.runner.run_backtest",
    ) -> Path:
        run_id = run_id or self.make_run_id(effective_config, data_manifest)
        final_dir = self.root / run_id
        if final_dir.exists():
            raise FileExistsError(f"run already exists and will not be overwritten: {final_dir}")
        temp_dir = self.root / f".{run_id}.tmp-{uuid4().hex}"
        temp_dir.mkdir()
        started = datetime.now().astimezone()
        try:
            (temp_dir / "effective_config.yaml").write_text(
                yaml.safe_dump(dict(effective_config), allow_unicode=True, sort_keys=True), encoding="utf-8"
            )
            self._write_json(temp_dir / "data_manifest.json", data_manifest)
            self._write_json(temp_dir / "metrics.json", result.metrics)
            result.net_returns.to_frame().to_parquet(temp_dir / "returns.parquet")
            result.nav.to_frame().to_parquet(temp_dir / "nav.parquet")
            result.target_weights.to_parquet(temp_dir / "target_weights.parquet")
            result.executed_weights.to_parquet(temp_dir / "executed_weights.parquet")
            result.costs.to_frame().to_parquet(temp_dir / "costs.parquet")
            result.holdings.to_parquet(temp_dir / "holdings.parquet")

            dirty = self._git("status", "--porcelain")
            patch = self._git("diff", "--binary", "HEAD")
            artifacts = {
                path.name: _sha256(path)
                for path in sorted(temp_dir.iterdir()) if path.name != "manifest.json"
            }
            manifest = {
                "run_id": run_id,
                "status": "success",
                "entrypoint": entrypoint,
                "started_at": started.isoformat(),
                "finished_at": datetime.now().astimezone().isoformat(),
                "git_commit": self._git("rev-parse", "HEAD"),
                "git_dirty": bool(dirty),
                "git_status": dirty.splitlines(),
                "git_patch_sha256": hashlib.sha256(patch.encode("utf-8")).hexdigest(),
                "python": sys.version,
                "platform": platform.platform(),
                "dependencies": self._dependencies(),
                "metrics_version": METRICS_VERSION,
                "config_sha256": hashlib.sha256(_canonical_json(effective_config)).hexdigest(),
                "data_manifest_sha256": hashlib.sha256(_canonical_json(data_manifest)).hexdigest(),
                "artifact_sha256": artifacts,
            }
            self._write_json(temp_dir / "manifest.json", manifest)
            os.rename(temp_dir, final_dir)
            return final_dir
        except Exception:
            for path in temp_dir.iterdir():
                path.unlink()
            temp_dir.rmdir()
            raise

