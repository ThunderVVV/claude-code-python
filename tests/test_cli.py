"""Tests for CLI utilities."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from claude_code.cli import ensure_log_directory, resolve_log_path


def test_resolve_log_path_uses_hidden_logs_dir() -> None:
    log_path = resolve_log_path(
        log_file=None,
        debug=True,
        now=datetime(2026, 4, 8, 13, 52, 1),
    )
    assert log_path == str(Path(".logs") / "claude-code-debug-20260408_135201.log")


def test_resolve_log_path_returns_explicit_log_file() -> None:
    assert resolve_log_path("custom.log", debug=True) == "custom.log"


def test_resolve_log_path_is_none_without_debug() -> None:
    assert resolve_log_path(None, debug=False) is None


def test_ensure_log_directory_creates_parent_directory(tmp_path: Path) -> None:
    log_path = tmp_path / ".logs" / "session.log"
    ensure_log_directory(str(log_path))
    assert log_path.parent.is_dir()
