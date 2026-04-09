
"""Bash tool for executing shell commands - aligned with TypeScript version"""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
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
    description = """Executes a given bash command and returns its output.

The working directory persists between commands, but shell state does not. The shell environment is initialized from the user's profile (bash or zsh).

IMPORTANT: Avoid using this tool to run `find`, `grep`, `cat`, `head`, `tail`, `sed`, `awk`, or `echo` commands, unless explicitly instructed or after you have verified that a dedicated tool cannot accomplish your task. Instead, use the appropriate dedicated tool as this will provide a much better experience for the user:

 - File search: Use Glob (NOT find or ls)
 - Content search: Use Grep (NOT grep or rg)
 - Read files: Use Read (NOT cat/head/tail)
 - Edit files: Use Edit (NOT sed/awk)
 - Write files: Use Write (NOT echo >/cat <<EOF)
 - Communication: Output text directly (NOT echo/printf)

While the Bash tool can do similar things, it's better to use the built-in tools as they provide a better user experience and make it easier to review tool calls and give permission.

# Instructions
 - If your command will create new directories or files, first use this tool to run `ls` to verify the parent directory exists and is the correct location.
 - Always quote file paths that contain spaces with double quotes in your command (e.g., cd "path with spaces/file.txt")
 - Try to maintain your current working directory throughout the session by using absolute paths and avoiding usage of `cd`. You may use `cd` if the User explicitly requests it.
 - You may specify an optional timeout in milliseconds (up to 600000ms / 10 minutes). By default, your command will timeout after 120000ms (2 minutes).
 - You can use the `run_in_background` parameter to run the command in the background. Only use this if you don't need the result immediately and are OK being notified when the command completes later. You do not need to check the output right away - you'll be notified when it finishes. You do not need to use '&' at the end of the command when using this parameter.
 - When issuing multiple commands:
   - If the commands are independent and can run in parallel, make multiple Bash tool calls in a single message. Example: if you need to run "git status" and "git diff", send a single message with two Bash tool calls in parallel.
   - If the commands depend on each other and must run sequentially, use a single Bash call with '&&' to chain them together.
   - Use ';' only when you need to run commands sequentially but don't care if earlier commands fail.
   - DO NOT use newlines to separate commands (newlines are ok in quoted strings).
 - For git commands:
   - Prefer to create a new commit rather than amending an existing commit.
   - Before running destructive operations (e.g., git reset --hard, git push --force, git checkout --), consider whether there is a safer alternative that achieves the same goal. Only use destructive operations when they are truly the best approach.
   - Never skip hooks (--no-verify) or bypass signing (--no-gpg-sign, -c commit.gpgsign=false) unless the user has explicitly asked for it. If a hook fails, investigate and fix the underlying issue.
 - Avoid unnecessary `sleep` commands:
   - Do not sleep between commands that can run immediately — just run them.
   - If your command is long running and you would like to be notified when it finishes — use `run_in_background`. No sleep needed.
   - Do not retry failing commands in a sleep loop — diagnose the root cause.
   - If waiting for a background task you started with `run_in_background`, you will be notified when it completes — do not poll.
   - If you must sleep, keep the duration short (1-5 seconds) to avoid blocking the user."""
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
                "description": """Clear, concise description of what this command does in active voice. Never use words like "complex" or "risk" in the description.

For simple commands (git, npm, standard CLI tools), keep it brief (5-10 words):
- ls → "List files in current directory"
- git status → "Show working tree status"
- npm install → "Install package dependencies"

For commands that are harder to parse at a glance (piped commands, obscure flags, etc.), add enough context to clarify what it does:
- find . -name "*.tmp" -exec rm {} \\; → "Find and delete all .tmp files recursively"
- git reset --hard origin/main → "Discard all local changes and match remote main"
- curl -s url | jq '.data[]' → "Fetch JSON from URL and extract data array elements" """,
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

    def is_error_result(
        self,
        result: str,
        input: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if result.startswith("Error") or result.startswith("Command timed out after"):
            return True

        first_line = result.splitlines()[0] if result else ""
        match = re.match(r"Exit code:\s*(-?\d+)", first_line)
        return bool(match and int(match.group(1)) != 0)

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

    async def _terminate_process(
        self,
        process: asyncio.subprocess.Process,
    ) -> None:
        """Terminate an in-flight subprocess during timeout or cancellation."""
        if process.returncode is not None:
            return
        try:
            process.terminate()
            await asyncio.wait_for(process.wait(), timeout=1.0)
        except (ProcessLookupError, asyncio.TimeoutError):
            try:
                process.kill()
                await process.wait()
            except ProcessLookupError:
                pass

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
            context.raise_if_cancelled()

            # Create subprocess
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
                # Use shell to support operators like &&, ||, |
                executable=shutil.which("bash") or "/bin/bash",
            )

            communicate_task = asyncio.create_task(process.communicate())
            cancel_task: Optional[asyncio.Task[bool]] = None
            if context.cancel_event is not None:
                cancel_task = asyncio.create_task(context.cancel_event.wait())

            try:
                wait_tasks = {communicate_task}
                if cancel_task is not None:
                    wait_tasks.add(cancel_task)

                done, _pending = await asyncio.wait(
                    wait_tasks,
                    timeout=timeout_seconds,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if communicate_task in done:
                    stdout, stderr = communicate_task.result()
                elif cancel_task is not None and cancel_task in done:
                    await self._terminate_process(process)
                    raise asyncio.CancelledError
                else:
                    communicate_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await communicate_task
                    await self._terminate_process(process)
                    return (
                        f"Command timed out after {timeout_seconds:.1f} seconds\n\n"
                        f"Command: {command}"
                    )
            except asyncio.CancelledError:
                communicate_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await communicate_task
                await self._terminate_process(process)
                raise
            finally:
                if cancel_task is not None:
                    cancel_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await cancel_task

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
