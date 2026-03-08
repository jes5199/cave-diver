"""Optional coder tool kit: read_file, write_file, list_files, grep, bash."""

from __future__ import annotations

import asyncio
import glob as globmod
import os
import re

from ..types import Tool


def _read_file(input: dict) -> str:
    path = input["file_path"]
    try:
        with open(path) as f:
            content = f.read()
        # Truncate very large files
        if len(content) > 100_000:
            return content[:100_000] + f"\n... (truncated, {len(content)} chars total)"
        return content
    except (OSError, ValueError) as e:
        return f"Error reading {path}: {e}"


def _write_file(input: dict) -> str:
    path = input["file_path"]
    content = input["content"]
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return f"Wrote {len(content)} chars to {path}"
    except OSError as e:
        return f"Error writing {path}: {e}"


def _list_files(input: dict) -> str:
    pattern = input.get("pattern", "**/*")
    path = input.get("path", ".")
    try:
        matches = sorted(globmod.glob(os.path.join(path, pattern), recursive=True))
        if not matches:
            return "No files matched."
        # Limit output
        if len(matches) > 200:
            return "\n".join(matches[:200]) + f"\n... ({len(matches)} total)"
        return "\n".join(matches)
    except OSError as e:
        return f"Error: {e}"


def _grep(input: dict) -> str:
    pattern = input["pattern"]
    path = input.get("path", ".")
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"Invalid regex: {e}"

    results = []
    for root, _, files in os.walk(path):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, errors="replace") as f:
                    for i, line in enumerate(f, 1):
                        if regex.search(line):
                            results.append(f"{fpath}:{i}: {line.rstrip()}")
                            if len(results) >= 200:
                                results.append("... (truncated at 200 matches)")
                                return "\n".join(results)
            except (OSError, ValueError):
                continue
    if not results:
        return "No matches found."
    return "\n".join(results)


async def _bash(input: dict) -> str:
    command = input["command"]
    timeout = input.get("timeout", 30)
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode(errors="replace")
        if stderr:
            output += "\nSTDERR:\n" + stderr.decode(errors="replace")
        if proc.returncode != 0:
            output += f"\n(exit code {proc.returncode})"
        # Truncate large output
        if len(output) > 50_000:
            output = output[:50_000] + "\n... (truncated)"
        return output
    except asyncio.TimeoutError:
        return f"Command timed out after {timeout}s"
    except OSError as e:
        return f"Error: {e}"


read_file = Tool(
    name="read_file",
    description="Read the contents of a file at the given path.",
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute or relative path to the file",
            },
        },
        "required": ["file_path"],
    },
    handler=_read_file,
)

write_file = Tool(
    name="write_file",
    description="Write content to a file, creating directories as needed.",
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to write to",
            },
            "content": {
                "type": "string",
                "description": "Content to write",
            },
        },
        "required": ["file_path", "content"],
    },
    handler=_write_file,
)

list_files = Tool(
    name="list_files",
    description="List files matching a glob pattern.",
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern (default: **/*)",
                "default": "**/*",
            },
            "path": {
                "type": "string",
                "description": "Base directory (default: .)",
                "default": ".",
            },
        },
    },
    handler=_list_files,
)

grep = Tool(
    name="grep",
    description="Search file contents with a regex pattern. Returns matching lines with file paths and line numbers.",
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regex pattern to search for",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in (default: .)",
                "default": ".",
            },
        },
        "required": ["pattern"],
    },
    handler=_grep,
)

bash = Tool(
    name="bash",
    description="Execute a shell command and return its output.",
    input_schema={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 30)",
                "default": 30,
            },
        },
        "required": ["command"],
    },
    handler=_bash,
)

coder_tools: list[Tool] = [read_file, write_file, list_files, grep, bash]
