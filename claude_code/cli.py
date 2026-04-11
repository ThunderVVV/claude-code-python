"""CLI entry point for Claude Code Python - gRPC client only"""

from __future__ import annotations

import os
import socket
import sys
from typing import Optional

import click
from dotenv import load_dotenv

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
    "grpc_host",
    envvar="CLAUDE_CODE_GRPC_HOST",
    default="localhost",
    help="gRPC server host (default: localhost)",
)
@click.option(
    "--port",
    "grpc_port",
    envvar="CLAUDE_CODE_GRPC_PORT",
    type=int,
    default=50051,
    help="gRPC server port (default: 50051)",
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
@click.option(
    "--env-file",
    type=click.Path(exists=True),
    help="Path to .env file",
)
@click.version_option(version="0.2.0", prog_name="claude-code-python")
def main(
    grpc_host: str,
    grpc_port: int,
    debug: bool,
    log_file: Optional[str],
    env_file: Optional[str],
) -> None:
    """Claude Code Python - AI programming assistant TUI (gRPC client)

    This is the TUI client that connects to a gRPC server.
    Start the server first with: cc-server
    """
    setup_client_logging(debug=debug)

    if debug:
        click.echo(click.style("Debug logging enabled", fg="yellow"))

    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    if not check_server_available(grpc_host, grpc_port):
        click.echo(
            click.style("Error: ", fg="red", bold=True)
            + f"gRPC server not running at {grpc_host}:{grpc_port}",
            err=True,
        )
        click.echo(
            click.style("Please start the server first with:", fg="yellow")
            + " cc-server"
        )
        sys.exit(1)

    click.echo(
        click.style(f"Connecting to gRPC server at {grpc_host}:{grpc_port}", fg="green")
    )

    try:
        run_tui(
            grpc_host=grpc_host,
            grpc_port=grpc_port,
            working_directory=os.getcwd(),
        )
    except ImportError as e:
        click.echo(
            click.style("Error: ", fg="red", bold=True) + f"Import error: {e}",
            err=True,
        )
        sys.exit(1)


def run_tui(
    grpc_host: str,
    grpc_port: int,
    working_directory: str,
) -> None:
    from claude_code.client.grpc_client import ClaudeCodeClient
    from claude_code.ui.app import ClaudeCodeApp

    client = ClaudeCodeClient(grpc_host, grpc_port)

    app = ClaudeCodeApp(
        client=client,
        working_directory=working_directory,
    )
    app.run()


if __name__ == "__main__":
    main()
