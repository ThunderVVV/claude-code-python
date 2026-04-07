
"""File-related tools - aligned with TypeScript version"""

from __future__ import annotations

import os
import glob as glob_module
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from claude_code.core.tools import (
    BaseTool,
    ToolContext,
    ToolInputSchema,
    PermissionResult,
    ValidationResult,
)


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


class ReadTool(BaseTool):
    """Tool for reading text files - aligned with FileReadTool.ts"""

    name = "Read"
    description = """Reads a file from the local filesystem. You can access any file directly by using this tool.
Assume this tool is able to read all files on the machine. If the User provides a path to a file assume that path is valid. It is okay to read a file that does not exist; an error will be returned.

Usage:
- The file_path parameter must be an absolute path, not a relative path
- By default, it reads up to 2000 lines starting from the beginning of the file
- You can optionally specify a line offset and limit (especially handy for long files), but it's recommended to read the whole file by not providing these parameters
- Results are returned using cat -n format, with line numbers starting at 1
- This tool can only read files, not directories. To read a directory, use an ls command via the Bash tool.
- You will regularly be asked to read screenshots. If the user provides a path to a screenshot, ALWAYS use this tool to view the file at the path. This tool will work with all temporary file paths.
- If you read a file that exists but has empty contents you will receive a system reminder warning in place of file contents."""
    input_schema = ToolInputSchema(
        properties={
            "file_path": {
                "type": "string",
                "description": "The absolute path to the file to read",
            },
            "offset": {
                "type": "integer",
                "description": "The line number to start reading from (1-indexed). Only provide if the file is too large to read at once.",
                "default": 1,
            },
            "limit": {
                "type": "integer",
                "description": "The number of lines to read. Only provide if the file is too large to read at once.",
                "default": 2000,
            },
        },
        required=["file_path"],
    )
    aliases = ["read", "cat"]
    max_result_size_chars = float("inf")  # Read tool doesn't truncate

    def is_read_only(self, input: Dict[str, Any]) -> bool:
        return True

    def is_concurrency_safe(self, input: Dict[str, Any]) -> bool:
        return True

    def get_path(self, input: Dict[str, Any]) -> Optional[str]:
        return input.get("file_path")

    def get_tool_use_summary(self, input: Optional[Dict[str, Any]] = None) -> Optional[str]:
        if not input:
            return None
        path = input.get("file_path", "")
        if path:
            return os.path.basename(path)
        return None

    def get_activity_description(self, input: Optional[Dict[str, Any]] = None) -> Optional[str]:
        if not input:
            return "Reading file"
        path = input.get("file_path", "")
        if path:
            return f"Reading {os.path.basename(path)}"
        return "Reading file"

    def user_facing_name(self, input: Optional[Dict[str, Any]] = None) -> str:
        if not input:
            return self.name
        path = input.get("file_path", "")
        if path:
            return os.path.basename(path)
        return self.name

    async def validate_input(
        self,
        input: Dict[str, Any],
        context: ToolContext,
    ) -> ValidationResult:
        """Validate file path before reading"""
        file_path = input.get("file_path", "")
        if not file_path:
            return ValidationResult(
                result=False,
                message="file_path is required",
                error_code=1,
            )
        return ValidationResult(result=True)

    async def call(self, input: Dict[str, Any], context: ToolContext) -> str:
        file_path = input.get("file_path", "")
        if not file_path:
            return "Error: 'file_path' parameter is required"

        offset = input.get("offset", 1)
        limit = input.get("limit", 2000)

        # Expand path
        full_path = expand_path(file_path)

        # Check if file exists
        if not os.path.exists(full_path):
            return f"Error: File does not exist: {full_path}"

        # Check if it's a directory
        if os.path.isdir(full_path):
            return f"Error: Path is a directory, not a file: {full_path}"

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)

            # Normalize offset to 1-indexed
            if offset < 1:
                offset = 1

            start_idx = offset - 1
            end_idx = start_idx + limit

            selected_lines = lines[start_idx:end_idx]
            content = "".join(selected_lines)

            actual_end_line = min(offset + limit - 1, total_lines)

            return format_file_result(full_path, content, offset, actual_end_line, total_lines)

        except PermissionError:
            return f"Error: Permission denied reading file: {full_path}"
        except UnicodeDecodeError:
            return f"Error: File appears to be binary or uses an unsupported encoding: {full_path}"
        except Exception as e:
            return f"Error reading file: {str(e)}"


class WriteTool(BaseTool):
    """Tool for writing text files - aligned with FileWriteTool.ts"""

    name = "Write"
    description = """Writes a file to the local filesystem.

Usage:
- This tool will overwrite the existing file if there is one at the provided path.
- If this is an existing file, you MUST use the Read tool first to read the file's contents. This tool will fail if you did not read the file first.
- Prefer the Edit tool for modifying existing files — it only sends the diff. Only use this tool to create new files or for complete rewrites.
- NEVER create documentation files (*.md) or README files unless explicitly requested by the User.
- Only use emojis if the user explicitly requests it. Avoid writing emojis to files unless asked."""
    input_schema = ToolInputSchema(
        properties={
            "file_path": {
                "type": "string",
                "description": "The absolute path to the file to write (must be absolute, not relative)",
            },
            "content": {
                "type": "string",
                "description": "The content to write to the file",
            },
        },
        required=["file_path", "content"],
    )
    aliases = ["write"]

    def is_read_only(self, input: Dict[str, Any]) -> bool:
        return False

    def is_destructive(self, input: Dict[str, Any]) -> bool:
        return True

    def get_path(self, input: Dict[str, Any]) -> Optional[str]:
        return input.get("file_path")

    def get_tool_use_summary(self, input: Optional[Dict[str, Any]] = None) -> Optional[str]:
        if not input:
            return None
        path = input.get("file_path", "")
        if path:
            return os.path.basename(path)
        return None

    def get_activity_description(self, input: Optional[Dict[str, Any]] = None) -> Optional[str]:
        if not input:
            return "Writing file"
        path = input.get("file_path", "")
        if path:
            return f"Writing {os.path.basename(path)}"
        return "Writing file"

    async def call(self, input: Dict[str, Any], context: ToolContext) -> str:
        file_path = input.get("file_path", "")
        if not file_path:
            return "Error: 'file_path' parameter is required"

        content = input.get("content", "")

        # Expand path
        full_path = expand_path(file_path)

        try:
            # Create parent directories if needed
            parent_dir = os.path.dirname(full_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Get file size for feedback
            file_size = os.path.getsize(full_path)
            line_count = content.count("\n") + 1

            return f"Successfully wrote to {full_path} ({line_count} lines, {file_size} bytes)"

        except PermissionError:
            return f"Error: Permission denied writing to file: {full_path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"


class EditTool(BaseTool):
    """Tool for editing text files - aligned with FileEditTool.ts"""

    name = "Edit"
    description = """Performs exact string replacements in files.

Usage:
- You must use your `Read` tool at least once in the conversation before editing. This tool will error if you attempt an edit without reading the file.
- When editing text from Read tool output, ensure you preserve the exact indentation (tabs/spaces) as it appears AFTER the line number prefix. The line number prefix format is: line number + tab. Everything after that is the actual file content to match. Never include any part of the line number prefix in the old_string or new_string.
- ALWAYS prefer editing existing files in the codebase. NEVER write new files unless explicitly required.
- Only use emojis if the user explicitly requests it. Avoid adding emojis to files unless asked.
- The edit will FAIL if `old_string` is not unique in the file. Either provide a larger string with more surrounding context to make it unique or use `replace_all` to change every instance of `old_string`.
- Use `replace_all` for replacing and renaming strings across the file. This parameter is useful if you want to rename a variable for instance."""
    input_schema = ToolInputSchema(
        properties={
            "file_path": {
                "type": "string",
                "description": "The absolute path to the file to modify",
            },
            "old_string": {
                "type": "string",
                "description": "The text to replace",
            },
            "new_string": {
                "type": "string",
                "description": "The text to replace it with (must be different from old_string)",
            },
            "replace_all": {
                "type": "boolean",
                "description": "Replace all occurrences of old_string (default false)",
                "default": False,
            },
        },
        required=["file_path", "old_string", "new_string"],
    )
    aliases = ["edit"]

    def is_read_only(self, input: Dict[str, Any]) -> bool:
        return False

    def is_destructive(self, input: Dict[str, Any]) -> bool:
        return True

    def get_path(self, input: Dict[str, Any]) -> Optional[str]:
        return input.get("file_path")

    def get_tool_use_summary(self, input: Optional[Dict[str, Any]] = None) -> Optional[str]:
        if not input:
            return None
        path = input.get("file_path", "")
        if path:
            return os.path.basename(path)
        return None

    def get_activity_description(self, input: Optional[Dict[str, Any]] = None) -> Optional[str]:
        if not input:
            return "Editing file"
        path = input.get("file_path", "")
        if path:
            return f"Editing {os.path.basename(path)}"
        return "Editing file"

    async def validate_input(
        self,
        input: Dict[str, Any],
        context: ToolContext,
    ) -> ValidationResult:
        """Validate edit input"""
        old_string = input.get("old_string", "")
        new_string = input.get("new_string", "")

        if old_string == new_string:
            return ValidationResult(
                result=False,
                message="No changes to make: old_string and new_string are exactly the same.",
                error_code=1,
            )

        return ValidationResult(result=True)

    async def call(self, input: Dict[str, Any], context: ToolContext) -> str:
        file_path = input.get("file_path", "")
        if not file_path:
            return "Error: 'file_path' parameter is required"

        old_string = input.get("old_string", "")
        new_string = input.get("new_string", "")
        replace_all = input.get("replace_all", False)

        # Expand path
        full_path = expand_path(file_path)

        # Check if file exists
        if not os.path.exists(full_path):
            return f"Error: File does not exist: {full_path}"

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check if old_string exists
            if old_string not in content:
                return f"Error: Could not find the specified text in {full_path}"

            # Check for multiple occurrences if not replace_all
            count = content.count(old_string)
            if count > 1 and not replace_all:
                return (
                    f"Error: Found {count} occurrences of the specified text in {full_path}. "
                    f"Use replace_all=true to replace all occurrences, or provide a more specific old_string."
                )

            # Perform the replacement
            if replace_all:
                new_content = content.replace(old_string, new_string)
            else:
                new_content = content.replace(old_string, new_string, 1)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return f"Successfully edited {full_path} (replaced {count} occurrence{'s' if count > 1 else ''})"

        except PermissionError:
            return f"Error: Permission denied editing file: {full_path}"
        except UnicodeDecodeError:
            return f"Error: File appears to be binary: {full_path}"
        except Exception as e:
            return f"Error editing file: {str(e)}"


class GlobTool(BaseTool):
    """Tool for searching files with glob patterns - aligned with GlobTool.ts"""

    name = "Glob"
    description = """- Fast file pattern matching tool that works with any codebase size
- Supports glob patterns like "**/*.js" or "src/**/*.ts"
- Returns matching file paths sorted by modification time
- Use this tool when you need to find files by name patterns
- When you are doing an open ended search that may require multiple rounds of globbing and grepping, use the Agent tool instead"""
    input_schema = ToolInputSchema(
        properties={
            "pattern": {
                "type": "string",
                "description": "The glob pattern to match files against (e.g., \"**/*.js\")",
            },
            "path": {
                "type": "string",
                "description": "The directory to search in. If not specified, the current working directory will be used.",
            },
        },
        required=["pattern"],
    )
    aliases = ["glob"]

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
            return "Searching for files"
        pattern = input.get("pattern", "")
        if pattern:
            return f"Searching for '{pattern}'"
        return "Searching for files"

    async def call(self, input: Dict[str, Any], context: ToolContext) -> str:
        pattern = input.get("pattern", "")
        if not pattern:
            return "Error: 'pattern' parameter is required"

        search_path = input.get("path", context.working_directory)

        # Expand search path
        full_search_path = expand_path(search_path)

        try:
            # Build full pattern
            full_pattern = os.path.join(full_search_path, pattern)

            # Use glob with recursive support
            matches = glob_module.glob(full_pattern, recursive=True)

            # Sort by modification time (most recent first)
            matches.sort(key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)

            if not matches:
                return f"No files found matching pattern: {pattern}"

            # Make paths relative to search path for cleaner output
            rel_matches = []
            for m in matches:
                try:
                    rel_path = os.path.relpath(m, full_search_path)
                    rel_matches.append(rel_path)
                except ValueError:
                    rel_matches.append(m)

            result = f"Found {len(matches)} file{'s' if len(matches) > 1 else ''} matching '{pattern}':\n\n"
            result += "\n".join(rel_matches[:100])

            if len(matches) > 100:
                result += f"\n\n... and {len(matches) - 100} more files"

            return result

        except Exception as e:
            return f"Error searching files: {str(e)}"


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
                "description": "The regular expression pattern to search for",
            },
            "path": {
                "type": "string",
                "description": "The directory or file to search in. If not specified, the current working directory will be used.",
            },
            "glob": {
                "type": "string",
                "description": "File pattern to include in the search (e.g., \"*.py\").",
            },
            "-i": {
                "type": "boolean",
                "description": "Perform a case-insensitive search",
                "default": False,
            },
            "-n": {
                "type": "boolean",
                "description": "Show line numbers (default: true)",
                "default": True,
            },
            "output_mode": {
                "type": "string",
                "description": "Output mode: 'content' (default), 'files_with_matches', or 'count'",
            },
            "-C": {
                "type": "integer",
                "description": "Number of lines of context to show before and after matches",
            },
        },
        required=["pattern"],
    )
    aliases = ["grep"]

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
            return "Searching for pattern"
        pattern = input.get("pattern", "")
        if pattern:
            return f"Searching for '{pattern}'"
        return "Searching for pattern"

    async def call(self, input: Dict[str, Any], context: ToolContext) -> str:
        pattern = input.get("pattern", "")
        if not pattern:
            return "Error: 'pattern' parameter is required"

        search_path = input.get("path", context.working_directory)
        glob_pattern = input.get("glob", "*")
        case_insensitive = input.get("-i", False)
        show_line_numbers = input.get("-n", True)
        output_mode = input.get("output_mode", "content")
        context_lines = input.get("-C", 0)

        # Expand search path
        full_search_path = expand_path(search_path)

        try:
            # Compile regex pattern
            flags = re.MULTILINE
            if case_insensitive:
                flags |= re.IGNORECASE

            try:
                regex = re.compile(pattern, flags)
            except re.error as e:
                return f"Error: Invalid regex pattern: {str(e)}"

            matches = []

            if os.path.isfile(full_search_path):
                files = [full_search_path]
            else:
                files = []
                for root, _, filenames in os.walk(full_search_path):
                    for filename in filenames:
                        if glob_module.fnmatch.fnmatch(filename, glob_pattern):
                            files.append(os.path.join(root, filename))

            files_with_matches = set()
            match_count = 0

            for file_path in files:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()

                    file_matches = []
                    for line_num, line in enumerate(lines, 1):
                        if regex.search(line):
                            file_matches.append((line_num, line.rstrip()))
                            files_with_matches.add(file_path)
                            match_count += 1

                    if output_mode == "content" and file_matches:
                        for line_num, line in file_matches:
                            rel_path = os.path.relpath(file_path, full_search_path)
                            if show_line_numbers:
                                matches.append(f"{rel_path}:{line_num}: {line}")
                            else:
                                matches.append(f"{rel_path}: {line}")

                except (IOError, PermissionError):
                    continue

            if output_mode == "files_with_matches":
                if not files_with_matches:
                    return f"No files matched the pattern: {pattern}"
                result = f"Found {len(files_with_matches)} file{'s' if len(files_with_matches) > 1 else ''} matching '{pattern}':\n\n"
                rel_files = [os.path.relpath(f, full_search_path) for f in files_with_matches]
                result += "\n".join(sorted(rel_files)[:100])
                if len(files_with_matches) > 100:
                    result += f"\n\n... and {len(files_with_matches) - 100} more files"
                return result

            if output_mode == "count":
                return f"Found {match_count} match{'es' if match_count != 1 else ''} for '{pattern}'"

            if not matches:
                return f"No matches found for pattern: {pattern}"

            result = f"Found {len(matches)} match{'es' if len(matches) != 1 else ''} for '{pattern}':\n\n"
            result += "\n".join(matches[:100])

            if len(matches) > 100:
                result += f"\n\n... and {len(matches) - 100} more matches"

            return result

        except Exception as e:
            return f"Error searching content: {str(e)}"
