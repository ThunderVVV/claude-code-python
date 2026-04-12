"""Glob tool - aligned with GlobTool.ts"""

from __future__ import annotations

import glob as glob_module
import os
from typing import Any, Dict, Optional

from claude_code.core.tools import BaseTool, ToolContext, ToolInputSchema
from claude_code.tools.file_utils import expand_path


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
                "description": 'The glob pattern to match files against (e.g., "**/*.js")',
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

    def get_tool_use_summary(
        self, input: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        if not input:
            return None
        pattern = input.get("pattern", "")
        return f"'{pattern}'" if pattern else None

    def get_activity_description(
        self, input: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
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
        full_search_path = expand_path(search_path)

        try:
            full_pattern = os.path.join(full_search_path, pattern)
            matches = glob_module.glob(full_pattern, recursive=True)
            matches.sort(
                key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0,
                reverse=True,
            )

            if not matches:
                return f"No files found matching pattern: {pattern}"

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
