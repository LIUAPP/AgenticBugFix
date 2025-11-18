"""Helpers to load demo measurement data for the CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List


def load_measurements(path: str | Path | None = None) -> Dict[str, List[int]]:
    """Return demo measurement batches from JSON."""
    dataset_path = Path(path) if path else Path(__file__).with_name("measurements.json")
    with dataset_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return {label: _coerce(values) for label, values in raw.items()}


def _coerce(values: Iterable[int]) -> List[int]:
    return [int(v) for v in values]
