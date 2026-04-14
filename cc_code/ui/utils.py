"""UI utility functions for text sanitization and tool summarization"""

from __future__ import annotations

import json
import os
import re
from typing import Iterable, List, Tuple

# Configuration constants
TOOL_RESULT_TRUNCATE_LENGTH = 500
PREVIEW_LINE_MAX_WIDTH = 88
COMMAND_PREVIEW_MAX_WIDTH = 64
DETAIL_LINE_MAX_WIDTH = 104


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


def truncate_preview_line(text: str, max_width: int = PREVIEW_LINE_MAX_WIDTH) -> str:
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
    """Build a compact title summary plus bounded output lines for a tool result."""
    lines = sanitize_terminal_text(result).splitlines()
    trimmed_lines = [line for line in lines if line.strip()]

    def _norm(s: str) -> str:
        normalized = s.rstrip()
        return normalized[:-1].rstrip() if normalized.endswith(":") else normalized

    def _basename(default: str = "file") -> str:
        fp = tool_input.get("file_path", "")
        return os.path.basename(str(fp)) or default

    def _quote_pattern(pattern: object) -> str:
        sanitized = sanitize_terminal_text(str(pattern)).strip()
        if not sanitized:
            return ""
        return (
            f"'{sanitized}'"
            if "'" not in sanitized
            else json.dumps(sanitized, ensure_ascii=True)
        )

    def _compact_path(summary: str) -> str:
        fp = tool_input.get("file_path")
        if not fp:
            return summary
        spath = sanitize_terminal_text(str(fp))
        return summary.replace(spath, os.path.basename(spath) or spath)

    if is_error:
        if tool_name == "Bash":
            cmd = sanitize_terminal_text(str(tool_input.get("command", ""))).strip()
            summary = (
                f"Failed to run {truncate_preview_line(cmd, COMMAND_PREVIEW_MAX_WIDTH)}"
                if cmd
                else "Failed to run command"
            )
        elif tool_name in ("Read", "Write", "Edit"):
            summary = f"Failed to {tool_name.lower()} {_basename()}"
        elif tool_name in ("Glob", "Grep"):
            pat = _quote_pattern(tool_input.get("pattern", ""))
            what = "files matching" if tool_name == "Glob" else "for"
            summary = f"Failed to search {what} {pat}" if pat else "Failed to search"
        else:
            summary = f"Failed to run {tool_name}"
        return _norm(truncate_preview_line(summary)), trimmed_lines[:6] or [
            "Tool failed"
        ]

    if tool_name == "Read":
        match = re.search(r"Lines:\s*(\d+)-(\d+)\s+of\s+(\d+)", result)
        fn = _basename()
        if match:
            start, end, total = map(int, match.groups())
            count = end - start + 1
            summary = f"Read {count} line{'s' if count != 1 else ''} from {fn} ({start}-{end} of {total})"
        else:
            summary = f"Read {fn}"
        preview = [line for line in lines[3:] if line.strip()]
        return _norm(summary), preview or trimmed_lines[:1]

    if tool_name == "Glob":
        pat = _quote_pattern(tool_input.get("pattern", ""))
        first = trimmed_lines[0] if trimmed_lines else ""
        if first.startswith("No files found matching pattern:"):
            summary = (
                f"Glob found no files matching {pat}"
                if pat
                else "Glob found no matching files"
            )
        elif first.startswith("Found "):
            summary = f"Glob {first[0].lower()}{first[1:]}"
        else:
            summary = f"Glob results matching {pat}" if pat else "Glob completed"
        return _norm(truncate_preview_line(summary)), trimmed_lines[
            1:
        ] or trimmed_lines[:1]

    if tool_name == "Grep":
        pat = _quote_pattern(tool_input.get("pattern", ""))
        first = trimmed_lines[0] if trimmed_lines else ""
        last = trimmed_lines[-1] if trimmed_lines else ""
        if first in ("No matches found", "No files found"):
            summary = (
                f"Grep found no matches for {pat}" if pat else "Grep found no matches"
            )
        elif str(tool_input.get("output_mode")) == "count" and last.startswith(
            "Found "
        ):
            summary = f"Grep {last[0].lower()}{last[1:]}"
            if pat and "matching " not in summary:
                for marker in (" with pagination = ", " limit: ", " offset: "):
                    idx = summary.find(marker)
                    if idx != -1:
                        summary = f"{summary[:idx]} matching {pat}{summary[idx:]}"
                        break
                else:
                    summary = f"{summary} matching {pat}"
        elif first.startswith("Found "):
            summary = f"Grep {first[0].lower()}{first[1:]}"
            if pat and "matching " not in summary:
                summary = f"{summary} matching {pat}"
        else:
            summary = f"Grep matches for {pat}" if pat else "Grep completed"
        return _norm(truncate_preview_line(summary)), trimmed_lines[
            1:
        ] or trimmed_lines[:1]

    if tool_name in ("Write", "Edit"):
        first = trimmed_lines[0] if trimmed_lines else f"{tool_name} completed"
        summary = truncate_preview_line(_compact_path(first))
        return _norm(summary), trimmed_lines[:1]

    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        summary = (
            f"Ran: {truncate_preview_line(cmd, COMMAND_PREVIEW_MAX_WIDTH)}"
            if cmd
            else "Command completed"
        )
        return _norm(summary), trimmed_lines

    first = trimmed_lines[0] if trimmed_lines else f"{tool_name} completed"
    summary = truncate_preview_line(_compact_path(first))
    return _norm(summary), trimmed_lines[1:] or trimmed_lines[:1]


def summarize_tool_use(tool_name: str, tool_input: dict) -> str:
    """Build a compact one-line summary for a tool invocation."""
    if "command" in tool_input:
        return f"{tool_name}: {truncate_preview_line(str(tool_input['command']), COMMAND_PREVIEW_MAX_WIDTH)}"
    if "file_path" in tool_input:
        file_path = str(tool_input["file_path"])
        file_name = os.path.basename(file_path) or file_path
        return f"{tool_name}: {truncate_preview_line(file_name, COMMAND_PREVIEW_MAX_WIDTH)}"
    if "pattern" in tool_input:
        return f"{tool_name}: {truncate_preview_line(str(tool_input['pattern']), COMMAND_PREVIEW_MAX_WIDTH)}"
    if tool_input:
        keys = list(tool_input.keys())
        preview = ", ".join(keys[:3])
        if len(keys) > 3:
            preview += ", ..."
        return f"{tool_name}: {preview}"
    return tool_name


def format_tool_input_details(
    tool_input: dict,
    exclude_keys: Iterable[str] = (),
) -> List[str]:
    """Format tool input parameters for a collapsible details section."""
    detail_lines: List[str] = []
    excluded = set(exclude_keys)

    for key, value in tool_input.items():
        if key in excluded:
            continue
        if isinstance(value, (dict, list, bool, int, float)) or value is None:
            raw_value = json.dumps(value, ensure_ascii=True)
        else:
            raw_value = str(value)

        value_lines = sanitize_terminal_text(raw_value).splitlines() or [""]
        detail_lines.append(
            f"{key}: {truncate_preview_line(value_lines[0], DETAIL_LINE_MAX_WIDTH)}"
        )

        for line in value_lines[1:4]:
            detail_lines.append(
                f"  {truncate_preview_line(line, DETAIL_LINE_MAX_WIDTH - 2)}"
            )

        if len(value_lines) > 4:
            detail_lines.append("  ...")

    return detail_lines
