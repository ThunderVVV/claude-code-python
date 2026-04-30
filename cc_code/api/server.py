"""FastAPI backend server for CC Code Python - direct integration with QueryEngine"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import string
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Dict, List

import httpx
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from cc_code.core.messages import (
    generate_uuid,
    message_to_api_dict,
    event_to_api_dict,
    SessionState,
)
from cc_code.core.query_engine import QueryEngine
from cc_code.core.tools import ToolRegistry
from cc_code.core.session_store import SessionStore
from cc_code.core.settings import (
    SettingsStore,
    build_client_config,
    find_model_id_by_model_name,
    DEFAULT_THEME_NAME,
    AppSettings,
    ProviderSettings,
    ModelInProviderSettings,
)
from cc_code.core.instruction import InstructionConfig
from cc_code.services.openai_client import OpenAIClientConfig
from cc_code.skills.loader import get_all_skills, format_commands_within_budget

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

        if model_id and ":" in model_id:
            provider_id, model_short_id = model_id.split(":", 1)
            if provider_id in settings.providers and model_short_id in settings.providers[provider_id].models:
                return build_client_config(settings, model_id)

        if session_id:
            persisted = self._session_store.load_session(session_id)
            if persisted:
                if persisted.model_id and ":" in persisted.model_id:
                    provider_id, model_short_id = persisted.model_id.split(":", 1)
                    if provider_id in settings.providers and model_short_id in settings.providers[provider_id].models:
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
            # Update state with current values and return it
            engine.state.working_directory = engine.get_working_directory()
            engine.state.model_id = engine.client_config.model_id
            engine.state.model_name = engine.client_config.model_name
            return engine.state

        return self._session_store.load_session(session_id)

    async def get_or_restore_engine(self, session_id: str) -> Optional[QueryEngine]:
        """Return a live engine, restoring it from persisted session state if needed."""
        engine = self._engines.get(session_id)
        if engine:
            return engine

        session = self._session_store.load_session(session_id)
        if not session:
            return None

        return await self.get_or_create_engine(
            session_id,
            session.working_directory or "",
        )


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
    model_id: str
    session_id: Optional[str] = None


class CompactRequest(BaseModel):
    session_id: str
    working_directory: str = os.getcwd()
    model: Optional[str] = None


class ModelItem(BaseModel):
    model_name: str
    context: int = 0


class SaveProviderSettings(BaseModel):
    api_key: Optional[str] = None
    api_url: str
    models: Dict[str, ModelItem]


class SaveSettingsRequest(BaseModel):
    current_model: str
    theme: str = DEFAULT_THEME_NAME
    providers: Dict[str, SaveProviderSettings]
    instructions: List[str] = []


def _resolve_existing_directory(path: Optional[str]) -> str:
    """Resolve and validate a directory path from API input."""
    raw_path = (path or "").strip()
    resolved = os.path.abspath(os.path.expanduser(raw_path or os.getcwd()))

    if not os.path.exists(resolved):
        raise HTTPException(status_code=404, detail="Directory not found")
    if not os.path.isdir(resolved):
        raise HTTPException(status_code=400, detail="Path is not a directory")

    return resolved


def _list_directory_roots() -> list[dict[str, str]]:
    """Return navigable filesystem roots for the current platform."""
    roots: list[dict[str, str]] = []

    if os.name == "nt":
        for drive in string.ascii_uppercase:
            drive_path = f"{drive}:\\"
            if os.path.isdir(drive_path):
                roots.append({"name": drive_path, "path": drive_path})
    else:
        roots.append({"name": "/", "path": "/"})

    home_dir = str(Path.home())
    if home_dir and not any(root["path"] == home_dir for root in roots):
        roots.append({"name": "Home", "path": home_dir})

    current_dir = os.getcwd()
    if current_dir and not any(root["path"] == current_dir for root in roots):
        roots.append({"name": "Current", "path": current_dir})

    return roots


def _build_directory_browser_payload(path: str) -> dict:
    """Serialize directory browser metadata for the Web UI."""
    current_path = _resolve_existing_directory(path)
    current = Path(current_path)
    parent_path = str(current.parent) if current.parent != current else None
    directories = []

    try:
        with os.scandir(current_path) as entries:
            for entry in entries:
                try:
                    if not entry.is_dir():
                        continue
                except OSError:
                    continue

                directories.append(
                    {
                        "name": entry.name,
                        "path": os.path.abspath(entry.path),
                        "is_symlink": entry.is_symlink(),
                    }
                )
    except PermissionError:
        directories = []

    directories.sort(key=lambda item: item["name"].casefold())

    return {
        "path": current_path,
        "name": current.name or current_path,
        "parent_path": parent_path,
        "roots": _list_directory_roots(),
        "directories": directories,
    }


def _normalize_api_prefix(api_prefix: str) -> str:
    """Normalize an optional API prefix for route registration."""
    prefix = api_prefix.strip().strip("/")
    return f"/{prefix}" if prefix else ""


api_router = APIRouter()


async def event_stream(chat_request: ChatRequest, session_manager: SessionManager, user_text_override: Optional[str] = None):
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

        user_text = user_text_override or chat_request.user_text
        async for event in engine.submit_message(user_text):
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


@api_router.post("/chat")
async def chat(request: ChatRequest, http_request: Request):
    """Stream chat response via SSE"""
    if not request.user_text.strip():
        raise HTTPException(status_code=400, detail="user_text must not be empty")
    request.working_directory = _resolve_existing_directory(request.working_directory)
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
    request.working_directory = _resolve_existing_directory(request.working_directory)
    logger.info(f"POST /compact - session_id={request.session_id}")
    session_manager = http_request.app.state.session_manager
    return StreamingResponse(
        event_stream(request, session_manager, user_text_override="/compact"),
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
            success = await engine.interrupt(request.reason or "user_interrupt")
            return {"success": success}
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
        engine = await session_manager.get_or_restore_engine(request.session_id)
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
        for provider_id, provider in settings.providers.items():
            for model_id, model_settings in provider.models.items():
                full_model_id = f"{provider_id}:{model_id}"
                models_list.append(
                    {
                        "model_id": full_model_id,
                        "model_name": model_settings.model_name,
                        "context": model_settings.context,
                        "api_url": provider.api_url,
                        "provider": provider_id,
                        "is_current": full_model_id == settings.current_model,
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
        settings = session_manager.get_settings()
        # Validate model exists
        if ":" not in request.model_id:
            raise HTTPException(status_code=400, detail="Invalid model_id format, expected provider:model_id")
        provider_id, model_short_id = request.model_id.split(":", 1)
        if provider_id not in settings.providers or model_short_id not in settings.providers[provider_id].models:
            raise HTTPException(status_code=404, detail="Model configuration not found")

        settings.current_model = request.model_id
        session_manager._settings_store.save(settings)

        client_config = build_client_config(settings, request.model_id)

        if request.session_id:
            engine = session_manager.get_engine(request.session_id)
            if engine:
                await engine.switch_model(client_config)

        return {
            "success": True,
            "model_id": request.model_id,
            "model_name": client_config.model_name,
            "context": settings.providers[provider_id].models[model_short_id].context,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to switch model")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/skills")
async def list_skills(http_request: Request):
    """List all available skills."""
    logger.info("GET /skills")
    try:
        import os
        cwd = os.getcwd()
        all_skills = await get_all_skills(cwd)
        skills_list = []
        for skill in all_skills:
            skills_list.append({
                "name": skill.name,
                "description": skill.description,
                "source": skill.source,
                "loaded_from": skill.loaded_from,
                "user_invocable": skill.user_invocable,
                "when_to_use": skill.when_to_use,
                "argument_hint": skill.argument_hint,
                "aliases": skill.aliases,
            })
        return {
            "skills": skills_list,
            "count": len(skills_list),
        }
    except Exception as e:
        logger.exception("Failed to list skills")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/snapshot_status/{session_id}")
async def get_snapshot_status(session_id: str, http_request: Request):
    """Get the snapshot status (files modified, additions, deletions)"""
    logger.info(f"GET /snapshot_status/{session_id}")
    try:
        session_manager = http_request.app.state.session_manager
        engine = await session_manager.get_or_restore_engine(session_id)
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


@api_router.get("/debug/{session_id}")
async def get_debug_state(session_id: str, http_request: Request):
    """Get serialized QueryEngine member state for debugging."""
    logger.info(f"GET /debug/{session_id}")
    try:
        session_manager = http_request.app.state.session_manager
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        engine = session_manager.get_engine(session_id)
        if not engine:
            engine = await session_manager.get_or_create_engine(
                session_id,
                session.working_directory or "",
            )

        return {
            "success": True,
            "session_id": session_id,
            "debug": engine.get_debug_state(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get debug state")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/workspace")
async def get_workspace(http_request: Request):
    """Get current working directory"""
    logger.info("GET /workspace")
    try:
        import os
        return {
            "workspace": os.getcwd()
        }
    except Exception as e:
        logger.exception("Failed to get workspace")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/workspace/browse")
async def browse_workspace(path: Optional[str] = None):
    """Browse server-side directories for Web UI session creation."""
    logger.info(f"GET /workspace/browse - path={path or ''}")
    try:
        return _build_directory_browser_payload(path or os.getcwd())
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to browse workspace")
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


@api_router.get("/settings")
async def get_settings(http_request: Request):
    """Get current application settings"""
    logger.info("GET /settings")
    try:
        session_manager = http_request.app.state.session_manager
        settings = session_manager.get_settings()
        return {
            "current_model": settings.current_model,
            "theme": settings.theme,
            "providers": {
                provider_id: {
                    "api_url": provider.api_url,
                    "models": {
                        model_id: {
                            "model_name": model.model_name,
                            "context": model.context
                        } for model_id, model in provider.models.items()
                    }
                } for provider_id, provider in settings.providers.items()
            },
            "instructions": settings.instructions
        }
    except Exception as e:
        logger.exception("Failed to get settings")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/settings")
async def save_settings(http_request: Request, request: SaveSettingsRequest):
    """Save application settings"""
    logger.info("POST /settings")
    try:
        session_manager = http_request.app.state.session_manager
        settings_store = session_manager._settings_store
        existing_settings = session_manager.get_settings()
        
        # Convert request to AppSettings
        providers = {}
        for provider_id, provider_data in request.providers.items():
            models = {}
            for model_id, model_data in provider_data.models.items():
                models[model_id] = ModelInProviderSettings(
                    model_name=model_data.model_name,
                    context=model_data.context
                )
            # Preserve existing api_key if not provided in request
            api_key = provider_data.api_key
            if not api_key and provider_id in existing_settings.providers:
                api_key = existing_settings.providers[provider_id].api_key
            providers[provider_id] = ProviderSettings(
                api_key=api_key,
                api_url=provider_data.api_url,
                models=models
            )
        
        settings = AppSettings(
            current_model=request.current_model,
            theme=request.theme,
            providers=providers,
            instructions=request.instructions
        )
        
        settings_store.save(settings)
        return {"status": "ok"}
    except Exception as e:
        logger.exception("Failed to save settings")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/providers/{provider_id}/models")
async def get_provider_models(provider_id: str, http_request: Request):
    """Get available models from provider's API"""
    logger.info(f"GET /providers/{provider_id}/models")
    try:
        session_manager = http_request.app.state.session_manager
        settings = session_manager.get_settings()
        
        provider = settings.providers.get(provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
        
        # Call provider's models API (api_url already contains /vX version suffix)
        api_url = provider.api_url.rstrip("/")
        models_url = f"{api_url}/models"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                models_url,
                headers={"Authorization": f"Bearer {provider.api_key}"},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
        
        models = []
        for item in data.get("data", []):
            models.append({
                "id": item["id"],
                "name": item["id"],
                "context": 0  # Default context, user can edit later
            })
        
        return {"models": models}
    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch models from provider {provider_id}: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch models from provider: {str(e)}")
    except Exception as e:
        logger.exception("Failed to get provider models")
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
        tool_registry = ToolRegistry.create_default(cwd=os.getcwd())

    app.state.session_manager = SessionManager(settings_store, tool_registry)

    @app.get("/health")
    async def health():
        """Health check endpoint"""
        logger.info("GET /health")
        return {"status": "ok", "service": "cc-code-api"}

    # Web UI dist path (Vite build output)
    web_dist_path = Path(__file__).parent.parent / "web" / "dist"

    @app.get("/", response_class=HTMLResponse)
    async def index():
        """Serve Vue app from Vite build"""
        logger.info("GET /")
        html_path = web_dist_path / "index.html"
        if html_path.exists():
            return HTMLResponse(content=html_path.read_text(), media_type="text/html")
        return HTMLResponse(
            content="<h1>CC Code Python API</h1>", media_type="text/html"
        )

    app.include_router(api_router, prefix=_normalize_api_prefix(api_prefix))

    # Mount static files from Vite build output
    if web_dist_path.exists():
        # Vite build: assets are in dist/assets/
        app.mount("/assets", StaticFiles(directory=web_dist_path / "assets"), name="assets")

    return app
