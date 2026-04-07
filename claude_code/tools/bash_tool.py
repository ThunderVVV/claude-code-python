
"""Bash tool for executing shell commands - aligned with TypeScript version"""

from __future__ import annotations

import asyncio
import os
import shlex
import shutil
from typing import Any, Dict, List, Optional

from claude_code.core.tools import (
    BaseTool,
    ToolContext,
    ToolInputSchema,
    PermissionResult,
    ValidationResult,
)


# Default timeout in milliseconds
DEFAULT_TIMEOUT_MS = 120000  # 2 minutes
MAX_TIMEOUT_MS = 600000  # 10 minutes

# Commands that typically produce no stdout on success
SILENT_COMMANDS = {
    "mv", "cp", "rm", "mkdir", "rmdir", "chmod", "chown", "chgrp",
    "touch", "ln", "cd", "export", "unset", "wait",
}

# Search commands for collapsible display
SEARCH_COMMANDS = {
    "find", "grep", "rg", "ag", "ack", "locate", "which", "whereis",
}

# Read/view commands for collapsible display
READ_COMMANDS = {
    "cat", "head", "tail", "less", "more", "wc", "stat", "file",
    "strings", "jq", "awk", "cut", "sort", "uniq", "tr",
}

# List commands for collapsible display
LIST_COMMANDS = {
    "ls", "tree", "du",
}


def get_base_command(command: str) -> str:
    """Extract the base command from a potentially complex command string"""
    # Split on common operators and pipes
    for separator in ["|", "&&", "||", ";", "\n"]:
        if separator in command:
            parts = command.split(separator)
            command = parts[0].strip()

    # Get the first word as the base command
    return command.split()[0] if command.split() else ""


def is_silent_command(command: str) -> bool:
    """Check if command is expected to produce no stdout on success"""
    base = get_base_command(command)
    return base in SILENT_COMMANDS


def is_search_command(command: str) -> bool:
    """Check if command is a search operation"""
    base = get_base_command(command)
    return base in SEARCH_COMMANDS


def is_read_command(command: str) -> bool:
    """Check if command is a read operation"""
    base = get_base_command(command)
    return base in READ_COMMANDS


def is_list_command(command: str) -> bool:
    """Check if command is a list operation"""
    base = get_base_command(command)
    return base in LIST_COMMANDS


class BashTool(BaseTool):
    """Tool for executing bash commands - aligned with BashTool.tsx"""

    name = "Bash"
    description = (
        "Executes a given bash command in a persistent shell session with optional timeout, "
        "handling shell operators like && and |, and allowing for background execution of long-running processes."
    )
    input_schema = ToolInputSchema(
        properties={
            "command": {
                "type": "string",
                "description": "The command to execute",
            },
            "timeout": {
                "type": "integer",
                "description": f"Timeout in milliseconds (default: {DEFAULT_TIMEOUT_MS}, max: {MAX_TIMEOUT_MS})",
                "default": DEFAULT_TIMEOUT_MS,
            },
            "description": {
                "type": "string",
                "description": "A clear, concise description of what this command does",
            },
            "sandbox": {
                "type": "boolean",
                "description": "Run the command in a sandbox for safety (default: true for certain commands)",
                "default": None,
            },
        },
        required=["command"],
    )
    aliases = ["bash", "sh", "shell"]

    def is_read_only(self, input: Dict[str, Any]) -> bool:
        """Check if command is read-only"""
        command = input.get("command", "")
        return is_search_command(command) or is_read_command(command) or is_list_command(command)

    def is_concurrency_safe(self, input: Dict[str, Any]) -> bool:
        """Check if command can run concurrently"""
        return self.is_read_only(input)

    def is_destructive(self, input: Dict[str, Any]) -> bool:
        """Check if command performs destructive operations"""
        command = input.get("command", "")
        destructive_keywords = ["rm", "rmdir", "dd", "mkfs", "shred", "wipe"]
        for keyword in destructive_keywords:
            if keyword in command.split():
                return True
        return False

    def get_tool_use_summary(self, input: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Get summary for display"""
        if not input:
            return None
        command = input.get("command", "")
        description = input.get("description", "")

        if description:
            return description

        if command:
            # Truncate long commands
            if len(command) > 50:
                return command[:47] + "..."
            return command

        return None

    def get_activity_description(self, input: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Get activity description for spinner"""
        if not input:
            return "Running command"
        description = input.get("description", "")
        command = input.get("command", "")

        if description:
            return description

        base = get_base_command(command)
        if base:
            return f"Running {base}"
        return "Running command"

    def user_facing_name(self, input: Optional[Dict[str, Any]] = None) -> str:
        """Get human-readable name"""
        if not input:
            return self.name
        description = input.get("description", "")
        command = input.get("command", "")

        if description:
            return description

        base = get_base_command(command)
        if base:
            return f"{base} command"
        return self.name

    async def validate_input(
        self,
        input: Dict[str, Any],
        context: ToolContext,
    ) -> ValidationResult:
        """Validate command before execution"""
        command = input.get("command", "")
        if not command:
            return ValidationResult(
                result=False,
                message="command is required",
                error_code=1,
            )

        timeout = input.get("timeout", DEFAULT_TIMEOUT_MS)
        if timeout > MAX_TIMEOUT_MS:
            return ValidationResult(
                result=False,
                message=f"Timeout exceeds maximum allowed ({MAX_TIMEOUT_MS}ms)",
                error_code=2,
            )

        return ValidationResult(result=True)

    async def check_permissions(
        self,
        input: Dict[str, Any],
        context: ToolContext,
    ) -> PermissionResult:
        """Check if command is allowed"""
        # For now, allow all commands
        # In a full implementation, this would check against permission rules
        return PermissionResult(behavior="allow", updated_input=input)

    async def call(self, input: Dict[str, Any], context: ToolContext) -> str:
        command = input.get("command", "")
        if not command:
            return "Error: 'command' parameter is required"

        timeout_ms = input.get("timeout", DEFAULT_TIMEOUT_MS)
        description = input.get("description", "")

        # Convert timeout to seconds
        timeout_seconds = min(timeout_ms / 1000, MAX_TIMEOUT_MS / 1000)

        # Determine working directory
        workdir = context.working_directory

        try:
            # Create subprocess
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
                # Use shell to support operators like &&, ||, |
                executable=shutil.which("bash") or "/bin/bash",
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                # Kill the process on timeout
                try:
                    process.kill()
                    await process.wait()
                except ProcessLookupError:
                    pass

                return (
                    f"Command timed out after {timeout_seconds:.1f} seconds\n\n"
                    f"Command: {command}"
                )

            # Decode output
            stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
            stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""
            return_code = process.returncode or 0

            # Build result
            result_parts = []

            # Check if command was expected to be silent
            is_silent = is_silent_command(command)

            # Add exit code if non-zero
            if return_code != 0:
                result_parts.append(f"Exit code: {return_code}")

            # Add stdout
            if stdout_str.strip():
                result_parts.append(f"\n{stdout_str.strip()}")

            # Add stderr if present
            if stderr_str.strip():
                result_parts.append(f"\n[stderr]\n{stderr_str.strip()}")

            # If no output and successful
            if not result_parts:
                if is_silent:
                    return "Done"
                else:
                    return "(No output)"

            return "\n".join(result_parts).strip()

        except FileNotFoundError as e:
            return f"Error: Command not found: {str(e)}"
        except PermissionError:
            return f"Error: Permission denied executing command"
        except Exception as e:
            return f"Error executing command: {str(e)}"


# Export for convenience
Bash = BashTool()
