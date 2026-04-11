"""Client CLI entry point"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Optional

import click
from dotenv import load_dotenv

from claude_code.client.grpc_client import ClaudeCodeClient
from claude_code.utils.logging_config import setup_client_logging


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.pass_context
def main(ctx: click.Context, debug: bool) -> None:
    """Claude Code gRPC client CLI"""
    setup_client_logging(debug=debug)

    load_dotenv()
    ctx.ensure_object(dict)
    ctx.obj["host"] = os.environ.get("CLAUDE_CODE_GRPC_HOST", "localhost")
    ctx.obj["port"] = int(os.environ.get("CLAUDE_CODE_GRPC_PORT", "50051"))


@main.command()
@click.argument("prompt")
@click.option("--session-id", help="Session ID to continue")
@click.option("--working-directory", default="", help="Working directory")
@click.pass_context
def chat(
    ctx: click.Context, prompt: str, session_id: Optional[str], working_directory: str
) -> None:
    """Send a chat message and stream the response"""
    host = ctx.obj["host"]
    port = ctx.obj["port"]

    async def run():
        async with ClaudeCodeClient(host, port) as client:
            async for event in client.stream_chat(
                prompt, session_id, working_directory
            ):
                if hasattr(event, "text"):
                    click.echo(event.text, nl=False)
                elif hasattr(event, "thinking") and event.thinking:
                    click.echo(
                        click.style(f"[Thinking: {event.thinking}]", fg="yellow")
                    )
                elif hasattr(event, "error") and event.error:
                    click.echo(click.style(f"Error: {event.error}", fg="red"), err=True)

    asyncio.run(run())


@main.command("list-sessions")
@click.pass_context
def list_sessions(ctx: click.Context) -> None:
    """List all saved sessions"""
    host = ctx.obj["host"]
    port = ctx.obj["port"]

    async def run():
        async with ClaudeCodeClient(host, port) as client:
            sessions = await client.list_sessions()
            if not sessions:
                click.echo("No sessions found.")
                return
            for s in sessions:
                click.echo(f"  {s.session_id}: {s.title}")
                click.echo(f"    Messages: {s.message_count}, Updated: {s.updated_at}")

    asyncio.run(run())


@main.command("create-session")
@click.option("--working-directory", default="", help="Working directory")
@click.pass_context
def create_session(ctx: click.Context, working_directory: str) -> None:
    """Create a new session"""
    host = ctx.obj["host"]
    port = ctx.obj["port"]

    async def run():
        async with ClaudeCodeClient(host, port) as client:
            session_id = await client.create_session(working_directory)
            click.echo(f"Created session: {session_id}")

    asyncio.run(run())


@main.command("delete-session")
@click.argument("session_id")
@click.pass_context
def delete_session(ctx: click.Context, session_id: str) -> None:
    """Delete a session"""
    host = ctx.obj["host"]
    port = ctx.obj["port"]

    async def run():
        async with ClaudeCodeClient(host, port) as client:
            success = await client.delete_session(session_id)
            if success:
                click.echo(f"Deleted session: {session_id}")
            else:
                click.echo(f"Failed to delete session: {session_id}", err=True)

    asyncio.run(run())


if __name__ == "__main__":
    main()
