from __future__ import annotations
from pathlib import Path
import yaml

from .paths import config_dir


def load_config(path: str | Path | None = None) -> dict:
    with open(path or config_dir() / "default.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)
