"""API Server CLI entry point"""

from __future__ import annotations

import asyncio
import sys

import click

from cc_code.core.settings import SettingsStore
from cc_code.core.tools import ToolRegistry
from cc_code.tools import (
    ReadTool,
    WriteTool,
    EditTool,
    GlobTool,
    GrepTool,
)
from cc_code.tools.bash_tool import BashTool
from cc_code.utils.logging_config import setup_server_logging


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
    "--debug",
    is_flag=True,
    help="Enable debug logging",
)
def main(
    host: str,
    port: int,
    debug: bool,
) -> None:
    """Start the CC Code FastAPI server and browser UI"""
    setup_server_logging(debug=debug)
    if debug:
        click.echo(click.style("Debug logging enabled", fg="yellow"))

    settings_store = SettingsStore()
    settings = settings_store.ensure_settings()

    if not settings.models or not settings.current_model:
        click.echo(
            click.style("Error: ", fg="red", bold=True)
            + "No model settings found in ~/.cc-py/settings.json.",
            err=True,
        )
        sys.exit(1)

    tool_registry = create_tool_registry()

    from cc_code.api.server import create_app
    import uvicorn

    app = create_app(
        settings_store=settings_store,
        tool_registry=tool_registry,
    )

    click.echo(
        click.style(f"Starting CC Code FastAPI server on {host}:{port}", fg="green")
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
