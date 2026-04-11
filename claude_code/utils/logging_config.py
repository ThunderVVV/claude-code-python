"""Logging configuration utilities for Claude Code Python"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional


def setup_server_logging(log_dir: str = ".logs", debug: bool = True) -> None:
    """Configure logging for the gRPC server."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(log_dir) / f"claude-code_{timestamp}_server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    _setup_logging(log_path, debug, "server")


def setup_client_logging(log_dir: str = ".logs", debug: bool = True) -> None:
    """Configure logging for the gRPC client."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(log_dir) / f"claude-code_{timestamp}_client.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    _setup_logging(log_path, debug, "client")


def _setup_logging(log_path: Path, debug: bool, component: str) -> None:
    """Internal logging setup."""
    log_format = f"%(asctime)s [{component}] %(name)s - %(levelname)s - %(message)s"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)

    claude_logger = logging.getLogger("claude_code")
    claude_logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format))
    claude_logger.addHandler(file_handler)

    if debug:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(logging.Formatter(log_format))
        claude_logger.addHandler(console_handler)


def log_exception(logger: logging.Logger, message: str, exc: Exception) -> None:
    """Log an exception with full traceback at DEBUG level."""
    tb = traceback.format_exc()
    logger.debug(f"{message}\n{tb}")
