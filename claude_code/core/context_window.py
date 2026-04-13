"""Context window helpers aligned with the TypeScript implementation."""

from __future__ import annotations

from typing import Optional

from claude_code.core.messages import Usage


def parse_context_window_tokens(raw_value: Optional[str]) -> Optional[int]:
    """Parse a positive integer context window token value."""
    if raw_value is None:
        return None

    value = raw_value.strip()
    if not value:
        return None

    try:
        context_window_tokens = int(value)
    except ValueError:
        return None

    if context_window_tokens <= 0:
        return None

    return context_window_tokens


def get_configured_context_window_tokens(raw_value: Optional[str]) -> Optional[int]:
    """Read the configured context window size from the persistent settings."""
    return parse_context_window_tokens(raw_value)


def get_used_context_tokens(usage: Optional[Usage]) -> int:
    """Return prompt-side context tokens from the latest API usage block."""
    if usage is None:
        return 0

    return usage.input_tokens + usage.output_tokens


def get_used_context_percentage(
    usage: Optional[Usage],
    context_window_tokens: int,
) -> int:
    """Return the clamped context usage percentage."""
    if context_window_tokens <= 0:
        return 0

    used_tokens = get_used_context_tokens(usage)
    used_percentage = round((used_tokens / context_window_tokens) * 100)
    return max(0, min(100, used_percentage))


def format_token_count(count: int) -> str:
    """Format token counts with compact lower-case suffixes."""
    absolute_count = abs(count)
    if absolute_count >= 1_000_000:
        return _format_compact(count / 1_000_000, "m")
    if absolute_count >= 1_000:
        return _format_compact(count / 1_000, "k")
    return str(count)


def _format_compact(value: float, suffix: str) -> str:
    formatted = f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{formatted}{suffix}"
