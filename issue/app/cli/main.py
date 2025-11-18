import argparse

from app.core.processor import aggregate_visit_durations, format_totals
from app.data.loader import load_user_visits


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo CLI with a subtle bug.")
    parser.add_argument(
        "--repeat",
        type=int,
        default=2,
        help="How many times to recompute totals. The wrong numbers appear after the first run.",
    )
    args = parser.parse_args()

    visits = load_user_visits()

    for run_number in range(1, args.repeat + 1):
        totals = aggregate_visit_durations(visits)
        print(f"Run #{run_number}")
        print(format_totals(totals))
        print("-")


if __name__ == "__main__":
    main()
