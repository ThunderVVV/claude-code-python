"""gRPC client for Claude Code Python - stateless frontend client"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator, List, Optional

import grpc
from grpc import aio

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


def proto_to_content_block(pb) -> Optional[object]:
    which = pb.WhichOneof("block")
    if which == "text":
        return TextContent(text=pb.text.text)
    elif which == "thinking":
        return ThinkingContent(
            thinking=pb.thinking.thinking,
            signature=pb.thinking.signature,
        )
    elif which == "tool_use":
        return ToolUseContent(
            id=pb.tool_use.id,
            name=pb.tool_use.name,
            input=json.loads(pb.tool_use.input_json) if pb.tool_use.input_json else {},
        )
    elif which == "tool_result":
        return ToolResultContent(
            tool_use_id=pb.tool_result.tool_use_id,
            content=pb.tool_result.content,
            is_error=pb.tool_result.is_error,
        )
    return None


def proto_to_message_role(role: int) -> MessageRole:
    from claude_code.proto import claude_code_pb2

    mapping = {
        claude_code_pb2.MESSAGE_ROLE_USER: MessageRole.USER,
        claude_code_pb2.MESSAGE_ROLE_ASSISTANT: MessageRole.ASSISTANT,
        claude_code_pb2.MESSAGE_ROLE_SYSTEM: MessageRole.SYSTEM,
        claude_code_pb2.MESSAGE_ROLE_TOOL: MessageRole.TOOL,
    }
    return mapping.get(role, MessageRole.USER)


def proto_to_message(pb) -> Message:
    content_blocks = []
    for block_pb in pb.content:
        block = proto_to_content_block(block_pb)
        if block:
            content_blocks.append(block)

    msg = Message(
        type=proto_to_message_role(pb.role),
        content=content_blocks,
        uuid=pb.uuid,
        timestamp=datetime.fromtimestamp(pb.timestamp)
        if pb.timestamp
        else datetime.now(),
        original_text=pb.original_text,
        message={},
    )

    if pb.HasField("usage"):
        msg.message["usage"] = {
            "input_tokens": pb.usage.input_tokens,
            "output_tokens": pb.usage.output_tokens,
        }

    return msg


def proto_to_query_event(pb_event) -> QueryEvent:
    from claude_code.proto import claude_code_pb2

    which = pb_event.WhichOneof("event")

    if which == "text_event":
        return TextEvent(text=pb_event.text_event.text)
    elif which == "thinking_event":
        return ThinkingEvent(thinking=pb_event.thinking_event.thinking)
    elif which == "tool_use_event":
        return ToolUseEvent(
            tool_use_id=pb_event.tool_use_event.tool_use_id,
            tool_name=pb_event.tool_use_event.tool_name,
            input=json.loads(pb_event.tool_use_event.input_json)
            if pb_event.tool_use_event.input_json
            else {},
        )
    elif which == "tool_result_event":
        return ToolResultEvent(
            tool_use_id=pb_event.tool_result_event.tool_use_id,
            result=pb_event.tool_result_event.result,
            is_error=pb_event.tool_result_event.is_error,
        )
    elif which == "message_complete_event":
        msg = (
            proto_to_message(pb_event.message_complete_event.message)
            if pb_event.message_complete_event.HasField("message")
            else None
        )
        return MessageCompleteEvent(message=msg)
    elif which == "turn_complete_event":
        return TurnCompleteEvent(
            turn=pb_event.turn_complete_event.turn,
            has_more_turns=pb_event.turn_complete_event.has_more_turns,
            stop_reason=pb_event.turn_complete_event.stop_reason or None,
        )
    elif which == "error_event":
        return ErrorEvent(
            error=pb_event.error_event.error,
            is_fatal=pb_event.error_event.is_fatal,
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


class ClaudeCodeClient:
    """Stateless gRPC client for Claude Code TUI."""

    def __init__(self, host: str = "localhost", port: int = 50051):
        self._host = host
        self._port = port
        self._channel: Optional[aio.Channel] = None
        self._chat_stub = None
        self._session_stub = None
        self._is_connected = False

    async def connect(self) -> None:
        from claude_code.proto import claude_code_pb2_grpc

        self._channel = aio.insecure_channel(f"{self._host}:{self._port}")
        self._chat_stub = claude_code_pb2_grpc.ChatServiceStub(self._channel)
        self._session_stub = claude_code_pb2_grpc.SessionServiceStub(self._channel)
        self._is_connected = True

    async def close(self) -> None:
        if self._channel:
            await self._channel.close()
            self._channel = None
            self._chat_stub = None
            self._session_stub = None
            self._is_connected = False

    async def __aenter__(self) -> "ClaudeCodeClient":
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
        from claude_code.proto import claude_code_pb2

        request = claude_code_pb2.ChatRequest(
            session_id=session_id,
            user_text=user_text,
            working_directory=working_directory,
        )

        logger.debug(f"Sending StreamChat request - session_id: {session_id}, user_text: {user_text[:100]}..., working_directory: {working_directory}")

        try:
            async for response in self._chat_stub.StreamChat(request):
                event = proto_to_query_event(response.event)
                yield event
        except grpc.RpcError as e:
            log_full_exception(logger, "gRPC error in stream_chat")
            yield ErrorEvent(error=str(e), is_fatal=True)

    async def interrupt(self, session_id: str, reason: str = "user_interrupt") -> bool:
        """Send interrupt signal to server."""
        from claude_code.proto import claude_code_pb2

        request = claude_code_pb2.InterruptRequest(
            session_id=session_id,
            reason=reason,
        )
        logger.debug(f"Sending Interrupt request - session_id: {session_id}, reason: {reason}")
        response = await self._chat_stub.Interrupt(request)
        return response.success

    async def create_session(self, working_directory: str = "") -> str:
        """Create a new session on server."""
        from claude_code.proto import claude_code_pb2

        request = claude_code_pb2.CreateSessionRequest(
            working_directory=working_directory
        )
        logger.debug(f"Sending CreateSession request - working_directory: {working_directory}")
        response = await self._session_stub.CreateSession(request)
        return response.session_id

    async def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """Get session info from server."""
        from claude_code.proto import claude_code_pb2

        request = claude_code_pb2.GetSessionRequest(session_id=session_id)
        logger.debug(f"Sending GetSession request - session_id: {session_id}")
        response = await self._session_stub.GetSession(request)

        if not response.session_id:
            return None

        messages = [proto_to_message(msg_pb) for msg_pb in response.messages]

        return SessionInfo(
            session_id=response.session_id,
            messages=messages,
            current_turn=response.current_turn,
            total_usage=Usage(
                input_tokens=response.total_usage.input_tokens,
                output_tokens=response.total_usage.output_tokens,
            ),
            working_directory=response.working_directory,
            title=response.title,
        )

    async def list_sessions(self) -> List[SessionSummary]:
        """List all sessions from server."""
        from datetime import datetime, timezone
        from claude_code.proto import claude_code_pb2

        request = claude_code_pb2.ListSessionsRequest()
        logger.debug("Sending ListSessions request")
        response = await self._session_stub.ListSessions(request)

        summaries = []
        for s in response.sessions:
            if s.updated_at:
                dt = datetime.fromtimestamp(s.updated_at, tz=timezone.utc)
                updated_at_str = dt.isoformat()
            else:
                updated_at_str = ""
            summaries.append(
                SessionSummary(
                    session_id=s.session_id,
                    title=s.title,
                    created_at=updated_at_str,
                    updated_at=updated_at_str,
                    working_directory=s.working_directory,
                    message_count=s.message_count,
                )
            )
        return summaries
