"""Session revert service - aligned with OpenCode session/revert.ts

This module provides revert and unrevert functionality for file changes
made during AI tool execution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional

from claude_code.core.messages import (
    Message,
    MessageRole,
    PatchContent,
)
from claude_code.core.snapshot import DiffSummary, Patch, SnapshotManager

if TYPE_CHECKING:
    from claude_code.core.query_engine import QueryEngine

logger = logging.getLogger(__name__)


@dataclass
class RevertState:
    """State tracking for a revert operation"""

    message_id: str  # Message ID where revert started
    part_id: Optional[str] = None  # Specific part ID (if reverting partial message)
    snapshot: Optional[str] = None  # Snapshot hash before revert (for unrevert)
    diff: Optional[DiffSummary] = None  # Diff summary of reverted changes


@dataclass
class RevertResult:
    """Result of a revert or unrevert operation"""

    success: bool
    message: str
    revert_state: Optional[RevertState] = None
    summary: Optional[DiffSummary] = None


class SessionRevertService:
    """Service for reverting and un-reverting file changes in a session.

    This service works with the snapshot system to provide undo/redo
    functionality for file changes made by AI tools.
    """

    def __init__(self, snapshot_manager: SnapshotManager):
        self.snapshot_manager = snapshot_manager

    def _collect_patches(
        self,
        messages: List[Message],
        start_message_id: str,
        start_part_id: Optional[str] = None,
    ) -> List[Patch]:
        """Collect all patches from messages after the revert point.

        Returns patches with both prev_hash (before changes) and hash (after changes).
        """
        patches: List[Patch] = []
        found_start = False

        logger.debug(
            f"_collect_patches: start_message_id={start_message_id}, "
            f"total_messages={len(messages)}"
        )

        for message in messages:
            if message.uuid == start_message_id:
                found_start = True
                logger.debug(f"Found start message at uuid={message.uuid[:8]}")
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
                    logger.debug(
                        f"Collected patch: prev={content.prev_hash[:8]}, "
                        f"hash={content.hash[:8]}, files={len(content.files)}"
                    )

        logger.debug(f"_collect_patches: collected {len(patches)} patches")
        return patches

    def _find_revert_point(
        self,
        messages: List[Message],
        target_message_id: Optional[str] = None,
        target_part_id: Optional[str] = None,
    ) -> Optional[RevertState]:
        """Find the revert point in message history.

        If target_message_id and target_part_id are provided, revert to that point.
        If only target_message_id is provided, revert to the beginning of that message.
        If neither is provided, revert the last message.
        """
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
        engine: "QueryEngine",
        target_message_id: Optional[str] = None,
        target_part_id: Optional[str] = None,
    ) -> RevertResult:
        """Revert file changes from the target point to the current state.

        Args:
            engine: The QueryEngine instance with session state
            target_message_id: Message ID to revert to (optional, defaults to last user message)
            target_part_id: Specific part ID to revert to (optional)

        Returns:
            RevertResult indicating success or failure
        """
        messages = engine.get_messages()

        revert_point = self._find_revert_point(
            messages, target_message_id, target_part_id
        )
        if not revert_point:
            return RevertResult(
                success=False,
                message="Could not find revert point",
            )

        existing_revert = engine.get_revert_state()
        if existing_revert:
            if existing_revert.snapshot:
                self.snapshot_manager.restore(existing_revert.snapshot)

        current_snapshot = self.snapshot_manager.track()
        revert_point.snapshot = current_snapshot

        patches = self._collect_patches(
            messages,
            revert_point.message_id,
            revert_point.part_id,
        )

        logger.debug(
            f"Total messages in engine: {len(messages)}, "
            f"message uuids: {[m.uuid[:8] for m in messages]}"
        )

        earliest_prev_hash = ""
        if patches:
            earliest_prev_hash = patches[0].prev_hash
            diff = self.snapshot_manager.diff(earliest_prev_hash, current_snapshot)
            revert_point.diff = diff
            self.snapshot_manager.restore(earliest_prev_hash)
        else:
            revert_point.diff = DiffSummary()

        removed_count = engine.truncate_messages_to(revert_point.message_id)

        engine.recalculate_total_diff()

        engine.set_revert_state(revert_point)
        engine.persist_session()

        logger.info(
            f"Reverted to snapshot {earliest_prev_hash[:8] if earliest_prev_hash else 'N/A'}, "
            f"removed {removed_count} messages, "
            f"diff: +{revert_point.diff.additions}/-{revert_point.diff.deletions} "
            f"in {revert_point.diff.files} files"
        )

        return RevertResult(
            success=True,
            message=f"Reverted changes from {len(patches)} tool operations, removed {removed_count} messages",
            revert_state=revert_point,
            summary=revert_point.diff,
        )

    async def unrevert(self, engine: "QueryEngine") -> RevertResult:
        """Undo a previous revert operation.

        Args:
            engine: The QueryEngine instance with session state

        Returns:
            RevertResult indicating success or failure
        """
        revert_state = engine.get_revert_state()
        if not revert_state:
            return RevertResult(
                success=False,
                message="No revert to undo",
            )

        if not revert_state.snapshot:
            engine.clear_revert_state()
            return RevertResult(
                success=True,
                message="Revert state cleared (no snapshot to restore)",
            )

        self.snapshot_manager.restore(revert_state.snapshot)
        engine.clear_revert_state()

        logger.info(f"Un-reverted to snapshot {revert_state.snapshot[:8]}")

        return RevertResult(
            success=True,
            message="Restored previous state",
            revert_state=None,
            summary=revert_state.diff,
        )
