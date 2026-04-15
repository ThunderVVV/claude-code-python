"""Persistent TUI session storage."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from cc_code.core.messages import (
    Message,
    MessageRole,
    Usage,
    generate_uuid,
    content_block_from_dict,
    SessionState,
)


DEFAULT_SESSION_BASE_DIR = Path.home() / ".cc-py"
_DISPLAY_TAG_PATTERN = re.compile(
    r"<([a-z][\w-]*)(?:\s[^>]*)?>[\s\S]*?</\1>\n?",
    re.MULTILINE,
)
_WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass
class RevertStateData:
    """Persisted revert state data."""

    message_id: str = ""
    part_id: Optional[str] = None
    snapshot: Optional[str] = None
    additions: int = 0
    deletions: int = 0
    files: int = 0


@dataclass
class SessionSummary:
    """Metadata used by the session picker."""

    session_id: str
    title: str
    created_at: str
    updated_at: str
    working_directory: str
    message_count: int = 0


def derive_session_title(
    messages: list[Message],
    fallback_session_id: str = "",
) -> str:
    """Build a compact title from the first user-authored message."""
    for message in messages:
        if message.type != MessageRole.USER or message.is_meta:
            continue
        title = _normalize_title_text(message.get_text())
        if title:
            return title

    fallback = fallback_session_id[:8].strip()
    return fallback or "Untitled session"


class SessionStore:
    """Read and write persisted TUI sessions."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = (
            Path(base_dir) if base_dir is not None else DEFAULT_SESSION_BASE_DIR
        )
        self.sessions_dir = self.base_dir / "sessions"

    def save_snapshot(
        self,
        *,
        session_id: str,
        messages: list[Message],
        working_directory: str,
        current_turn: int,
        title: Optional[str] = None,
        created_at: Optional[str] = None,
        model_name: Optional[str] = None,
        model_id: Optional[str] = None,
        total_usage: Optional[Usage] = None,
        revert_state: Optional[RevertStateData] = None,
        total_diff: Optional[dict] = None,
    ) -> SessionState:
        """Persist a stable session snapshot to disk."""
        existing = self.load_session(session_id)
        now = _local_now()
        resolved_created_at = created_at or (existing.created_at if existing else now)
        resolved_title = (
            (title or "").strip()
            or (existing.title if existing else "")
            or derive_session_title(messages, fallback_session_id=session_id)
        )
        
        state = SessionState(
            session_id=session_id,
            title=resolved_title,
            created_at=resolved_created_at,
            updated_at=now,
            working_directory=working_directory,
            current_turn=current_turn,
            model_id=model_id
            if model_id is not None
            else (existing.model_id if existing else None),
            model_name=model_name
            if model_name is not None
            else (existing.model_name if existing else None),
            total_usage=_clone_usage(
                total_usage or (existing.total_usage if existing else None)
            ),
            messages=list(messages),
        )

        if revert_state:
            from cc_code.core.snapshot import DiffSummary, RevertState

            state.set_revert_state(
                RevertState(
                    message_id=revert_state.message_id,
                    part_id=revert_state.part_id,
                    snapshot=revert_state.snapshot,
                    diff=DiffSummary(
                        additions=revert_state.additions,
                        deletions=revert_state.deletions,
                        files=revert_state.files,
                    ),
                ),
            )

        if total_diff is not None:
            state.total_diff_additions = total_diff.get("additions", 0)
            state.total_diff_deletions = total_diff.get("deletions", 0)
            state.total_diff_files = total_diff.get("files", 0)
        elif existing:
            state.total_diff_additions = existing.total_diff_additions
            state.total_diff_deletions = existing.total_diff_deletions
            state.total_diff_files = existing.total_diff_files

        self.save_session(state)
        return state

    def save_session(self, state: SessionState) -> None:
        """Persist a session state to disk."""
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        session_path = self._session_path(state.session_id)
        tmp_path = session_path.with_suffix(".json.tmp")
        
        # Get revert state for serialization
        revert_data = None
        revert = state.get_revert_state()
        if revert:
            revert_data = {
                "message_id": revert.message_id,
                "part_id": revert.part_id,
                "snapshot": revert.snapshot,
                "additions": revert.diff.additions if revert.diff else 0,
                "deletions": revert.diff.deletions if revert.diff else 0,
                "files": revert.diff.files if revert.diff else 0,
            }
        
        # Get total diff
        total_diff = None
        if state.total_diff_additions or state.total_diff_deletions or state.total_diff_files:
            total_diff = {
                "additions": state.total_diff_additions,
                "deletions": state.total_diff_deletions,
                "files": state.total_diff_files,
            }
        
        payload = {
            "session_id": state.session_id,
            "title": state.title,
            "created_at": state.created_at,
            "updated_at": state.updated_at,
            "working_directory": state.working_directory,
            "current_turn": state.current_turn,
            "model_id": state.model_id,
            "model_name": state.model_name,
            "total_usage": {
                "input_tokens": state.total_usage.input_tokens,
                "output_tokens": state.total_usage.output_tokens,
            },
            "messages": [message.serialize(format="persistence") for message in state.messages],
            "revert_state": revert_data,
            "total_diff": total_diff,
        }
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(session_path)

    def load_session(self, session_id: str) -> Optional[SessionState]:
        """Load a persisted session by ID."""
        session_path = self._session_path(session_id)
        if not session_path.exists():
            return None

        try:
            payload = json.loads(session_path.read_text(encoding="utf-8"))
        except Exception:
            return None

        try:
            # Reconstruct usage
            usage_data = payload.get("total_usage")
            if not isinstance(usage_data, dict):
                usage_data = {}
            total_usage = Usage(
                input_tokens=int(usage_data.get("input_tokens", 0)),
                output_tokens=int(usage_data.get("output_tokens", 0)),
            )

            # Reconstruct messages
            messages = []
            for message_data in payload.get("messages", []):
                if isinstance(message_data, dict):
                    messages.append(_reconstruct_message(message_data))

            state = SessionState(
                session_id=str(payload["session_id"]),
                title=str(payload.get("title", "")).strip() or session_id[:8],
                created_at=str(payload.get("created_at", "")),
                updated_at=str(payload.get("updated_at", "")),
                working_directory=str(payload.get("working_directory", "")),
                current_turn=int(payload.get("current_turn", 0)),
                model_id=payload.get("model_id"),
                model_name=payload.get("model_name"),
                total_usage=total_usage,
                messages=messages,
            )
            
            # Restore revert state
            revert_data = payload.get("revert_state")
            if revert_data and isinstance(revert_data, dict):
                from cc_code.core.snapshot import DiffSummary, RevertState
                state.set_revert_state(RevertState(
                    message_id=str(revert_data.get("message_id", "")),
                    part_id=revert_data.get("part_id"),
                    snapshot=revert_data.get("snapshot"),
                    diff=DiffSummary(
                        additions=int(revert_data.get("additions", 0)),
                        deletions=int(revert_data.get("deletions", 0)),
                        files=int(revert_data.get("files", 0)),
                    ),
                ))
            
            # Restore total diff
            total_diff = payload.get("total_diff")
            if total_diff and isinstance(total_diff, dict):
                state.total_diff_additions = total_diff.get("additions", 0)
                state.total_diff_deletions = total_diff.get("deletions", 0)
                state.total_diff_files = total_diff.get("files", 0)
            
            return state
            
        except Exception:
            return None

    def list_sessions(self) -> list[SessionSummary]:
        """List saved sessions ordered by most recent update."""
        if not self.sessions_dir.exists():
            return []

        summaries: list[SessionSummary] = []
        for session_path in self.sessions_dir.glob("*.json"):
            try:
                payload = json.loads(session_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            session_id = str(payload.get("session_id", "")).strip()
            if not session_id:
                continue

            title = str(payload.get("title", "")).strip() or session_id[:8]
            summaries.append(
                SessionSummary(
                    session_id=session_id,
                    title=title,
                    created_at=str(payload.get("created_at", "")),
                    updated_at=str(payload.get("updated_at", "")),
                    working_directory=str(payload.get("working_directory", "")),
                    message_count=len(payload.get("messages", [])),
                )
            )

        return sorted(
            summaries,
            key=lambda session: session.updated_at,
            reverse=True,
        )

    def _session_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"


def _local_now() -> str:
    """Return a timestamp in local system timezone."""
    return datetime.now().isoformat()


def _clone_usage(usage: Optional[Usage]) -> Usage:
    """Return a detached usage copy."""
    if usage is None:
        return Usage()
    return Usage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
    )


def _normalize_title_text(text: str) -> str:
    """Strip XML-like tags and collapse the first sentence into a title."""
    stripped = _DISPLAY_TAG_PATTERN.sub(" ", text or "").strip()
    normalized = _WHITESPACE_PATTERN.sub(" ", stripped).strip()
    if not normalized:
        return ""

    sentence = re.split(r"(?<=[。！？.!?])\s+", normalized, maxsplit=1)[0].strip()
    if len(sentence) <= 80:
        return sentence
    return sentence[:77].rstrip() + "..."


def _reconstruct_message(data: dict[str, Any]) -> Message:
    """Reconstruct Message from persisted dict."""
    timestamp_value = data.get("timestamp")
    timestamp = (
        datetime.fromisoformat(str(timestamp_value))
        if isinstance(timestamp_value, str) and timestamp_value
        else datetime.now()
    )
    role_value = str(data.get("type", MessageRole.USER.value))
    role = MessageRole(role_value)

    file_expansions = []
    expansions_data = data.get("file_expansions", [])
    if isinstance(expansions_data, list):
        from cc_code.core.file_expansion import FileExpansion

        for exp_data in expansions_data:
            if isinstance(exp_data, dict):
                file_expansions.append(
                    FileExpansion(
                        file_path=str(exp_data.get("file_path", "")),
                        content=str(exp_data.get("content", "")),
                        display_path=str(exp_data.get("display_path", "")),
                    )
                )

    original_text = str(data.get("original_text", ""))
    content = [
        content_block_from_dict(block_data)
        for block_data in data.get("content", [])
        if isinstance(block_data, dict)
    ]

    usage = None
    usage_data = data.get("usage")
    if isinstance(usage_data, dict):
        usage = Usage(
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
        )

    return Message(
        type=role,
        content=content,
        uuid=str(data.get("uuid", "")) or generate_uuid(),
        timestamp=timestamp,
        is_meta=bool(data.get("is_meta", False)),
        is_compact_summary=bool(data.get("is_compact_summary", False)),
        usage=usage,
        stop_reason=data.get("stop_reason"),
        parent_id=data.get("parent_id"),
        subtype=data.get("subtype"),
        file_expansions=file_expansions,
        original_text=original_text,
    )
