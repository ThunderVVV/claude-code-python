"""Synchronous query lifecycle guard aligned with claude-code's QueryGuard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


QueryStatus = Literal["idle", "dispatching", "running"]


@dataclass
class QueryGuard:
    """Track query ownership and invalidate stale finally blocks."""

    _status: QueryStatus = "idle"
    _generation: int = 0

    def reserve(self) -> bool:
        if self._status != "idle":
            return False
        self._status = "dispatching"
        return True

    def cancel_reservation(self) -> None:
        if self._status == "dispatching":
            self._status = "idle"

    def try_start(self) -> Optional[int]:
        if self._status == "running":
            return None
        self._status = "running"
        self._generation += 1
        return self._generation

    def end(self, generation: int) -> bool:
        if self._generation != generation or self._status != "running":
            return False
        self._status = "idle"
        return True

    def force_end(self) -> None:
        if self._status == "idle":
            return
        self._status = "idle"
        self._generation += 1

    @property
    def is_active(self) -> bool:
        return self._status != "idle"

    @property
    def generation(self) -> int:
        return self._generation
