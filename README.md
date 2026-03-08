# cave-diver

Context-aware Claude agent harness. Runs a Claude agent loop with configurable
warning messages as context fills up, instead of automatic compaction.

## Why

Compaction silently summarizes your conversation history. Sometimes you want the
agent to *know* it's running out of room and plan accordingly. cave-diver gives
the agent a `check_context_remaining` tool and injects custom warning messages
at configurable thresholds.

## Install

```bash
uv add cave-diver
```

Requires Python 3.14+ and an `ANTHROPIC_API_KEY` environment variable.

## Quick start

```python
import anyio
from cave_diver import run_agent, Event, Threshold

async def main():
    async for event in run_agent(
        prompt="Write a detailed analysis of this codebase.",
        thresholds=[
            Threshold(50, "You've used half your context. Plan accordingly."),
            Threshold(25, "25% remaining. Start wrapping up."),
            Threshold(10, "CRITICAL: 10% left. Finish NOW."),
        ],
    ):
        match event:
            case Event(type="text_delta", text=t):
                print(t, end="", flush=True)
            case Event(type="threshold", pct=p):
                print(f"\n[warning at {p}% remaining]")
            case Event(type="result"):
                print()
            case Event(type="context_exhausted"):
                print("\n[context exhausted]")

anyio.run(main)
```

## Custom tools

```python
from cave_diver import Tool

weather = Tool(
    name="get_weather",
    description="Get weather for a city",
    input_schema={
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
    handler=lambda input: f"Sunny in {input['city']}",
)

async for event in run_agent(prompt="...", tools=[weather]):
    ...
```

Handlers can be sync or async.

## Coder tools

A batteries-included tool kit for working on codebases:

```python
from cave_diver.tools.coder import coder_tools

async for event in run_agent(
    prompt="Read the source files and summarize this project.",
    tools=coder_tools,
):
    ...
```

Includes: `read_file`, `write_file`, `list_files`, `grep`, `bash`.

## Events

The async generator yields `Event` objects with a `type` field:

| type | fields | description |
|------|--------|-------------|
| `turn_start` | | API call started |
| `thinking_start` | | Model began thinking |
| `thinking_delta` | `text` | Thinking token |
| `thinking_end` | | Thinking finished |
| `text_delta` | `text` | Response token |
| `tool_use` | `name` | Tool call started |
| `tool_result` | `name`, `result` | Tool call finished |
| `threshold` | `pct`, `message` | Context threshold crossed |
| `result` | `text`, `stop_reason` | Agent finished |
| `context_exhausted` | `used_pct` | Hard stop, context full |

## Configuration

| param | type | default | description |
|-------|------|---------|-------------|
| `prompt` | `str` | required | Initial user prompt |
| `tools` | `list[Tool]` | `[]` | Custom tools |
| `thresholds` | `list[Threshold]` | `[]` | Warning thresholds |
| `model` | `str` | `claude-opus-4-6` | Model ID |
| `system_prompt` | `str` | `None` | System prompt |
| `max_tokens` | `int` | `8192` | Max output tokens per response |
| `context_window` | `int` | `200000` | Context window size in tokens |
| `thinking` | `dict` | adaptive/auto | Thinking config |

The `check_context_remaining` tool is always available. It returns
`used_pct`, `remaining_pct`, and `remaining_tokens`.

## How it works

1. Streams each API call, yielding events as they happen
2. After each response, checks `input_tokens / context_window` against thresholds
3. Crossed thresholds inject their message as a user message before the next turn
4. If context usage hits 95%, yields `context_exhausted` and stops
5. The agent can also call `check_context_remaining` at any time to see where it stands
