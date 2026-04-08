#!/usr/bin/env python3
"""Manual TUI launcher for local debugging."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)
load_dotenv(PROJECT_ROOT / ".env")

# Provide safe defaults for layout debugging when no real config is present.
os.environ.setdefault("CLAUDE_CODE_API_URL", "https://api.example.com/v1")
os.environ.setdefault("CLAUDE_CODE_API_KEY", "test-key")
os.environ.setdefault("CLAUDE_CODE_MODEL", "test-model")

from claude_code.core.query_engine import QueryEngine, QueryConfig  # noqa: E402
from claude_code.core.tools import ToolRegistry  # noqa: E402
from claude_code.services.openai_client import OpenAIClientConfig  # noqa: E402
from claude_code.tools.bash_tool import BashTool  # noqa: E402
from claude_code.tools.file_tools import (  # noqa: E402
    EditTool,
    GlobTool,
    GrepTool,
    ReadTool,
    WriteTool,
)
from claude_code.ui.app import ClaudeCodeApp  # noqa: E402


def main() -> None:
    """Launch the TUI manually for local debugging."""
    registry = ToolRegistry()
    for tool_cls in [ReadTool, WriteTool, EditTool, GlobTool, GrepTool, BashTool]:
        registry.register(tool_cls())

    client_config = OpenAIClientConfig(
        api_url=os.environ["CLAUDE_CODE_API_URL"],
        api_key=os.environ["CLAUDE_CODE_API_KEY"],
        model_name=os.environ["CLAUDE_CODE_MODEL"],
    )
    query_config = QueryConfig(
        system_prompt="",
        stream=True,
    )

    engine = QueryEngine(client_config, registry, query_config)
    app = ClaudeCodeApp(engine, model_name=os.environ["CLAUDE_CODE_MODEL"])
    print("Starting TUI... Press ESC or 'q' to quit.")
    app.run()


if __name__ == "__main__":
    main()
