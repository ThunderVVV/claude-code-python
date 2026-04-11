"""Logging configuration utilities for Claude Code Python"""

from __future__ import annotations

import logging
import os
import traceback
from datetime import datetime
from pathlib import Path


def suppress_grpc_logs() -> None:
    """Suppress verbose gRPC C++ core library logs.
    
    These logs (like 'FD from fork parent still in poll list') come from
    gRPC's internal event polling mechanism and are not controlled by
    Python's logging system.
    """
    # Suppress INFO level logs from gRPC C++ core
    # Options: ERROR, WARNING, INFO, DEBUG
    os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
    # Disable gRPC tracing (empty string means no tracers enabled)
    os.environ.setdefault("GRPC_TRACE", "")


def setup_server_logging(log_dir: str = ".logs", debug: bool = True) -> None:
    """Configure logging for the gRPC server."""
    suppress_grpc_logs()
    _setup_logging(log_dir, debug, "server")


def setup_client_logging(log_dir: str = ".logs", debug: bool = True) -> None:
    """Configure logging for the gRPC client."""
    suppress_grpc_logs()
    _setup_logging(log_dir, debug, "client")


def _setup_logging(log_dir: str, debug: bool, component: str) -> None:
    """Internal logging setup."""
    log_format = f"%(asctime)s [{component}] %(name)s - %(levelname)s - %(message)s"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)

    claude_logger = logging.getLogger("claude_code")
    claude_logger.setLevel(logging.DEBUG)

    if debug:
        # Debug mode: log to both file and console at DEBUG level
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = Path(log_dir) / f"claude-code_{timestamp}_{component}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(log_format))
        claude_logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(logging.Formatter(log_format))
        claude_logger.addHandler(console_handler)
    else:
        # Non-debug mode: only console at INFO level and above
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(log_format))
        claude_logger.addHandler(console_handler)


def log_full_exception(logger: logging.Logger, message: str, exc: Exception) -> None:
    """Log an exception with full traceback at DEBUG level."""
    tb = traceback.format_exc()
    logger.debug(f"{exc}: {message}\n{tb}")
