"""Web server CLI entry point"""

from __future__ import annotations

import asyncio
from typing import Optional

import click

from claude_code.utils.logging_config import setup_server_logging


@click.command()
@click.option(
    "--grpc-host",
    default="localhost",
    help="gRPC server host",
)
@click.option(
    "--grpc-port",
    default=50051,
    type=int,
    help="gRPC server port",
)
@click.option(
    "--web-host",
    default="0.0.0.0",
    help="Host to bind the web server to",
)
@click.option(
    "--web-port",
    default=8080,
    type=int,
    help="Port to bind the web server to",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging",
)
def main(
    grpc_host: str,
    grpc_port: int,
    web_host: str,
    web_port: int,
    debug: bool,
) -> None:
    """Start the Claude Code web server (connects to gRPC backend)"""
    setup_server_logging(debug=debug)
    if debug:
        click.echo(click.style("Debug logging enabled", fg="yellow"))

    from claude_code.web.server import run_web_server

    click.echo(
        click.style(
            f"Starting Claude Code web server on http://{web_host}:{web_port}",
            fg="green",
        )
    )
    asyncio.run(
        run_web_server(
            grpc_host=grpc_host,
            grpc_port=grpc_port,
            web_host=web_host,
            web_port=web_port,
        )
    )


if __name__ == "__main__":
    main()
