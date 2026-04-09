"""Core query engine and execution logic - aligned with TypeScript query.ts and QueryEngine.ts"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional, Callable

logger = logging.getLogger(__name__)

from claude_code.core.messages import (
    ContentBlock,
    Message,
    MessageRole,
    QueryState,
    QueryEvent,
    TextContent,
    ThinkingContent,
    ToolResultContent,
    ToolUseContent,
    Usage,
    TextEvent,
    ThinkingEvent,
    ToolUseEvent,
    ToolResultEvent,
    MessageCompleteEvent,
    TurnCompleteEvent,
    RequestStartEvent,
    ErrorEvent,
    generate_uuid,
)
from claude_code.core.tools import ToolContext, ToolRegistry, find_tool_by_name
from claude_code.core.prompts import create_default_system_prompt, build_context_message
from claude_code.services.openai_client import (
    OpenAIClient,
    OpenAIClientConfig,
    ToolCallDelta,
    APIError,
    APINetworkError,
)


@dataclass
class QueryConfig:
    """Configuration for the query engine"""

    max_turns: int = 1000000
    stream: bool = True
    system_prompt: str = ""
    working_directory: str = ""


@dataclass
class QueryResult:
    """Result of a query execution"""

    success: bool = True
    text: str = ""
    stop_reason: str = "end_turn"
    num_turns: int = 0
    error: Optional[str] = None
    usage: Optional[Usage] = None


@dataclass
class QueryStateSnapshot:
    """Snapshot of mutable query state used for turn rollback."""

    message_count: int
    tool_call_count: int
    current_turn: int
    total_usage: Usage
    undo_operation_count: int = 0


class QueryEngine:
    """
    Core query engine that handles the conversation loop.

    Aligned with TypeScript QueryEngine class in QueryEngine.ts.
    One QueryEngine per conversation. Each submit_message() call starts a new
    turn within the same conversation. State (messages, usage, etc.) persists
    across turns.
    """

    def __init__(
        self,
        client_config: OpenAIClientConfig,
        tool_registry: ToolRegistry,
        config: Optional[QueryConfig] = None,
        session_id: Optional[str] = None,
        initial_messages: Optional[List[Message]] = None,
        initial_current_turn: int = 0,
        initial_usage: Optional[Usage] = None,
    ):
        self.client_config = client_config
        self.tool_registry = tool_registry
        self.config = config or QueryConfig()

        # Mutable state
        self.state = QueryState()
        self.state.messages = list(initial_messages or [])
        self.state.current_turn = initial_current_turn
        self.state.total_usage = Usage(
            input_tokens=(initial_usage.input_tokens if initial_usage else 0),
            output_tokens=(initial_usage.output_tokens if initial_usage else 0),
        )
        self._client: Optional[OpenAIClient] = None
        self._session_id = session_id or generate_uuid()
        self.state.session_id = self._session_id
        self._is_initialized = False
        self._interrupt_reason: Optional[str] = None
        self._active_task: Optional[asyncio.Task[Any]] = None
        self._cancelled_tasks: set[asyncio.Task[Any]] = set()
        self._cancel_event = asyncio.Event()
        self._undo_operations: List[Callable[[], None]] = []

        # Working directory
        self._cwd = self.config.working_directory or os.getcwd()

    async def initialize(self) -> None:
        """Initialize the engine (create HTTP client)"""
        if not self._is_initialized:
            self._client = OpenAIClient(self.client_config)
            self._is_initialized = True

    async def close(self) -> None:
        """Close the engine and release resources"""
        if self._client:
            await self._client.close()
            self._client = None
        self._is_initialized = False

    async def __aenter__(self) -> "QueryEngine":
        """Async context manager entry"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit"""
        # Don't close - keep client alive for reuse
        pass

    def get_session_id(self) -> str:
        """Get the session ID"""
        return self._session_id

    def get_working_directory(self) -> str:
        """Return the working directory for this session."""
        return self._cwd

    def get_messages(self) -> List[Message]:
        """Get all messages in the conversation"""
        return self.state.messages

    def _get_tool_context(self) -> ToolContext:
        """Get tool execution context"""
        return ToolContext(
            working_directory=self._cwd,
            project_root=self._cwd,
            session_id=self._session_id,
            cancel_event=self._cancel_event,
            register_undo_operation=self._register_undo_operation,
        )

    def _register_undo_operation(self, undo_operation: Callable[[], None]) -> None:
        """Track a side-effect undo function for the current conversation state."""
        self._undo_operations.append(undo_operation)

    def _build_system_prompt(self) -> str:
        """Build the system prompt"""
        parts = []

        # Default system prompt with cwd and model name
        parts.append(
            create_default_system_prompt(
                cwd=self._cwd,
                model_name=self.client_config.model_name,
            )
        )

        # Custom system prompt if provided
        if self.config.system_prompt:
            parts.append(self.config.system_prompt)

        return "\n\n".join(parts)

    def clear(self) -> None:
        """Clear the query state"""
        self.state.clear()
        self._undo_operations = []
        self.clear_interrupt()

    def create_state_snapshot(self) -> QueryStateSnapshot:
        """Capture mutable state so the current turn can be rolled back."""
        usage = self.state.total_usage
        return QueryStateSnapshot(
            message_count=len(self.state.messages),
            tool_call_count=len(self.state.tool_calls),
            current_turn=self.state.current_turn,
            total_usage=Usage(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
            ),
            undo_operation_count=len(self._undo_operations),
        )

    def rollback_to_snapshot(
        self,
        snapshot: QueryStateSnapshot,
        message_count: Optional[int] = None,
    ) -> None:
        """Restore state captured before an interrupted turn."""
        retained_messages = snapshot.message_count
        if message_count is not None:
            retained_messages = max(snapshot.message_count, message_count)

        while len(self._undo_operations) > snapshot.undo_operation_count:
            undo_operation = self._undo_operations.pop()
            try:
                undo_operation()
            except Exception as exc:
                logger.warning("Failed to roll back tool side effect: %s", exc)

        self.state.messages = self.state.messages[:retained_messages]
        self.state.tool_calls = self.state.tool_calls[: snapshot.tool_call_count]
        self.state.current_turn = snapshot.current_turn
        self.state.total_usage = Usage(
            input_tokens=snapshot.total_usage.input_tokens,
            output_tokens=snapshot.total_usage.output_tokens,
        )
        self.state.is_streaming = False
        self.state.current_streaming_text = ""
        self.clear_interrupt()

    def interrupt(self, reason: str = "interrupt") -> None:
        """Interrupt the in-flight query, matching the TypeScript QueryEngine API."""
        self._interrupt_reason = reason
        self._cancel_event.set()
        if self._active_task and not self._active_task.done():
            self._cancelled_tasks.add(self._active_task)
            self._active_task.cancel()

    def clear_interrupt(self) -> None:
        """Reset interrupt state before a fresh query starts."""
        self._interrupt_reason = None
        if self._cancel_event.is_set():
            self._cancel_event = asyncio.Event()

    def get_interrupt_reason(self) -> Optional[str]:
        """Return the current interrupt reason, if any."""
        return self._interrupt_reason

    def _raise_if_interrupted(self) -> None:
        """Abort the current query loop when an interrupt has been requested."""
        if self._interrupt_reason is not None:
            raise asyncio.CancelledError

    async def submit_message(
        self,
        user_text: str,
    ) -> AsyncGenerator[QueryEvent, None]:
        """
        Submit a user message and run the query loop.

        This is the main entry point for processing user input.

        Yields events as the conversation progresses:
        - TextEvent: Streaming text from the assistant
        - ToolUseEvent: When a tool starts executing
        - ToolResultEvent: When a tool finishes executing
        - MessageCompleteEvent: When a message is complete
        - TurnCompleteEvent: When a turn is complete
        - ErrorEvent: When an error occurs
        """
        # Auto-initialize if needed
        if not self._is_initialized:
            await self.initialize()

        self._active_task = asyncio.current_task()

        try:
            self._raise_if_interrupted()

            # Create and add user message
            user_message = Message.user_message(user_text)
            self.state.add_message(user_message)
            yield MessageCompleteEvent(message=user_message)

            # Run the query loop
            async for event in self._query_loop():
                yield event
        except asyncio.CancelledError:
            current_task = asyncio.current_task()
            if current_task in self._cancelled_tasks or self._interrupt_reason is not None:
                if current_task in self._cancelled_tasks:
                    self._cancelled_tasks.discard(current_task)
                return
            raise
        finally:
            current_task = asyncio.current_task()
            if current_task in self._cancelled_tasks:
                self._cancelled_tasks.discard(current_task)
            if self._active_task is current_task:
                self._active_task = None

    async def _query_loop(self) -> AsyncGenerator[QueryEvent, None]:
        """
        Internal query loop - aligned with query() in TypeScript query.ts

        This is the core execution loop that:
        1. Calls the API
        2. Processes the response
        3. Executes any tool calls
        4. Continues until done or max turns reached
        """
        if not self._is_initialized or not self._client:
            raise RuntimeError("QueryEngine not initialized. Call initialize() first.")

        system_prompt = self._build_system_prompt()

        while self.state.current_turn < self.config.max_turns:
            self.state.is_streaming = True
            self.state.current_streaming_text = ""

            # Track accumulated content for this turn
            current_text = ""
            current_thinking = ""
            accumulated_tool_calls: List[ToolCallDelta] = []
            previewed_tool_use_ids: set[str] = set()
            stop_reason = "end_turn"
            current_usage: Optional[Usage] = None

            try:
                self._raise_if_interrupted()
                # Yield request start event
                yield RequestStartEvent()

                # Call the API
                async for chunk in self._client.chat_completion(
                    self.state.messages,
                    self.tool_registry,
                    stream=self.config.stream,
                    system_prompt=system_prompt,
                ):
                    self._raise_if_interrupted()
                    if self.config.stream:
                        extract_usage = getattr(self._client, "extract_usage", None)
                        chunk_usage = (
                            extract_usage(chunk) if callable(extract_usage) else None
                        )
                        if chunk_usage:
                            current_usage = chunk_usage
                            self.state.total_usage = chunk_usage

                        # Parse streaming chunk
                        text_delta, thinking_delta, tool_call_deltas = (
                            self._client.parse_stream_chunk(chunk)
                        )

                        # Accumulate thinking
                        if thinking_delta:
                            current_thinking += thinking_delta
                            yield ThinkingEvent(thinking=thinking_delta)

                        # Accumulate text
                        if text_delta:
                            current_text += text_delta
                            self.state.current_streaming_text = current_text
                            yield TextEvent(text=text_delta)

                        # Accumulate tool calls
                        if tool_call_deltas:
                            accumulated_tool_calls = self._client.accumulate_tool_calls(
                                accumulated_tool_calls,
                                tool_call_deltas,
                            )
                            preview_tool_uses = (
                                self._client.partial_tool_calls_to_content_blocks(
                                    accumulated_tool_calls
                                )
                            )
                            for tool_use in preview_tool_uses:
                                if tool_use.id in previewed_tool_use_ids:
                                    continue
                                previewed_tool_use_ids.add(tool_use.id)
                                yield ToolUseEvent(
                                    tool_use_id=tool_use.id,
                                    tool_name=tool_use.name,
                                    input=tool_use.input,
                                )

                        # Check for finish reason
                        choices = chunk.get("choices", [])
                        if choices:
                            finish_reason = choices[0].get("finish_reason")
                            if finish_reason:
                                stop_reason = finish_reason
                    else:
                        # Non-streaming response
                        choices = chunk.get("choices", [])
                        text, thinking, tool_uses, usage = (
                            self._client.parse_non_stream_response(chunk)
                        )
                        current_text = text
                        current_thinking = thinking
                        current_usage = usage
                        accumulated_tool_calls = []

                        # Convert tool uses to deltas
                        for tu in tool_uses:
                            accumulated_tool_calls.append(
                                ToolCallDelta(
                                    id=tu.id,
                                    name=tu.name,
                                    arguments=json.dumps(tu.input),
                                )
                            )

                        if thinking:
                            yield ThinkingEvent(thinking=thinking)

                        if text:
                            yield TextEvent(text=text)

                        if usage:
                            self.state.total_usage = usage

                        stop_reason = (
                            choices[0].get("finish_reason", "stop")
                            if choices
                            else "stop"
                        )

                # Build content blocks
                self._raise_if_interrupted()
                content_blocks: List[ContentBlock] = []

                if current_thinking:
                    content_blocks.append(ThinkingContent(thinking=current_thinking))

                if current_text:
                    content_blocks.append(TextContent(text=current_text))

                # Convert accumulated tool calls to content blocks
                tool_use_blocks = self._client.tool_calls_to_content_blocks(
                    accumulated_tool_calls
                )
                content_blocks.extend(tool_use_blocks)

                # Create assistant message
                assistant_message = Message.assistant_message(
                    content_blocks,
                    usage=current_usage,
                    stop_reason=stop_reason,
                )
                self.state.add_message(assistant_message)
                yield MessageCompleteEvent(message=assistant_message)

                # Check if we have tool calls to execute
                if not tool_use_blocks:
                    # No tool calls - we're done
                    yield TurnCompleteEvent(
                        turn=self.state.current_turn + 1,
                        has_more_turns=False,
                        stop_reason=stop_reason,
                    )
                    return

                # Execute tool calls
                logger.debug(f"Executing {len(tool_use_blocks)} tool calls")
                tool_results: List[tuple] = []

                for tool_use in tool_use_blocks:
                    self._raise_if_interrupted()
                    if not tool_use.id or not tool_use.name:
                        continue

                    # Emit tool use event
                    if tool_use.id not in previewed_tool_use_ids:
                        yield ToolUseEvent(
                            tool_use_id=tool_use.id,
                            tool_name=tool_use.name,
                            input=tool_use.input,
                        )

                    # Find and execute the tool
                    tool = self.tool_registry.get(tool_use.name)
                    if not tool:
                        error_msg = f"Tool not found: {tool_use.name}"
                        yield ToolResultEvent(
                            tool_use_id=tool_use.id,
                            result=error_msg,
                            is_error=True,
                        )
                        tool_results.append((tool_use.id, error_msg, True))
                        continue

                    try:
                        # Execute tool
                        result = await tool.call(
                            tool_use.input, self._get_tool_context()
                        )
                        is_error = tool.is_error_result(result, tool_use.input)
                        yield ToolResultEvent(
                            tool_use_id=tool_use.id,
                            result=result,
                            is_error=is_error,
                        )
                        tool_results.append((tool_use.id, result, is_error))
                    except Exception as e:
                        error_msg = f"Tool execution failed: {str(e)}"
                        yield ToolResultEvent(
                            tool_use_id=tool_use.id,
                            result=error_msg,
                            is_error=True,
                        )
                        tool_results.append((tool_use.id, error_msg, True))

                # Add tool result messages
                self._raise_if_interrupted()
                for tool_use_id, result, is_error in tool_results:
                    tool_msg = Message.tool_result_message(
                        tool_use_id, result, is_error
                    )
                    self.state.add_message(tool_msg)
                    yield MessageCompleteEvent(message=tool_msg)

                # Increment turn counter
                self.state.current_turn += 1

                # Check if we should continue
                has_more = self.state.current_turn < self.config.max_turns

                yield TurnCompleteEvent(
                    turn=self.state.current_turn,
                    has_more_turns=has_more,
                    stop_reason=stop_reason,
                )

                if not has_more:
                    logger.debug("Max turns reached, ending query")
                    return

            except asyncio.CancelledError:
                current_task = asyncio.current_task()
                if current_task in self._cancelled_tasks or self._interrupt_reason is not None:
                    return
                raise
            except APINetworkError as e:
                error_msg = f"Network error: {str(e)}"
                yield ErrorEvent(error=error_msg, is_fatal=True)
                return
            except APIError as e:
                error_msg = f"API error: {str(e)}"
                yield ErrorEvent(error=error_msg, is_fatal=True)
                return
            except Exception as e:
                error_msg = f"Query failed: {str(e)}"
                yield ErrorEvent(error=error_msg, is_fatal=True)
                return

            finally:
                self.state.is_streaming = False
                self.state.current_streaming_text = ""

    async def run(
        self,
        user_text: str,
        on_text: Optional[Callable[[str], None]] = None,
        on_tool_start: Optional[Callable[[str, str, Dict], None]] = None,
        on_tool_end: Optional[Callable[[str, str, bool], None]] = None,
        on_message: Optional[Callable[[Message], None]] = None,
        on_turn: Optional[Callable[[int, bool], None]] = None,
    ) -> QueryResult:
        """
        Run a query with optional callbacks.

        This is a convenience method that handles the event stream.
        """
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

        # Get final text from last assistant message
        for msg in reversed(self.state.messages):
            if msg.type == MessageRole.ASSISTANT:
                text = msg.get_text()
                if text:
                    result.text = text
                    break

        result.usage = self.state.total_usage

        return result


async def ask(
    prompt: str,
    client_config: OpenAIClientConfig,
    tool_registry: ToolRegistry,
    max_turns: int = 1000000,
    working_directory: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> QueryResult:
    """
    Convenience function for one-shot queries.

    Aligned with ask() in TypeScript QueryEngine.ts.
    """
    config = QueryConfig(
        max_turns=max_turns,
        system_prompt=system_prompt or "",
        working_directory=working_directory or os.getcwd(),
    )

    async with QueryEngine(client_config, tool_registry, config) as engine:
        return await engine.run(prompt)
