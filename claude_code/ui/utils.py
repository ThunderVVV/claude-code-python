"""UI utility functions for text sanitization and tool summarization"""

from __future__ import annotations

import json
import os
import re
from typing import Iterable, List, Tuple


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


def _truncate_result_lines(
    lines: List[str],
    max_lines: int,
    max_width: int = 88,
) -> List[str]:
    """Trim a result preview to a bounded number of lines."""
    preview = [truncate_preview_line(line, max_width) for line in lines[:max_lines]]
    if len(lines) > max_lines:
        preview.append(f"... ({len(lines) - max_lines} more lines)")
    return preview


def _normalize_summary_text(summary: str) -> str:
    """Keep summary titles compact by dropping trailing punctuation we don't render well."""
    normalized = summary.rstrip()
    if normalized.endswith(":"):
        normalized = normalized[:-1].rstrip()
    return normalized


def _compact_file_path_in_summary(summary: str, tool_input: dict) -> str:
    """Replace any full file path in a title summary with its basename."""
    file_path = tool_input.get("file_path")
    if not file_path:
        return summary

    sanitized_path = sanitize_terminal_text(str(file_path))
    file_name = os.path.basename(sanitized_path) or sanitized_path
    return summary.replace(sanitized_path, file_name)


def _quote_search_pattern(pattern: object) -> str:
    """Render a search pattern for compact UI summaries."""
    sanitized = sanitize_terminal_text(str(pattern)).strip()
    if not sanitized:
        return ""
    if "'" not in sanitized:
        return f"'{sanitized}'"
    return json.dumps(sanitized, ensure_ascii=True)


def _prefix_tool_name(summary: str, tool_name: str) -> str:
    """Prefix a summary with the tool name while keeping it readable."""
    normalized = _normalize_summary_text(summary)
    if not normalized:
        return f"{tool_name} completed"
    return f"{tool_name} {normalized[0].lower()}{normalized[1:]}"


def _append_matching_pattern(summary: str, pattern: str) -> str:
    """Append a matching-clause before pagination/limit suffixes when possible."""
    if not pattern or "matching " in summary:
        return summary

    for marker in (" with pagination = ", " limit: ", " offset: "):
        index = summary.find(marker)
        if index != -1:
            return f"{summary[:index]} matching {pattern}{summary[index:]}"

    return f"{summary} matching {pattern}"


def _summarize_glob_result(tool_input: dict, trimmed_lines: List[str]) -> str:
    """Build a compact Glob-specific summary."""
    pattern = _quote_search_pattern(tool_input.get("pattern", ""))
    first_line = trimmed_lines[0] if trimmed_lines else ""

    if first_line.startswith("No files found matching pattern:"):
        return (
            f"Glob found no files matching {pattern}"
            if pattern
            else "Glob found no matching files"
        )

    if first_line.startswith("Found "):
        return _prefix_tool_name(first_line, "Glob")

    if pattern:
        return f"Glob results matching {pattern}"
    return "Glob completed"


def _summarize_grep_result(tool_input: dict, trimmed_lines: List[str]) -> str:
    """Build a compact Grep-specific summary."""
    pattern = _quote_search_pattern(tool_input.get("pattern", ""))
    output_mode = str(tool_input.get("output_mode", "files_with_matches"))
    first_line = trimmed_lines[0] if trimmed_lines else ""
    last_line = trimmed_lines[-1] if trimmed_lines else ""

    if first_line in {"No matches found", "No files found"}:
        return (
            f"Grep found no matches for {pattern}" if pattern else "Grep found no matches"
        )

    if output_mode == "count" and last_line.startswith("Found "):
        return _append_matching_pattern(_prefix_tool_name(last_line, "Grep"), pattern)

    if first_line.startswith("Found "):
        return _append_matching_pattern(_prefix_tool_name(first_line, "Grep"), pattern)

    if pattern:
        return f"Grep matches for {pattern}"
    return "Grep completed"


def summarize_tool_result(
    tool_name: str,
    tool_input: dict,
    result: str,
    is_error: bool,
) -> Tuple[str, List[str]]:
    """Build a compact title summary plus bounded output lines for a tool result."""
    lines = sanitize_terminal_text(result).splitlines()
    trimmed_lines = [line for line in lines if line.strip()]

    if is_error:
        summary = truncate_preview_line(
            _compact_file_path_in_summary(
                trimmed_lines[0] if trimmed_lines else "Tool failed",
                tool_input,
            )
        )
        output_lines = _truncate_result_lines(trimmed_lines[1:] or trimmed_lines[:1], 4)
        return _normalize_summary_text(summary), output_lines

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
        preview_source = [line for line in lines[3:] if line.strip()]
        output_lines = _truncate_result_lines(preview_source or trimmed_lines[:1], 5)
        return _normalize_summary_text(summary), output_lines

    if tool_name == "Glob":
        summary = truncate_preview_line(_summarize_glob_result(tool_input, trimmed_lines))
        output_lines = _truncate_result_lines(trimmed_lines[1:] or trimmed_lines[:1], 5)
        return _normalize_summary_text(summary), output_lines

    if tool_name == "Grep":
        summary = truncate_preview_line(_summarize_grep_result(tool_input, trimmed_lines))
        output_lines = _truncate_result_lines(trimmed_lines[1:] or trimmed_lines[:1], 5)
        return _normalize_summary_text(summary), output_lines

    if tool_name in {"Write", "Edit"}:
        summary = truncate_preview_line(
            _compact_file_path_in_summary(
                trimmed_lines[0] if trimmed_lines else f"{tool_name} completed",
                tool_input,
            )
        )
        output_lines = _truncate_result_lines(trimmed_lines[:1], 1)
        return _normalize_summary_text(summary), output_lines

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if command:
            summary = f"Ran: {truncate_preview_line(command, 64)}"
        else:
            summary = "Command completed"
        output_lines = _truncate_result_lines(trimmed_lines, 6)
        return _normalize_summary_text(summary), output_lines

    summary = truncate_preview_line(
        _compact_file_path_in_summary(
            trimmed_lines[0] if trimmed_lines else f"{tool_name} completed",
            tool_input,
        )
    )
    output_lines = _truncate_result_lines(trimmed_lines[1:] or trimmed_lines[:1], 4)
    return _normalize_summary_text(summary), output_lines


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
        detail_lines.append(f"{key}: {truncate_preview_line(value_lines[0], 104)}")

        for line in value_lines[1:4]:
            detail_lines.append(f"  {truncate_preview_line(line, 102)}")

        if len(value_lines) > 4:
            detail_lines.append("  ...")

    return detail_lines
