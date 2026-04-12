"""FastAPI-based web server with Vue 3 frontend - uses direct API backend"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from claude_code.api.server import (
    build_visible_file_expansions as _build_visible_file_expansions,
    event_to_dict as _event_to_dict,
    message_to_dict as _message_to_dict,
    create_app as create_api_app,
    set_global_dependencies,
)
from claude_code.core.tools import ToolRegistry
from claude_code.services.openai_client import OpenAIClientConfig

logger = logging.getLogger(__name__)

build_visible_file_expansions = _build_visible_file_expansions
event_to_dict = _event_to_dict
message_to_dict = _message_to_dict

__all__ = [
    "build_visible_file_expansions",
    "create_combined_app",
    "event_to_dict",
    "message_to_dict",
    "run_web_server",
]


# Create a combined app that mounts the API and serves the web UI
def create_combined_app(
    client_config: OpenAIClientConfig,
    tool_registry: ToolRegistry,
) -> FastAPI:
    """Create combined FastAPI app with API and web UI"""
    set_global_dependencies(client_config, tool_registry)

    app = FastAPI(title="Claude Code Python")

    # Mount the unprefixed API app so browser requests stay at /api/*
    api_app = create_api_app(api_prefix="")
    app.mount("/api", api_app)

    # Serve static files
    static_path = Path(__file__).parent / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=static_path), name="static")

    # Serve the main HTML
    @app.get("/", response_class=HTMLResponse)
    async def index():
        """Serve Vue app"""
        html_path = Path(__file__).parent / "static" / "index.html"
        if html_path.exists():
            return HTMLResponse(content=html_path.read_text(), media_type="text/html")
        return HTMLResponse(
            content="<h1>Claude Code Python</h1>", media_type="text/html"
        )

    return app


async def run_web_server(
    client_config: OpenAIClientConfig,
    tool_registry: ToolRegistry,
    host: str = "0.0.0.0",
    port: int = 8080,
):
    """Run combined web and API server"""
    app = create_combined_app(client_config, tool_registry)

    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)

    logger.info(f"Web & API server started at http://{host}:{port}")
    print(f"🎨 Web interface available at: http://{host}:{port}")
    print(f"🔌 API available at: http://{host}:{port}/api")

    await server.serve()
