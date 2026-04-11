from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import AsyncGenerator, Dict, Optional

import aiohttp
from aiohttp import web

from claude_code.client.grpc_client import ClaudeCodeClient
from claude_code.utils.logging_config import setup_server_logging

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

_grpc_client: Optional[ClaudeCodeClient] = None


def content_block_to_dict(block) -> dict:
    from claude_code.core.messages import (
        TextContent,
        ThinkingContent,
        ToolUseContent,
        ToolResultContent,
    )

    if isinstance(block, TextContent):
        return {"type": "text", "text": block.text}
    elif isinstance(block, ThinkingContent):
        return {"type": "thinking", "thinking": block.thinking}
    elif isinstance(block, ToolUseContent):
        return {
            "type": "tool_use",
            "tool_use_id": block.id,
            "tool_name": block.name,
            "input": block.input,
        }
    elif isinstance(block, ToolResultContent):
        return {
            "type": "tool_result",
            "tool_use_id": block.tool_use_id,
            "result": block.content,
            "is_error": block.is_error,
        }
    return {"type": "unknown"}


def event_to_dict(event) -> dict:
    from claude_code.core.messages import (
        TextEvent as CoreTextEvent,
        ThinkingEvent as CoreThinkingEvent,
        ToolUseEvent as CoreToolUseEvent,
        ToolResultEvent as CoreToolResultEvent,
        MessageCompleteEvent as CoreMessageCompleteEvent,
        TurnCompleteEvent as CoreTurnCompleteEvent,
        ErrorEvent as CoreErrorEvent,
    )

    if isinstance(event, CoreTextEvent):
        return {"type": "text", "text": event.text}
    elif isinstance(event, CoreThinkingEvent):
        return {"type": "thinking", "thinking": event.thinking}
    elif isinstance(event, CoreToolUseEvent):
        return {
            "type": "tool_use",
            "tool_use_id": event.tool_use_id,
            "tool_name": event.tool_name,
            "input": event.input,
        }
    elif isinstance(event, CoreToolResultEvent):
        return {
            "type": "tool_result",
            "tool_use_id": event.tool_use_id,
            "result": event.result,
            "is_error": event.is_error,
        }
    elif isinstance(event, CoreMessageCompleteEvent):
        return {"type": "message_complete"}
    elif isinstance(event, CoreTurnCompleteEvent):
        return {
            "type": "turn_complete",
            "turn": event.turn,
            "has_more_turns": event.has_more_turns,
        }
    elif isinstance(event, CoreErrorEvent):
        return {"type": "error", "error": event.error, "is_fatal": event.is_fatal}
    return {"type": "unknown"}


@routes.get("/")
async def index(request):
    html_path = Path(__file__).parent / "index.html"
    return web.FileResponse(html_path)


@routes.post("/api/chat")
async def chat(request):
    data = await request.json()
    session_id = data.get("session_id")
    user_text = data.get("user_text", "")
    working_directory = data.get("working_directory", os.getcwd())

    response = web.StreamResponse()
    response.headers["Content-Type"] = "text/event-stream"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    await response.prepare(request)

    try:
        if not session_id:
            session_id = await _grpc_client.create_session(working_directory)

        await response.write(
            f"data: {json.dumps({'type': 'session_id', 'session_id': session_id})}\n\n".encode()
        )

        async for event in _grpc_client.stream_chat(
            user_text, session_id, working_directory
        ):
            event_dict = event_to_dict(event)
            await response.write(f"data: {json.dumps(event_dict)}\n\n".encode())

    except Exception as e:
        logger.exception("Chat error")
        error_dict = {"type": "error", "error": str(e), "is_fatal": True}
        await response.write(f"data: {json.dumps(error_dict)}\n\n".encode())

    return response


@routes.get("/api/sessions")
async def list_sessions(request):
    try:
        sessions = await _grpc_client.list_sessions()
        sessions_list = []
        for sess in sessions:
            sessions_list.append(
                {
                    "session_id": sess.session_id,
                    "title": sess.title,
                    "updated_at": sess.updated_at,
                    "working_directory": sess.working_directory,
                    "message_count": sess.message_count,
                }
            )
        return web.json_response({"sessions": sessions_list})
    except Exception as e:
        logger.exception("Failed to list sessions")
        return web.json_response({"error": str(e)}, status=500)


@routes.get("/api/sessions/{session_id}")
async def get_session(request):
    session_id = request.match_info["session_id"]
    try:
        session_info = await _grpc_client.get_session(session_id)
        if not session_info:
            return web.json_response({"error": "Session not found"}, status=404)

        messages_list = []
        for msg in session_info.messages:
            msg_dict = {
                "role": msg.type.value if hasattr(msg.type, "value") else str(msg.type),
                "content_blocks": [],
            }

            for block in msg.content:
                block_dict = content_block_to_dict(block)
                if block_dict:
                    msg_dict["content_blocks"].append(block_dict)

            if msg.file_expansions:
                msg_dict["file_expansions"] = [
                    {
                        "file_path": exp.file_path,
                        "content": exp.content,
                        "display_path": getattr(exp, "display_path", exp.file_path),
                    }
                    for exp in msg.file_expansions
                ]

            if msg.original_text:
                msg_dict["original_text"] = msg.original_text

            messages_list.append(msg_dict)

        return web.json_response(
            {
                "session_id": session_info.session_id,
                "title": session_info.title,
                "messages": messages_list,
                "current_turn": session_info.current_turn,
                "total_usage": {
                    "input_tokens": session_info.total_usage.input_tokens,
                    "output_tokens": session_info.total_usage.output_tokens,
                },
                "working_directory": session_info.working_directory,
            }
        )
    except Exception as e:
        logger.exception("Failed to get session")
        return web.json_response({"error": str(e)}, status=500)


def create_app():
    app = web.Application()
    app.add_routes(routes)
    return app


async def run_web_server(
    grpc_host: str = "localhost",
    grpc_port: int = 50051,
    web_host: str = "0.0.0.0",
    web_port: int = 8080,
):
    global _grpc_client
    _grpc_client = ClaudeCodeClient(host=grpc_host, port=grpc_port)

    await _grpc_client.connect()
    logger.info(f"Connected to gRPC server at {grpc_host}:{grpc_port}")

    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, web_host, web_port)
    await site.start()

    logger.info(f"Web server started at http://{web_host}:{web_port}")
    print(f"🎨 Web interface available at: http://{web_host}:{web_port}")
    print(f"🔌 Connected to gRPC server at: {grpc_host}:{grpc_port}")

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        await _grpc_client.close()
        await runner.cleanup()
