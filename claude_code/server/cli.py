"""Server CLI entry point"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Optional

import click
from dotenv import load_dotenv

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
    registry = ToolRegistry()
    registry.register(ReadTool())
    registry.register(WriteTool())
    registry.register(EditTool())
    registry.register(GlobTool())
    registry.register(GrepTool())
    registry.register(BashTool())
    return registry


@click.command()
@click.option(
    "--api-url",
    envvar="CLAUDE_CODE_API_URL",
    help="OpenAI compatible API URL",
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
    "--host",
    default="[::]",
    help="Host to bind the server to",
)
@click.option(
    "--port",
    default=50051,
    type=int,
    help="Port to bind the server to",
)
@click.option(
    "--env-file",
    type=click.Path(exists=True),
    help="Path to .env file",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging",
)
def main(
    api_url: Optional[str],
    api_key: Optional[str],
    model: Optional[str],
    host: str,
    port: int,
    env_file: Optional[str],
    debug: bool,
) -> None:
    """Start the Claude Code gRPC server"""
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    api_url = api_url or os.environ.get("CLAUDE_CODE_API_URL")
    api_key = api_key or os.environ.get("CLAUDE_CODE_API_KEY")
    model = model or os.environ.get("CLAUDE_CODE_MODEL")

    if not api_url or not api_key or not model:
        click.echo(
            click.style("Error: ", fg="red", bold=True)
            + "API URL, API key, and model must be provided.",
            err=True,
        )
        sys.exit(1)

    if api_url.endswith("/v1/chat/completions"):
        api_url = api_url.removesuffix("/chat/completions")

    client_config = OpenAIClientConfig(
        api_url=api_url,
        api_key=api_key,
        model_name=model,
    )

    tool_registry = create_tool_registry()

    from claude_code.server.server import serve

    click.echo(
        click.style(f"Starting Claude Code gRPC server on {host}:{port}", fg="green")
    )
    asyncio.run(serve(client_config, tool_registry, host, port))


if __name__ == "__main__":
    main()
