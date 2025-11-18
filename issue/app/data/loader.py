from dataclasses import dataclass
from typing import List


@dataclass
class Visit:
    user: str
    page: str
    duration: int  # seconds


def load_user_visits() -> List[Visit]:
    """Return a small deterministic dataset for reproducing bugs."""
    return [
        Visit(user="alice", page="/", duration=5),
        Visit(user="alice", page="/search", duration=15),
        Visit(user="bob", page="/", duration=3),
        Visit(user="bob", page="/products", duration=7),
    ]
