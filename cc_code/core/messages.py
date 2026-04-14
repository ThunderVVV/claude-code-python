"""Message types and data models - aligned with TypeScript version"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union


def get_configured_context_window_tokens(raw_value: Optional[str]) -> Optional[int]:
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


def get_used_context_tokens(usage: Optional["Usage"]) -> int:
    """Return prompt-side context tokens from the latest API usage block."""
    if usage is None:
        return 0

    return usage.input_tokens + usage.output_tokens


def get_used_context_percentage(
    usage: Optional["Usage"],
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


class MessageRole(Enum):
    """Message role types"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass
class TextContent:
    """Text content block"""

    type: str = field(default="text", init=False)
    text: str = ""

    def to_api_format(self) -> Dict[str, Any]:
        return self.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {"type": "text", "text": self.text}


@dataclass
class ThinkingContent:
    """Thinking/reasoning content block - for models that support chain-of-thought"""

    type: str = field(default="thinking", init=False)
    thinking: str = ""
    signature: str = ""

    def to_api_format(self) -> Dict[str, Any]:
        return self.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "type": "thinking",
            "thinking": self.thinking,
            "signature": self.signature,
        }


@dataclass
class ToolUseContent:
    """Tool use content block"""

    type: str = field(default="tool_use", init=False)
    id: str = ""
    name: str = ""
    input: Dict[str, Any] = field(default_factory=dict)

    def to_api_format(self) -> Dict[str, Any]:
        return {
            "type": "tool_use",
            "id": self.id,
            "name": self.name,
            "input": self.input,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "type": "tool_use",
            "tool_use_id": self.id,
            "tool_name": self.name,
            "input": self.input,
        }


@dataclass
class ToolResultContent:
    """Tool result content block"""

    type: str = field(default="tool_result", init=False)
    tool_use_id: str = ""
    content: str = ""
    is_error: bool = False
    metadata: Optional[Dict[str, Any]] = None  # For tracking loaded instruction files

    def to_api_format(self) -> Dict[str, Any]:
        result = {
            "type": "tool_result",
            "tool_use_id": self.tool_use_id,
            "content": self.content,
            "is_error": self.is_error,
        }
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        result = {
            "type": "tool_result",
            "tool_use_id": self.tool_use_id,
            "result": self.content,
            "is_error": self.is_error,
        }
        if self.metadata:
            result["metadata"] = self.metadata
        return result


@dataclass
class PatchContent:
    """Patch content block for file revert tracking - aligned with OpenCode PatchPart"""

    type: str = field(default="patch", init=False)
    prev_hash: str = ""  # Git tree hash BEFORE changes (snapshot before tool execution)
    hash: str = ""  # Git tree hash AFTER changes
    files: List[str] = field(default_factory=list)  # List of changed file paths

    def to_api_format(self) -> Dict[str, Any]:
        return self.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "type": "patch",
            "prev_hash": self.prev_hash,
            "hash": self.hash,
            "files": self.files,
        }


ContentBlock = Union[
    TextContent,
    ThinkingContent,
    ToolUseContent,
    ToolResultContent,
    PatchContent,
]


def content_block_from_dict(data: dict[str, Any]) -> ContentBlock:
    """Reconstruct ContentBlock from dict for session persistence."""
    block_type = data.get("type", "")
    if block_type == "text":
        return TextContent(text=str(data.get("text", "")))
    if block_type == "thinking":
        return ThinkingContent(
            thinking=str(data.get("thinking", "")),
            signature=str(data.get("signature", "")),
        )
    if block_type == "tool_use":
        return ToolUseContent(
            id=str(data.get("tool_use_id", data.get("id", ""))),
            name=str(data.get("tool_name", data.get("name", ""))),
            input=data.get("input", {}) if isinstance(data.get("input"), dict) else {},
        )
    if block_type == "tool_result":
        return ToolResultContent(
            tool_use_id=str(data.get("tool_use_id", "")),
            content=str(data.get("result", data.get("content", ""))),
            is_error=bool(data.get("is_error", False)),
            metadata=data.get("metadata"),
        )
    if block_type == "patch":
        files = data.get("files", [])
        return PatchContent(
            prev_hash=str(data.get("prev_hash", "")),
            hash=str(data.get("hash", "")),
            files=files if isinstance(files, list) else [],
        )
    raise ValueError(f"Unknown content block type: {block_type!r}")


def generate_uuid() -> str:
    """Generate a UUID string"""
    return str(uuid.uuid4())


@dataclass
class Usage:
    """API usage statistics"""

    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class Message:
    """Base message class - aligned with TypeScript Message type"""

    type: MessageRole
    content: List[ContentBlock] = field(default_factory=list)
    uuid: str = field(default_factory=generate_uuid)
    timestamp: datetime = field(default_factory=datetime.now)
    is_meta: bool = False
    is_compact_summary: bool = False
    tool_use_result: Any = None
    is_visible_in_transcript_only: bool = False
    # Usage and stop reason (previously in message dict)
    usage: Optional[Usage] = None
    stop_reason: Optional[str] = None
    # For compact summary: parent message ID
    parent_id: Optional[str] = None
    # For system messages: subtype
    subtype: Optional[str] = None
    # File expansion info for user messages
    file_expansions: List[Any] = field(
        default_factory=list
    )  # List of FileExpansion objects
    original_text: str = ""  # Original user text before expansion (for display)
    web_enabled: bool = False  # Whether @web was referenced in the message

    @classmethod
    def user_message(
        cls,
        text: str,
        file_expansions: Optional[List[Any]] = None,
        original_text: str = "",
        web_enabled: bool = False,
    ) -> "Message":
        """Create a user message"""
        return cls(
            type=MessageRole.USER,
            content=[TextContent(text=text)],
            file_expansions=file_expansions or [],
            original_text=original_text or text,
            web_enabled=web_enabled,
        )

    @classmethod
    def assistant_message(
        cls,
        content: List[ContentBlock],
        usage: Optional[Usage] = None,
        stop_reason: Optional[str] = None,
    ) -> "Message":
        """Create an assistant message"""
        return cls(
            type=MessageRole.ASSISTANT,
            content=content,
            usage=usage,
            stop_reason=stop_reason,
        )

    @classmethod
    def system_message(cls, text: str, subtype: Optional[str] = None) -> "Message":
        """Create a system message"""
        return cls(
            type=MessageRole.SYSTEM,
            content=[TextContent(text=text)],
            subtype=subtype,
        )

    @classmethod
    def tool_result_message(
        cls,
        tool_use_id: str,
        content: str,
        is_error: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "Message":
        """Create a tool result message"""
        return cls(
            type=MessageRole.TOOL,
            content=[
                ToolResultContent(
                    tool_use_id=tool_use_id,
                    content=content,
                    is_error=is_error,
                    metadata=metadata,
                )
            ],
            tool_use_result=content,
        )

    def get_text(self) -> str:
        """Get all text content from message"""
        texts = []
        for block in self.content:
            if isinstance(block, TextContent):
                texts.append(block.text)
            elif isinstance(block, ToolResultContent):
                texts.append(block.content)
        return "\n".join(texts)

    def get_tool_uses(self) -> List[ToolUseContent]:
        """Get all tool use blocks from message"""
        return [block for block in self.content if isinstance(block, ToolUseContent)]

    def has_tool_uses(self) -> bool:
        """Check if message has tool uses"""
        return any(isinstance(block, ToolUseContent) for block in self.content)

    def get_usage(self) -> Optional[Usage]:
        """Get usage data from assistant messages when available."""
        return self.usage

    def to_api_format(self) -> Dict[str, Any]:
        """Convert to API format for OpenAI"""
        if self.type == MessageRole.SYSTEM:
            return {"role": "system", "content": self.get_text()}
        elif self.type == MessageRole.USER:
            return {"role": "user", "content": self.get_text()}
        elif self.type == MessageRole.ASSISTANT:
            content = []
            has_tool_use = False
            for block in self.content:
                if isinstance(block, TextContent):
                    content.append({"type": "text", "text": block.text})
                elif isinstance(block, ToolUseContent):
                    has_tool_use = True
                    content.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )
            if not has_tool_use and len(content) == 1:
                return {"role": "assistant", "content": content[0].get("text", "")}
            return {"role": "assistant", "content": content}
        elif self.type == MessageRole.TOOL:
            for block in self.content:
                if isinstance(block, ToolResultContent):
                    return {
                        "role": "tool",
                        "tool_call_id": block.tool_use_id,
                        "content": block.content,
                    }
        return {"role": "user", "content": ""}

    def to_dict(
        self, use_content_key: bool = False, include_persistence_fields: bool = False
    ) -> Dict[str, Any]:
        """Convert to dictionary for serialization.

        This is the unified serialization method for all purposes.

        Args:
            use_content_key: If True, use "content" key instead of "content_blocks"
            include_persistence_fields: If True, include timestamp, is_meta, etc. for disk persistence
        """
        content_key = "content" if use_content_key else "content_blocks"
        message_dict = {
            "uuid": self.uuid,
            "role": self.type.value if hasattr(self.type, "value") else str(self.type),
            content_key: [block.to_dict() for block in self.content],
        }

        if self.original_text:
            message_dict["original_text"] = self.original_text

        if self.usage:
            message_dict["usage"] = {
                "input_tokens": self.usage.input_tokens,
                "output_tokens": self.usage.output_tokens,
            }

        if self.stop_reason:
            message_dict["stop_reason"] = self.stop_reason

        # Persistence-specific fields
        if include_persistence_fields:
            message_dict["type"] = self.type.value
            message_dict["timestamp"] = self.timestamp.isoformat()
            message_dict["is_meta"] = self.is_meta
            message_dict["is_compact_summary"] = self.is_compact_summary
            message_dict["is_visible_in_transcript_only"] = (
                self.is_visible_in_transcript_only
            )

            if self.parent_id:
                message_dict["parent_id"] = self.parent_id

            if self.subtype:
                message_dict["subtype"] = self.subtype

            if self.file_expansions:
                message_dict["file_expansions"] = [
                    {
                        "file_path": exp.file_path,
                        "content": exp.content,
                        "display_path": exp.display_path,
                    }
                    for exp in self.file_expansions
                ]

        return message_dict


@dataclass
class QueryState:
    """State for a query session"""

    messages: List[Message] = field(default_factory=list)
    current_turn: int = 0
    is_streaming: bool = False
    current_streaming_text: str = ""
    session_id: str = field(default_factory=generate_uuid)
    total_usage: Usage = field(default_factory=Usage)

    def add_message(self, message: Message) -> None:
        """Add a message to the state"""
        self.messages.append(message)

    def get_last_message(self) -> Optional[Message]:
        """Get the last message"""
        return self.messages[-1] if self.messages else None

    def clear(self) -> None:
        """Clear the state"""
        self.messages = []
        self.current_turn = 0
        self.is_streaming = False
        self.current_streaming_text = ""
        self.total_usage = Usage()


# Query event types for the query loop
@dataclass
class QueryEvent:
    """Base query event"""

    pass


@dataclass
class TextEvent(QueryEvent):
    """Event for streaming text content"""

    text: str = ""

    def to_dict(self, working_directory: str = "") -> Dict[str, Any]:
        return {"type": "text", "text": self.text}


@dataclass
class ThinkingEvent(QueryEvent):
    """Event for streaming thinking/reasoning content"""

    thinking: str = ""

    def to_dict(self, working_directory: str = "") -> Dict[str, Any]:
        return {"type": "thinking", "thinking": self.thinking}


@dataclass
class ToolUseEvent(QueryEvent):
    """Event for tool use"""

    tool_use_id: str = ""
    tool_name: str = ""
    input: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, working_directory: str = "") -> Dict[str, Any]:
        return {
            "type": "tool_use",
            "tool_use_id": self.tool_use_id,
            "tool_name": self.tool_name,
            "input": self.input,
        }


@dataclass
class ToolResultEvent(QueryEvent):
    """Event for tool result"""

    tool_use_id: str = ""
    result: str = ""
    is_error: bool = False

    def to_dict(self, working_directory: str = "") -> Dict[str, Any]:
        return {
            "type": "tool_result",
            "tool_use_id": self.tool_use_id,
            "result": self.result,
            "is_error": self.is_error,
        }


@dataclass
class MessageCompleteEvent(QueryEvent):
    """Event when a message is complete"""

    message: Optional[Message] = None

    def to_dict(self, working_directory: str = "") -> Dict[str, Any]:
        event_dict: dict[str, object] = {"type": "message_complete"}
        if self.message:
            # Basic message dict - server.py's message_to_dict will add file expansions
            event_dict["message"] = self.message.to_dict()
        return event_dict


@dataclass
class TurnCompleteEvent(QueryEvent):
    """Event when a turn is complete"""

    turn: int = 0
    has_more_turns: bool = False
    stop_reason: Optional[str] = None

    def to_dict(self, working_directory: str = "") -> Dict[str, Any]:
        return {
            "type": "turn_complete",
            "turn": self.turn,
            "has_more_turns": self.has_more_turns,
        }


@dataclass
class ErrorEvent(QueryEvent):
    """Event for errors"""

    error: str = ""
    is_fatal: bool = False

    def to_dict(self, working_directory: str = "") -> Dict[str, Any]:
        return {"type": "error", "error": self.error, "is_fatal": self.is_fatal}
