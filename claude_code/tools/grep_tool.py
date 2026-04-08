
"""Grep tool - aligned with GrepTool.ts"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from claude_code.core.tools import BaseTool, ToolContext, ToolInputSchema, ValidationResult
from claude_code.tools.file_utils import expand_path
from claude_code.tools.ripgrep import (
    VCS_DIRECTORIES_TO_EXCLUDE,
    apply_head_limit,
    rip_grep,
)


class GrepTool(BaseTool):
    """Tool for searching content in files - aligned with GrepTool.ts"""

    name = "Grep"
    description = """A powerful search tool built on ripgrep

  Usage:
  - ALWAYS use Grep for search tasks. NEVER invoke `grep` or `rg` as a Bash command. The Grep tool has been optimized for correct permissions and access.
  - Supports full regex syntax (e.g., "log.*Error", "function\\s+\\w+")
  - Filter files with glob parameter (e.g., "*.js", "**/*.tsx") or type parameter (e.g., "js", "py", "rust")
  - Output modes: "content" shows matching lines, "files_with_matches" shows only file paths (default), "count" shows match counts
  - Use Agent tool for open-ended searches requiring multiple rounds
  - Pattern syntax: Uses ripgrep (not grep) - literal braces need escaping (use `interface\\{\\}` to find `interface{}` in Go code)
  - Multiline matching: By default patterns match within single lines only. For cross-line patterns like `struct \\{[\\s\\S]*?field`, use `multiline: true`"""
    input_schema = ToolInputSchema(
        properties={
            "pattern": {
                "type": "string",
                "description": "The regular expression pattern to search for in file contents",
            },
            "path": {
                "type": "string",
                "description": "File or directory to search in (rg PATH). Defaults to current working directory.",
            },
            "glob": {
                "type": "string",
                "description": 'Glob pattern to filter files (e.g. "*.js", "*.{ts,tsx}") - maps to rg --glob',
            },
            "output_mode": {
                "type": "string",
                "description": 'Output mode: "content" shows matching lines (supports -A/-B/-C context, -n line numbers, head_limit), "files_with_matches" shows file paths (supports head_limit), "count" shows match counts (supports head_limit). Defaults to "files_with_matches".',
                "enum": ["content", "files_with_matches", "count"],
            },
            "-B": {
                "type": "integer",
                "description": 'Number of lines to show before each match (rg -B). Requires output_mode: "content", ignored otherwise.',
            },
            "-A": {
                "type": "integer",
                "description": 'Number of lines to show after each match (rg -A). Requires output_mode: "content", ignored otherwise.',
            },
            "-C": {
                "type": "integer",
                "description": "Alias for context.",
            },
            "context": {
                "type": "integer",
                "description": 'Number of lines to show before and after each match (rg -C). Requires output_mode: "content", ignored otherwise.',
            },
            "-n": {
                "type": "boolean",
                "description": 'Show line numbers in output (rg -n). Requires output_mode: "content", ignored otherwise. Defaults to true.',
                "default": True,
            },
            "-i": {
                "type": "boolean",
                "description": "Case insensitive search (rg -i)",
                "default": False,
            },
            "type": {
                "type": "string",
                "description": 'File type to search (rg --type). Common types: js, py, rust, go, java, etc. More efficient than include for standard file types.',
            },
            "head_limit": {
                "type": "integer",
                "description": 'Limit output to first N lines/entries, equivalent to "| head -N". Works across all output modes: content (limits output lines), files_with_matches (limits file paths), count (limits count entries). Defaults to 250 when unspecified. Pass 0 for unlimited (use sparingly — large result sets waste context).',
            },
            "offset": {
                "type": "integer",
                "description": 'Skip first N lines/entries before applying head_limit, equivalent to "| tail -n +N | head -N". Works across all output modes. Defaults to 0.',
                "default": 0,
            },
            "multiline": {
                "type": "boolean",
                "description": "Enable multiline mode where . matches newlines and patterns can span lines (rg -U --multiline-dotall). Default: false.",
                "default": False,
            },
        },
        required=["pattern"],
    )
    aliases = ["grep"]
    max_result_size_chars = 20000

    def is_read_only(self, input: Dict[str, Any]) -> bool:
        return True

    def is_concurrency_safe(self, input: Dict[str, Any]) -> bool:
        return True

    def get_tool_use_summary(self, input: Optional[Dict[str, Any]] = None) -> Optional[str]:
        if not input:
            return None
        pattern = input.get("pattern", "")
        return f"'{pattern}'" if pattern else None

    def get_activity_description(self, input: Optional[Dict[str, Any]] = None) -> Optional[str]:
        if not input:
            return "Searching"
        pattern = input.get("pattern", "")
        if pattern:
            return f"Searching for {pattern}"
        return "Searching"

    def user_facing_name(self, input: Optional[Dict[str, Any]] = None) -> str:
        return "Search"

    def get_path(self, input: Dict[str, Any]) -> str:
        return input.get("path") or os.getcwd()

    def is_error_result(
        self,
        result: str,
        input: Optional[Dict[str, Any]] = None,
    ) -> bool:
        return result.startswith("Error: 'pattern' parameter is required") or result.startswith(
            "Error searching content:"
        )

    async def validate_input(
        self, input: Dict[str, Any], context: ToolContext
    ) -> ValidationResult:
        path = input.get("path")
        if path:
            absolute_path = expand_path(path)
            if not os.path.exists(absolute_path):
                return ValidationResult(
                    result=False,
                    message=f"Path does not exist: {path}",
                    error_code=1,
                )
        return ValidationResult(result=True)

    async def call(self, input: Dict[str, Any], context: ToolContext) -> str:
        pattern = input.get("pattern", "")
        if not pattern:
            return "Error: 'pattern' parameter is required"

        path = input.get("path")
        glob_param = input.get("glob")
        output_mode = input.get("output_mode", "files_with_matches")
        context_before = input.get("-B")
        context_after = input.get("-A")
        context_c = input.get("-C")
        context_param = input.get("context")
        show_line_numbers = input.get("-n", True)
        case_insensitive = input.get("-i", False)
        type_param = input.get("type")
        head_limit = input.get("head_limit")
        offset = input.get("offset", 0)
        multiline = input.get("multiline", False)

        absolute_path = expand_path(path) if path else os.getcwd()

        args = ["--hidden"]

        for dir_name in VCS_DIRECTORIES_TO_EXCLUDE:
            args.extend(["--glob", f"!{dir_name}"])

        args.extend(["--max-columns", "500"])

        if multiline:
            args.extend(["-U", "--multiline-dotall"])

        if case_insensitive:
            args.append("-i")

        if output_mode == "files_with_matches":
            args.append("-l")
        elif output_mode == "count":
            args.append("-c")

        if show_line_numbers and output_mode == "content":
            args.append("-n")

        if output_mode == "content":
            if context_param is not None:
                args.extend(["-C", str(context_param)])
            elif context_c is not None:
                args.extend(["-C", str(context_c)])
            else:
                if context_before is not None:
                    args.extend(["-B", str(context_before)])
                if context_after is not None:
                    args.extend(["-A", str(context_after)])

        if pattern.startswith("-"):
            args.extend(["-e", pattern])
        else:
            args.append(pattern)

        if type_param:
            args.extend(["--type", type_param])

        if glob_param:
            glob_patterns = []
            raw_patterns = glob_param.split()
            for raw_pattern in raw_patterns:
                if "{" in raw_pattern and "}" in raw_pattern:
                    glob_patterns.append(raw_pattern)
                else:
                    glob_patterns.extend([p for p in raw_pattern.split(",") if p])

            for glob_pat in glob_patterns:
                if glob_pat:
                    args.extend(["--glob", glob_pat])

        try:
            results = rip_grep(args, absolute_path)

            if output_mode == "content":
                limited_results, applied_limit = apply_head_limit(
                    results, head_limit, offset
                )

                final_lines = []
                for line in limited_results:
                    colon_idx = line.find(":")
                    if colon_idx > 0:
                        file_path = line[:colon_idx]
                        rest = line[colon_idx:]
                        try:
                            rel_path = os.path.relpath(file_path, absolute_path)
                            final_lines.append(rel_path + rest)
                        except ValueError:
                            final_lines.append(line)
                    else:
                        final_lines.append(line)

                content = "\n".join(final_lines)
                limit_info = []
                if applied_limit is not None:
                    limit_info.append(f"limit: {applied_limit}")
                if offset > 0:
                    limit_info.append(f"offset: {offset}")

                if limit_info:
                    content += f"\n\n[Showing results with pagination = {', '.join(limit_info)}]"

                return content or "No matches found"

            if output_mode == "count":
                limited_results, applied_limit = apply_head_limit(
                    results, head_limit, offset
                )

                final_count_lines = []
                total_matches = 0
                file_count = 0

                for line in limited_results:
                    colon_idx = line.rfind(":")
                    if colon_idx > 0:
                        file_path = line[:colon_idx]
                        count_str = line[colon_idx + 1 :]
                        try:
                            count = int(count_str)
                            total_matches += count
                            file_count += 1
                            try:
                                rel_path = os.path.relpath(file_path, absolute_path)
                                final_count_lines.append(f"{rel_path}:{count}")
                            except ValueError:
                                final_count_lines.append(line)
                        except ValueError:
                            final_count_lines.append(line)
                    else:
                        final_count_lines.append(line)

                content = "\n".join(final_count_lines)
                limit_info = []
                if applied_limit is not None:
                    limit_info.append(f"limit: {applied_limit}")
                if offset > 0:
                    limit_info.append(f"offset: {offset}")

                summary = f"\n\nFound {total_matches} total {'occurrence' if total_matches == 1 else 'occurrences'} across {file_count} {'file' if file_count == 1 else 'files'}"
                if limit_info:
                    summary += f" with pagination = {', '.join(limit_info)}"

                return (content or "No matches found") + summary

            limited_results, applied_limit = apply_head_limit(
                results, head_limit, offset
            )

            sorted_matches = sorted(limited_results)

            relative_matches = []
            for match in sorted_matches:
                try:
                    rel_path = os.path.relpath(match, absolute_path)
                    relative_matches.append(rel_path)
                except ValueError:
                    relative_matches.append(match)

            if not relative_matches:
                return "No files found"

            limit_info = []
            if applied_limit is not None:
                limit_info.append(f"limit: {applied_limit}")
            if offset > 0:
                limit_info.append(f"offset: {offset}")

            result = f"Found {len(relative_matches)} {'file' if len(relative_matches) == 1 else 'files'}"
            if limit_info:
                result += f" {', '.join(limit_info)}"
            result += "\n" + "\n".join(relative_matches)

            return result

        except Exception as e:
            return f"Error searching content: {str(e)}"
