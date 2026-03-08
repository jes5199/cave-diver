from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, NamedTuple


class Threshold(NamedTuple):
    """A context warning threshold.

    pct: percentage of context REMAINING (not used) at which to fire.
    message: injected as a user message when the threshold is crossed.
    """

    pct: int
    message: str


@dataclass
class Tool:
    """A tool the agent can call."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], str | Awaitable[str]] | None = None

    def to_api_param(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass
class Event:
    """An event yielded by the agent loop."""

    type: str
    text: str | None = None
    name: str | None = None
    input: dict[str, Any] | None = None
    result: str | None = None
    pct: int | None = None
    message: str | None = None
    stop_reason: str | None = None
    used_pct: int | None = None
