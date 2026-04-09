
"""Write tool - aligned with FileWriteTool.ts"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Optional

from claude_code.core.tools import BaseTool, ToolContext, ToolInputSchema
from claude_code.tools.file_utils import expand_path


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

    def is_error_result(
        self,
        result: str,
        input: Optional[Dict[str, Any]] = None,
    ) -> bool:
        return result.startswith("Error")

    async def call(self, input: Dict[str, Any], context: ToolContext) -> str:
        file_path = input.get("file_path", "")
        if not file_path:
            return "Error: 'file_path' parameter is required"

        content = input.get("content", "")

        full_path = expand_path(file_path)

        try:
            context.raise_if_cancelled()
            parent_dir = os.path.dirname(full_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

            context.capture_file_rollback(full_path)
            context.raise_if_cancelled()
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

            file_size = os.path.getsize(full_path)
            line_count = content.count("\n") + 1

            return f"Successfully wrote to {full_path} ({line_count} lines, {file_size} bytes)"

        except asyncio.CancelledError:
            raise
        except PermissionError:
            return f"Error: Permission denied writing to file: {full_path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"
