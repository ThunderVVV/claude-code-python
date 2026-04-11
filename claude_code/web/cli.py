"""Web server CLI entry point (FastAPI version)"""

from __future__ import annotations

import asyncio
from typing import Optional

import click
import uvicorn

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

    from claude_code.web.server import create_app, set_grpc_config
    from claude_code.client.grpc_client import ClaudeCodeClient

    # Set gRPC config for lifespan
    set_grpc_config(grpc_host, grpc_port)

    click.echo(
        click.style(
            f"Starting Claude Code web server on http://{web_host}:{web_port}",
            fg="green",
        )
    )
    click.echo(f"🔌 Will connect to gRPC server at: {grpc_host}:{grpc_port}")

    # Create app (connection happens in lifespan)
    app = create_app()

    # Run with uvicorn
    uvicorn.run(
        app,
        host=web_host,
        port=web_port,
        log_level="debug" if debug else "info",
    )


if __name__ == "__main__":
    main()
