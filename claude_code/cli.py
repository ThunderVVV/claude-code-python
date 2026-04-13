"""CLI entry point for Claude Code Python - HTTP client only"""

from __future__ import annotations

import os
import socket
import sys
from typing import Optional

import click

from claude_code.utils.logging_config import setup_client_logging


def check_server_available(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


@click.command()
@click.option(
    "--host",
    "api_host",
    envvar="CLAUDE_CODE_API_HOST",
    default="localhost",
    help="API server host (default: localhost)",
)
@click.option(
    "--port",
    "api_port",
    envvar="CLAUDE_CODE_API_PORT",
    type=int,
    default=8000,
    help="API server port (default: 8000)",
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
    help="Path to write debug log file",
)
@click.version_option(version="0.2.0", prog_name="claude-code-python")
def main(
    api_host: str,
    api_port: int,
    debug: bool,
    log_file: Optional[str],
) -> None:
    """Claude Code Python - AI programming assistant TUI (HTTP client)

    This is the TUI client that connects to a FastAPI server.
    Start the server first with: cc-api
    """
    setup_client_logging(debug=debug)

    if debug:
        click.echo(click.style("Debug logging enabled", fg="yellow"))

    if not check_server_available(api_host, api_port):
        click.echo(
            click.style("Error: ", fg="red", bold=True)
            + f"API server not running at {api_host}:{api_port}",
            err=True,
        )
        click.echo(
            click.style("Please start the server first with:", fg="yellow") + " cc-api"
        )
        sys.exit(1)

    click.echo(
        click.style(f"Connecting to API server at {api_host}:{api_port}", fg="green")
    )

    try:
        run_tui(
            api_host=api_host,
            api_port=api_port,
            working_directory=os.getcwd(),
        )
    except ImportError as e:
        click.echo(
            click.style("Error: ", fg="red", bold=True) + f"Import error: {e}",
            err=True,
        )
        sys.exit(1)


def run_tui(
    api_host: str,
    api_port: int,
    working_directory: str,
) -> None:
    from claude_code.client.http_client import ClaudeCodeHttpClient
    from claude_code.ui.app import ClaudeCodeApp

    client = ClaudeCodeHttpClient(api_host, api_port)

    app = ClaudeCodeApp(
        client=client,
        working_directory=working_directory,
    )
    app.run()


if __name__ == "__main__":
    main()
