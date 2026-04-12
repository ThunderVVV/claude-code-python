"""HTTP client for Claude Code Python - connects to FastAPI backend"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import AsyncGenerator, List, Optional

import httpx

from claude_code.core.messages import (
    Message,
    MessageRole,
    TextContent,
    ThinkingContent,
    ToolUseContent,
    ToolResultContent,
    Usage,
    QueryEvent,
    TextEvent,
    ThinkingEvent,
    ToolUseEvent,
    ToolResultEvent,
    MessageCompleteEvent,
    TurnCompleteEvent,
    ErrorEvent,
)
from claude_code.core.session_store import SessionSummary
from claude_code.utils.logging_config import log_full_exception

logger = logging.getLogger(__name__)


def dict_to_content_block(data: dict) -> Optional[object]:
    block_type = data.get("type")
    if block_type == "text":
        return TextContent(text=data.get("text", ""))
    elif block_type == "thinking":
        return ThinkingContent(
            thinking=data.get("thinking", ""),
            signature="",
        )
    elif block_type == "tool_use":
        return ToolUseContent(
            id=data.get("tool_use_id", ""),
            name=data.get("tool_name", ""),
            input=data.get("input", {}),
        )
    elif block_type == "tool_result":
        return ToolResultContent(
            tool_use_id=data.get("tool_use_id", ""),
            content=data.get("result", ""),
            is_error=data.get("is_error", False),
        )
    return None


def dict_to_message_role(role_str: str) -> MessageRole:
    mapping = {
        "user": MessageRole.USER,
        "USER": MessageRole.USER,
        "assistant": MessageRole.ASSISTANT,
        "ASSISTANT": MessageRole.ASSISTANT,
        "system": MessageRole.SYSTEM,
        "SYSTEM": MessageRole.SYSTEM,
        "tool": MessageRole.TOOL,
        "TOOL": MessageRole.TOOL,
    }
    return mapping.get(role_str, MessageRole.USER)


def dict_to_message(data: dict) -> Message:
    from claude_code.core.file_expansion import FileExpansion

    content_blocks = []
    for block_data in data.get("content_blocks", []):
        block = dict_to_content_block(block_data)
        if block:
            content_blocks.append(block)

    # Handle file_expansions
    file_expansions = []
    for file_exp_data in data.get("file_expansions", []):
        file_expansions.append(
            FileExpansion(
                file_path=file_exp_data.get("file_path", ""),
                content=file_exp_data.get("content", ""),
                display_path=file_exp_data.get("display_path", ""),
            )
        )

    msg = Message(
        type=dict_to_message_role(data.get("role", "user")),
        content=content_blocks,
        uuid=data.get("uuid", ""),
        timestamp=datetime.now(),
        original_text=data.get("original_text", ""),
        message={"usage": data.get("usage")} if data.get("usage") else {},
        file_expansions=file_expansions,
        web_enabled=data.get("web_enabled", False),
    )

    return msg


def dict_to_query_event(data: dict) -> QueryEvent:
    event_type = data.get("type")

    if event_type == "text":
        return TextEvent(text=data.get("text", ""))
    elif event_type == "thinking":
        return ThinkingEvent(thinking=data.get("thinking", ""))
    elif event_type == "tool_use":
        return ToolUseEvent(
            tool_use_id=data.get("tool_use_id", ""),
            tool_name=data.get("tool_name", ""),
            input=data.get("input", {}),
        )
    elif event_type == "tool_result":
        return ToolResultEvent(
            tool_use_id=data.get("tool_use_id", ""),
            result=data.get("result", ""),
            is_error=data.get("is_error", False),
        )
    elif event_type == "message_complete":
        msg_data = data.get("message")
        msg = dict_to_message(msg_data) if msg_data else None
        return MessageCompleteEvent(message=msg)
    elif event_type == "turn_complete":
        return TurnCompleteEvent(
            turn=data.get("turn", 0),
            has_more_turns=data.get("has_more_turns", False),
            stop_reason=None,
        )
    elif event_type == "error":
        return ErrorEvent(
            error=data.get("error", ""),
            is_fatal=data.get("is_fatal", False),
        )

    return ErrorEvent(error="Unknown event type", is_fatal=False)


class SessionInfo:
    """Session information returned from server."""

    def __init__(
        self,
        session_id: str,
        messages: List[Message] = None,
        current_turn: int = 0,
        total_usage: Usage = None,
        working_directory: str = "",
        title: str = "",
    ):
        self.session_id = session_id
        self.messages = messages or []
        self.current_turn = current_turn
        self.total_usage = total_usage or Usage()
        self.working_directory = working_directory
        self.title = title


class ClaudeCodeHttpClient:
    """HTTP client for Claude Code TUI."""

    def __init__(self, host: str = "localhost", port: int = 8000):
        self._host = host
        self._port = port
        self._base_url = f"http://{host}:{port}"
        self._client: Optional[httpx.AsyncClient] = None
        self._is_connected = False

    async def connect(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=None,
        )
        self._is_connected = True

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
            self._is_connected = False

    async def __aenter__(self) -> "ClaudeCodeHttpClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    async def stream_chat(
        self,
        user_text: str,
        session_id: str,
        working_directory: str = "",
    ) -> AsyncGenerator[QueryEvent, None]:
        """Send a message and receive event stream from server."""
        logger.debug(f"stream_chat called, URL={self._base_url}/api/chat")

        if not self._client:
            raise RuntimeError("Client not connected")

        request_data = {
            "session_id": session_id,
            "user_text": user_text,
            "working_directory": working_directory,
        }

        try:
            async with self._client.stream(
                "POST",
                f"{self._base_url}/api/chat",
                json=request_data,
                timeout=None,
            ) as response:
                response.raise_for_status()

                buffer = ""
                async for byte_chunk in response.aiter_bytes():
                    chunk = byte_chunk.decode("utf-8", errors="replace")
                    buffer += chunk

                    while "\n\n" in buffer:
                        event_part, buffer = buffer.split("\n\n", 1)
                        if event_part.startswith("data: "):
                            data_str = event_part[6:]
                            if data_str:
                                try:
                                    data = json.loads(data_str)
                                    if data.get("type") == "session_id":
                                        continue
                                    event = dict_to_query_event(data)
                                    yield event
                                except json.JSONDecodeError as e:
                                    logger.warning(f"JSON decode error: {e}")

        except httpx.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            log_full_exception(logger, "HTTP error in stream_chat", e)
            yield ErrorEvent(error=str(e), is_fatal=True)

    async def interrupt(self, session_id: str, reason: str = "user_interrupt") -> bool:
        """Send interrupt signal to server."""
        if not self._client:
            raise RuntimeError("Client not connected")

        request_data = {
            "session_id": session_id,
            "reason": reason,
        }
        logger.debug(
            f"Sending Interrupt request - session_id: {session_id}, reason: {reason}"
        )

        try:
            response = await self._client.post(
                f"{self._base_url}/api/interrupt",
                json=request_data,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("success", False)
        except httpx.HTTPError as e:
            logger.error(f"Interrupt request failed: {e}")
            return False

    async def create_session(self, working_directory: str = "") -> str:
        """Create a new session on server - returns random UUID since we generate client-side."""
        from claude_code.core.messages import generate_uuid

        return generate_uuid()

    async def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """Get session info from server."""
        if not self._client:
            raise RuntimeError("Client not connected")

        logger.debug(f"Sending GetSession request - session_id: {session_id}")

        try:
            response = await self._client.get(
                f"{self._base_url}/api/sessions/{session_id}",
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()

            messages = [
                dict_to_message(msg_data) for msg_data in data.get("messages", [])
            ]
            usage_data = data.get("total_usage", {})

            return SessionInfo(
                session_id=data.get("session_id", ""),
                messages=messages,
                current_turn=data.get("current_turn", 0),
                total_usage=Usage(
                    input_tokens=usage_data.get("input_tokens", 0),
                    output_tokens=usage_data.get("output_tokens", 0),
                ),
                working_directory=data.get("working_directory", ""),
                title=data.get("title", ""),
            )
        except httpx.HTTPError as e:
            logger.error(f"Get session request failed: {e}")
            return None

    async def list_sessions(self) -> List[SessionSummary]:
        """List all sessions from server."""
        if not self._client:
            raise RuntimeError("Client not connected")

        logger.debug("Sending ListSessions request")

        try:
            response = await self._client.get(f"{self._base_url}/api/sessions")
            response.raise_for_status()
            data = response.json()

            summaries = []
            for s in data.get("sessions", []):
                summaries.append(
                    SessionSummary(
                        session_id=s.get("session_id", ""),
                        title=s.get("title", ""),
                        created_at=s.get("updated_at", ""),
                        updated_at=s.get("updated_at", ""),
                        working_directory=s.get("working_directory", ""),
                        message_count=s.get("message_count", 0),
                    )
                )
            return summaries
        except httpx.HTTPError as e:
            logger.error(f"List sessions request failed: {e}")
            return []

    async def revert(
        self,
        session_id: str,
        target_message_id: Optional[str] = None,
        target_part_id: Optional[str] = None,
    ) -> dict:
        """Revert file changes from a specific point."""
        if not self._client:
            raise RuntimeError("Client not connected")

        request_data = {
            "session_id": session_id,
            "target_message_id": target_message_id,
            "target_part_id": target_part_id,
        }
        logger.info(
            f"[CLIENT] Revert request: session_id={session_id}, "
            f"target_message_id={target_message_id!r}"
        )

        try:
            response = await self._client.post(
                f"{self._base_url}/api/revert",
                json=request_data,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Revert request failed: {e}")
            return {"success": False, "message": str(e)}

    async def unrevert(self, session_id: str) -> dict:
        """Undo a previous revert operation."""
        if not self._client:
            raise RuntimeError("Client not connected")

        request_data = {"session_id": session_id}
        logger.debug(f"Sending Unrevert request - session_id: {session_id}")

        try:
            response = await self._client.post(
                f"{self._base_url}/api/unrevert",
                json=request_data,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Unrevert request failed: {e}")
            return {"success": False, "message": str(e)}

    async def get_revert_state(self, session_id: str) -> dict:
        """Get the current revert state for a session."""
        if not self._client:
            raise RuntimeError("Client not connected")

        logger.debug(f"Sending GetRevertState request - session_id: {session_id}")

        try:
            response = await self._client.get(
                f"{self._base_url}/api/revert_state/{session_id}",
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Get revert state request failed: {e}")
            return {"has_revert": False}

    async def get_snapshot_status(self, session_id: str) -> dict:
        """Get the snapshot status (files modified, additions, deletions)."""
        if not self._client:
            raise RuntimeError("Client not connected")

        try:
            response = await self._client.get(
                f"{self._base_url}/api/snapshot_status/{session_id}",
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Get snapshot status request failed: {e}")
            return {"available": False}
