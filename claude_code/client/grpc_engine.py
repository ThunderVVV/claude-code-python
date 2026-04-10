"""gRPC-based QueryEngine adapter for TUI compatibility"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from claude_code.core.messages import (
    Message,
    Usage,
    QueryEvent,
    TextEvent,
    ThinkingEvent,
    ToolUseEvent,
    ToolResultEvent,
    MessageCompleteEvent,
    TurnCompleteEvent,
    ErrorEvent,
    generate_uuid,
)
from claude_code.client.grpc_client import ClaudeCodeClient

logger = logging.getLogger(__name__)


@dataclass
class QueryConfig:
    max_turns: int = 1000000
    stream: bool = True
    system_prompt: str = ""
    working_directory: str = ""


@dataclass
class QueryResult:
    success: bool = True
    text: str = ""
    stop_reason: str = "end_turn"
    num_turns: int = 0
    error: Optional[str] = None
    usage: Optional[Usage] = None


class GrpcQueryEngine:
    """
    QueryEngine-compatible adapter that uses gRPC client.

    This class provides the same interface as QueryEngine but communicates
    with a remote gRPC server instead of running locally.
    """

    def __init__(
        self,
        grpc_client: ClaudeCodeClient,
        session_id: Optional[str] = None,
        working_directory: str = "",
    ):
        self._client = grpc_client
        self._session_id = session_id or generate_uuid()
        self._cwd = working_directory or os.getcwd()
        self._is_initialized = False
        self._messages: List[Message] = []
        self._current_turn = 0
        self._total_usage = Usage()
        self._is_streaming = False
        self._current_streaming_text = ""
        self._cancel_event = asyncio.Event()

    async def initialize(self) -> None:
        if not self._is_initialized:
            await self._client.connect()
            self._is_initialized = True

    async def close(self) -> None:
        if self._is_initialized:
            await self._client.close()
            self._is_initialized = False

    async def __aenter__(self) -> "GrpcQueryEngine":
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    def get_session_id(self) -> str:
        return self._session_id

    def get_working_directory(self) -> str:
        return self._cwd

    def get_messages(self) -> List[Message]:
        return self._messages

    def clear(self) -> None:
        self._messages = []
        self._current_turn = 0
        self._total_usage = Usage()
        self._is_streaming = False
        self._current_streaming_text = ""
        self._session_id = generate_uuid()
        self.clear_interrupt()

    def interrupt(self, reason: str = "interrupt") -> None:
        self._cancel_event.set()

    def clear_interrupt(self) -> None:
        if self._cancel_event.is_set():
            self._cancel_event = asyncio.Event()

    def get_interrupt_reason(self) -> Optional[str]:
        return None if not self._cancel_event.is_set() else "user_interrupt"

    async def submit_message(
        self,
        user_text: str,
    ) -> AsyncGenerator[QueryEvent, None]:
        if not self._is_initialized:
            await self.initialize()

        self._is_streaming = True
        self._current_streaming_text = ""
        current_text = ""

        try:
            async for event in self._client.stream_chat(
                user_text,
                self._session_id,
                self._cwd,
            ):
                if self._cancel_event.is_set():
                    return

                if isinstance(event, TextEvent):
                    current_text += event.text
                    self._current_streaming_text = current_text
                    yield event
                elif isinstance(event, ThinkingEvent):
                    yield event
                elif isinstance(event, ToolUseEvent):
                    yield event
                elif isinstance(event, ToolResultEvent):
                    yield event
                elif isinstance(event, MessageCompleteEvent):
                    if event.message:
                        self._messages.append(event.message)
                    yield event
                elif isinstance(event, TurnCompleteEvent):
                    self._current_turn = event.turn
                    yield event
                elif isinstance(event, ErrorEvent):
                    yield event
                    return

        except Exception as e:
            logger.error(f"gRPC stream error: {e}")
            yield ErrorEvent(error=str(e), is_fatal=True)
        finally:
            self._is_streaming = False
            self._current_streaming_text = ""

    async def run(
        self,
        user_text: str,
        on_text: Optional[Callable[[str], None]] = None,
        on_tool_start: Optional[Callable[[str, str, Dict], None]] = None,
        on_tool_end: Optional[Callable[[str, str, bool], None]] = None,
        on_message: Optional[Callable[[Message], None]] = None,
        on_turn: Optional[Callable[[int, bool], None]] = None,
    ) -> QueryResult:
        result = QueryResult()

        try:
            async for event in self.submit_message(user_text):
                if isinstance(event, TextEvent):
                    if on_text:
                        on_text(event.text)
                elif isinstance(event, ToolUseEvent):
                    if on_tool_start:
                        on_tool_start(event.tool_use_id, event.tool_name, event.input)
                elif isinstance(event, ToolResultEvent):
                    if on_tool_end:
                        on_tool_end(event.tool_use_id, event.result, event.is_error)
                elif isinstance(event, MessageCompleteEvent):
                    if on_message and event.message:
                        on_message(event.message)
                elif isinstance(event, TurnCompleteEvent):
                    result.num_turns = event.turn
                    if on_turn:
                        on_turn(event.turn, event.has_more_turns)
                    if event.stop_reason:
                        result.stop_reason = event.stop_reason
                elif isinstance(event, ErrorEvent):
                    result.success = False
                    result.error = event.error
        except Exception as e:
            result.success = False
            result.error = str(e)

        for msg in reversed(self._messages):
            text = msg.get_text()
            if text:
                result.text = text
                break

        result.usage = self._total_usage
        return result
