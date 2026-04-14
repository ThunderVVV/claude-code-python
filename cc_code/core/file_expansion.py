"""File expansion utilities for @file_path references in user messages"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class FileExpansion:
    """Represents an expanded file reference"""

    file_path: str
    content: str
    display_path: str  # The original @path as written by user


def parse_file_references(text: str) -> List[Tuple[str, int, int]]:
    """
    Parse @file_path references from user text.

    Matches: @ + (relative or absolute path)
    Path can contain alphanumeric, dots, dashes, underscores, slashes, backslashes, and colon (for Windows).
    Path must be followed by whitespace, punctuation, or end of string.

    Returns: List of (file_path, start_pos, end_pos) tuples
    """
    # Pattern matches @ followed by a path
    # Valid path characters: alphanumeric, dots, dashes, underscores, slashes, backslashes, colon (for Windows drive)
    # Strategy: match the path, then strip trailing dots (which are likely sentence-ending punctuation)
    pattern = r"@([a-zA-Z0-9._\-/~\\:]+)"

    matches = []
    for match in re.finditer(pattern, text):
        file_path = match.group(1)
        end_pos = match.end()

        # Check what follows the match
        should_strip_dots = False
        if end_pos < len(text):
            next_char = text[end_pos]
            # If followed by alphanumeric or underscore, it's not a valid reference
            if next_char.isalnum() or next_char == "_":
                continue
            # If followed by space or punctuation, strip trailing dots
            if next_char in " \t\n\r,;:!?()":
                should_strip_dots = True
        else:
            # End of string - also strip trailing dots
            should_strip_dots = True

        if should_strip_dots:
            # Strip trailing dots from the path (likely sentence-ending punctuation)
            file_path = file_path.rstrip(".")

        start_pos = match.start()
        matches.append((file_path, start_pos, end_pos))

    return matches


def resolve_file_path(file_path: str, working_directory: str) -> Optional[str]:
    """
    Resolve a file path to an absolute path.

    Returns None if the path cannot be resolved or doesn't exist.
    """
    # Expand ~ to home directory
    if file_path.startswith("~"):
        file_path = os.path.expanduser(file_path)

    # If already absolute, use as-is
    if os.path.isabs(file_path):
        full_path = file_path
    else:
        # Resolve relative to working directory
        full_path = os.path.join(working_directory, file_path)

    # Normalize the path
    full_path = os.path.normpath(full_path)

    # Check if file exists and is a file (not directory)
    if not os.path.exists(full_path):
        return None
    if os.path.isdir(full_path):
        return None

    return full_path


def read_file_content(file_path: str) -> Optional[str]:
    """
    Read the content of a file.

    Returns None if the file cannot be read.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except (IOError, OSError, PermissionError):
        return None


def has_web_reference(text: str) -> bool:
    """Check if text contains @web reference."""
    import re

    pattern = r"(?<!\S)@web(?=$|[\s,;:!?()])"
    return bool(re.search(pattern, text))


def expand_web(text: str) -> str:
    web_skill_file_prompt = (
        "@.claude/skills/tavily-search/SKILL.md",
        "@.claude/skills/tavily-extract/SKILL.md",
    )
    text = text.replace("@web", " ".join(web_skill_file_prompt) + " ")
    return text


def expand_file_references(
    text: str,
    working_directory: str,
) -> Tuple[str, List[FileExpansion]]:
    """
    Expand @file_path references in user text.

    Returns:
        - expanded_text: The text with file contents prepended
        - expansions: List of FileExpansion objects for display purposes
    """
    text = expand_web(text)

    matches = parse_file_references(text)
    if not matches:
        return text, []

    expansions: List[FileExpansion] = []
    seen_paths: set[str] = set()  # Avoid duplicate expansions

    for file_path, start_pos, end_pos in matches:
        # Skip if we've already expanded this path
        if file_path in seen_paths:
            continue

        # Resolve the file path
        full_path = resolve_file_path(file_path, working_directory)
        if full_path is None:
            # File doesn't exist or is a directory, skip expansion
            continue

        # Read file content
        content = read_file_content(full_path)
        if content is None:
            # Cannot read file, skip expansion
            continue

        seen_paths.add(file_path)
        expansions.append(
            FileExpansion(
                file_path=full_path,
                content=content,
                display_path=file_path,
            )
        )

    if not expansions:
        return text, []

    # Build expanded text: file contents first, then original message
    expanded_parts: List[str] = []

    for expansion in expansions:
        expanded_parts.append(f"@{expansion.display_path}:")
        expanded_parts.append(expansion.content)
        expanded_parts.append("")  # Empty line between files

    # Add original message
    expanded_parts.append(text)

    expanded_text = "\n".join(expanded_parts)

    return expanded_text, expansions


def format_expansion_for_display(expansion: FileExpansion, max_lines: int = 5) -> str:
    """
    Format a file expansion for TUI display with line limit.

    Similar to how Read tool results are displayed.
    """
    lines = expansion.content.splitlines()
    total_lines = len(lines)

    # Format with line numbers like Read tool
    formatted_lines = []
    for i, line in enumerate(lines[:max_lines], start=1):
        formatted_lines.append(f"{i:6}\t{line}")

    result = f"@{expansion.display_path}:\n"
    result += "\n".join(formatted_lines)

    if total_lines > max_lines:
        result += f"\n... ({total_lines - max_lines} more lines)"

    return result


def format_expansions_for_display(
    expansions: List[FileExpansion], max_lines: int = 5
) -> str:
    """
    Format multiple file expansions for TUI display.

    Returns a condensed display string for the user message widget.
    """
    if not expansions:
        return ""

    parts = []
    for expansion in expansions:
        parts.append(format_expansion_for_display(expansion, max_lines))

    return "\n\n".join(parts)


def serialize_file_expansions(file_expansions: list[FileExpansion]) -> list[dict]:
    """Convert file-expansion objects into JSON-friendly dictionaries."""
    return [
        {
            "file_path": exp.file_path,
            "content": exp.content,
            "display_path": exp.display_path,
        }
        for exp in file_expansions
    ]


def build_visible_file_expansions(
    user_text: str,
    working_directory: str,
) -> list[FileExpansion]:
    """Reconstruct visible @file_path expansions for the web frontend."""
    if not user_text:
        return []

    expansions: list[FileExpansion] = []
    seen_paths: set[str] = set()
    web_requested = has_web_reference(user_text)

    for file_path, _start_pos, _end_pos in parse_file_references(user_text):
        if file_path == "web" and web_requested:
            continue
        if file_path in seen_paths:
            continue

        full_path = resolve_file_path(file_path, working_directory)
        if full_path is None:
            continue

        content = read_file_content(full_path)
        if content is None:
            continue

        seen_paths.add(file_path)
        expansions.append(
            FileExpansion(
                file_path=full_path,
                content=content,
                display_path=file_path,
            )
        )

    return expansions
