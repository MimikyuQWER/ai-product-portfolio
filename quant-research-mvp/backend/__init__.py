"""Self-contained, synthetic portfolio demo backend."""

import sys
from pathlib import Path

_VENDOR_ROOT = Path(__file__).resolve().parents[1] / "vendor"
if str(_VENDOR_ROOT) not in sys.path:
    sys.path.insert(0, str(_VENDOR_ROOT))

from .demo_pipeline import build_demo_payload, run_demo_pipeline

__all__ = ["build_demo_payload", "run_demo_pipeline"]
