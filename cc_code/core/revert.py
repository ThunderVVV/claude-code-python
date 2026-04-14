"""Session revert data models - aligned with OpenCode session/revert.ts

This module provides data models for revert functionality.
The actual revert logic is now integrated into QueryEngine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from cc_code.core.snapshot import DiffSummary


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
