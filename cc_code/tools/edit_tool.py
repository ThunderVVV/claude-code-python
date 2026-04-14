"""Edit tool - aligned with FileEditTool.ts"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Optional

from cc_code.core.tools import (
    BaseTool,
    ToolContext,
    ToolInputSchema,
)
from cc_code.tools.file_utils import (
    expand_path,
    find_actual_string,
    preserve_quote_style,
)


class EditTool(BaseTool):
    """Tool for editing text files - aligned with FileEditTool.ts"""

    name = "Edit"
    description = """Performs exact string replacements in files.

Usage:
- You must use your `Read` tool at least once in the conversation before editing. This tool will error if you attempt an edit without reading the file.
- When editing text from Read tool output, ensure you preserve the exact indentation (tabs/spaces) as it appears AFTER the line number prefix. The line number prefix format is: line number + tab. Everything after that is the actual file content to match. Never include any part of the line number prefix in the old_string or new_string.
- ALWAYS prefer editing existing files in the codebase. NEVER write new files unless explicitly required.
- Only use emojis if the user explicitly requests it. Avoid writing emojis to files unless asked.
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

    def get_tool_use_summary(
        self, input: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        if not input:
            return None
        path = input.get("file_path", "")
        if path:
            return os.path.basename(path)
        return None

    def get_activity_description(
        self, input: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        if not input:
            return "Editing file"
        path = input.get("file_path", "")
        if path:
            return f"Editing {os.path.basename(path)}"
        return "Editing file"

    async def call(self, input: Dict[str, Any], context: ToolContext) -> str:
        file_path = input.get("file_path", "")
        if not file_path:
            return "Error: 'file_path' parameter is required"

        old_string = input.get("old_string", "")
        new_string = input.get("new_string", "")
        replace_all = input.get("replace_all", False)

        full_path = expand_path(file_path)

        if not os.path.exists(full_path):
            return f"Error: File does not exist: {full_path}"

        try:
            context.raise_if_cancelled()
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            actual_old_string = find_actual_string(content, old_string)
            if actual_old_string is None:
                return f"Error: Could not find the specified text in {full_path}"

            actual_new_string = preserve_quote_style(
                old_string, actual_old_string, new_string
            )

            count = content.count(actual_old_string)
            if count > 1 and not replace_all:
                return (
                    f"Error: Found {count} occurrences of the specified text in {full_path}. "
                    f"Use replace_all=true to replace all occurrences, or provide a more specific old_string."
                )

            if replace_all:
                new_content = content.replace(actual_old_string, actual_new_string)
            else:
                new_content = content.replace(actual_old_string, actual_new_string, 1)

            context.raise_if_cancelled()
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return f"Successfully edited {full_path} (replaced {count} occurrence{'s' if count > 1 else ''})"

        except asyncio.CancelledError:
            raise
        except PermissionError:
            return f"Error: Permission denied editing file: {full_path}"
        except UnicodeDecodeError:
            return f"Error: File appears to be binary: {full_path}"
        except Exception as e:
            return f"Error editing file: {str(e)}"
