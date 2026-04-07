
"""CLI entry point for Claude Code Python - aligned with TypeScript main.tsx and cli.tsx"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Optional

import click
from dotenv import load_dotenv

from claude_code.core.messages import (
    Message,
    MessageRole,
    TextEvent,
    ToolUseEvent,
    ToolResultEvent,
    MessageCompleteEvent,
    TurnCompleteEvent,
    ErrorEvent,
)
from claude_code.core.query_engine import QueryEngine, QueryConfig
from claude_code.core.tools import ToolRegistry
from claude_code.services.openai_client import OpenAIClientConfig
from claude_code.tools.file_tools import (
    ReadTool,
    WriteTool,
    EditTool,
    GlobTool,
    GrepTool,
)
from claude_code.tools.bash_tool import BashTool


def create_tool_registry() -> ToolRegistry:
    """Create and populate the tool registry with all available tools"""
    registry = ToolRegistry()
    registry.register(ReadTool())
    registry.register(WriteTool())
    registry.register(EditTool())
    registry.register(GlobTool())
    registry.register(GrepTool())
    registry.register(BashTool())
    return registry


def print_tool_use_header(tool_name: str, tool_input: dict) -> None:
    """Print a formatted header for tool use"""
    click.echo(f"\n  {click.style(tool_name, fg='yellow', bold=True)}")

    # Print key parameters
    if "file_path" in tool_input:
        click.echo(f"   📄 {tool_input['file_path']}")
    elif "command" in tool_input:
        cmd = tool_input["command"]
        if len(cmd) > 80:
            cmd = cmd[:77] + "..."
        click.echo(f"   ⌨️  {cmd}")
    elif "pattern" in tool_input:
        click.echo(f"   🔍 {tool_input['pattern']}")


def print_tool_result(result: str, is_error: bool = False) -> None:
    """Print tool result with appropriate formatting"""
    if is_error:
        click.echo(click.style(f"   ❌ {result}", fg="red"))
    else:
        # Truncate long results
        lines = result.split("\n")
        if len(lines) > 20:
            display_lines = lines[:20]
            display_lines.append(f"... ({len(lines) - 20} more lines)")
            result = "\n".join(display_lines)

        # Indent result lines
        for line in result.split("\n"):
            click.echo(f"   {line}")


async def run_cli_mode(
    api_url: str,
    api_key: str,
    model_name: str,
    system_prompt: Optional[str] = None,
) -> None:
    """Run Claude Code in simple CLI mode"""
    registry = create_tool_registry()

    client_config = OpenAIClientConfig(
        api_url=api_url,
        api_key=api_key,
        model_name=model_name,
    )

    query_config = QueryConfig(
        system_prompt=system_prompt or "",
        stream=True,
    )

    # Print header - using Claude orange color
    click.echo(click.style("=" * 60, fg="yellow"))  # Yellow approximates orange in terminal
    click.echo(click.style("  Claude Code Python", fg="yellow", bold=True))
    click.echo(click.style("=" * 60, fg="yellow"))
    click.echo(f"  Model: {click.style(model_name, fg='yellow')}")
    click.echo(f"  API:   {click.style(api_url, fg='bright_black')}")
    click.echo(click.style("=" * 60, fg="yellow"))
    click.echo("  Type 'quit' or 'exit' to exit.")
    click.echo("")

    async with QueryEngine(client_config, registry, query_config) as engine:
        while True:
            try:
                # Get user input
                user_input = click.prompt(
                    click.style("You: ", fg="green", bold=True),
                    type=str,
                    prompt_suffix="",
                )

                # Handle exit commands
                if user_input.lower() in ("quit", "exit", "q"):
                    click.echo(click.style("\n  Goodbye! 👋", fg="yellow"))
                    break

                # Skip empty input
                if not user_input.strip():
                    continue

                click.echo("")  # Blank line before response

                # Process query with callbacks
                current_text = ""
                in_tool_block = False

                async for event in engine.submit_message(user_input):
                    if isinstance(event, TextEvent):
                        # Print streaming text
                        if not in_tool_block:
                            click.echo(event.text, nl=False)
                            current_text += event.text
                        else:
                            # First text after tools
                            click.echo(f"\n\n{event.text}", nl=False)
                            in_tool_block = False
                            current_text = event.text

                    elif isinstance(event, ToolUseEvent):
                        # Print tool use header
                        if current_text:
                            click.echo()  # Newline after text
                            current_text = ""
                        print_tool_use_header(event.tool_name, event.input)
                        in_tool_block = True

                    elif isinstance(event, ToolResultEvent):
                        # Print tool result
                        print_tool_result(event.result, event.is_error)

                    elif isinstance(event, ErrorEvent):
                        click.echo(click.style(f"\n  Error: {event.error}", fg="red"))

                # Ensure newline after response
                if current_text:
                    click.echo()

                click.echo()  # Blank line before next prompt

            except click.exceptions.Abort:
                click.echo(click.style("\n\n  Interrupted. Type 'quit' or 'exit' to exit.\n", fg="yellow"))
            except KeyboardInterrupt:
                click.echo(click.style("\n\n  Interrupted. Type 'quit' or 'exit' to exit.\n", fg="yellow"))
            except Exception as e:
                click.echo(click.style(f"\n  Error: {str(e)}\n", fg="red"), err=True)


@click.command()
@click.option(
    "--api-url",
    envvar="CLAUDE_CODE_API_URL",
    help="OpenAI compatible API URL (e.g., https://api.openai.com/v1)",
)
@click.option(
    "--api-key",
    envvar="CLAUDE_CODE_API_KEY",
    help="API key for authentication",
)
@click.option(
    "--model",
    envvar="CLAUDE_CODE_MODEL",
    help="Model name to use",
)
@click.option(
    "--system-prompt",
    envvar="CLAUDE_CODE_SYSTEM_PROMPT",
    help="System prompt for the assistant",
)
@click.option(
    "--tui",
    is_flag=True,
    help="Use Textual TUI interface (experimental)",
)
@click.option(
    "--env-file",
    type=click.Path(exists=True),
    help="Path to .env file",
)
@click.option(
    "--max-turns",
    type=int,
    default=20,
    help="Maximum number of turns per query (default: 20)",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging",
)
@click.version_option(version="0.1.0", prog_name="claude-code-python")
def main(
    api_url: Optional[str],
    api_key: Optional[str],
    model: Optional[str],
    system_prompt: Optional[str],
    tui: bool,
    env_file: Optional[str],
    max_turns: int,
    debug: bool,
) -> None:
    """Claude Code Python - AI programming assistant

    A Python implementation of Claude Code that helps with software engineering tasks.
    Uses OpenAI-compatible APIs to connect to various LLM providers.
    """
    # Enable debug logging if requested
    if debug:
        import logging
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        click.echo(click.style("Debug logging enabled", fg="yellow"))

    # Load environment variables
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    # Get configuration from environment if not provided
    if not api_url:
        api_url = os.environ.get("CLAUDE_CODE_API_URL")
    if not api_key:
        api_key = os.environ.get("CLAUDE_CODE_API_KEY")
    if not model:
        model = os.environ.get("CLAUDE_CODE_MODEL")

    # Validate configuration
    if not api_url or not api_key or not model:
        click.echo(
            click.style("Error: ", fg="red", bold=True) +
            "API URL, API key, and model must be provided either via "
            "command line options or environment variables.",
            err=True,
        )
        click.echo("\nEnvironment variables:", err=True)
        click.echo("  CLAUDE_CODE_API_URL   - API endpoint URL", err=True)
        click.echo("  CLAUDE_CODE_API_KEY   - API authentication key", err=True)
        click.echo("  CLAUDE_CODE_MODEL     - Model name to use", err=True)
        click.echo("\nExample:", err=True)
        click.echo("  export CLAUDE_CODE_API_URL=https://api.openai.com/v1", err=True)
        click.echo("  export CLAUDE_CODE_API_KEY=sk-...", err=True)
        click.echo("  export CLAUDE_CODE_MODEL=gpt-4", err=True)
        sys.exit(1)

    # Ensure API URL doesn't end with /chat/completions
    if api_url.endswith("/chat/completions"):
        api_url = api_url.rsplit("/chat/completions", 1)[0]
    elif api_url.endswith("/v1/chat/completions"):
        api_url = api_url.rsplit("/v1/chat/completions", 1)[0] + "/v1"

    # Run in TUI or CLI mode
    if tui:
        try:
            from claude_code.ui.app import ClaudeCodeApp

            registry = create_tool_registry()
            client_config = OpenAIClientConfig(
                api_url=api_url,
                api_key=api_key,
                model_name=model,
            )
            query_config = QueryConfig(
                system_prompt=system_prompt or "",
                stream=True,
                max_turns=max_turns,
            )
            engine = QueryEngine(client_config, registry, query_config)
            app = ClaudeCodeApp(engine, model_name=model)
            app.run()
        except ImportError as e:
            click.echo(
                click.style("Error: ", fg="red", bold=True) +
                f"Textual is required for TUI mode. Install it with 'pip install textual'.\n"
                f"Import error: {e}",
                err=True,
            )
            sys.exit(1)
    else:
        asyncio.run(run_cli_mode(api_url, api_key, model, system_prompt))


if __name__ == "__main__":
    main()
