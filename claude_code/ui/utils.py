"""UI utility functions for text sanitization and tool summarization"""

from __future__ import annotations

import json
import os
import re
from typing import List, Tuple


ANSI_ESCAPE_RE = re.compile(
    r"\x1b(?:\][^\x07\x1b]*(?:\x07|\x1b\\)|\[[0-?]*[ -/]*[@-~]|[@-Z\\-_])"
)
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_terminal_text(text: str) -> str:
    """Strip ANSI/control sequences that can corrupt terminal rendering."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = ANSI_ESCAPE_RE.sub("", normalized)
    normalized = CONTROL_CHAR_RE.sub("", normalized)
    return normalized


def truncate_preview_line(text: str, max_width: int = 88) -> str:
    """Trim a single preview line to a stable width."""
    expanded = sanitize_terminal_text(text).expandtabs(2)
    if len(expanded) <= max_width:
        return expanded
    return expanded[: max_width - 3] + "..."


def summarize_tool_result(
    tool_name: str,
    tool_input: dict,
    result: str,
    is_error: bool,
) -> Tuple[str, List[str]]:
    """Build a compact, always-visible summary for a tool result."""
    lines = sanitize_terminal_text(result).splitlines()
    trimmed_lines = [line for line in lines if line.strip()]

    if is_error:
        summary = truncate_preview_line(
            trimmed_lines[0] if trimmed_lines else "Tool failed"
        )
        preview = [truncate_preview_line(line) for line in trimmed_lines[1:5]]
        return summary, preview

    if tool_name == "Read":
        match = re.search(r"Lines:\s*(\d+)-(\d+)\s+of\s+(\d+)", result)
        file_name = os.path.basename(tool_input.get("file_path", "")) or "file"
        if match:
            start_line = int(match.group(1))
            end_line = int(match.group(2))
            total_lines = int(match.group(3))
            count = end_line - start_line + 1
            summary = f"Read {count} line{'s' if count != 1 else ''} from {file_name} ({start_line}-{end_line} of {total_lines})"
        else:
            summary = f"Read {file_name}"
        preview_source = lines[3:] if len(lines) > 3 else []
        preview = [
            truncate_preview_line(line) for line in preview_source[:5] if line.strip()
        ]
        return summary, preview

    if tool_name in {"Glob", "Grep"}:
        summary = truncate_preview_line(
            trimmed_lines[0] if trimmed_lines else f"{tool_name} completed"
        )
        preview = [truncate_preview_line(line) for line in trimmed_lines[1:6]]
        return summary, preview

    if tool_name in {"Write", "Edit"}:
        summary = truncate_preview_line(
            trimmed_lines[0] if trimmed_lines else f"{tool_name} completed"
        )
        return summary, []

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if command:
            summary = f"Ran: {truncate_preview_line(command, 64)}"
        else:
            summary = "Command completed"
        preview = [truncate_preview_line(line) for line in trimmed_lines[:6]]
        if len(trimmed_lines) > 6:
            preview.append(f"... ({len(trimmed_lines) - 6} more lines)")
        return summary, preview

    summary = truncate_preview_line(
        trimmed_lines[0] if trimmed_lines else f"{tool_name} completed"
    )
    preview = [truncate_preview_line(line) for line in trimmed_lines[1:5]]
    return summary, preview


def summarize_tool_use(tool_name: str, tool_input: dict) -> str:
    """Build a compact one-line summary for a tool invocation."""
    if "command" in tool_input:
        return f"{tool_name}: {truncate_preview_line(str(tool_input['command']), 64)}"
    if "file_path" in tool_input:
        file_path = str(tool_input["file_path"])
        file_name = os.path.basename(file_path) or file_path
        return f"{tool_name}: {truncate_preview_line(file_name, 64)}"
    if "pattern" in tool_input:
        return f"{tool_name}: {truncate_preview_line(str(tool_input['pattern']), 64)}"
    if tool_input:
        keys = list(tool_input.keys())
        preview = ", ".join(keys[:3])
        if len(keys) > 3:
            preview += ", ..."
        return f"{tool_name}: {preview}"
    return tool_name


def format_tool_input_details(tool_input: dict) -> List[str]:
    """Format tool input parameters for a collapsible details section."""
    detail_lines: List[str] = []

    for key, value in tool_input.items():
        if isinstance(value, (dict, list, bool, int, float)) or value is None:
            raw_value = json.dumps(value, ensure_ascii=True)
        else:
            raw_value = str(value)

        value_lines = sanitize_terminal_text(raw_value).splitlines() or [""]
        detail_lines.append(f"{key}: {truncate_preview_line(value_lines[0], 104)}")

        for line in value_lines[1:4]:
            detail_lines.append(f"  {truncate_preview_line(line, 102)}")

        if len(value_lines) > 4:
            detail_lines.append("  ...")

    return detail_lines
