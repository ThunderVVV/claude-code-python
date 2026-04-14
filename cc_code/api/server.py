"""FastAPI backend server for CC Code Python - direct integration with QueryEngine"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from cc_code.core.messages import (
    generate_uuid,
    message_to_api_dict,
    event_to_api_dict,
    SessionState,
    Usage,
)
from cc_code.core.query_engine import QueryEngine
from cc_code.core.tools import ToolRegistry
from cc_code.core.session_store import SessionStore
from cc_code.core.settings import (
    SettingsStore,
    build_client_config,
    find_model_id_by_model_name,
)
from cc_code.core.instruction import InstructionConfig
from cc_code.services.openai_client import OpenAIClientConfig

logger = logging.getLogger(__name__)

class SessionManager:
    """Manages session and engine lifecycle."""

    def __init__(self, settings_store: SettingsStore, tool_registry: ToolRegistry):
        self._engines: dict[str, QueryEngine] = {}
        self._session_store = SessionStore()
        self._settings_store = settings_store
        self._tool_registry = tool_registry
        self._lock = asyncio.Lock()

    async def get_or_create_engine(
        self,
        session_id: Optional[str],
        working_directory: str = "",
        model_id: Optional[str] = None,
    ) -> QueryEngine:
        async with self._lock:
            if session_id and session_id in self._engines:
                return self._engines[session_id]

            engine = await self._create_engine(
                session_id, working_directory, model_id
            )
            self._engines[engine.get_session_id()] = engine
            return engine

    async def _create_engine(
        self,
        session_id: Optional[str],
        working_directory: str,
        model_id: Optional[str] = None,
    ) -> QueryEngine:
        client_config = self._resolve_client_config(session_id, model_id)

        settings = self.get_settings()
        instruction_config = InstructionConfig(
            custom_instructions=settings.instructions,
        )

        return await QueryEngine.create_from_session_id(
            session_id=session_id,
            client_config=client_config,
            tool_registry=self._tool_registry,
            session_store=self._session_store,
            working_directory=working_directory,
            instruction_config=instruction_config,
        )

    def get_engine(self, session_id: str) -> Optional[QueryEngine]:
        return self._engines.get(session_id)

    def get_settings(self) -> SettingsStore:
        return self._settings_store.ensure_settings()

    def _resolve_client_config(
        self, session_id: Optional[str], model_id: Optional[str] = None
    ) -> OpenAIClientConfig:
        settings = self.get_settings()

        if model_id and model_id in settings.models:
            return build_client_config(settings, model_id)

        if session_id:
            persisted = self._session_store.load_session(session_id)
            if persisted:
                if persisted.model_id and persisted.model_id in settings.models:
                    return build_client_config(settings, persisted.model_id)

                if persisted.model_name:
                    persisted_model_id = find_model_id_by_model_name(
                        settings, persisted.model_name
                    )
                    if persisted_model_id:
                        return build_client_config(settings, persisted_model_id)

        return build_client_config(settings)

    def list_sessions(self):
        return self._session_store.list_sessions()

    async def close_all(self) -> None:
        """Close all engines and release resources."""
        for engine in self._engines.values():
            await engine.close()
        self._engines.clear()

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Get session details from engine or disk."""
        engine = self._engines.get(session_id)
        if engine:
            messages = engine.get_messages()
            return SessionState(
                session_id=session_id,
                title=engine._session_title or "",
                created_at=engine._session_created_at or "",
                updated_at="",
                working_directory=engine.get_working_directory(),
                current_turn=engine.state.current_turn,
                model_id=engine.client_config.model_id,
                model_name=engine.client_config.model_name,
                total_usage=engine.state.total_usage or Usage(),
                messages=messages,
            )

        return self._session_store.load_session(session_id)


# Request models
class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    user_text: str
    working_directory: str = os.getcwd()
    model: Optional[str] = None  # model_id to use for this request


class InterruptRequest(BaseModel):
    session_id: str
    reason: str = "user_interrupt"


class RevertRequest(BaseModel):
    session_id: str
    target_message_id: Optional[str] = None
    target_part_id: Optional[str] = None


class SwitchModelRequest(BaseModel):
    session_id: str
    model_id: str


class CompactRequest(BaseModel):
    session_id: str
    working_directory: str = os.getcwd()
    model: Optional[str] = None


def _normalize_api_prefix(api_prefix: str) -> str:
    """Normalize an optional API prefix for route registration."""
    prefix = api_prefix.strip().strip("/")
    return f"/{prefix}" if prefix else ""


api_router = APIRouter()


async def event_stream(chat_request: ChatRequest, session_manager: SessionManager):
    """Generate SSE events from QueryEngine directly"""

    try:
        session_id = chat_request.session_id

        if not session_id:
            session_id = generate_uuid()

        yield f"data: {json.dumps({'type': 'session_id', 'session_id': session_id})}\n\n"
        logger.debug("yielded session_id")

        engine = await session_manager.get_or_create_engine(
            session_id,
            chat_request.working_directory,
            model_id=chat_request.model,
        )

        async for event in engine.submit_message(chat_request.user_text):
            event_dict = event_to_api_dict(
                event,
                working_directory=chat_request.working_directory,
            )
            yield f"data: {json.dumps(event_dict)}\n\n"

        logger.info(f"Streaming completed - session_id={session_id}")

    except Exception as e:
        logger.exception("event_stream failed")
        error_dict = {"type": "error", "error": str(e), "is_fatal": True}
        yield f"data: {json.dumps(error_dict)}\n\n"


async def compact_stream(request: CompactRequest, session_manager: SessionManager):
    """Generate SSE events for compact session - aligns with opencode principle.

    Streams the summary while preserving all history messages, only adds
    the summary marked as is_compact_summary.
    """
    try:
        session_id = request.session_id

        engine = await session_manager.get_or_create_engine(
            session_id,
            request.working_directory,
            model_id=request.model,
        )

        # Use the engine's compact handling directly (streaming)
        async for event in engine.submit_message("/compact"):
            event_dict = event_to_api_dict(
                event,
                working_directory=request.working_directory,
            )
            yield f"data: {json.dumps(event_dict)}\n\n"

        logger.info(f"Compact streaming completed - session_id={session_id}")

    except Exception as e:
        logger.exception("compact_stream failed")
        error_dict = {"type": "error", "error": str(e), "is_fatal": True}
        yield f"data: {json.dumps(error_dict)}\n\n"


@api_router.post("/chat")
async def chat(request: ChatRequest, http_request: Request):
    """Stream chat response via SSE"""
    logger.info(
        f"POST /chat - session_id={request.session_id}, user_text={request.user_text[:50]}..."
    )
    logger.debug(
        f"Request: user_text={request.user_text[:50]}..., session_id={request.session_id}"
    )
    session_manager = http_request.app.state.session_manager
    return StreamingResponse(
        event_stream(request, session_manager),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@api_router.post("/compact")
async def compact_session(request: CompactRequest, http_request: Request):
    """Compact a session via streaming - aligns with opencode principle.

    This endpoint streams an AI summary of the conversation history,
    preserves all history messages, and adds the summary marked as
    is_compact_summary.
    """
    logger.info(f"POST /compact - session_id={request.session_id}")
    session_manager = http_request.app.state.session_manager
    return StreamingResponse(
        compact_stream(request, session_manager),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@api_router.post("/interrupt")
async def interrupt(request: InterruptRequest, http_request: Request):
    """Send interrupt signal to the backend"""
    logger.info(
        f"POST /interrupt - session_id={request.session_id}, reason={request.reason}"
    )
    try:
        session_manager = http_request.app.state.session_manager
        engine = session_manager.get_engine(request.session_id)
        if engine:
            engine.interrupt(request.reason or "user_interrupt")
            return {"success": True}
        return {"success": False}
    except Exception as e:
        logger.exception("Failed to send interrupt")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/revert")
async def revert(request: RevertRequest, http_request: Request):
    """Revert file changes from a specific point"""
    logger.info(
        f"POST /revert - session_id={request.session_id}, "
        f"target_message_id={request.target_message_id}, "
        f"target_part_id={request.target_part_id}"
    )
    try:
        # Normalize empty strings to None
        target_message_id = request.target_message_id or None
        target_part_id = request.target_part_id or None

        logger.debug(
            f"Revert request: session_id={request.session_id}, "
            f"target_message_id={target_message_id}, "
            f"target_part_id={target_part_id}"
        )

        session_manager = http_request.app.state.session_manager
        engine = session_manager.get_engine(request.session_id)
        if not engine:
            raise HTTPException(status_code=404, detail="Session not found")

        result = await engine.revert(
            target_message_id=target_message_id,
            target_part_id=target_part_id,
        )

        if result.success:
            response = {
                "success": True,
                "message": result.message,
            }
            if result.summary:
                response["summary"] = {
                    "additions": result.summary.additions,
                    "deletions": result.summary.deletions,
                    "files": result.summary.files,
                }
            return response
        else:
            return {"success": False, "message": result.message}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to revert")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/models")
async def list_models(http_request: Request):
    """List all available models from settings."""
    logger.info("GET /models")
    try:
        session_manager = http_request.app.state.session_manager
        settings = session_manager.get_settings()

        models_list = []
        for model_id, model_settings in settings.models.items():
            models_list.append(
                {
                    "model_id": model_id,
                    "model_name": model_settings.model_name,
                    "context": model_settings.context,
                    "api_url": model_settings.api_url,
                    "is_current": model_id == settings.current_model,
                }
            )

        return {
            "models": models_list,
            "current_model": settings.current_model,
        }
    except Exception as e:
        logger.exception("Failed to list models")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/model")
async def switch_model(request: SwitchModelRequest, http_request: Request):
    """Switch the active model for a session and persist it to settings.json."""
    logger.info(
        f"POST /model - session_id={request.session_id}, model_id={request.model_id}"
    )
    try:
        session_manager = http_request.app.state.session_manager
        engine = session_manager.get_engine(request.session_id)
        settings = session_manager.get_settings()
        if request.model_id not in settings.models:
            raise HTTPException(status_code=404, detail="Model configuration not found")

        settings.current_model = request.model_id
        session_manager._settings_store.save(settings)

        client_config = build_client_config(settings, request.model_id)
        if engine is None:
            engine = await session_manager.get_or_create_engine(
                request.session_id,
                "",
            )
        await engine.switch_model(client_config)
        return {
            "success": True,
            "model_id": request.model_id,
            "model_name": client_config.model_name,
            "context": settings.models[request.model_id].context,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to switch model")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/snapshot_status/{session_id}")
async def get_snapshot_status(session_id: str, http_request: Request):
    """Get the snapshot status (files modified, additions, deletions)"""
    logger.info(f"GET /snapshot_status/{session_id}")
    try:
        session_manager = http_request.app.state.session_manager
        engine = session_manager.get_engine(session_id)
        if not engine:
            raise HTTPException(status_code=404, detail="Session not found")

        total_diff = engine.get_total_diff()
        if not total_diff:
            return {"available": False}

        return {
            "available": True,
            "files": total_diff.files,
            "additions": total_diff.additions,
            "deletions": total_diff.deletions,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get snapshot status")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/sessions")
async def list_sessions(http_request: Request):
    """List all sessions"""
    logger.info("GET /sessions")
    try:
        session_manager = http_request.app.state.session_manager
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
async def get_session_endpoint(session_id: str, http_request: Request):
    """Get session details"""
    logger.info(f"GET /sessions/{session_id}")
    try:
        session_manager = http_request.app.state.session_manager
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        messages_list = []
        for msg in session.messages:
            messages_list.append(
                message_to_api_dict(msg, working_directory=session.working_directory)
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
            "model_id": session.model_id,
            "model_name": session.model_name,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get session")
        raise HTTPException(status_code=500, detail=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    logger.info("Server starting")
    yield

    session_manager: SessionManager = app.state.session_manager
    await session_manager.close_all()
    logger.info("Server shutting down")


def create_app(
    api_prefix: str = "/api",
    settings_store: Optional[SettingsStore] = None,
    tool_registry: Optional[ToolRegistry] = None,
) -> FastAPI:
    """Create a FastAPI app with optional API route prefix.
    
    Args:
        api_prefix: API route prefix (e.g., "/api")
        settings_store: Settings store instance (created if not provided)
        tool_registry: Tool registry instance (created if not provided)
    """
    app = FastAPI(title="CC Code Python API", lifespan=lifespan)

    if settings_store is None:
        settings_store = SettingsStore()
    if tool_registry is None:
        tool_registry = ToolRegistry()

    app.state.session_manager = SessionManager(settings_store, tool_registry)

    @app.get("/health")
    async def health():
        """Health check endpoint"""
        logger.info("GET /health")
        return {"status": "ok", "service": "cc-code-api"}

    @app.get("/", response_class=HTMLResponse)
    async def index():
        """Serve Vue app"""
        logger.info("GET /")
        html_path = Path(__file__).parent.parent / "web" / "static" / "index.html"
        if html_path.exists():
            return HTMLResponse(content=html_path.read_text(), media_type="text/html")
        return HTMLResponse(
            content="<h1>CC Code Python API</h1>", media_type="text/html"
        )

    app.include_router(api_router, prefix=_normalize_api_prefix(api_prefix))

    # Mount static files
    static_path = Path(__file__).parent.parent / "web" / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=static_path), name="static")

    return app


# Default app instance for backward compatibility
app = create_app()
