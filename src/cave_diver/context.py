from __future__ import annotations

from .types import Threshold, Event


class ContextTracker:
    """Tracks context usage and fires thresholds."""

    def __init__(self, context_window: int, thresholds: list[Threshold]) -> None:
        self.context_window = context_window
        # Sort thresholds descending by pct so we fire high ones first
        self.thresholds = sorted(thresholds, key=lambda t: t.pct, reverse=True)
        self.fired: set[int] = set()
        self.last_input_tokens: int = 0

    def update(self, input_tokens: int) -> None:
        self.last_input_tokens = input_tokens

    @property
    def used_pct(self) -> int:
        if self.context_window == 0:
            return 100
        return round(self.last_input_tokens / self.context_window * 100)

    @property
    def remaining_pct(self) -> int:
        return max(0, 100 - self.used_pct)

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.context_window - self.last_input_tokens)

    def check_thresholds(self) -> list[tuple[Event, str]]:
        """Return (event, message) pairs for newly crossed thresholds."""
        results = []
        for t in self.thresholds:
            if t.pct in self.fired:
                continue
            if self.remaining_pct <= t.pct:
                self.fired.add(t.pct)
                event = Event(type="threshold", pct=t.pct, message=t.message)
                results.append((event, t.message))
        return results

    def is_exhausted(self) -> bool:
        return self.used_pct >= 95

    def status_dict(self) -> dict[str, int]:
        return {
            "used_pct": self.used_pct,
            "remaining_pct": self.remaining_pct,
            "remaining_tokens": self.remaining_tokens,
        }
