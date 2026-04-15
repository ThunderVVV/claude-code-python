"""Session compaction functionality for compressing conversation history.

This module implements the /compact command which generates AI summaries
of conversation history to preserve key information while saving context space.

Aligned with TypeScript implementation in session/compaction.ts
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from cc_code.core.messages import (
    Message,
    MessageRole,
    TextContent,
    ToolUseContent,
    ToolResultContent,
)

logger = logging.getLogger(__name__)


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
