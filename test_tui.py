#!/usr/bin/env python
"""Test script for TUI functionality"""

import os
import sys

# Set required environment variables for testing
os.environ['CLAUDE_CODE_API_URL'] = 'https://api.example.com/v1'
os.environ['CLAUDE_CODE_API_KEY'] = 'test-key'
os.environ['CLAUDE_CODE_MODEL'] = 'test-model'

from claude_code.core.query_engine import QueryEngine, QueryConfig
from claude_code.core.tools import ToolRegistry
from claude_code.services.openai_client import OpenAIClientConfig
from claude_code.tools.file_tools import ReadTool, WriteTool, EditTool, GlobTool, GrepTool
from claude_code.tools.bash_tool import BashTool
from claude_code.ui.app import ClaudeCodeApp

def main() -> None:
    """Launch the TUI manually for local debugging."""
    registry = ToolRegistry()
    for tool_cls in [ReadTool, WriteTool, EditTool, GlobTool, GrepTool, BashTool]:
        registry.register(tool_cls())

    client_config = OpenAIClientConfig(
        api_url=os.environ['CLAUDE_CODE_API_URL'],
        api_key=os.environ['CLAUDE_CODE_API_KEY'],
        model_name=os.environ['CLAUDE_CODE_MODEL'],
    )
    query_config = QueryConfig(
        system_prompt='',
        stream=True,
    )

    engine = QueryEngine(client_config, registry, query_config)
    app = ClaudeCodeApp(engine, model_name=os.environ['CLAUDE_CODE_MODEL'])
    print("Starting TUI... Press ESC or 'q' to quit.")
    app.run()


if __name__ == "__main__":
    main()
