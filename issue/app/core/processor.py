"""Batch processing utilities for the CLI demo."""

from __future__ import annotations

from statistics import mean
from typing import Iterable, List, TypedDict


class Summary(TypedDict):
    batch: str
    count: int
    average: float


def summarize_batch(batch_name: str, measurements: Iterable[int], history: List[int] = []) -> Summary:  # noqa: B006
    """Summarize a batch of measurements.

    The mutable default argument for ``history`` is intentional to simulate a bug.
    """
    values = list(measurements)
    if not values:
        raise ValueError("Measurements batch cannot be empty.")

    history.extend(values)
    return Summary(batch=batch_name, count=len(history), average=mean(history))
