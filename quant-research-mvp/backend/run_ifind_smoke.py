"""Run a small live iFinD smoke and save metadata/results without raw prices."""
from __future__ import annotations

import json
from pathlib import Path

from .ifind_adapter import run_ifind_smoke


if __name__ == "__main__":
    output = Path(__file__).resolve().parents[1] / "validation" / "ifind_smoke_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    report = run_ifind_smoke(
        codes=["000300.SH", "000905.SH", "000852.SH", "000922.CSI", "000821.CSI"],
        start="2024-01-01",
        end="2025-12-31",
    )
    report["disclaimer"] = "This is a local iFinD smoke report. It contains metadata and derived metrics only; no raw prices or credentials are shipped."
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
