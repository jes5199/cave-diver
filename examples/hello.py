"""Minimal example: ask a question with context thresholds."""

import anyio

from cave_diver import Event, Threshold, run_agent


async def main():
    async for event in run_agent(
        prompt="What are the three laws of thermodynamics? Explain each briefly.",
        thresholds=[
            Threshold(50, "Half your context is used. Plan accordingly."),
            Threshold(25, "25% remaining. Start wrapping up."),
            Threshold(10, "CRITICAL: 10% left. Finish NOW."),
        ],
    ):
        match event:
            case Event(type="thinking_start"):
                print("[thinking...]", end="", flush=True)
            case Event(type="thinking_end"):
                print(" done", flush=True)
            case Event(type="text_delta", text=text):
                print(text, end="", flush=True)
            case Event(type="tool_use", name=name):
                print(f"\n[tool: {name}]", flush=True)
            case Event(type="tool_result", name=name):
                print(f"[tool result: {name}]", flush=True)
            case Event(type="threshold", pct=pct, message=message):
                print(f"\n>> THRESHOLD {pct}%: {message}", flush=True)
            case Event(type="result"):
                print("\n--- done ---", flush=True)
            case Event(type="context_exhausted"):
                print("\n--- context exhausted ---", flush=True)


anyio.run(main)
