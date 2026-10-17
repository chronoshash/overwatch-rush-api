"""Dataset loading and strict startup validation."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.models import Dataset

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_dataset(data_dir: Path | None = None) -> Dataset:
    """Load every JSON file, validate it and verify cross-references."""
    base = data_dir or DATA_DIR
    payload = {
        "game": _read_json(base / "game.json"),
        "heroes": _read_json(base / "heroes.json"),
        "roles": _read_json(base / "roles.json"),
        "modes": _read_json(base / "modes.json"),
        "maps": _read_json(base / "maps.json"),
    }
    dataset = Dataset.model_validate(payload)
    dataset.validate_references()
    return dataset


@lru_cache(maxsize=1)
def get_dataset() -> Dataset:
    return load_dataset()


def _read_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
