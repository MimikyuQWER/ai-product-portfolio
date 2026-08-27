from pathlib import Path

from .demo_pipeline import build_demo_payload


if __name__ == "__main__":
    build_demo_payload(Path(__file__).resolve().parents[1] / "site" / "data" / "demo-run.json")
