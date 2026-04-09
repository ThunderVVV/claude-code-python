"""Persistent TUI session storage."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from claude_code.core.messages import (
    Message,
    MessageRole,
    TextContent,
    ThinkingContent,
    ToolResultContent,
    ToolUseContent,
    Usage,
    generate_uuid,
)


DEFAULT_SESSION_BASE_DIR = Path.home() / ".claude-code-python"
_DISPLAY_TAG_PATTERN = re.compile(
    r"<([a-z][\w-]*)(?:\s[^>]*)?>[\s\S]*?</\1>\n?",
    re.MULTILINE,
)
_WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass
class PersistedSession:
    """Full persisted session payload."""

    session_id: str
    title: str
    created_at: str
    updated_at: str
    working_directory: str
    current_turn: int = 0
    model_name: Optional[str] = None
    total_usage: Usage = field(default_factory=Usage)
    messages: list[Message] = field(default_factory=list)


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
        self.base_dir = Path(base_dir) if base_dir is not None else DEFAULT_SESSION_BASE_DIR
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
        total_usage: Optional[Usage] = None,
    ) -> PersistedSession:
        """Persist a stable session snapshot to disk."""
        existing = self.load_session(session_id)
        now = _local_now()
        resolved_created_at = created_at or (existing.created_at if existing else now)
        resolved_title = (
            (title or "").strip()
            or (existing.title if existing else "")
            or derive_session_title(messages, fallback_session_id=session_id)
        )

        session = PersistedSession(
            session_id=session_id,
            title=resolved_title,
            created_at=resolved_created_at,
            updated_at=now,
            working_directory=working_directory,
            current_turn=current_turn,
            model_name=model_name if model_name is not None else (existing.model_name if existing else None),
            total_usage=_clone_usage(total_usage or (existing.total_usage if existing else None)),
            messages=list(messages),
        )
        self.save_session(session)
        return session

    def save_session(self, session: PersistedSession) -> None:
        """Persist a full session payload to disk."""
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        session_path = self._session_path(session.session_id)
        tmp_path = session_path.with_suffix(".json.tmp")
        payload = {
            "session_id": session.session_id,
            "title": session.title,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "working_directory": session.working_directory,
            "current_turn": session.current_turn,
            "model_name": session.model_name,
            "total_usage": _usage_to_dict(session.total_usage),
            "messages": [_message_to_dict(message) for message in session.messages],
        }
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(session_path)

    def load_session(self, session_id: str) -> Optional[PersistedSession]:
        """Load a persisted session by ID."""
        session_path = self._session_path(session_id)
        if not session_path.exists():
            return None

        try:
            payload = json.loads(session_path.read_text(encoding="utf-8"))
        except Exception:
            return None

        try:
            return PersistedSession(
                session_id=str(payload["session_id"]),
                title=str(payload.get("title", "")).strip() or session_id[:8],
                created_at=str(payload.get("created_at", "")),
                updated_at=str(payload.get("updated_at", "")),
                working_directory=str(payload.get("working_directory", "")),
                current_turn=int(payload.get("current_turn", 0)),
                model_name=payload.get("model_name"),
                total_usage=_usage_from_dict(payload.get("total_usage")),
                messages=[
                    _message_from_dict(message_data)
                    for message_data in payload.get("messages", [])
                    if isinstance(message_data, dict)
                ],
            )
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


def _usage_to_dict(usage: Usage) -> dict[str, int]:
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
    }


def _usage_from_dict(data: Any) -> Usage:
    if not isinstance(data, dict):
        return Usage()
    return Usage(
        input_tokens=int(data.get("input_tokens", 0)),
        output_tokens=int(data.get("output_tokens", 0)),
    )


def _content_block_to_dict(block: Any) -> dict[str, Any]:
    if isinstance(block, TextContent):
        return {"type": "text", "text": block.text}
    if isinstance(block, ThinkingContent):
        return {
            "type": "thinking",
            "thinking": block.thinking,
            "signature": block.signature,
        }
    if isinstance(block, ToolUseContent):
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": block.input,
        }
    if isinstance(block, ToolResultContent):
        return {
            "type": "tool_result",
            "tool_use_id": block.tool_use_id,
            "content": block.content,
            "is_error": block.is_error,
        }
    raise TypeError(f"Unsupported content block: {type(block)!r}")


def _content_block_from_dict(data: dict[str, Any]) -> Any:
    block_type = data.get("type")
    if block_type == "text":
        return TextContent(text=str(data.get("text", "")))
    if block_type == "thinking":
        return ThinkingContent(
            thinking=str(data.get("thinking", "")),
            signature=str(data.get("signature", "")),
        )
    if block_type == "tool_use":
        return ToolUseContent(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            input=data.get("input", {}) if isinstance(data.get("input"), dict) else {},
        )
    if block_type == "tool_result":
        return ToolResultContent(
            tool_use_id=str(data.get("tool_use_id", "")),
            content=str(data.get("content", "")),
            is_error=bool(data.get("is_error", False)),
        )
    raise ValueError(f"Unknown content block type: {block_type!r}")


def _message_to_dict(message: Message) -> dict[str, Any]:
    result = {
        "type": message.type.value,
        "content": [_content_block_to_dict(block) for block in message.content],
        "uuid": message.uuid,
        "timestamp": message.timestamp.isoformat(),
        "is_meta": message.is_meta,
        "is_compact_summary": message.is_compact_summary,
        "tool_use_result": message.tool_use_result,
        "is_visible_in_transcript_only": message.is_visible_in_transcript_only,
        "message": message.message,
    }
    # Save file expansion info for user messages
    if message.file_expansions:
        result["file_expansions"] = [
            {
                "file_path": exp.file_path,
                "content": exp.content,
                "display_path": exp.display_path,
            }
            for exp in message.file_expansions
        ]
    if message.original_text:
        result["original_text"] = message.original_text
    return result


def _message_from_dict(data: dict[str, Any]) -> Message:
    timestamp_value = data.get("timestamp")
    timestamp = (
        datetime.fromisoformat(str(timestamp_value))
        if isinstance(timestamp_value, str) and timestamp_value
        else datetime.now()
    )
    role_value = str(data.get("type", MessageRole.USER.value))

    # Restore file expansions
    file_expansions = []
    expansions_data = data.get("file_expansions", [])
    if isinstance(expansions_data, list):
        from claude_code.core.file_expansion import FileExpansion
        for exp_data in expansions_data:
            if isinstance(exp_data, dict):
                file_expansions.append(FileExpansion(
                    file_path=str(exp_data.get("file_path", "")),
                    content=str(exp_data.get("content", "")),
                    display_path=str(exp_data.get("display_path", "")),
                ))

    original_text = str(data.get("original_text", ""))

    return Message(
        type=MessageRole(role_value),
        content=[
            _content_block_from_dict(block_data)
            for block_data in data.get("content", [])
            if isinstance(block_data, dict)
        ],
        uuid=str(data.get("uuid", "")) or generate_uuid(),
        timestamp=timestamp,
        is_meta=bool(data.get("is_meta", False)),
        is_compact_summary=bool(data.get("is_compact_summary", False)),
        tool_use_result=data.get("tool_use_result"),
        is_visible_in_transcript_only=bool(
            data.get("is_visible_in_transcript_only", False)
        ),
        message=data.get("message") if isinstance(data.get("message"), dict) else None,
        file_expansions=file_expansions,
        original_text=original_text,
    )
