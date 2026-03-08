from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import AsyncIterator
from typing import Any

import anthropic

from .context import ContextTracker
from .tools.builtin import make_check_context_tool
from .types import Event, Threshold, Tool


async def run_agent(
    prompt: str,
    *,
    tools: list[Tool] | None = None,
    thresholds: list[Threshold] | None = None,
    model: str = "claude-opus-4-6",
    system_prompt: str | None = None,
    max_tokens: int = 8192,
    context_window: int = 200_000,
    thinking: dict[str, Any] | None = None,
) -> AsyncIterator[Event]:
    """Run an agent loop, yielding events as they occur.

    This is an async generator. Use it with `async for event in run_agent(...)`.
    """
    if thinking is None:
        # Adaptive thinking only works on Opus 4.6 and Sonnet 4.6
        if "haiku" in model or "sonnet-4-0" in model or "opus-4-0" in model:
            thinking = {"type": "disabled"}
        else:
            thinking = {"type": "adaptive"}

    tracker = ContextTracker(context_window, thresholds or [])
    context_tool = make_check_context_tool(tracker)

    all_tools = [context_tool] + (tools or [])
    tool_map: dict[str, Tool] = {t.name: t for t in all_tools}

    client = anthropic.AsyncAnthropic()

    messages: list[dict[str, Any]] = [
        {"role": "user", "content": prompt},
    ]

    api_tools = [t.to_api_param() for t in all_tools]

    while True:
        # --- Stream the API call ---
        yield Event(type="turn_start")

        create_kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
            "tools": api_tools,
        }
        if thinking.get("type") != "disabled":
            create_kwargs["thinking"] = thinking
        if system_prompt:
            create_kwargs["system"] = system_prompt

        try:
            async with client.messages.stream(**create_kwargs) as stream:
                current_block_type: str | None = None
                async for event in stream:
                    if event.type == "content_block_start":
                        current_block_type = event.content_block.type
                        if current_block_type == "thinking":
                            yield Event(type="thinking_start")
                        elif current_block_type == "tool_use":
                            yield Event(
                                type="tool_use",
                                name=event.content_block.name,
                            )
                    elif event.type == "content_block_delta":
                        if event.delta.type == "thinking_delta":
                            yield Event(type="thinking_delta", text=event.delta.thinking)
                        elif event.delta.type == "text_delta":
                            yield Event(type="text_delta", text=event.delta.text)
                    elif event.type == "content_block_stop":
                        if current_block_type == "thinking":
                            yield Event(type="thinking_end")
                        current_block_type = None

                response = await stream.get_final_message()
        except anthropic.BadRequestError as e:
            if "context" in str(e).lower() or "token" in str(e).lower():
                yield Event(type="context_exhausted", used_pct=tracker.used_pct)
                return
            raise

        # --- Update context tracking ---
        tracker.update(response.usage.input_tokens)

        # --- Append assistant response ---
        messages.append({"role": "assistant", "content": response.content})

        # --- Check for context exhaustion ---
        if tracker.is_exhausted():
            # Extract any final text
            final_text = _extract_text(response.content)
            if final_text:
                yield Event(type="result", text=final_text, stop_reason="context_exhausted")
            yield Event(type="context_exhausted", used_pct=tracker.used_pct)
            return

        # --- Fire crossed thresholds ---
        crossed = tracker.check_thresholds()
        for event, msg in crossed:
            yield event

        # --- Handle stop reason ---
        if response.stop_reason == "end_turn":
            final_text = _extract_text(response.content)
            yield Event(type="result", text=final_text or "", stop_reason="end_turn")
            return

        if response.stop_reason == "tool_use":
            tool_results = await _execute_tools(response.content, tool_map)

            for tool_use_id, name, result in tool_results:
                yield Event(type="tool_result", name=name, result=result)

            # Build tool_result content blocks
            result_blocks: list[dict[str, Any]] = []
            result_by_id = {tid: r for tid, _, r in tool_results}
            for block in response.content:
                if block.type == "tool_use":
                    result_blocks.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_by_id.get(block.id, "No result"),
                    })

            messages.append({"role": "user", "content": result_blocks})

            # Inject threshold messages as a separate exchange after tool results
            if crossed:
                threshold_text = "\n\n".join(
                    f"[CONTEXT WARNING] {msg}" for _, msg in crossed
                )
                # Need an assistant turn between two user messages
                messages.append({
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Acknowledged."}],
                })
                messages.append({
                    "role": "user",
                    "content": threshold_text,
                })
            continue

        if response.stop_reason == "max_tokens":
            final_text = _extract_text(response.content)
            yield Event(type="result", text=final_text or "", stop_reason="max_tokens")
            return

        # Unknown stop reason — yield what we have and stop
        final_text = _extract_text(response.content)
        yield Event(
            type="result",
            text=final_text or "",
            stop_reason=response.stop_reason or "unknown",
        )
        return


def _extract_text(content: list[Any]) -> str | None:
    """Extract text from response content blocks."""
    texts = []
    for block in content:
        if block.type == "text":
            texts.append(block.text)
    return "\n".join(texts) if texts else None


async def _execute_tools(
    content: list[Any],
    tool_map: dict[str, Tool],
) -> list[tuple[str, str, str]]:
    """Execute all tool calls in the response. Returns (tool_use_id, name, result) tuples."""
    results = []
    for block in content:
        if block.type != "tool_use":
            continue
        tool = tool_map.get(block.name)
        if tool is None:
            results.append((block.id, block.name, f"Error: unknown tool '{block.name}'"))
            continue
        if tool.handler is None:
            results.append((block.id, block.name, f"Error: tool '{block.name}' has no handler"))
            continue
        try:
            result = tool.handler(block.input)
            if inspect.isawaitable(result):
                result = await result
            results.append((block.id, block.name, str(result)))
        except Exception as e:
            results.append((block.id, block.name, f"Error executing {block.name}: {e}"))
    return results
