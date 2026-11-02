from __future__ import annotations
from pathlib import Path
import yaml

DEFAULT = Path(__file__).resolve().parents[2] / "config" / "default.yaml"


def load_config(path: str | Path | None = None) -> dict:
    with open(path or DEFAULT, encoding="utf-8") as f:
        return yaml.safe_load(f)
