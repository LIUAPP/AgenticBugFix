"""Command line entry point for the buggy demo app."""

from __future__ import annotations

from app.core.processor import summarize_batch
from app.data.loader import load_measurements


def main() -> None:
    dataset = load_measurements()
    print("Daily summaries:")
    for day, measurements in dataset.items():
        summary = summarize_batch(day, measurements)
        print(f" - {summary['batch']}: count={summary['count']}, average={summary['average']:.2f}")


if __name__ == "__main__":
    main()
