"""Test: make Haiku keep going until context thresholds fire and it hits exhaustion.

Uses a small context_window (4000 tokens) to trigger thresholds quickly.
Logs events to exhaust_test.log, only printing key events to stdout.
"""

import anyio
from cave_diver import run_agent, Event, Threshold

LOG = open("exhaust_test.log", "w")


def log(msg: str) -> None:
    LOG.write(msg + "\n")
    LOG.flush()


async def main():
    text_chars = 0
    turns = 0

    async for event in run_agent(
        prompt=(
            "I want you to write a very long, detailed essay about the history of "
            "mathematics, starting from ancient civilizations. Cover as many topics "
            "as you can. Use the check_context_remaining tool periodically to monitor "
            "your usage. Do NOT stop until you are told to stop or run out of context."
        ),
        model="claude-haiku-4-5",
        max_tokens=4096,
        context_window=4000,  # artificially small to trigger thresholds fast
        thresholds=[
            Threshold(75, "[CONTEXT] 75% remaining. You have plenty of room, keep going."),
            Threshold(50, "[CONTEXT] 50% remaining. You're halfway through. Keep going but be aware."),
            Threshold(25, "[CONTEXT] 25% remaining. Start thinking about wrapping up."),
            Threshold(10, "[CONTEXT] CRITICAL: 10% remaining. Write a concluding paragraph NOW."),
        ],
    ):
        match event:
            case Event(type="turn_start"):
                turns += 1
                msg = f"[turn {turns}]"
                print(msg)
                log(msg)
            case Event(type="text_delta", text=text):
                text_chars += len(text or "")
                log(text or "")
            case Event(type="tool_use", name=name):
                msg = f"  [tool: {name}]"
                print(msg)
                log(msg)
            case Event(type="tool_result", name=name, result=result):
                msg = f"  [result: {result}]"
                print(msg)
                log(msg)
            case Event(type="threshold", pct=pct, message=message):
                msg = f"  >> THRESHOLD {pct}%: {message}"
                print(msg)
                log(msg)
            case Event(type="result", stop_reason=sr):
                msg = f"[DONE stop_reason={sr}, {turns} turns, {text_chars} chars of text]"
                print(msg)
                log(msg)
            case Event(type="context_exhausted", used_pct=pct):
                msg = f"[EXHAUSTED at {pct}% used, {turns} turns, {text_chars} chars]"
                print(msg)
                log(msg)
            case Event(type=t):
                log(f"[{t}]")

    LOG.close()


anyio.run(main)
