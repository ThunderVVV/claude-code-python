"""FastAPI-based web server with Vue 3 frontend"""

from __future__ import annotations

import json
import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from claude_code.client.grpc_client import ClaudeCodeClient
from claude_code.core.file_expansion import (
    FileExpansion,
    parse_file_references,
    read_file_content,
    resolve_file_path,
)

logger = logging.getLogger(__name__)

# gRPC client
_grpc_client: Optional[ClaudeCodeClient] = None
_grpc_config: dict[str, str | int] = {"host": "localhost", "port": 50051}
_WEB_REFERENCE_PATTERN = re.compile(r"(?<!\S)@web(?=$|[\s,;:!?()])")


def set_grpc_config(host: str, port: int) -> None:
    """Set gRPC configuration before app startup"""
    global _grpc_config
    _grpc_config["host"] = host
    _grpc_config["port"] = port


def require_grpc_client() -> ClaudeCodeClient:
    """Return the active gRPC client or raise if startup has not completed."""
    if _grpc_client is None:
        raise RuntimeError("gRPC client is not connected")
    return _grpc_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - connect to gRPC on startup"""
    global _grpc_client
    try:
        _grpc_client = ClaudeCodeClient(
            host=str(_grpc_config["host"]),
            port=int(_grpc_config["port"]),
        )
        await _grpc_client.connect()
        logger.info(f"Connected to gRPC server at {_grpc_config['host']}:{_grpc_config['port']}")
        print(f"🔌 Connected to gRPC server at {_grpc_config['host']}:{_grpc_config['port']}")
        yield
    except Exception as e:
        logger.error(f"Failed to connect to gRPC server: {e}")
        print(f"❌ Failed to connect to gRPC server at {_grpc_config['host']}:{_grpc_config['port']}")
        print(f"   Error: {e}")
        raise
    finally:
        if _grpc_client:
            await _grpc_client.close()
            logger.info("Disconnected from gRPC server")


app = FastAPI(title="Claude Code Python Web", lifespan=lifespan)


# Request models
class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    user_text: str
    working_directory: str = os.getcwd()


class InterruptRequest(BaseModel):
    session_id: str
    reason: str = "user_interrupt"


def has_web_reference(text: str) -> bool:
    """Return True when the user explicitly requested @web."""
    return bool(_WEB_REFERENCE_PATTERN.search(text))


def serialize_file_expansions(file_expansions: list[FileExpansion]) -> list[dict]:
    """Convert file-expansion objects into JSON-friendly dictionaries."""
    return [
        {
            "file_path": exp.file_path,
            "content": exp.content,
            "display_path": exp.display_path,
        }
        for exp in file_expansions
    ]


def build_visible_file_expansions(
    user_text: str,
    working_directory: str,
) -> list[FileExpansion]:
    """Reconstruct visible @file_path expansions for the web frontend.

    This intentionally reflects only user-authored file references. `@web` is
    surfaced separately via a dedicated UI indicator rather than as expanded
    hidden skill-file content.
    """
    if not user_text:
        return []

    expansions: list[FileExpansion] = []
    seen_paths: set[str] = set()
    web_requested = has_web_reference(user_text)

    for file_path, _start_pos, _end_pos in parse_file_references(user_text):
        if file_path == "web" and web_requested:
            continue
        if file_path in seen_paths:
            continue

        full_path = resolve_file_path(file_path, working_directory)
        if full_path is None:
            continue

        content = read_file_content(full_path)
        if content is None:
            continue

        seen_paths.add(file_path)
        expansions.append(
            FileExpansion(
                file_path=full_path,
                content=content,
                display_path=file_path,
            )
        )

    return expansions


# Content block converters
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


def message_to_dict(message, working_directory: str = "") -> dict:
    """Serialize a message for web transport."""
    message_dict = {
        "role": message.type.value if hasattr(message.type, "value") else str(message.type),
        "content_blocks": [content_block_to_dict(block) for block in message.content],
    }

    if message.original_text:
        message_dict["original_text"] = message.original_text

    if getattr(message, "file_expansions", None):
        message_dict["file_expansions"] = serialize_file_expansions(
            message.file_expansions
        )
    elif (
        message_dict["role"] == "user"
        and message.original_text
        and working_directory
    ):
        file_expansions = build_visible_file_expansions(
            message.original_text,
            working_directory,
        )
        if file_expansions:
            message_dict["file_expansions"] = serialize_file_expansions(
                file_expansions
            )

    if message_dict["role"] == "user":
        source_text = message.original_text or ""
        message_dict["web_enabled"] = has_web_reference(source_text)

    return message_dict


def event_to_dict(event, working_directory: str = "") -> dict:
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
        event_dict: dict[str, object] = {"type": "message_complete"}
        if event.message:
            event_dict["message"] = message_to_dict(
                event.message,
                working_directory=working_directory,
            )
        return event_dict
    elif isinstance(event, CoreTurnCompleteEvent):
        return {
            "type": "turn_complete",
            "turn": event.turn,
            "has_more_turns": event.has_more_turns,
        }
    elif isinstance(event, CoreErrorEvent):
        return {"type": "error", "error": event.error, "is_fatal": event.is_fatal}
    return {"type": "unknown"}


async def event_stream(chat_request: ChatRequest):
    """Generate SSE events from gRPC stream"""
    session_id = chat_request.session_id
    grpc_client = require_grpc_client()
    try:
        if not session_id:
            session_id = await grpc_client.create_session(chat_request.working_directory)

        yield f"data: {json.dumps({'type': 'session_id', 'session_id': session_id})}\n\n"

        async for event in grpc_client.stream_chat(
            chat_request.user_text, session_id, chat_request.working_directory
        ):
            event_dict = event_to_dict(
                event,
                working_directory=chat_request.working_directory,
            )
            yield f"data: {json.dumps(event_dict)}\n\n"

    except Exception as e:
        logger.exception("Chat error")
        error_dict = {"type": "error", "error": str(e), "is_fatal": True}
        yield f"data: {json.dumps(error_dict)}\n\n"


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve Vue app"""
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(content=html_path.read_text(), media_type="text/html")


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Stream chat response via SSE"""
    return StreamingResponse(
        event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.post("/api/interrupt")
async def interrupt(request: InterruptRequest):
    """Send interrupt signal to the backend"""
    try:
        success = await require_grpc_client().interrupt(
            request.session_id,
            request.reason,
        )
        return {"success": success}
    except Exception as e:
        logger.exception("Failed to send interrupt")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions")
async def list_sessions():
    """List all sessions"""
    try:
        sessions = await require_grpc_client().list_sessions()
        return {
            "sessions": [
                {
                    "session_id": sess.session_id,
                    "title": sess.title,
                    "updated_at": sess.updated_at,
                    "working_directory": sess.working_directory,
                    "message_count": sess.message_count,
                }
                for sess in sessions
            ]
        }
    except Exception as e:
        logger.exception("Failed to list sessions")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session details"""
    try:
        session_info = await require_grpc_client().get_session(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail="Session not found")

        messages_list = []
        for msg in session_info.messages:
            messages_list.append(
                message_to_dict(msg, working_directory=session_info.working_directory)
            )

        return {
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
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get session")
        raise HTTPException(status_code=500, detail=str(e))


def create_app() -> FastAPI:
    """Create FastAPI app with static file mounting"""
    # Mount static files
    static_path = Path(__file__).parent / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=static_path), name="static")
    
    return app


async def run_web_server(
    grpc_host: str = "localhost",
    grpc_port: int = 50051,
    web_host: str = "0.0.0.0",
    web_port: int = 8080,
):
    """Run web server with gRPC connection (for programmatic use)"""
    global _grpc_client
    _grpc_client = ClaudeCodeClient(host=grpc_host, port=grpc_port)

    await _grpc_client.connect()
    logger.info(f"Connected to gRPC server at {grpc_host}:{grpc_port}")

    app = create_app()

    import uvicorn
    config = uvicorn.Config(app, host=web_host, port=web_port, log_level="info")
    server = uvicorn.Server(config)

    logger.info(f"Web server started at http://{web_host}:{web_port}")
    print(f"🎨 Web interface available at: http://{web_host}:{web_port}")
    print(f"🔌 Connected to gRPC server at: {grpc_host}:{grpc_port}")

    await server.serve()
