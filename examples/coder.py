"""Example: agent with coder tools that can read/write files and run commands."""

import anyio

from cave_diver import Event, Threshold, run_agent
from cave_diver.tools.coder import coder_tools


async def main():
    async for event in run_agent(
        prompt="List the Python files in the current directory, then read the pyproject.toml and summarize what this project does.",
        tools=coder_tools,
        thresholds=[
            Threshold(50, "You've used half your context window. Plan accordingly."),
            Threshold(25, "25% context remaining. Start wrapping up."),
            Threshold(10, "CRITICAL: 10% context left. Finish your current task NOW."),
        ],
        system_prompt="You are a helpful coding assistant. Use the available tools to explore and understand codebases.",
    ):
        match event:
            case Event(type="thinking_start"):
                print("[thinking...]", end="", flush=True)
            case Event(type="thinking_end"):
                print(" done", flush=True)
            case Event(type="text_delta", text=text):
                print(text, end="", flush=True)
            case Event(type="tool_use", name=name):
                print(f"\n  > {name}", end="", flush=True)
            case Event(type="tool_result", name=name, result=result):
                preview = (result or "")[:80]
                print(f" -> {preview}", flush=True)
            case Event(type="threshold", pct=pct, message=message):
                print(f"\n>> THRESHOLD {pct}%: {message}", flush=True)
            case Event(type="result"):
                print("\n", flush=True)
            case Event(type="context_exhausted"):
                print("\n--- context exhausted ---", flush=True)


anyio.run(main)
