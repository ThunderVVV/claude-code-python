"""FastAPI backend server for Claude Code Python - direct integration with QueryEngine"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from claude_code.core.messages import (
    TextContent,
    ThinkingContent,
    ToolUseContent,
    ToolResultContent,
    TextEvent as CoreTextEvent,
    ThinkingEvent as CoreThinkingEvent,
    ToolUseEvent as CoreToolUseEvent,
    ToolResultEvent as CoreToolResultEvent,
    MessageCompleteEvent as CoreMessageCompleteEvent,
    TurnCompleteEvent as CoreTurnCompleteEvent,
    ErrorEvent as CoreErrorEvent,
    generate_uuid,
)
from claude_code.core.query_engine import QueryEngine
from claude_code.core.tools import ToolRegistry
from claude_code.core.session_store import (
    SessionStore,
    PersistedSession,
)
from claude_code.services.openai_client import OpenAIClientConfig
from claude_code.core.file_expansion import (
    FileExpansion,
    parse_file_references,
    read_file_content,
    resolve_file_path,
    has_web_reference,
)

logger = logging.getLogger(__name__)

# Global state
_session_manager: Optional[object] = None


class SessionManager:
    def __init__(self):
        self._engines: dict[str, QueryEngine] = {}
        self._session_store = SessionStore()
        self._lock = asyncio.Lock()

    async def get_or_create_engine(
        self,
        session_id: Optional[str],
        client_config: OpenAIClientConfig,
        tool_registry: ToolRegistry,
        working_directory: str = "",
    ) -> QueryEngine:
        async with self._lock:
            if session_id and session_id in self._engines:
                return self._engines[session_id]

            engine = await self._create_engine(
                session_id, client_config, tool_registry, working_directory
            )
            self._engines[engine.get_session_id()] = engine
            return engine

    async def _create_engine(
        self,
        session_id: Optional[str],
        client_config: OpenAIClientConfig,
        tool_registry: ToolRegistry,
        working_directory: str,
    ) -> QueryEngine:
        return await QueryEngine.create_from_session_id(
            session_id=session_id,
            client_config=client_config,
            tool_registry=tool_registry,
            session_store=self._session_store,
            working_directory=working_directory,
        )

    def get_engine(self, session_id: str) -> Optional[QueryEngine]:
        return self._engines.get(session_id)

    def list_sessions(self):
        return self._session_store.list_sessions()

    def get_session(self, session_id: str) -> Optional[PersistedSession]:
        return self._session_store.load_session(session_id)


def get_session_manager() -> SessionManager:
    """Get or create the global session manager"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


# Request models
class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    user_text: str
    working_directory: str = os.getcwd()


class InterruptRequest(BaseModel):
    session_id: str
    reason: str = "user_interrupt"


def _normalize_api_prefix(api_prefix: str) -> str:
    """Normalize an optional API prefix for route registration."""
    prefix = api_prefix.strip()
    if not prefix or prefix == "/":
        return ""
    prefix = prefix.rstrip("/")
    if not prefix.startswith("/"):
        prefix = f"/{prefix}"
    return prefix


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
    """Reconstruct visible @file_path expansions for the web frontend."""
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
        "role": message.type.value
        if hasattr(message.type, "value")
        else str(message.type),
        "content_blocks": [content_block_to_dict(block) for block in message.content],
    }

    if message.original_text:
        message_dict["original_text"] = message.original_text

    if getattr(message, "file_expansions", None):
        message_dict["file_expansions"] = serialize_file_expansions(
            message.file_expansions
        )
    elif message_dict["role"] == "user" and message.original_text and working_directory:
        file_expansions = build_visible_file_expansions(
            message.original_text,
            working_directory,
        )
        if file_expansions:
            message_dict["file_expansions"] = serialize_file_expansions(file_expansions)

    if message_dict["role"] == "user":
        message_dict["web_enabled"] = bool(
            getattr(message, "web_enabled", False)
            or (message.original_text and has_web_reference(message.original_text))
        )

    return message_dict


def event_to_dict(event, working_directory: str = "") -> dict:
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


api_router = APIRouter()


# Global dependencies
_client_config: Optional[OpenAIClientConfig] = None
_tool_registry: Optional[ToolRegistry] = None


def set_global_dependencies(
    client_config: OpenAIClientConfig,
    tool_registry: ToolRegistry,
) -> None:
    """Set global dependencies before app startup"""
    global _client_config, _tool_registry
    _client_config = client_config
    _tool_registry = tool_registry


def require_global_dependencies() -> tuple[OpenAIClientConfig, ToolRegistry]:
    """Return global dependencies or raise if not set"""
    if _client_config is None or _tool_registry is None:
        raise RuntimeError("Global dependencies not set")
    return _client_config, _tool_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    logger.info("Server starting")
    yield
    logger.info("Server shutting down")


async def event_stream(chat_request: ChatRequest):
    """Generate SSE events from QueryEngine directly"""

    try:
        session_id = chat_request.session_id
        client_config, tool_registry = require_global_dependencies()
        session_manager = get_session_manager()

        if not session_id:
            session_id = generate_uuid()

        yield f"data: {json.dumps({'type': 'session_id', 'session_id': session_id})}\n\n"
        logger.debug("yielded session_id")

        engine = await session_manager.get_or_create_engine(
            session_id,
            client_config,
            tool_registry,
            chat_request.working_directory,
        )

        async for event in engine.submit_message(chat_request.user_text):
            event_dict = event_to_dict(
                event,
                working_directory=chat_request.working_directory,
            )
            yield f"data: {json.dumps(event_dict)}\n\n"

        logger.info(f"Streaming completed - session_id={session_id}")

    except Exception as e:
        logger.exception("event_stream failed")
        error_dict = {"type": "error", "error": str(e), "is_fatal": True}
        yield f"data: {json.dumps(error_dict)}\n\n"


@api_router.post("/chat")
async def chat(request: ChatRequest):
    """Stream chat response via SSE"""
    logger.debug(
        f"Request: user_text={request.user_text[:50]}..., session_id={request.session_id}"
    )
    return StreamingResponse(
        event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@api_router.post("/interrupt")
async def interrupt(request: InterruptRequest):
    """Send interrupt signal to the backend"""
    try:
        session_manager = get_session_manager()
        engine = session_manager.get_engine(request.session_id)
        if engine:
            engine.interrupt(request.reason or "user_interrupt")
            return {"success": True}
        return {"success": False}
    except Exception as e:
        logger.exception("Failed to send interrupt")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/sessions")
async def list_sessions():
    """List all sessions"""
    try:
        session_manager = get_session_manager()
        sessions = session_manager.list_sessions()
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


@api_router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session details"""
    try:
        session_manager = get_session_manager()
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        messages_list = []
        for msg in session.messages:
            messages_list.append(
                message_to_dict(msg, working_directory=session.working_directory)
            )

        return {
            "session_id": session.session_id,
            "title": session.title,
            "messages": messages_list,
            "current_turn": session.current_turn,
            "total_usage": {
                "input_tokens": session.total_usage.input_tokens,
                "output_tokens": session.total_usage.output_tokens,
            },
            "working_directory": session.working_directory,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get session")
        raise HTTPException(status_code=500, detail=str(e))


def create_app(api_prefix: str = "/api") -> FastAPI:
    """Create a FastAPI app with optional API route prefix."""
    app = FastAPI(title="Claude Code Python API", lifespan=lifespan)

    @app.get("/health")
    async def health():
        """Health check endpoint"""
        return {"status": "ok", "service": "claude-code-api"}

    @app.get("/", response_class=HTMLResponse)
    async def index():
        """Serve Vue app"""
        html_path = Path(__file__).parent.parent / "web" / "static" / "index.html"
        if html_path.exists():
            return HTMLResponse(content=html_path.read_text(), media_type="text/html")
        return HTMLResponse(
            content="<h1>Claude Code Python API</h1>", media_type="text/html"
        )

    app.include_router(api_router, prefix=_normalize_api_prefix(api_prefix))

    # Mount static files
    static_path = Path(__file__).parent.parent / "web" / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=static_path), name="static")

    return app


app = create_app()
