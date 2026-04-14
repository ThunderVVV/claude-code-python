"""Session compaction functionality for compressing conversation history.

This module implements the /compact command which generates AI summaries
of conversation history to preserve key information while saving context space.

Aligned with TypeScript implementation in session/compaction.ts
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from cc_code.core.messages import (
    Message,
    MessageRole,
    TextContent,
    ToolUseContent,
    ToolResultContent,
    Usage,
    generate_uuid,
)

logger = logging.getLogger(__name__)

# Constants aligned with TypeScript
PRUNE_MINIMUM = 20_000  # Minimum tokens to trigger pruning
PRUNE_PROTECT = 40_000  # Tokens to protect from pruning
PRUNE_PROTECTED_TOOLS = ["skill"]  # Tools that should not be pruned

# Default compaction prompt template - MUST match TypeScript version exactly
DEFAULT_COMPACTION_PROMPT = """Provide a detailed prompt for continuing our conversation above.
Focus on information that would be helpful for continuing the conversation, including what we did, what we're doing, which files we're working on, and what we're going to do next.
The summary that you construct will be used so that another agent can read it and continue the work.
Do not call any tools. Respond only with the summary text.
Respond in the same language as the user's messages in the conversation.

When constructing the summary, try to stick to this template:
---
## Goal

[What goal(s) is the user trying to accomplish?]

## Instructions

- [What important instructions did the user give you that are relevant]
- [If there is a plan or spec, include information about it so next agent can continue using it]

## Discoveries

[What notable things were learned during this conversation that would be useful for the next agent to know when continuing the work]

## Accomplished

[What work has been completed, what work is still in progress, and what work is left?]

## Relevant files / directories

[Construct a structured list of relevant files that have been read, edited, or created that pertain to the task at hand. If all the files in a directory are relevant, include the path to the directory.]
---"""


@dataclass
class CompactionResult:
    """Result of a compaction operation."""

    success: bool
    summary: str = ""
    error: Optional[str] = None
    tokens_saved: int = 0
    messages_compacted: int = 0


@dataclass
class CompactionConfig:
    """Configuration for compaction."""

    auto: bool = False
    overflow: bool = False
    prompt: Optional[str] = None
    prune_enabled: bool = True


class SessionCompaction:
    """Handles session compaction to compress conversation history.

    This class provides functionality to:
    1. Generate AI summaries of conversation history
    2. Prune old tool outputs to free context space
    3. Create compacted messages that preserve key information
    """

    def __init__(
        self,
        messages: List[Message],
        model_name: str = "",
        context_window: Optional[int] = None,
    ):
        self.messages = messages
        self.model_name = model_name
        self.context_window = context_window

    def get_messages_for_compaction(
        self,
        exclude_last_user: bool = False,
    ) -> List[Message]:
        """Get messages eligible for compaction.

        Args:
            exclude_last_user: Whether to exclude the last user message

        Returns:
            List of messages that can be compacted
        """
        messages = list(self.messages)

        # Remove meta messages and compacted summaries
        filtered = []
        for msg in messages:
            if msg.is_meta:
                continue
            if msg.is_compact_summary:
                continue
            filtered.append(msg)

        # Optionally exclude the last user message
        if exclude_last_user and filtered:
            last = filtered[-1]
            if last.type == MessageRole.USER:
                filtered = filtered[:-1]

        return filtered

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Simple estimation: ~4 characters per token on average.
        """
        return len(text) // 4

    def estimate_message_tokens(self, message: Message) -> int:
        """Estimate token count for a message."""
        total = 0
        for block in message.content:
            if isinstance(block, TextContent):
                total += self.estimate_tokens(block.text)
            elif isinstance(block, ToolResultContent):
                total += self.estimate_tokens(block.content)
            elif isinstance(block, ToolUseContent):
                # Tool use input can be large
                import json
                total += self.estimate_tokens(json.dumps(block.input))
        return total

    def should_compact(self) -> bool:
        """Check if compaction should be triggered based on message count."""
        # Simple heuristic: compact if more than 20 messages
        eligible = self.get_messages_for_compaction()
        return len(eligible) > 20

    def get_tool_results_to_prune(self) -> List[tuple]:
        """Get tool results that can be pruned to save context.

        Returns list of (message_index, block_index, estimated_tokens) tuples.
        """
        if not self.messages:
            return []

        to_prune: List[tuple] = []
        total_tokens = 0
        pruned_tokens = 0
        turns = 0

        # Iterate backwards through messages
        for msg_idx in range(len(self.messages) - 1, -1, -1):
            msg = self.messages[msg_idx]

            # Count turns
            if msg.type == MessageRole.USER:
                turns += 1

            # Skip recent turns
            if turns < 2:
                continue

            # Stop at previous summary
            if msg.type == MessageRole.ASSISTANT and msg.is_compact_summary:
                break

            # Check tool results
            for block_idx in range(len(msg.content) - 1, -1, -1):
                block = msg.content[block_idx]
                if isinstance(block, ToolResultContent):
                    # Skip protected tools
                    # Note: we'd need tool name info to check PRUNE_PROTECTED_TOOLS
                    # For now, estimate all tool results

                    estimate = self.estimate_tokens(block.content)
                    total_tokens += estimate

                    if total_tokens > PRUNE_PROTECT:
                        pruned_tokens += estimate
                        to_prune.append((msg_idx, block_idx, estimate))

        # Only prune if we'd save enough tokens
        if pruned_tokens > PRUNE_MINIMUM:
            return to_prune
        return []

    def create_compaction_prompt(
        self,
        custom_prompt: Optional[str] = None,
        additional_context: Optional[List[str]] = None,
    ) -> str:
        """Create the prompt for generating a summary.

        Args:
            custom_prompt: Optional custom prompt to use instead of default
            additional_context: Optional additional context to include

        Returns:
            The prompt string to send to the AI
        """
        if custom_prompt:
            return custom_prompt

        parts = [DEFAULT_COMPACTION_PROMPT]

        if additional_context:
            parts.extend(additional_context)

        return "\n\n".join(parts)

    def build_messages_for_summary(
        self,
        strip_tool_results: bool = True,
        max_messages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Build messages to send to AI for generating summary.

        Args:
            strip_tool_results: Whether to strip large tool results
            max_messages: Maximum number of messages to include

        Returns:
            List of message dicts in API format (text only, no tool blocks)
        """
        messages = self.get_messages_for_compaction(exclude_last_user=True)

        if max_messages:
            messages = messages[-max_messages:]

        result = []
        for msg in messages:
            # For compaction, we only want text content
            # Strip all tool_use and tool_result blocks to avoid API errors
            if msg.type == MessageRole.USER:
                # User messages: just get the text
                text = msg.get_text()
                result.append({"role": "user", "content": text})
            elif msg.type == MessageRole.ASSISTANT:
                # Assistant messages: extract only text content
                text_parts = []
                for block in msg.content:
                    if isinstance(block, TextContent):
                        text_parts.append(block.text)
                
                text = "\n".join(text_parts) if text_parts else ""
                if text:
                    result.append({"role": "assistant", "content": text})
            elif msg.type == MessageRole.SYSTEM:
                text = msg.get_text()
                if text:
                    result.append({"role": "system", "content": text})
            # Skip TOOL messages entirely for compaction

        return result

    def create_summary_message(
        self,
        summary_text: str,
        parent_message_id: Optional[str] = None,
    ) -> Message:
        """Create a summary message from the generated summary text.

        Args:
            summary_text: The generated summary text
            parent_message_id: Optional parent message ID

        Returns:
            A Message object marked as a compact summary
        """
        msg = Message.assistant_message(
            content=[TextContent(text=summary_text)],
        )
        msg.is_compact_summary = True
        msg.uuid = parent_message_id or generate_uuid()
        return msg

    def compact_messages(
        self,
        summary_text: str,
        keep_last_n: int = 2,
    ) -> List[Message]:
        """Create a compacted message list with the summary.

        Args:
            summary_text: The generated summary text
            keep_last_n: Number of recent messages to keep after summary

        Returns:
            New list of messages with summary replacing old history
        """
        if not self.messages:
            return []

        # Find where to insert the summary
        # Keep the last few messages after the summary
        summary_msg = self.create_summary_message(summary_text)

        # Get messages to keep (recent ones)
        recent_messages = []
        eligible = self.get_messages_for_compaction()

        # Keep last N messages
        if len(eligible) > keep_last_n:
            recent_messages = eligible[-keep_last_n:]
        else:
            recent_messages = eligible

        # Build new message list
        result = [summary_msg]

        # Add recent messages
        for msg in recent_messages:
            result.append(msg)

        return result


async def compact_session(
    messages: List[Message],
    client,  # OpenAIClient
    model_name: str = "",
    context_window: Optional[int] = None,
    custom_prompt: Optional[str] = None,
) -> CompactionResult:
    """Compact a session by generating an AI summary.

    This is the main entry point for session compaction.

    Args:
        messages: List of messages to compact
        client: OpenAI client to use for generating summary
        model_name: Name of the model being used
        context_window: Context window size for the model
        custom_prompt: Optional custom prompt for summary generation

    Returns:
        CompactionResult with summary and metadata
    """
    if not messages:
        return CompactionResult(
            success=False,
            error="No messages to compact",
        )

    compaction = SessionCompaction(
        messages=messages,
        model_name=model_name,
        context_window=context_window,
    )

    # Build messages for summary generation
    history_messages = compaction.build_messages_for_summary(
        strip_tool_results=True,
        max_messages=50,  # Limit to avoid context overflow
    )

    if not history_messages:
        return CompactionResult(
            success=False,
            error="No eligible messages for compaction",
        )

    # Create the summary request
    prompt = compaction.create_compaction_prompt(custom_prompt)

    # Add the summary request as a user message
    summary_request = {"role": "user", "content": prompt}

    try:
        # Call the AI to generate summary
        # Note: This uses a simplified approach - in production you'd want
        # to use the streaming API and handle errors properly
        response = await client._chat_completion_raw(
            messages=history_messages + [summary_request],
            model=model_name,
            max_tokens=2000,
            temperature=0.3,
        )

        # Extract summary text
        choices = response.get("choices", [])
        if not choices:
            return CompactionResult(
                success=False,
                error="No response from AI",
            )

        summary_text = choices[0].get("message", {}).get("content", "")

        if not summary_text:
            return CompactionResult(
                success=False,
                error="Empty summary generated",
            )

        # Calculate tokens saved
        original_tokens = sum(
            compaction.estimate_message_tokens(msg)
            for msg in compaction.get_messages_for_compaction()
        )
        summary_tokens = compaction.estimate_tokens(summary_text)
        tokens_saved = max(0, original_tokens - summary_tokens)

        return CompactionResult(
            success=True,
            summary=summary_text,
            tokens_saved=tokens_saved,
            messages_compacted=len(history_messages),
        )

    except Exception as e:
        logger.exception("Failed to generate compaction summary")
        return CompactionResult(
            success=False,
            error=str(e),
        )


def prune_tool_results(messages: List[Message]) -> tuple[List[Message], int]:
    """Prune old tool results from messages to save context space.

    Args:
        messages: List of messages to prune

    Returns:
        Tuple of (pruned messages, tokens saved)
    """
    if not messages:
        return messages, 0

    compaction = SessionCompaction(messages=messages)
    to_prune = compaction.get_tool_results_to_prune()

    if not to_prune:
        return messages, 0

    # Create a copy of messages
    result = [msg for msg in messages]
    tokens_saved = 0

    # Prune from end to start to preserve indices
    for msg_idx, block_idx, estimate in sorted(to_prune, reverse=True):
        if msg_idx < len(result):
            msg = result[msg_idx]
            # Replace tool result with placeholder
            if block_idx < len(msg.content):
                block = msg.content[block_idx]
                if isinstance(block, ToolResultContent):
                    # Create truncated version
                    truncated = ToolResultContent(
                        tool_use_id=block.tool_use_id,
                        content="[Output pruned to save context space]",
                        is_error=block.is_error,
                    )
                    msg.content[block_idx] = truncated
                    tokens_saved += estimate

    return result, tokens_saved


def is_context_overflow(
    usage: Usage,
    context_window: int,
    threshold: float = 0.9,
) -> bool:
    """Check if context is near overflow.

    Args:
        usage: Current token usage
        context_window: Maximum context window size
        threshold: Fraction of context window to consider overflow (default 90%)

    Returns:
        True if context usage exceeds threshold
    """
    if not context_window:
        return False

    total_tokens = usage.input_tokens + usage.output_tokens
    return total_tokens > context_window * threshold
