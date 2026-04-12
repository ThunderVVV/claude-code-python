"""Logging configuration utilities for Claude Code Python"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime
from pathlib import Path


_LOG_TAG_RULES: tuple[tuple[str, str], ...] = (
    ("claude_code.api.", "FASTAPI"),
    ("claude_code.client.http_client", "CLIENT"),
    ("claude_code.client.", "CLIENT"),
    ("claude_code.ui.", "TUI"),
    ("claude_code.cli", "TUI"),
    ("claude_code.core.", "ENGINE"),
    ("claude_code.services.", "ENGINE"),
)


def _resolve_log_tag(logger_name: str, default_tag: str) -> str:
    for prefix, tag in _LOG_TAG_RULES:
        if logger_name.startswith(prefix):
            return tag
    return default_tag


class _SourceTagFilter(logging.Filter):
    def __init__(self, default_tag: str):
        super().__init__()
        self._default_tag = default_tag

    def filter(self, record: logging.LogRecord) -> bool:
        record.source_tag = _resolve_log_tag(record.name, self._default_tag)
        return True


def setup_server_logging(log_dir: str = ".logs", debug: bool = True) -> None:
    """Configure logging for the API server."""
    _setup_logging(log_dir, debug, "cc-api")


def setup_client_logging(log_dir: str = ".logs", debug: bool = True) -> None:
    """Configure logging for the HTTP/TUI client."""
    _setup_logging(log_dir, debug, "cc-py")


def _setup_logging(log_dir: str, debug: bool, default_tag: str) -> None:
    """Internal logging setup."""
    log_format = "%(asctime)s [%(source_tag)s] %(name)s - %(levelname)s - %(message)s"
    source_tag_filter = _SourceTagFilter(default_tag)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)

    claude_logger = logging.getLogger("claude_code")
    claude_logger.setLevel(logging.DEBUG)

    if debug:
        # Debug mode: log to both file and console at DEBUG level
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = Path(log_dir) / f"claude-code_{timestamp}_{default_tag.lower()}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(log_format))
        file_handler.addFilter(source_tag_filter)
        claude_logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(logging.Formatter(log_format))
        console_handler.addFilter(source_tag_filter)
        claude_logger.addHandler(console_handler)
    else:
        # Non-debug mode: only console at INFO level and above
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(log_format))
        console_handler.addFilter(source_tag_filter)
        claude_logger.addHandler(console_handler)


def log_full_exception(logger: logging.Logger, message: str, exc: Exception) -> None:
    """Log an exception with full traceback at DEBUG level."""
    tb = traceback.format_exc()
    logger.debug(f"{exc}: {message}\n{tb}")
