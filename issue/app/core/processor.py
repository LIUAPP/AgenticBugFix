from typing import Dict, List

from app.data.loader import Visit


def aggregate_visit_durations(visits: List[Visit], totals: Dict[str, int] = {}) -> Dict[str, int]:
    """Aggregate total visit durations by user.

    BUG: the mutable default `totals` keeps values between calls, so aggregating
    more than once returns ever-growing numbers.
    """
    for visit in visits:
        totals[visit.user] = totals.get(visit.user, 0) + visit.duration
    return totals


def format_totals(totals: Dict[str, int]) -> str:
    lines = ["user,total_duration_seconds"]
    for user, total in sorted(totals.items()):
        lines.append(f"{user},{total}")
    return "\n".join(lines)
