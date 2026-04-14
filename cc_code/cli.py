"""CLI entry point for CC Code Python - HTTP client only"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from typing import Optional

import click

from cc_code.utils.logging_config import setup_client_logging


def check_server_available(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def start_api_server(host: str, port: int) -> Optional[subprocess.Popen]:
    try:
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "api", "--host", host, "--port", str(port)]
        else:
            cmd = [
                sys.executable,
                "-m",
                "cc_code.cli",
                "api",
                "--host",
                host,
                "--port",
                str(port),
            ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return process
    except Exception as e:
        click.echo(
            click.style("Error: ", fg="red", bold=True)
            + f"Failed to start API server: {e}",
            err=True,
        )
        return None


def wait_for_server(host: str, port: int, timeout: float = 10.0) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout:
        if check_server_available(host, port, timeout=0.5):
            return True
        time.sleep(0.2)
    return False


@click.group(invoke_without_command=True)
@click.pass_context
@click.option(
    "--host",
    "api_host",
    envvar="CC_CODE_API_HOST",
    default="localhost",
    help="API server host (default: localhost)",
)
@click.option(
    "--port",
    "api_port",
    envvar="CC_CODE_API_PORT",
    type=int,
    default=8000,
    help="API server port (default: 8000)",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging to console",
)
@click.version_option(version="0.3.0", prog_name="cc-py")
def cli(
    ctx: click.Context,
    api_host: str,
    api_port: int,
    debug: bool,
) -> None:
    """CC Code Python - AI programming assistant TUI (HTTP client)

    This is the TUI client that connects to a FastAPI server.
    If the server is not running, it will be started automatically.
    """
    if ctx.invoked_subcommand is not None:
        return

    setup_client_logging(debug=debug)

    if debug:
        click.echo(click.style("Debug logging enabled", fg="yellow"))

    server_process: Optional[subprocess.Popen] = None
    shutting_down = False

    def cleanup_server(signum=None, frame=None):
        nonlocal shutting_down
        if shutting_down:
            return
        shutting_down = True
        if server_process and server_process.poll() is None:
            click.echo(click.style("\nStopping API server...", fg="yellow"))
            try:
                server_process.terminate()
                server_process.wait(timeout=3)
            except Exception:
                try:
                    server_process.kill()
                except Exception:
                    pass
        if signum is not None:
            sys.exit(128 + signum)

    signal.signal(signal.SIGHUP, cleanup_server)
    signal.signal(signal.SIGTERM, cleanup_server)

    if not check_server_available(api_host, api_port):
        click.echo(
            click.style(
                f"API server not running. Starting at {api_host}:{api_port}...",
                fg="yellow",
            )
        )
        server_process = start_api_server(api_host, api_port)
        if not server_process:
            sys.exit(1)

        click.echo(click.style("Waiting for API server to start...", fg="yellow"))

        start_time = time.time()
        while time.time() - start_time < 15.0:
            if server_process.poll() is not None:
                stdout, stderr = server_process.communicate()
                click.echo(
                    click.style("Error: ", fg="red", bold=True)
                    + "API server failed to start",
                    err=True,
                )
                output = (stdout or b"") + (stderr or b"")
                if output:
                    click.echo(output.decode("utf-8", errors="replace"), err=True)
                sys.exit(1)
            if check_server_available(api_host, api_port, timeout=0.5):
                break
            time.sleep(0.2)
        else:
            click.echo(
                click.style("Error: ", fg="red", bold=True)
                + "API server failed to start in time",
                err=True,
            )
            if server_process.poll() is None:
                server_process.terminate()
            sys.exit(1)

        click.echo(click.style("API server started successfully", fg="green"))

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
    finally:
        cleanup_server()


@click.command("api")
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
def api_cmd(host: str, port: int, debug: bool) -> None:
    """Start the CC Code FastAPI server"""
    import asyncio

    from cc_code.core.settings import SettingsStore
    from cc_code.core.tools import ToolRegistry
    from cc_code.tools import (
        EditTool,
        GlobTool,
        GrepTool,
        ReadTool,
        WriteTool,
    )
    from cc_code.tools.bash_tool import BashTool
    from cc_code.utils.logging_config import setup_server_logging

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

    registry = ToolRegistry()
    registry.register(ReadTool())
    registry.register(WriteTool())
    registry.register(EditTool())
    registry.register(GlobTool())
    registry.register(GrepTool())
    registry.register(BashTool())

    from cc_code.api.server import app, set_global_dependencies

    import uvicorn

    set_global_dependencies(settings_store, registry)

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


cli.add_command(api_cmd)

main = cli


def run_tui(
    api_host: str,
    api_port: int,
    working_directory: str,
) -> None:
    from cc_code.client.http_client import CCCodeHttpClient
    from cc_code.ui.app import CCCodeApp

    client = CCCodeHttpClient(api_host, api_port)

    app = CCCodeApp(
        client=client,
        working_directory=working_directory,
    )
    app.run()


if __name__ == "__main__":
    main()
