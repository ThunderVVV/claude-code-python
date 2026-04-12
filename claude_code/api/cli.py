"""API Server CLI entry point"""

from __future__ import annotations

import asyncio
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
from claude_code.utils.logging_config import setup_server_logging


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
    help="OpenAI compatible API URL",
)
@click.option(
    "--api-key",
    help="API key for authentication",
)
@click.option(
    "--model",
    help="Model name to use",
)
@click.option(
    "--host",
    default="0.0.0.0",
    help="Host to bind the server to",
)
@click.option(
    "--port",
    default=8000,
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
    """Start the Claude Code FastAPI server and browser UI"""
    setup_server_logging(debug=debug)
    if debug:
        click.echo(click.style("Debug logging enabled", fg="yellow"))

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

    from claude_code.api.server import set_global_dependencies, app
    import uvicorn

    set_global_dependencies(client_config, tool_registry)

    click.echo(
        click.style(f"Starting Claude Code FastAPI server on {host}:{port}", fg="green")
    )
    display_host = "localhost" if host == "0.0.0.0" else host
    click.echo(
        click.style(f"Health check: http://{display_host}:{port}/health", fg="yellow")
    )
    click.echo(click.style(f"Browser UI: http://{display_host}:{port}/", fg="yellow"))

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info" if not debug else "debug",
        access_log=debug,
    )
    server = uvicorn.Server(config)

    try:
        asyncio.run(server.serve())
    except KeyboardInterrupt:
        click.echo("\n" + click.style("Server stopped by user", fg="yellow"))
    except Exception as e:
        click.echo(click.style(f"Server error: {e}", fg="red"))
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
