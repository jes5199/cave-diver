# cave-diver: Context-Aware Agent Harness

## Overview

A Python library that runs a Claude agent loop using the raw Anthropic API,
with explicit context management instead of compaction. The agent gets
configurable warning messages as context fills up, a tool to check remaining
context on demand, and full streaming event fidelity.

## Why raw API (not Agent SDK)

- **Per-turn injection**: inject threshold warnings between any two API calls,
  not just between high-level queries
- **No compaction**: compaction is opt-in at the API level; we simply don't
  enable it
- **Full streaming fidelity**: raw stream events distinguish thinking_start,
  thinking_delta, text_delta, tool_use — no blind awaits

## Core API

```python
from cave_diver import run_agent, Tool, Threshold, Event

async for event in run_agent(
    prompt="Refactor the auth module",
    tools=[...],
    thresholds=[
        Threshold(50, "Half your context is used. Plan accordingly."),
        Threshold(25, "25% remaining. Start wrapping up."),
        Threshold(10, "CRITICAL: 10% left. Finish NOW."),
    ],
    model="claude-opus-4-6",
    system_prompt="You are a coding assistant.",
    max_tokens=8192,
    context_window=200_000,
):
    match event:
        case Event(type="turn_start"):
            pass  # API call accepted
        case Event(type="thinking_start"):
            show_indicator()
        case Event(type="thinking_end"):
            hide_indicator()
        case Event(type="text_delta", text=t):
            print(t, end="", flush=True)
        case Event(type="tool_use", name=n):
            print(f"\n[tool: {n}]")
        case Event(type="threshold", pct=p, message=m):
            print(f"\n warning at {p}%")
        case Event(type="result", text=t):
            print(f"\n\nDone: {t}")
        case Event(type="context_exhausted"):
            print("\n\nContext exhausted.")
```

## Threshold System

- `Threshold` is a NamedTuple: `(pct: int, message: str)`
- `pct` is the percentage of context REMAINING (not used)
- Each threshold fires once, when remaining% drops at-or-below the value
- When fired: yield a `threshold` event, inject `message` as a user message
  before the next API call
- If multiple thresholds are crossed in a single turn, fire all of them in
  descending order (e.g., 50 -> 25 -> 10)
- Hard stop when context is exhausted (API error or harness estimate >95% used)

## Tool System

### Built-in tool: check_context_remaining

Always included. Returns:
```json
{"used_pct": 63, "remaining_pct": 37, "remaining_tokens": 74000}
```

### Custom tools

```python
weather_tool = Tool(
    name="get_weather",
    description="Get current weather for a location",
    input_schema={
        "type": "object",
        "properties": {
            "location": {"type": "string", "description": "City name"}
        },
        "required": ["location"],
    },
    handler=lambda input: f"Sunny in {input['location']}",
)
```

`Tool.handler` is a callable: `(dict) -> str`. Async handlers supported via
`async_handler`.

### Coder tools (optional)

```python
from cave_diver.tools.coder import coder_tools
# Includes: read_file, write_file, list_files, grep, bash
```

## Agent Loop

1. Build messages list: system prompt + user prompt
2. Stream request via `client.messages.stream()`
3. Yield streaming events (turn_start, thinking_start/end, text_delta)
4. Get final message via `.get_final_message()`
5. Check `response.usage.input_tokens / context_window` against thresholds
6. If new thresholds crossed: yield threshold events, inject messages
7. If `stop_reason == "tool_use"`: execute handlers, append results,
   yield tool_use events, go to step 2
8. If `stop_reason == "end_turn"`: yield result event, stop
9. If context exhausted: yield context_exhausted event, stop

## Event Types

| type               | fields              | when                              |
|--------------------|---------------------|-----------------------------------|
| turn_start         |                     | API call accepted                 |
| thinking_start     |                     | thinking block began              |
| thinking_delta     | text                | thinking token (optional to show) |
| thinking_end       |                     | thinking block done               |
| text_delta         | text                | response token                    |
| tool_use           | name, input         | tool call starting                |
| tool_result        | name, result        | tool call finished                |
| threshold          | pct, message        | threshold crossed                 |
| result             | text, stop_reason   | agent finished                    |
| context_exhausted  | used_pct            | hard stop                         |

## Configuration

| param           | type              | default           | description                        |
|-----------------|-------------------|-------------------|------------------------------------|
| prompt          | str               | required          | initial user prompt                |
| tools           | list[Tool]        | []                | custom tools                       |
| thresholds      | list[Threshold]   | []                | context warning thresholds         |
| model           | str               | "claude-opus-4-6" | model ID                           |
| system_prompt   | str               | None              | system prompt                      |
| max_tokens      | int               | 8192              | per-response max output tokens     |
| context_window  | int               | 200000            | context window size in tokens      |
| thinking        | dict              | {"type":"adaptive"} | thinking config                  |

## Project Structure

```
cave-diver/
  pyproject.toml          # uv project, anthropic dependency
  src/
    cave_diver/
      __init__.py         # exports run_agent, Tool, Threshold, Event
      types.py            # Tool, Threshold, Event dataclasses
      agent.py            # run_agent async generator + loop logic
      context.py          # context tracking, threshold checking
      tools/
        __init__.py
        builtin.py        # check_context_remaining
        coder.py          # read_file, write_file, list_files, grep, bash
```
