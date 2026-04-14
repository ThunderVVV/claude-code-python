from __future__ import annotations

import asyncio
from pathlib import Path

from claude_code.core.tools import ToolContext
from claude_code.tools.bash_tool import BashTool


async def _run_bash(command: str) -> str:
    tool = BashTool()
    context = ToolContext(
        working_directory=str(Path.cwd()),
        project_root=str(Path.cwd()),
        session_id="test-session",
    )
    return await tool.call({"command": command}, context)


def test_bash_output_does_not_emit_stderr_field_label() -> None:
    result = asyncio.run(_run_bash("echo stdout-message; echo stderr-message 1>&2"))

    assert "[stderr]" not in result
    assert "stdout-message" in result
    assert "stderr-message" in result
