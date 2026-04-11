"""Web v2 module - FastAPI + Vue 3 implementation"""

from claude_code.web_v2.server import app, create_app, set_grpc_config

__all__ = ["app", "create_app", "set_grpc_config"]
