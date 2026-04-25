"""Core query engine and execution logic - aligned with TypeScript query.ts and QueryEngine.ts"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Any, AsyncGenerator, List, Optional

if TYPE_CHECKING:
    from cc_code.core.instruction import InstructionConfig, InstructionService
    from cc_code.core.snapshot import (
        DiffSummary,
        Patch,
        RevertResult,
        RevertState,
        SnapshotManager,
    )

from cc_code.core.messages import (
    ContentBlock,
    Message,
    MessageRole,
    SessionState,
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
from cc_code.core.tools import ToolContext, ToolRegistry
from cc_code.core.prompts import create_default_system_prompt
from cc_code.services.openai_client import (
    OpenAIClient,
    OpenAIClientConfig,
    ToolCallDelta,
    APIError,
)
from cc_code.utils.logging_config import log_full_exception

logger = logging.getLogger(__name__)


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

    _DEBUG_MAX_DEPTH = 3
    _DEBUG_MAX_ITEMS = 25
    _DEBUG_MAX_STRING_LENGTH = 4000

    def __init__(
        self,
        client_config: OpenAIClientConfig,
        tool_registry: ToolRegistry,
        working_directory: str = "",
        max_turns: Optional[int] = None,  # None for unlimited turns
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
        self.max_turns = max_turns

        # Mutable state
        self.state = SessionState()
        self.state.messages = list(initial_messages or [])
        self.state.current_turn = initial_current_turn
        self.state.total_usage = Usage(
            input_tokens=(initial_usage.input_tokens if initial_usage else 0),
            output_tokens=(initial_usage.output_tokens if initial_usage else 0),
        )
        self._client: Optional[OpenAIClient] = None
        self.state.session_id = session_id or generate_uuid()
        self.state.title = session_title or ""
        self.state.created_at = session_created_at or ""
        self._is_initialized = False
        self._interrupt_reason: Optional[str] = None
        self._active_task: Optional[asyncio.Task[Any]] = None
        self._cancelled_tasks: set[asyncio.Task[Any]] = set()
        self._cancel_event = asyncio.Event()

        # Working directory
        self._cwd = working_directory or os.getcwd()

        # Session store for persistence
        self._session_store = session_store

        # Snapshot system for file revert
        self._snapshot_manager: Optional["SnapshotManager"] = None
        self._current_snapshot: Optional[str] = None
        self._revert_state: Optional["RevertState"] = None
        self._total_diff: Optional["DiffSummary"] = None

        # Instruction service for loading CLAUDE.md, AGENTS.md, etc.
        self._instruction_service: Optional["InstructionService"] = None
        self._cached_instructions: Optional[List[str]] = None
        self._instruction_config: Optional["InstructionConfig"] = None

    @classmethod
    async def create_from_session_id(
        cls,
        session_id: Optional[str],
        client_config: OpenAIClientConfig,
        tool_registry: ToolRegistry,
        session_store: Any,
        working_directory: str = "",
        instruction_config: Optional["InstructionConfig"] = None,
    ) -> "QueryEngine":
        """Create a QueryEngine from a session ID, loading persisted state if exists.

        Args:
            session_id: Optional session ID to restore
            client_config: OpenAI client configuration
            tool_registry: Tool registry for tool execution
            session_store: Session persistence store
            working_directory: Working directory for the session
            instruction_config: Optional instruction configuration for CLAUDE.md/AGENTS.md loading
        """
        from cc_code.core.snapshot import DiffSummary

        persisted: Optional[SessionState] = None
        if session_id:
            persisted = session_store.load_session(session_id)

        engine = cls(
            client_config,
            tool_registry,
            working_directory=working_directory
            or (persisted.working_directory if persisted else ""),
            session_id=(persisted.session_id if persisted else session_id),
            initial_messages=list(persisted.messages) if persisted else None,
            initial_current_turn=persisted.current_turn if persisted else 0,
            initial_usage=persisted.total_usage if persisted else None,
            session_store=session_store,
            session_title=persisted.title if persisted else None,
            session_created_at=persisted.created_at if persisted else None,
        )

        # Set instruction config if provided
        if instruction_config:
            engine._instruction_config = instruction_config

        if persisted:
            revert = persisted.get_revert_state()
            if revert:
                engine._initial_revert_state = revert

            if persisted.total_diff_additions or persisted.total_diff_deletions or persisted.total_diff_files:
                engine._total_diff = DiffSummary(
                    additions=persisted.total_diff_additions,
                    deletions=persisted.total_diff_deletions,
                    files=persisted.total_diff_files,
                )

        await engine.initialize()
        if engine._snapshot_manager:
            engine.recalculate_total_diff()
        return engine

    async def initialize(self) -> None:
        """Initialize the engine (create HTTP client and instruction service)"""
        if not self._is_initialized:
            from cc_code.core.snapshot import (
                SnapshotManager,
                build_snapshot_project_id,
            )
            from cc_code.core.instruction import InstructionService

            self._client = OpenAIClient(self.client_config)
            # Isolate snapshot repos by session_id to prevent cross-session rewind.
            snapshot_project_id = build_snapshot_project_id(
                self._cwd,
                self.state.session_id,
            )
            self._snapshot_manager = SnapshotManager(
                self._cwd,
                project_id=snapshot_project_id,
            )
            self._instruction_service = InstructionService(self._instruction_config)
            if hasattr(self, "_initial_revert_state"):
                self._revert_state = self._initial_revert_state
                delattr(self, "_initial_revert_state")
            self._is_initialized = True

    async def close(self) -> None:
        """Close the engine and release resources"""
        if self._client:
            await self._client.close()
            self._client = None
        if self._instruction_service:
            await self._instruction_service.close()
            self._instruction_service = None
        self._is_initialized = False

    async def switch_model(self, client_config: OpenAIClientConfig) -> None:
        """Switch the active model configuration for the current session."""
        if self._client:
            await self._client.close()
            self._client = None

        self.client_config = client_config
        self._is_initialized = False
        await self.initialize()
        self.persist_session()

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
        return self.state.session_id

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

    def get_snapshot_manager(self) -> Optional[SnapshotManager]:
        """Get the snapshot manager"""
        return self._snapshot_manager

    def _truncate_debug_text(self, value: str, limit: Optional[int] = None) -> str:
        """Truncate debug text to keep payloads bounded."""
        max_length = limit or self._DEBUG_MAX_STRING_LENGTH
        if len(value) <= max_length:
            return value
        trimmed = len(value) - max_length
        return f"{value[:max_length]}... <truncated {trimmed} chars>"

    def _safe_debug_repr(self, value: Any) -> str:
        """Get a safe repr for arbitrary objects."""
        try:
            return repr(value)
        except Exception as exc:
            return f"<repr failed: {type(value).__name__}: {exc}>"

    def _serialize_debug_value(
        self,
        value: Any,
        *,
        depth: int = 0,
        seen: Optional[set[int]] = None,
    ) -> Any:
        """Convert arbitrary runtime values to JSON-friendly debug payloads."""
        if seen is None:
            seen = set()

        if value is None or isinstance(value, (bool, int, float)):
            return value

        if isinstance(value, str):
            return self._truncate_debug_text(value)

        if isinstance(value, (bytes, bytearray)):
            return {"type": type(value).__name__, "length": len(value)}

        if isinstance(value, asyncio.Event):
            return {"type": "Event", "is_set": value.is_set()}

        if isinstance(value, asyncio.Lock):
            return {"type": "Lock", "locked": value.locked()}

        if isinstance(value, asyncio.Task):
            return {
                "type": "Task",
                "done": value.done(),
                "cancelled": value.cancelled(),
                "repr": self._truncate_debug_text(
                    self._safe_debug_repr(value),
                    limit=500,
                ),
            }

        if depth >= self._DEBUG_MAX_DEPTH:
            return {
                "type": type(value).__name__,
                "repr": self._truncate_debug_text(
                    self._safe_debug_repr(value),
                    limit=500,
                ),
            }

        object_id = id(value)
        if object_id in seen:
            return {
                "type": type(value).__name__,
                "repr": "<recursive reference>",
            }
        seen.add(object_id)

        if isinstance(value, dict):
            serialized: dict[str, Any] = {}
            items = list(value.items())
            for idx, (key, item_value) in enumerate(items):
                if idx >= self._DEBUG_MAX_ITEMS:
                    serialized["..."] = f"{len(items) - self._DEBUG_MAX_ITEMS} more items"
                    break
                serialized[str(key)] = self._serialize_debug_value(
                    item_value,
                    depth=depth + 1,
                    seen=seen,
                )
            return {
                "type": "dict",
                "size": len(value),
                "items": serialized,
            }

        if isinstance(value, (list, tuple, set, frozenset)):
            values = list(value)
            serialized_items: list[Any] = []
            for idx, item in enumerate(values):
                if idx >= self._DEBUG_MAX_ITEMS:
                    serialized_items.append(
                        f"... {len(values) - self._DEBUG_MAX_ITEMS} more items"
                    )
                    break
                serialized_items.append(
                    self._serialize_debug_value(item, depth=depth + 1, seen=seen)
                )
            return {
                "type": type(value).__name__,
                "size": len(values),
                "items": serialized_items,
            }

        try:
            object_vars = vars(value)
        except TypeError:
            return {
                "type": type(value).__name__,
                "repr": self._truncate_debug_text(
                    self._safe_debug_repr(value),
                    limit=500,
                ),
            }

        serialized_attrs: dict[str, Any] = {}
        attr_names = sorted(object_vars.keys())
        for idx, attr_name in enumerate(attr_names):
            if idx >= self._DEBUG_MAX_ITEMS:
                serialized_attrs["..."] = (
                    f"{len(attr_names) - self._DEBUG_MAX_ITEMS} more attributes"
                )
                break
            serialized_attrs[attr_name] = self._serialize_debug_value(
                object_vars[attr_name],
                depth=depth + 1,
                seen=seen,
            )

        return {
            "type": type(value).__name__,
            "attributes": serialized_attrs,
            "repr": self._truncate_debug_text(
                self._safe_debug_repr(value),
                limit=500,
            ),
        }

    def get_debug_state(self) -> dict[str, Any]:
        """Return serialized runtime state for debugging."""
        members: dict[str, Any] = {}
        for name in sorted(vars(self).keys()):
            try:
                members[name] = self._serialize_debug_value(
                    getattr(self, name),
                    depth=0,
                    seen=set(),
                )
            except Exception as exc:
                members[name] = {
                    "type": type(getattr(self, name, None)).__name__,
                    "error": str(exc),
                }

        return {
            "class": self.__class__.__name__,
            "member_count": len(members),
            "members": members,
        }

    def _get_file_modifying_paths(self, tool_use_blocks: List[ContentBlock]) -> List[str]:
        """Collect candidate file paths from file-modifying tool calls."""
        paths: List[str] = []
        seen: set[str] = set()

        for tool_use in tool_use_blocks:
            if not hasattr(tool_use, "name") or tool_use.name not in ("Edit", "Write"):
                continue
            if not hasattr(tool_use, "input") or not isinstance(tool_use.input, dict):
                continue

            file_path = tool_use.input.get("file_path")
            if not isinstance(file_path, str) or not file_path.strip():
                continue

            normalized = file_path.strip()
            if normalized in seen:
                continue

            seen.add(normalized)
            paths.append(normalized)

        return paths

    def _collect_patch_file_paths(self, patches: List["Patch"]) -> List[str]:
        """Collect unique file paths from patches while preserving order."""
        paths: List[str] = []
        seen: set[str] = set()

        for patch in patches:
            for file_path in patch.files:
                if not file_path or file_path in seen:
                    continue
                seen.add(file_path)
                paths.append(file_path)

        return paths

    def _collect_patches(
        self,
        messages: List[Message],
        start_message_id: str,
        start_part_id: Optional[str] = None,
    ) -> List["Patch"]:
        """Collect all patches from messages after the revert point."""
        from cc_code.core.snapshot import Patch

        patches: List[Patch] = []
        found_start = False

        for message in messages:
            if message.uuid == start_message_id:
                found_start = True
                if start_part_id:
                    continue
                else:
                    patches = []
                    continue

            if not found_start:
                continue

            for content in message.content:
                if isinstance(content, PatchContent):
                    patches.append(
                        Patch(
                            hash=content.hash,
                            prev_hash=content.prev_hash,
                            files=content.files,
                        )
                    )
        return patches

    def _find_revert_point(
        self,
        messages: List[Message],
        target_message_id: Optional[str] = None,
        target_part_id: Optional[str] = None,
    ) -> Optional["RevertState"]:
        """Find the revert point in message history."""
        from cc_code.core.snapshot import RevertState

        if not messages:
            return None

        if target_message_id:
            for message in messages:
                if message.uuid == target_message_id:
                    return RevertState(
                        message_id=target_message_id,
                        part_id=target_part_id,
                    )
            return None

        last_user_message_id: Optional[str] = None
        for message in reversed(messages):
            if message.type == MessageRole.USER:
                last_user_message_id = message.uuid
                break

        if last_user_message_id:
            return RevertState(message_id=last_user_message_id)

        return None

    async def revert(
        self,
        target_message_id: Optional[str] = None,
        target_part_id: Optional[str] = None,
    ) -> "RevertResult":
        """Revert file changes from the target point to the current state."""
        from cc_code.core.snapshot import DiffSummary, RevertResult

        if not self._snapshot_manager:
            return RevertResult(
                success=False,
                message="Snapshot manager not available",
            )

        messages = self.get_messages()

        revert_point = self._find_revert_point(
            messages, target_message_id, target_part_id
        )
        if not revert_point:
            return RevertResult(
                success=False,
                message="Could not find revert point",
            )

        existing_revert = self.get_revert_state()
        if existing_revert:
            if existing_revert.snapshot:
                self._snapshot_manager.restore(existing_revert.snapshot)

        patches = self._collect_patches(
            messages,
            revert_point.message_id,
            revert_point.part_id,
        )
        candidate_files = self._collect_patch_file_paths(patches)

        current_snapshot: Optional[str] = None
        if candidate_files:
            current_snapshot = self._snapshot_manager.track(candidate_files)
            revert_point.snapshot = current_snapshot

        earliest_prev_hash = ""
        if patches:
            earliest_prev_hash = patches[0].prev_hash
            if current_snapshot:
                diff = self._snapshot_manager.diff(earliest_prev_hash, current_snapshot)
            else:
                latest_hash = patches[-1].hash
                diff = self._snapshot_manager.diff(earliest_prev_hash, latest_hash)
            revert_point.diff = diff
            self._snapshot_manager.restore(earliest_prev_hash)
        else:
            revert_point.diff = DiffSummary()

        removed_count = self.truncate_messages_to(revert_point.message_id)
        self.recalculate_total_diff()
        self.set_revert_state(revert_point)
        self.persist_session()

        return RevertResult(
            success=True,
            message=f"Reverted changes from {len(patches)} tool operations, removed {removed_count} messages",
            revert_state=revert_point,
            summary=revert_point.diff,
        )

    def get_total_diff(self) -> Optional[DiffSummary]:
        """Get the total diff accumulated from all AI tool operations"""
        return self._total_diff

    def recalculate_total_diff(self) -> None:
        """Recalculate total_diff from all PatchContent in messages."""
        from cc_code.core.snapshot import DiffSummary

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

    def _get_tool_context(self, message_id: Optional[str] = None) -> ToolContext:
        """Get tool execution context"""
        return ToolContext(
            working_directory=self._cwd,
            project_root=self._cwd,
            session_id=self.state.session_id,
            cancel_event=self._cancel_event,
            instruction_service=self._instruction_service,
            message_id=message_id,
            messages=self.state.messages,
        )

    async def _load_instructions(self) -> List[str]:
        """Load instructions from CLAUDE.md, AGENTS.md, etc.

        Instructions are cached after first load to avoid repeated file I/O.
        """
        if self._cached_instructions is not None:
            return self._cached_instructions

        if self._instruction_service is None:
            return []

        try:
            self._cached_instructions = (
                await self._instruction_service.get_system_instructions(self._cwd)
            )
            return self._cached_instructions
        except Exception as e:
            logger.warning(f"Failed to load instructions: {e}")
            return []

    async def _load_skills_listing(self) -> Optional[str]:
        """Load and format the skills listing for the system prompt.

        Cached after first load to avoid repeated directory scanning.
        """
        if hasattr(self, "_cached_skills_listing") and self._cached_skills_listing is not None:
            return self._cached_skills_listing

        try:
            from cc_code.skills.loader import (
                get_skill_tool_commands,
                format_commands_within_budget,
            )

            skill_commands = await get_skill_tool_commands(self._cwd)
            if skill_commands:
                self._cached_skills_listing = format_commands_within_budget(skill_commands)
                return self._cached_skills_listing
        except Exception as e:
            logger.warning(f"Failed to load skills listing: {e}")

        self._cached_skills_listing = None
        return None

    async def _build_system_prompt(self) -> str:
        """Build the system prompt with instructions from CLAUDE.md, AGENTS.md, etc."""
        # Load instructions from CLAUDE.md, AGENTS.md, etc.
        instructions = await self._load_instructions()

        # Load skills listing
        skills_listing = await self._load_skills_listing()

        # Build system prompt with instructions, skills, and tool prompts
        return create_default_system_prompt(
            cwd=self._cwd,
            model_name=self.client_config.model_name,
            instructions=instructions if instructions else None,
            skills_listing=skills_listing,
            tool_prompts=self.tool_registry.get_tool_prompts(),
        )

    def _filter_compacted_messages(self) -> List[Message]:
        """Filter messages to only include those after the last successful compaction summary.

        This aligns with TypeScript MessageV2.filterCompacted():
        - Iterates through messages and adds them to result
        - When a successful summary is found (summary=true, finish set, no error),
          marks its parent message ID as "completed"
        - When encountering a user message that triggered a completed compaction, stops
        - Returns messages from the compaction boundary onwards

        Returns:
            List of messages that should be sent to the model
        """
        messages = self.state.messages
        if not messages:
            return messages

        # Find completed compaction boundaries
        # A successful summary has: is_compact_summary=True, has finish reason, no error
        completed_parent_ids = set()

        # First pass: find all completed compaction summaries
        for msg in messages:
            if (
                msg.type == MessageRole.ASSISTANT
                and msg.is_compact_summary
                and msg.stop_reason
                and not msg.stop_reason.startswith("error")
            ):
                # This summary completed successfully
                if msg.parent_id:
                    completed_parent_ids.add(msg.parent_id)

        if not completed_parent_ids:
            # No compaction done, return all messages
            return messages

        # Second pass: filter messages
        # Include messages from the last compaction boundary onwards
        # The summary message itself should be included
        result = []
        for msg in messages:
            # Check if this is a user message that triggered a completed compaction
            if msg.type == MessageRole.USER and msg.uuid in completed_parent_ids:
                # Start from the next message (which is the summary)
                result = []  # Clear previous messages
                continue
            result.append(msg)

        return result

    def clear(self) -> None:
        """Clear the query state and reset to a new session.

        This effectively starts a fresh conversation with a new session_id,
        as if the user had started a new TUI session.
        """
        self.state.clear()
        self.clear_interrupt()

        # Clear skills listing cache so new skills are discovered
        if hasattr(self, "_cached_skills_listing"):
            del self._cached_skills_listing

        # Clear skill caches
        try:
            from cc_code.skills.loader import clear_skill_caches
            clear_skill_caches()
        except Exception:
            pass

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
        """Persist session to disk."""
        if self._session_store is None:
            return

        # Don't save empty sessions (no user messages)
        if not self.state.messages:
            logger.debug("Skipping session persistence - no messages")
            return

        # Check if there's at least one user message
        has_user_message = any(
            msg.type == MessageRole.USER and not msg.is_meta
            for msg in self.state.messages
        )
        if not has_user_message:
            logger.debug("Skipping session persistence - no user messages")
            return

        try:
            from cc_code.core.session_store import RevertStateData, derive_session_title

            # Derive title if not set
            if not self.state.title:
                self.state.title = derive_session_title(
                    self.state.messages, self.state.session_id
                )

            # Update state metadata
            self.state.working_directory = self._cwd
            self.state.model_id = self.client_config.model_id
            self.state.model_name = self.client_config.model_name
            
            # Keep persisted state aligned with current runtime state.
            self.state.set_revert_state(self._revert_state)

            if self._total_diff:
                self.state.total_diff_additions = self._total_diff.additions
                self.state.total_diff_deletions = self._total_diff.deletions
                self.state.total_diff_files = self._total_diff.files
            else:
                self.state.total_diff_additions = 0
                self.state.total_diff_deletions = 0
                self.state.total_diff_files = 0

            revert_data = None
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
                    files=self._revert_state.diff.files if self._revert_state.diff else 0,
                )

            total_diff = {
                "additions": self.state.total_diff_additions,
                "deletions": self.state.total_diff_deletions,
                "files": self.state.total_diff_files,
            }

            session = self._session_store.save_snapshot(
                session_id=self.state.session_id,
                messages=list(self.state.messages),
                working_directory=self._cwd,
                current_turn=self.state.current_turn,
                title=self.state.title,
                created_at=self.state.created_at,
                model_id=self.client_config.model_id,
                model_name=self.client_config.model_name,
                total_usage=self.state.total_usage,
                revert_state=revert_data,
                total_diff=total_diff,
            )
            # Update state with any derived values from save
            self.state.title = session.title
            self.state.created_at = session.created_at
            logger.debug(
                f"Persisted session {self.state.session_id}: {len(self.state.messages)} messages"
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

            # Check for /compact command
            user_text_lower = user_text.strip().lower()
            if user_text_lower in ("/compact", "/summarize"):
                async for event in self._handle_compact():
                    yield event
                return

            from cc_code.core.file_expansion import (
                expand_file_references,
                has_web_reference,
            )

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
                        f"Replaced rewound user message - session_id={self.state.session_id}"
                    )
                    # Clear revert state since user has submitted a new message
                    self.set_revert_state(None)
                else:
                    self.state.add_message(user_message)
                    logger.info(
                        f"User message created - session_id={self.state.session_id}, web_enabled={web_enabled}"
                    )
            else:
                self.state.add_message(user_message)
                logger.info(
                    f"User message created - session_id={self.state.session_id}, web_enabled={web_enabled}"
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
                self.persist_session()
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

    async def _handle_compact(self) -> AsyncGenerator[QueryEvent, None]:
        """Handle /compact command to generate streaming summary of conversation.

        Aligns with opencode principle:
        1. Build messages for summary generation
        2. Stream the summary as assistant message
        3. KEEP ALL HISTORY MESSAGES, just add the summary marked as is_compact_summary
        """
        from cc_code.core.compaction import (
            SessionCompaction,
        )

        if not self._is_initialized or not self._client:
            raise RuntimeError("QueryEngine not initialized. Call initialize() first.")

        # Get messages to compact BEFORE adding the /compact user message
        original_messages = list(self.state.messages)

        # Create user message for the compaction request
        user_message = Message.user_message("/compact")
        user_message.is_meta = True  # Mark as meta so it doesn't affect compaction
        self.state.add_message(user_message)
        yield MessageCompleteEvent(message=user_message)

        # Get messages to compact (from original, not including /compact)
        compaction = SessionCompaction(
            messages=original_messages,
            model_name=self.client_config.model_name,
            context_window=None,  # Will be fetched from settings if needed
        )

        # Build messages for summary generation (already in API format)
        history_messages = compaction.build_messages_for_summary(
            strip_tool_results=True,
            max_messages=50,
        )

        if not history_messages:
            error_msg = Message.system_message("No messages to compact")
            yield MessageCompleteEvent(message=error_msg)
            return

        # Create the summary request
        prompt = compaction.create_compaction_prompt()

        # Build OpenAI format messages - history_messages are already dicts
        openai_messages = list(history_messages)

        # Add the summary request
        openai_messages.append({"role": "user", "content": prompt})

        # Create assistant message for streaming
        assistant_message = Message.assistant_message(content=[])
        assistant_message.is_compact_summary = True
        # Store parent_id for filtering (the user message that triggered compaction)
        assistant_message.parent_id = user_message.uuid

        # Stream the summary using raw API call
        current_text = ""
        current_usage: Optional[Usage] = None

        try:
            # Use the raw chat completion method for streaming
            request_params = {
                "model": self.client_config.model_name,
                "messages": openai_messages,
                "max_tokens": 2000,  # Reasonable limit for summary
                "temperature": 0.3,  # Lower temperature for more focused summary
                "stream": True,
                "stream_options": {"include_usage": True},
            }

            stream_response = await self._client._client.chat.completions.create(
                **request_params
            )

            async for chunk in stream_response:
                self._raise_if_interrupted()

                chunk_dict = chunk.model_dump()

                # Extract usage if available
                extract_usage = getattr(self._client, "extract_usage", None)
                chunk_usage = (
                    extract_usage(chunk_dict) if callable(extract_usage) else None
                )
                if chunk_usage:
                    current_usage = chunk_usage
                    self.state.total_usage = chunk_usage

                # Parse streaming chunk
                text_delta, _, _ = self._client.parse_stream_chunk(chunk_dict)

                if text_delta:
                    current_text += text_delta
                    yield TextEvent(text=text_delta)

            # Update the assistant message with the final text
            assistant_message.content = [TextContent(text=current_text)]
            # Set stop_reason to mark this as a completed summary (for filtering)
            assistant_message.stop_reason = "stop"

            # Attach usage to the message so UI can refresh context info
            if current_usage:
                assistant_message.usage = current_usage

            # Align with opencode: KEEP ALL HISTORY, just add the summary message
            # The summary is marked with is_compact_summary = True for filtering
            self.state.add_message(assistant_message)

            # Calculate tokens saved (for logging only)
            summary_tokens = compaction.estimate_tokens(current_text)

            logger.info(
                f"Compaction complete: summary generated ({summary_tokens} tokens), "
                f"history preserved ({len(original_messages)} messages)"
            )

            # Update total usage
            if current_usage:
                self.state.total_usage.input_tokens = current_usage.input_tokens
                self.state.total_usage.output_tokens = current_usage.output_tokens

            yield MessageCompleteEvent(message=assistant_message)

            # Persist the session
            self.persist_session()

            yield TurnCompleteEvent(
                turn=self.state.current_turn,
                has_more_turns=False,
                stop_reason="stop",
            )

        except asyncio.CancelledError:
            raise
        except Exception as e:
            log_full_exception(logger, "Error during compaction", e)
            yield ErrorEvent(error=f"Compaction failed: {str(e)}", is_fatal=True)

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

        system_prompt = await self._build_system_prompt()

        while self.max_turns is None or self.state.current_turn < self.max_turns:
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

                # Filter compacted messages - only send messages after the last summary
                filtered_messages = self._filter_compacted_messages()

                async for chunk in self._client.chat_completion(
                    filtered_messages,  # Use filtered messages, not all messages
                    self.tool_registry,
                    stream=True,
                    system_prompt=system_prompt,
                ):
                    self._raise_if_interrupted()
                    extract_final_reasoning = getattr(
                        self._client, "extract_final_message_reasoning", None
                    )
                    final_reasoning = (
                        extract_final_reasoning(chunk)
                        if callable(extract_final_reasoning)
                        else ""
                    )
                    if final_reasoning:
                        if not current_thinking:
                            current_thinking = final_reasoning
                            yield ThinkingEvent(thinking=final_reasoning)
                        elif (
                            len(final_reasoning) > len(current_thinking)
                            and final_reasoning.startswith(current_thinking)
                        ):
                            missing_suffix = final_reasoning[len(current_thinking) :]
                            current_thinking = final_reasoning
                            if missing_suffix:
                                yield ThinkingEvent(thinking=missing_suffix)

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
                            self._client.tool_calls_to_content_blocks(
                                accumulated_tool_calls,
                                allow_partial=True,
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
                        self.persist_session()
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
                tool_results: List[
                    tuple
                ] = []  # (tool_use_id, result, is_error, metadata)

                # Track snapshots for file-modifying tools
                step_snapshot: Optional[str] = None
                has_file_modifying_tools = any(
                    tool_use.name in ("Edit", "Write")
                    for tool_use in tool_use_blocks
                    if tool_use.name
                )
                candidate_files = self._get_file_modifying_paths(tool_use_blocks)
                if has_file_modifying_tools and self._snapshot_manager:
                    try:
                        if candidate_files:
                            step_snapshot = self._snapshot_manager.track(candidate_files)
                            logger.debug(f"Created step snapshot: {step_snapshot[:8]}")
                        else:
                            logger.warning(
                                "Skipping snapshot for file-modifying tools because no candidate files were found"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to create step snapshot: {e}")

                # Get assistant message ID for nearby instruction loading
                assistant_message_id = assistant_message.uuid

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
                        tool_results.append((tool_use.id, error_msg, True, None))
                        continue

                    try:
                        # Execute tool with message ID for nearby instruction loading
                        result = await tool.call(
                            tool_use.input, self._get_tool_context(assistant_message_id)
                        )
                        
                        # Handle structured tool results (e.g., Read tool with metadata)
                        metadata = None
                        if isinstance(result, dict) and "content" in result:
                            # Structured result with metadata
                            metadata = result.get("metadata")
                            is_error = tool.is_error_result(result["content"], tool_use.input)
                            result_str = result["content"]
                        else:
                            # Simple string result
                            result_str = result
                            is_error = tool.is_error_result(result_str, tool_use.input)

                        yield ToolResultEvent(
                            tool_use_id=tool_use.id,
                            result=result_str,
                            is_error=is_error,
                        )
                        tool_results.append((tool_use.id, result_str, is_error, metadata))
                    except Exception as e:
                        error_msg = f"Tool execution failed: {str(e)}"
                        yield ToolResultEvent(
                            tool_use_id=tool_use.id,
                            result=error_msg,
                            is_error=True,
                        )
                        tool_results.append((tool_use.id, error_msg, True, None))

                # Create patch after tool execution if we had a snapshot
                if step_snapshot and self._snapshot_manager:
                    from cc_code.core.snapshot import DiffSummary

                    try:
                        patch = self._snapshot_manager.patch(
                            step_snapshot,
                            candidate_files=candidate_files,
                        )
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
                for tool_use_id, result, is_error, metadata in tool_results:
                    tool_msg = Message.tool_result_message(
                        tool_use_id, result, is_error, metadata
                    )
                    self.state.add_message(tool_msg)
                    yield MessageCompleteEvent(message=tool_msg)

                # Increment turn counter
                self.state.current_turn += 1

                # Check if we should continue
                has_more = (
                    self.max_turns is None
                    or self.state.current_turn < self.max_turns
                )

                # Persist session when stop_reason is 'stop'
                if stop_reason == "stop":
                    self.persist_session()

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
                self.persist_session()
                logger.info(f"saved session due to API error: {error_msg}")
                yield ErrorEvent(error=error_msg, is_fatal=True)
                return
            except Exception as e:
                log_full_exception(logger, "Unexpected error in query loop", e)
                error_msg = f"Query failed: {str(e)}"
                self.persist_session()
                logger.info(f"saved session due to Unexpected error: {error_msg}")
                yield ErrorEvent(error=error_msg, is_fatal=True)
                return

            finally:
                self.state.is_streaming = False
                self.state.current_streaming_text = ""
