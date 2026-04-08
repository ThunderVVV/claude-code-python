
"""File-related utility functions shared across tools"""

from __future__ import annotations

import os
from typing import Optional


def expand_path(path: str) -> str:
    """Expand path (handle ~, relative paths, etc.)"""
    if path.startswith("~"):
        path = os.path.expanduser(path)
    return os.path.abspath(path)


def add_line_numbers(content: str, start_line: int = 1) -> str:
    """Add line numbers to content"""
    lines = content.split("\n")
    max_line_num = start_line + len(lines) - 1
    line_num_width = len(str(max_line_num))

    result_lines = []
    for i, line in enumerate(lines):
        line_num = start_line + i
        result_lines.append(f"{line_num:>{line_num_width}d}\t{line}")

    return "\n".join(result_lines)


def format_file_result(
    path: str,
    content: str,
    start_line: int,
    end_line: int,
    total_lines: int,
) -> str:
    """Format file read result with line numbers"""
    numbered_content = add_line_numbers(content, start_line)
    return (
        f"File: {path}\n"
        f"Lines: {start_line}-{end_line} of {total_lines}\n\n"
        f"{numbered_content}"
    )


# Quote handling functions for EditTool
LEFT_SINGLE_CURLY_QUOTE = "‘"
RIGHT_SINGLE_CURLY_QUOTE = "’"
LEFT_DOUBLE_CURLY_QUOTE = "“"
RIGHT_DOUBLE_CURLY_QUOTE = "”"


def normalize_quotes(s: str) -> str:
    """Normalizes quotes in a string by converting curly quotes to straight quotes"""
    return (
        s.replace(LEFT_SINGLE_CURLY_QUOTE, "'")
        .replace(RIGHT_SINGLE_CURLY_QUOTE, "'")
        .replace(LEFT_DOUBLE_CURLY_QUOTE, '"')
        .replace(RIGHT_DOUBLE_CURLY_QUOTE, '"')
    )


def find_actual_string(file_content: str, search_string: str) -> str | None:
    """Finds the actual string in the file content that matches the search string, accounting for quote normalization"""
    if search_string in file_content:
        return search_string

    normalized_search = normalize_quotes(search_string)
    normalized_file = normalize_quotes(file_content)

    search_index = normalized_file.find(normalized_search)
    if search_index != -1:
        return file_content[search_index : search_index + len(search_string)]

    return None


def _is_opening_context(chars: list[str], index: int) -> bool:
    if index == 0:
        return True
    prev = chars[index - 1]
    return prev in (" ", "\t", "\n", "\r", "(", "[", "{", "\u2014", "\u2013")


def _apply_curly_double_quotes(s: str) -> str:
    chars = list(s)
    result = []
    for i, char in enumerate(chars):
        if char == '"':
            if _is_opening_context(chars, i):
                result.append(LEFT_DOUBLE_CURLY_QUOTE)
            else:
                result.append(RIGHT_DOUBLE_CURLY_QUOTE)
        else:
            result.append(char)
    return "".join(result)


def _apply_curly_single_quotes(s: str) -> str:
    chars = list(s)
    result = []
    for i, char in enumerate(chars):
        if char == "'":
            prev = chars[i - 1] if i > 0 else None
            next_char = chars[i + 1] if i < len(chars) - 1 else None
            prev_is_letter = prev is not None and prev.isalpha()
            next_is_letter = next_char is not None and next_char.isalpha()
            if prev_is_letter and next_is_letter:
                result.append(RIGHT_SINGLE_CURLY_QUOTE)
            else:
                if _is_opening_context(chars, i):
                    result.append(LEFT_SINGLE_CURLY_QUOTE)
                else:
                    result.append(RIGHT_SINGLE_CURLY_QUOTE)
        else:
            result.append(char)
    return "".join(result)


def preserve_quote_style(old_string: str, actual_old_string: str, new_string: str) -> str:
    """Preserves the quote style from the actual_old_string in the new_string"""
    if old_string == actual_old_string:
        return new_string

    has_double_quotes = LEFT_DOUBLE_CURLY_QUOTE in actual_old_string or RIGHT_DOUBLE_CURLY_QUOTE in actual_old_string
    has_single_quotes = LEFT_SINGLE_CURLY_QUOTE in actual_old_string or RIGHT_SINGLE_CURLY_QUOTE in actual_old_string

    if not has_double_quotes and not has_single_quotes:
        return new_string

    result = new_string
    if has_double_quotes:
        result = _apply_curly_double_quotes(result)
    if has_single_quotes:
        result = _apply_curly_single_quotes(result)

    return result

