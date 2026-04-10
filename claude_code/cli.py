
"""CLI entry point for Claude Code Python - aligned with TypeScript main.tsx and cli.tsx"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv

from claude_code.core.context_window import get_configured_context_window_tokens
from claude_code.core.query_engine import QueryEngine, QueryConfig
from claude_code.core.session_store import PersistedSession, SessionStore, SessionSummary
from claude_code.core.tools import ToolRegistry
from claude_code.services.openai_client import OpenAIClientConfig
from claude_code.tools import (
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


def resolve_log_path(
    log_file: Optional[str],
    debug: bool,
    now: Optional[datetime] = None,
) -> Optional[str]:
    """Return the log file path for the current invocation."""
    if log_file:
        return log_file
    if not debug:
        return None
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    return str(Path(".logs") / f"claude-code-python-debug-{timestamp}.log")


def ensure_log_directory(log_path: Optional[str]) -> None:
    """Create the parent directory for a log path when needed."""
    if not log_path:
        return
    Path(log_path).expanduser().parent.mkdir(parents=True, exist_ok=True)


def format_session_summary(index: int, session: SessionSummary) -> str:
    """Format a saved session for terminal selection."""
    updated_at = session.updated_at.replace("T", " ")
    cwd = session.working_directory or "."
    return (
        f"{index}. {session.title}\n"
        f"   id: {session.session_id}\n"
        f"   updated: {updated_at}\n"
        f"   cwd: {cwd}\n"
        f"   messages: {session.message_count}"
    )


def resolve_session_choice(
    choice: str,
    sessions: list[SessionSummary],
) -> Optional[str]:
    """Resolve a numeric picker choice or literal session ID."""
    normalized = choice.strip()
    if not normalized:
        return None

    if normalized.isdigit():
        index = int(normalized)
        if 1 <= index <= len(sessions):
            return sessions[index - 1].session_id
        return None

    return normalized


def prompt_for_session_selection(session_store: SessionStore) -> Optional[str]:
    """Prompt in the terminal for a saved TUI session."""
    sessions = session_store.list_sessions()
    if not sessions:
        click.echo("No saved sessions found. Starting a new session.")
        return None

    click.echo("Saved sessions:\n")
    for index, session in enumerate(sessions, start=1):
        click.echo(format_session_summary(index, session))
        click.echo("")

    while True:
        choice = click.prompt(
            "Select a session by number or session id",
            type=str,
            default="",
            show_default=False,
        )
        resolved_session_id = resolve_session_choice(choice, sessions)
        if resolved_session_id is not None:
            return resolved_session_id

        if not choice.strip():
            return None

        click.echo(click.style("Invalid selection. Try again.\n", fg="red"))


def resolve_initial_tui_session(
    session_store: SessionStore,
    session_id: Optional[str],
    use_sessions: bool,
) -> Optional[PersistedSession]:
    """Resolve the initial TUI session from CLI flags."""
    if session_id and use_sessions:
        raise click.UsageError("--resume and --sessions cannot be used together.")

    resolved_session_id = session_id
    if use_sessions:
        resolved_session_id = prompt_for_session_selection(session_store)

    if not resolved_session_id:
        return None

    session = session_store.load_session(resolved_session_id)
    if session is None:
        raise click.ClickException(f"Session not found: {resolved_session_id}")

    return session


def setup_logging(log_path: Optional[str], debug: bool) -> None:
    """Set up logging with file and/or console handlers."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Root logger - set to WARNING to suppress third-party library noise
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)

    # Enable DEBUG for our package only
    claude_logger = logging.getLogger('claude_code')
    claude_logger.setLevel(logging.DEBUG)

    if log_path:
        file_handler = logging.FileHandler(log_path, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(log_format))
        claude_logger.addHandler(file_handler)

    if debug:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(logging.Formatter(log_format))
        claude_logger.addHandler(console_handler)


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
    "--env-file",
    type=click.Path(exists=True),
    help="Path to .env file",
)
@click.option(
    "--resume",
    "session_id",
    help="Resume a saved TUI session by session ID",
)
@click.option(
    "--sessions",
    "sessions",
    is_flag=True,
    help="Interactively choose a saved TUI session before launch",
)
@click.option(
    "--max-turns",
    type=int,
    default=1000000,
    help="Maximum number of turns per query (default: 1000000)",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging to console",
)
@click.option(
    "--log-file",
    type=click.Path(),
    default=None,
    help="Path to write debug log file (default: .logs/claude-code-python-debug-<timestamp>.log if --debug)",
)
@click.version_option(version="0.1.0", prog_name="claude-code-python")
def main(
    api_url: Optional[str],
    api_key: Optional[str],
    model: Optional[str],
    system_prompt: Optional[str],
    env_file: Optional[str],
    session_id: Optional[str],
    sessions: bool,
    max_turns: int,
    debug: bool,
    log_file: Optional[str],
) -> None:
    """Claude Code Python - AI programming assistant with TUI interface

    A Python implementation of Claude Code that helps with software engineering tasks.
    Uses OpenAI-compatible APIs to connect to various LLM providers.
    """
    # Determine log file path
    log_path = resolve_log_path(log_file, debug)
    ensure_log_directory(log_path)

    # Configure logging
    setup_logging(log_path, debug)

    if log_path:
        click.echo(click.style(f"Debug logging to: {log_path}", fg="yellow"))
    elif debug:
        click.echo(click.style("Debug logging enabled", fg="yellow"))

    # Load environment variables
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    # Get configuration from environment if not provided
    api_url = api_url or os.environ.get("CLAUDE_CODE_API_URL")
    api_key = api_key or os.environ.get("CLAUDE_CODE_API_KEY")
    model = model or os.environ.get("CLAUDE_CODE_MODEL")
    context_window_tokens = get_configured_context_window_tokens()

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
    if api_url.endswith("/v1/chat/completions"):
        api_url = api_url.removesuffix("/chat/completions")
    else:
        api_url = api_url.removesuffix("/chat/completions")

    # Launch TUI
    try:
        from claude_code.ui.app import ClaudeCodeApp

        registry = create_tool_registry()
        session_store = SessionStore()
        initial_session = resolve_initial_tui_session(
            session_store,
            session_id,
            sessions,
        )
        client_config = OpenAIClientConfig(
            api_url=api_url,
            api_key=api_key,
            model_name=model,
        )
        query_config = QueryConfig(
            system_prompt=system_prompt or "",
            stream=True,
            max_turns=max_turns,
            working_directory=(
                initial_session.working_directory if initial_session else ""
            ),
        )
        engine = QueryEngine(
            client_config,
            registry,
            query_config,
            session_id=(initial_session.session_id if initial_session else None),
            initial_messages=(
                list(initial_session.messages) if initial_session else None
            ),
            initial_current_turn=(
                initial_session.current_turn if initial_session else 0
            ),
            initial_usage=(
                initial_session.total_usage if initial_session else None
            ),
        )
        app = ClaudeCodeApp(
            engine,
            model_name=model,
            context_window_tokens=context_window_tokens,
            session_store=session_store,
            initial_session=initial_session,
        )
        app.run()
    except ImportError as e:
        click.echo(
            click.style("Error: ", fg="red", bold=True) +
            f"Textual is required for TUI mode. Install it with 'pip install textual'.\n"
            f"Import error: {e}",
            err=True,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
