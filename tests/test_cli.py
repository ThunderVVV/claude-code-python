"""Tests for CLI utilities."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from claude_code.cli import (
    ensure_log_directory,
    prompt_for_session_selection,
    resolve_log_path,
    resolve_session_choice,
)
from claude_code.core.messages import Message
from claude_code.core.session_store import SessionStore


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


def test_resolve_session_choice_supports_index_and_id(tmp_path: Path) -> None:
    session_store = SessionStore(tmp_path)
    session_store.save_snapshot(
        session_id="session-a",
        messages=[Message.user_message("first")],
        working_directory="/tmp/a",
        current_turn=0,
        title="First",
    )
    session_store.save_snapshot(
        session_id="session-b",
        messages=[Message.user_message("second")],
        working_directory="/tmp/b",
        current_turn=0,
        title="Second",
    )
    sessions = session_store.list_sessions()

    assert resolve_session_choice("1", sessions) == sessions[0].session_id
    assert resolve_session_choice("session-b", sessions) == "session-b"
    assert resolve_session_choice("99", sessions) is None


def test_prompt_for_session_selection_accepts_numeric_choice(tmp_path: Path) -> None:
    session_store = SessionStore(tmp_path)
    session_store.save_snapshot(
        session_id="session-a",
        messages=[Message.user_message("resume me")],
        working_directory="/tmp/project",
        current_turn=0,
        title="Resume me",
    )

    with patch("click.prompt", return_value="1"):
        assert prompt_for_session_selection(session_store) == "session-a"
