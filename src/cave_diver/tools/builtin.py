from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ..types import Tool

if TYPE_CHECKING:
    from ..context import ContextTracker


def make_check_context_tool(tracker: ContextTracker) -> Tool:
    """Create the built-in check_context_remaining tool."""

    def handler(input: dict) -> str:
        return json.dumps(tracker.status_dict())

    return Tool(
        name="check_context_remaining",
        description=(
            "Check how much of the context window has been used. "
            "Returns used_pct, remaining_pct, and remaining_tokens. "
            "Use this to plan your work and decide when to wrap up."
        ),
        input_schema={
            "type": "object",
            "properties": {},
        },
        handler=handler,
    )
