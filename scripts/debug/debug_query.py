#!/usr/bin/env python3
"""
Debug script to diagnose tool execution issues.

Usage:
  python scripts/debug/debug_query.py

Set environment variables first:
  export CLAUDE_CODE_API_URL="your_api_url"
  export CLAUDE_CODE_API_KEY="your_api_key"
  export CLAUDE_CODE_MODEL="your_model_name"
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)
load_dotenv(PROJECT_ROOT / ".env")

from claude_code.core.query_engine import QueryEngine, QueryConfig  # noqa: E402
from claude_code.core.tools import ToolRegistry  # noqa: E402
from claude_code.services.openai_client import OpenAIClientConfig  # noqa: E402
from claude_code.tools.bash_tool import BashTool  # noqa: E402
from claude_code.tools.file_tools import GlobTool, GrepTool, ReadTool  # noqa: E402


def create_tool_registry() -> ToolRegistry:
    """Create a minimal read-only registry for query debugging."""
    registry = ToolRegistry()
    registry.register(ReadTool())
    registry.register(GlobTool())
    registry.register(GrepTool())
    registry.register(BashTool())
    return registry


async def main():
    """Run a single query and print each emitted event."""
    api_url = os.environ.get("CLAUDE_CODE_API_URL")
    api_key = os.environ.get("CLAUDE_CODE_API_KEY")
    model_name = os.environ.get("CLAUDE_CODE_MODEL")

    if not all([api_url, api_key, model_name]):
        print(
            "Error: Please set CLAUDE_CODE_API_URL, CLAUDE_CODE_API_KEY, "
            "and CLAUDE_CODE_MODEL"
        )
        sys.exit(1)

    print(f"=" * 60)
    print(f"API URL: {api_url}")
    print(f"Model: {model_name}")
    print(f"=" * 60)

    registry = create_tool_registry()
    client_config = OpenAIClientConfig(
        api_url=api_url,
        api_key=api_key,
        model_name=model_name,
    )
    query_config = QueryConfig(
        max_turns=5,
        stream=True,
    )

    engine = QueryEngine(client_config, registry, query_config)

    # Simple test: ask model to read a file
    test_prompt = "Please read the file pyproject.toml and tell me the project name"

    print(f"\nTest prompt: {test_prompt}")
    print(f"=" * 60)

    turn_count = 0
    tool_calls_made = 0
    tool_results_received = 0

    async for event in engine.submit_message(test_prompt):
        event_type = type(event).__name__

        if event_type == "TextEvent":
            print(f"[TEXT] {event.text}", end="", flush=True)

        elif event_type == "ToolUseEvent":
            tool_calls_made += 1
            print(f"\n[TOOL_USE] {event.tool_name}({event.input})")

        elif event_type == "ToolResultEvent":
            tool_results_received += 1
            result_preview = (
                event.result[:100] + "..." if len(event.result) > 100 else event.result
            )
            print(
                f"\n[TOOL_RESULT] {'ERROR' if event.is_error else 'OK'}: "
                f"{result_preview}"
            )

        elif event_type == "TurnCompleteEvent":
            turn_count = event.turn
            print(
                f"\n[TURN_COMPLETE] turn={event.turn}, "
                f"has_more={event.has_more_turns}, stop_reason={event.stop_reason}"
            )

        elif event_type == "ErrorEvent":
            print(f"\n[ERROR] {event.error}")

    print(f"\n" + f"=" * 60)
    print(f"Summary:")
    print(f"  Turns: {turn_count}")
    print(f"  Tool calls: {tool_calls_made}")
    print(f"  Tool results: {tool_results_received}")
    print(f"  Messages in state: {len(engine.get_messages())}")

    # Print message summary
    print(f"\nMessages:")
    for i, msg in enumerate(engine.get_messages()):
        role = msg.type.value
        tool_uses = msg.get_tool_uses() if hasattr(msg, "get_tool_uses") else []
        text = msg.get_text()[:50] + "..." if msg.get_text() else "(no text)"
        print(f"  {i}: {role} - {len(tool_uses)} tool uses, text: {text}")


if __name__ == "__main__":
    asyncio.run(main())
