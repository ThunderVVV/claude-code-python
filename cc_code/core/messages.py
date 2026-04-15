"""Message types and data models - aligned with TypeScript version"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

if TYPE_CHECKING:
    from cc_code.core.snapshot import RevertState


from cc_code.core.context_window import (
    get_configured_context_window_tokens,
    get_used_context_tokens,
    get_used_context_percentage,
    format_token_count,
)

__all__ = [
    "get_configured_context_window_tokens",
    "get_used_context_tokens",
    "get_used_context_percentage",
    "format_token_count",
    "MessageRole",
    "TextContent",
    "ThinkingContent",
    "ToolUseContent",
    "ToolResultContent",
    "PatchContent",
    "ContentBlock",
    "content_block_from_dict",
    "generate_uuid",
    "Usage",
    "Message",
    "SessionState",
    "QueryEvent",
    "TextEvent",
    "ThinkingEvent",
    "ToolUseEvent",
    "ToolResultEvent",
    "MessageCompleteEvent",
    "TurnCompleteEvent",
    "ErrorEvent",
]


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

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "text", "text": self.text}


@dataclass
class ThinkingContent:
    """Thinking/reasoning content block - for models that support chain-of-thought"""

    type: str = field(default="thinking", init=False)
    thinking: str = ""
    signature: str = ""

    def to_dict(self) -> Dict[str, Any]:
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

    def to_dict(self) -> Dict[str, Any]:
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
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
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
    """Patch content block for file revert tracking"""

    type: str = field(default="patch", init=False)
    prev_hash: str = ""
    hash: str = ""
    files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
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
    """Base message class"""

    type: MessageRole
    content: List[ContentBlock] = field(default_factory=list)
    uuid: str = field(default_factory=generate_uuid)
    timestamp: datetime = field(default_factory=datetime.now)
    is_meta: bool = False
    is_compact_summary: bool = False
    usage: Optional[Usage] = None
    stop_reason: Optional[str] = None
    parent_id: Optional[str] = None
    subtype: Optional[str] = None
    file_expansions: List[Any] = field(default_factory=list)
    original_text: str = ""
    web_enabled: bool = False

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

    def serialize(self, format: str = "api") -> Dict[str, Any]:
        """Serialize message to dictionary.
        
        Args:
            format: Output format
                - "api": OpenAI API format (for LLM requests)
                - "dict": General dict format (for API responses)
                - "persistence": Full format for disk storage
        
        Returns:
            Serialized message dictionary
        """
        if format == "api":
            return self._serialize_for_api()

        # Dict and persistence formats share common structure
        content_blocks = [block.to_dict() for block in self.content]
        message_dict = {
            "uuid": self.uuid,
            "role": self.type.value,
            "content": content_blocks,
            "content_blocks": content_blocks,
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
        if format == "persistence":
            message_dict["type"] = self.type.value
            message_dict["timestamp"] = self.timestamp.isoformat()
            message_dict["is_meta"] = self.is_meta
            message_dict["is_compact_summary"] = self.is_compact_summary

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

    def _serialize_for_api(self) -> Dict[str, Any]:
        """Convert to OpenAI API format for LLM requests."""
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


@dataclass
class SessionState:
    """Unified session state."""
    
    # Core state
    messages: List[Message] = field(default_factory=list)
    current_turn: int = 0
    is_streaming: bool = False
    current_streaming_text: str = ""
    session_id: str = field(default_factory=generate_uuid)
    total_usage: Usage = field(default_factory=Usage)
    
    # Session metadata
    title: str = ""
    created_at: str = ""
    updated_at: str = ""
    working_directory: str = ""
    model_id: Optional[str] = None
    model_name: Optional[str] = None
    
    # Revert tracking - use RevertState object directly
    _revert_state: Optional["RevertState"] = field(default=None, repr=False)
    
    # Total diff tracking
    total_diff_additions: int = 0
    total_diff_deletions: int = 0
    total_diff_files: int = 0

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
        self.title = ""
        self.created_at = ""
        self.updated_at = ""
        self.working_directory = ""
        self.model_id = None
        self.model_name = None
        self._revert_state = None
        self.total_diff_additions = 0
        self.total_diff_deletions = 0
        self.total_diff_files = 0
        self.session_id = generate_uuid()

    def get_revert_state(self) -> Optional["RevertState"]:
        """Get revert state if exists."""
        return self._revert_state

    def set_revert_state(self, state: Optional["RevertState"]) -> None:
        """Set revert state."""
        self._revert_state = state


# Query event types
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
            event_dict["message"] = self.message.serialize(format="dict")
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


def message_to_api_dict(
    message: Message,
    working_directory: str = "",
) -> Dict[str, Any]:
    """Serialize a message for web transport with file expansion support."""
    from cc_code.core.file_expansion import (
        build_visible_file_expansions,
        serialize_file_expansions,
        has_web_reference,
    )

    message_dict = message.serialize(format="dict")

    # Add file expansions if needed
    if getattr(message, "file_expansions", None):
        message_dict["file_expansions"] = serialize_file_expansions(
            message.file_expansions
        )
    elif message_dict["role"] == "user" and message.original_text and working_directory:
        file_expansions = build_visible_file_expansions(
            message.original_text,
            working_directory,
        )
        if file_expansions:
            message_dict["file_expansions"] = serialize_file_expansions(file_expansions)

    # Add web enabled flag
    if message_dict["role"] == "user":
        message_dict["web_enabled"] = bool(
            getattr(message, "web_enabled", False)
            or (message.original_text and has_web_reference(message.original_text))
        )

    return message_dict


def event_to_api_dict(
    event: QueryEvent,
    working_directory: str = "",
) -> Dict[str, Any]:
    """Convert event to dictionary for SSE streaming."""
    event_dict = event.to_dict(working_directory=working_directory)

    if isinstance(event, MessageCompleteEvent) and event.message:
        event_dict["message"] = message_to_api_dict(
            event.message,
            working_directory=working_directory,
        )

    return event_dict
