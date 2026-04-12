"""Core query engine and execution logic - aligned with TypeScript query.ts and QueryEngine.ts"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, AsyncGenerator, List, Optional

from claude_code.core.messages import (
    ContentBlock,
    Message,
    MessageRole,
    QueryState,
    QueryEvent,
    TextContent,
    ThinkingContent,
    Usage,
    TextEvent,
    ThinkingEvent,
    ToolUseEvent,
    ToolResultEvent,
    MessageCompleteEvent,
    TurnCompleteEvent,
    ErrorEvent,
    PatchContent,
    generate_uuid,
)
from claude_code.core.tools import ToolContext, ToolRegistry
from claude_code.core.prompts import create_default_system_prompt
from claude_code.core.file_expansion import expand_file_references
from claude_code.core.snapshot import SnapshotManager, DiffSummary
from claude_code.core.revert import RevertState, SessionRevertService
from claude_code.services.openai_client import (
    OpenAIClient,
    OpenAIClientConfig,
    ToolCallDelta,
    APIError,
)
from claude_code.utils.logging_config import log_full_exception

logger = logging.getLogger(__name__)


@dataclass
class QueryConfig:
    """Configuration for the query engine"""

    max_turns: int = 1000000
    stream: bool = True
    system_prompt: str = ""
    working_directory: str = ""


class QueryEngine:
    """
    Core query engine that handles the conversation loop.

    Aligned with TypeScript QueryEngine class in QueryEngine.ts.
    One QueryEngine per conversation. Each submit_message() call starts a new
    turn within the same conversation. State (messages, usage, etc.) persists
    across turns.

    State management:
    - Captures snapshot before processing user request
    - Rolls back to snapshot on interrupt
    - Persists to disk when stop_reason is 'stop'
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
        session_store: Optional[Any] = None,
        session_title: Optional[str] = None,
        session_created_at: Optional[str] = None,
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

        # Working directory
        self._cwd = self.config.working_directory or os.getcwd()

        # Session store for persistence
        self._session_store = session_store

        # Session metadata
        self._session_title = session_title
        self._session_created_at = session_created_at

        # Snapshot system for file revert
        self._snapshot_manager: Optional[SnapshotManager] = None
        self._current_snapshot: Optional[str] = None
        self._revert_state: Optional[RevertState] = None
        self._revert_service: Optional[SessionRevertService] = None
        self._total_diff: Optional[DiffSummary] = None

    @classmethod
    async def create_from_session_id(
        cls,
        session_id: Optional[str],
        client_config: OpenAIClientConfig,
        tool_registry: ToolRegistry,
        session_store: Any,
        working_directory: str = "",
    ) -> "QueryEngine":
        """Create a QueryEngine from a session ID, loading persisted state if exists."""
        from claude_code.core.session_store import PersistedSession

        persisted: Optional[PersistedSession] = None
        if session_id:
            persisted = session_store.load_session(session_id)

        config = QueryConfig(
            stream=True,
            working_directory=working_directory
            or (persisted.working_directory if persisted else ""),
        )

        engine = cls(
            client_config,
            tool_registry,
            config,
            session_id=(persisted.session_id if persisted else session_id),
            initial_messages=list(persisted.messages) if persisted else None,
            initial_current_turn=persisted.current_turn if persisted else 0,
            initial_usage=persisted.total_usage if persisted else None,
            session_store=session_store,
            session_title=persisted.title if persisted else None,
            session_created_at=persisted.created_at if persisted else None,
        )

        if persisted and persisted.revert_state:
            from claude_code.core.snapshot import DiffSummary

            engine._initial_revert_state = RevertState(
                message_id=persisted.revert_state.message_id,
                part_id=persisted.revert_state.part_id,
                snapshot=persisted.revert_state.snapshot,
                diff=DiffSummary(
                    additions=persisted.revert_state.additions,
                    deletions=persisted.revert_state.deletions,
                    files=persisted.revert_state.files,
                ),
            )

        if persisted and persisted.total_diff:
            engine._total_diff = DiffSummary(
                additions=persisted.total_diff.get("additions", 0),
                deletions=persisted.total_diff.get("deletions", 0),
                files=persisted.total_diff.get("files", 0),
            )

        await engine.initialize()
        if engine._snapshot_manager:
            engine.recalculate_total_diff()
        return engine

    async def initialize(self) -> None:
        """Initialize the engine (create HTTP client)"""
        if not self._is_initialized:
            self._client = OpenAIClient(self.client_config)
            self._snapshot_manager = SnapshotManager(self._cwd)
            self._revert_service = SessionRevertService(self._snapshot_manager)
            if hasattr(self, "_initial_revert_state"):
                self._revert_state = self._initial_revert_state
                delattr(self, "_initial_revert_state")
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

    def truncate_messages_to(self, message_id: str) -> int:
        """Truncate messages list to exclude messages after the given message_id.

        Returns the number of messages removed.
        """
        truncate_idx = None
        for idx, msg in enumerate(self.state.messages):
            if msg.uuid == message_id:
                truncate_idx = idx + 1
                break

        if truncate_idx is not None and truncate_idx < len(self.state.messages):
            removed_count = len(self.state.messages) - truncate_idx
            self.state.messages = self.state.messages[:truncate_idx]
            return removed_count
        return 0

    def get_revert_state(self) -> Optional[RevertState]:
        """Get the current revert state"""
        return self._revert_state

    def set_revert_state(self, state: Optional[RevertState]) -> None:
        """Set the revert state"""
        self._revert_state = state

    def clear_revert_state(self) -> None:
        """Clear the revert state"""
        self._revert_state = None

    def get_snapshot_manager(self) -> Optional[SnapshotManager]:
        """Get the snapshot manager"""
        return self._snapshot_manager

    def get_revert_service(self) -> Optional[SessionRevertService]:
        """Get the revert service"""
        return self._revert_service

    def get_total_diff(self) -> Optional[DiffSummary]:
        """Get the total diff accumulated from all AI tool operations"""
        return self._total_diff

    def recalculate_total_diff(self) -> None:
        """Recalculate total_diff from all PatchContent in messages."""
        if not self._snapshot_manager:
            return
        additions = 0
        deletions = 0
        all_file_paths: set = set()
        for message in self.state.messages:
            for content in message.content:
                if isinstance(content, PatchContent):
                    if content.prev_hash and content.hash:
                        patch_diff = self._snapshot_manager.diff(
                            content.prev_hash, content.hash
                        )
                        additions += patch_diff.additions
                        deletions += patch_diff.deletions
                        all_file_paths.update(patch_diff.file_paths)
        self._total_diff = DiffSummary(
            additions=additions,
            deletions=deletions,
            files=len(all_file_paths),
            file_paths=all_file_paths,
        )

    def _get_tool_context(self) -> ToolContext:
        """Get tool execution context"""
        return ToolContext(
            working_directory=self._cwd,
            project_root=self._cwd,
            session_id=self._session_id,
            cancel_event=self._cancel_event,
        )

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
        """Clear the query state and reset to a new session.

        This effectively starts a fresh conversation with a new session_id,
        as if the user had started a new TUI session.
        """
        self.state.clear()
        self.clear_interrupt()
        # Reset to a new session ID
        self._session_id = generate_uuid()
        self.state.session_id = self._session_id

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

    def persist_session(self) -> None:
        """Persist session to disk. Public method for external callers."""
        self._persist_session()

    def _persist_session(self) -> None:
        """Persist session to disk."""
        if self._session_store is None:
            return

        try:
            from claude_code.core.session_store import (
                derive_session_title,
                RevertStateData,
            )

            self._session_title = self._session_title or derive_session_title(
                self.state.messages, self._session_id
            )

            revert_data: Optional[RevertStateData] = None
            if self._revert_state:
                revert_data = RevertStateData(
                    message_id=self._revert_state.message_id,
                    part_id=self._revert_state.part_id,
                    snapshot=self._revert_state.snapshot,
                    additions=self._revert_state.diff.additions
                    if self._revert_state.diff
                    else 0,
                    deletions=self._revert_state.diff.deletions
                    if self._revert_state.diff
                    else 0,
                    files=self._revert_state.diff.files
                    if self._revert_state.diff
                    else 0,
                )

            session = self._session_store.save_snapshot(
                session_id=self._session_id,
                messages=list(self.state.messages),
                working_directory=self._cwd,
                current_turn=self.state.current_turn,
                title=self._session_title,
                created_at=self._session_created_at,
                model_name=self.client_config.model_name,
                total_usage=self.state.total_usage,
                revert_state=revert_data,
                total_diff={
                    "additions": self._total_diff.additions if self._total_diff else 0,
                    "deletions": self._total_diff.deletions if self._total_diff else 0,
                    "files": self._total_diff.files if self._total_diff else 0,
                }
                if self._total_diff
                else None,
            )
            self._session_title = session.title
            self._session_created_at = session.created_at
            logger.debug(
                f"Persisted session {self._session_id}: {len(self.state.messages)} messages"
            )
        except Exception as e:
            logger.warning(f"Failed to persist session: {e}")

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

            from claude_code.core.file_expansion import has_web_reference

            # Expand @file_path references
            expanded_text, file_expansions = expand_file_references(
                user_text, self._cwd
            )

            # Check for @web reference
            web_enabled = has_web_reference(user_text)

            # Create and add user message with file expansion info and web flag
            user_message = Message.user_message(
                text=expanded_text,
                file_expansions=file_expansions,
                original_text=user_text,
                web_enabled=web_enabled,
            )

            # Check if we're in a rewind state - replace last message instead of appending
            if self._revert_state and self.state.messages:
                last_msg = self.state.messages[-1]
                if (
                    last_msg.type == MessageRole.USER
                    and last_msg.uuid == self._revert_state.message_id
                ):
                    # Replace the last user message (rewound message) with the new one
                    user_message.uuid = (
                        last_msg.uuid
                    )  # Keep the same UUID for consistency
                    self.state.messages[-1] = user_message
                    logger.info(
                        f"Replaced rewound user message - session_id={self._session_id}"
                    )
                    # Clear revert state since user has submitted a new message
                    self.clear_revert_state()
                else:
                    self.state.add_message(user_message)
                    logger.info(
                        f"User message created - session_id={self._session_id}, web_enabled={web_enabled}"
                    )
            else:
                self.state.add_message(user_message)
                logger.info(
                    f"User message created - session_id={self._session_id}, web_enabled={web_enabled}"
                )

            yield MessageCompleteEvent(message=user_message)

            # Run the query loop
            async for event in self._query_loop():
                yield event
        except asyncio.CancelledError:
            current_task = asyncio.current_task()
            if (
                current_task in self._cancelled_tasks
                or self._interrupt_reason is not None
            ):
                if current_task in self._cancelled_tasks:
                    self._cancelled_tasks.discard(current_task)
                self._persist_session()
                self.clear_interrupt()
                return
            raise
        except Exception as e:
            log_full_exception(logger, "Unexpected error in submit_message", e)
            error_msg = f"Error processing message: {str(e)}"
            yield ErrorEvent(error=error_msg, is_fatal=True)
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
                                logger.debug(
                                    f"Previewing partial tool use: tool_use.name={tool_use.name}, tool_use.id={tool_use.id}, tool_use.input: {tool_use.input}"
                                )
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
                    # Persist session when stop_reason is 'stop'
                    if stop_reason == "stop":
                        self._persist_session()
                    yield TurnCompleteEvent(
                        turn=self.state.current_turn + 1,
                        has_more_turns=False,
                        stop_reason=stop_reason,
                    )
                    return

                # Execute tool calls
                tool_calls_info = []
                for tool_use in tool_use_blocks:
                    input_str = str(tool_use.input)
                    truncated = (
                        input_str[:50] + "..." if len(input_str) > 50 else input_str
                    )
                    tool_calls_info.append(f"{tool_use.name}({truncated})")
                logger.info(
                    f"Executing {len(tool_use_blocks)} tool calls: {tool_calls_info}"
                )
                tool_results: List[tuple] = []

                # Track snapshots for file-modifying tools
                step_snapshot: Optional[str] = None
                has_file_modifying_tools = any(
                    tool_use.name in ("Edit", "Write")
                    for tool_use in tool_use_blocks
                    if tool_use.name
                )
                if has_file_modifying_tools and self._snapshot_manager:
                    try:
                        step_snapshot = self._snapshot_manager.track()
                        logger.debug(f"Created step snapshot: {step_snapshot[:8]}")
                    except Exception as e:
                        logger.warning(f"Failed to create step snapshot: {e}")

                for tool_use in tool_use_blocks:
                    self._raise_if_interrupted()
                    if not tool_use.id or not tool_use.name:
                        continue

                    # Emit tool use event (always send to update potentially incomplete preview)
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

                # Create patch after tool execution if we had a snapshot
                if step_snapshot and self._snapshot_manager:
                    try:
                        patch = self._snapshot_manager.patch(step_snapshot)
                        if patch.files:
                            patch_content = PatchContent(
                                prev_hash=step_snapshot,
                                hash=patch.hash,
                                files=patch.files,
                            )
                            logger.info(
                                f"Created patch: prev={step_snapshot[:8]} -> {patch.hash[:8]} with {len(patch.files)} files"
                            )
                            # Attach patch to the last assistant message
                            if self.state.messages:
                                last_msg = self.state.messages[-1]
                                if last_msg.type.value == "assistant":
                                    last_msg.content.append(patch_content)

                            # Accumulate diff to total_diff
                            patch_diff = self._snapshot_manager.diff(
                                step_snapshot, patch.hash
                            )
                            if self._total_diff is None:
                                self._total_diff = DiffSummary()
                            self._total_diff.additions += patch_diff.additions
                            self._total_diff.deletions += patch_diff.deletions
                            self._total_diff.file_paths.update(patch_diff.file_paths)
                            self._total_diff.files = len(self._total_diff.file_paths)
                    except Exception as e:
                        logger.warning(f"Failed to create patch: {e}")

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

                # Persist session when stop_reason is 'stop'
                if stop_reason == "stop":
                    self._persist_session()

                yield TurnCompleteEvent(
                    turn=self.state.current_turn,
                    has_more_turns=has_more,
                    stop_reason=stop_reason,
                )

                if not has_more:
                    logger.debug("Max turns reached, ending query")
                    return

            except asyncio.CancelledError:
                # raise to outer handler
                raise
            except APIError as e:
                error_msg = f"API error: {str(e)}"
                self._persist_session()
                logger.info(f"saved session due to API error: {error_msg}")
                yield ErrorEvent(error=error_msg, is_fatal=True)
                return
            except Exception as e:
                log_full_exception(logger, "Unexpected error in query loop", e)
                error_msg = f"Query failed: {str(e)}"
                self._persist_session()
                logger.info(f"saved session due to Unexpected error: {error_msg}")
                yield ErrorEvent(error=error_msg, is_fatal=True)
                return

            finally:
                self.state.is_streaming = False
                self.state.current_streaming_text = ""
