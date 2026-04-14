"""Read tool - aligned with FileReadTool.ts"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from cc_code.core.tools import (
    BaseTool,
    ToolContext,
    ToolInputSchema,
)
from cc_code.tools.file_utils import expand_path, format_file_result

logger = logging.getLogger(__name__)


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
- This tool can only read text files, not directories, images, PDFs, or binary files. To read a directory, use an ls command via the Bash tool.
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
    max_result_size_chars = float("inf")

    def is_read_only(self, input: Dict[str, Any]) -> bool:
        return True

    def is_concurrency_safe(self, input: Dict[str, Any]) -> bool:
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

    async def call(self, input: Dict[str, Any], context: ToolContext) -> str:
        file_path = input.get("file_path", "")
        if not file_path:
            return "Error: 'file_path' parameter is required"

        offset = input.get("offset", 1)
        limit = input.get("limit", 2000)

        full_path = expand_path(file_path)

        if not os.path.exists(full_path):
            return f"Error: File does not exist: {full_path}"

        if os.path.isdir(full_path):
            return f"Error: Path is a directory, not a file: {full_path}"

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)

            if offset < 1:
                offset = 1

            start_idx = offset - 1
            end_idx = start_idx + limit

            selected_lines = lines[start_idx:end_idx]
            content = "".join(selected_lines)

            actual_end_line = min(offset + limit - 1, total_lines)

            result = format_file_result(
                full_path, content, offset, actual_end_line, total_lines
            )

            # Load nearby instructions if context provides the necessary info
            nearby_instructions: List[str] = []
            if context.instruction_service and context.message_id and context.messages:
                try:
                    
                    instructions = await context.instruction_service.resolve_nearby_instructions(
                        messages=context.messages,
                        filepath=full_path,
                        message_id=context.message_id,
                        project_root=context.project_root,
                    )
                    if instructions:
                        # instructions is now a list of formatted strings
                        nearby_instructions = []
                        for inst in instructions:
                            # Extract path from "Instructions from: <path>\n<content>"
                            lines = inst.split('\n', 1)
                            if lines[0].startswith("Instructions from: "):
                                path = lines[0][len("Instructions from: "):]
                                nearby_instructions.append(path)
                            result += f"\n\n---\n{inst}"
                        logger.debug(f"Appended {len(instructions)} nearby instructions to Read result")
                except Exception as e:
                    logger.warning(f"Failed to load nearby instructions: {e}")

            # Add metadata about loaded instructions (for deduplication tracking)
            if nearby_instructions:
                # Add a metadata marker that can be extracted later
                result += f"\n\n<!-- loaded: {json.dumps(nearby_instructions)} -->"

            return result

        except PermissionError:
            return f"Error: Permission denied reading file: {full_path}"
        except UnicodeDecodeError:
            return f"Error: File appears to be binary or uses an unsupported encoding: {full_path}"
        except Exception as e:
            return f"Error reading file: {str(e)}"
