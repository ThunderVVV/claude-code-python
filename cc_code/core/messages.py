"""Message types and data models - aligned with TypeScript version"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union


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
        return {"type": "text", "text": self.text}


@dataclass
class ThinkingContent:
    """Thinking/reasoning content block - for models that support chain-of-thought"""

    type: str = field(default="thinking", init=False)
    thinking: str = ""
    signature: str = ""

    def to_api_format(self) -> Dict[str, Any]:
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


@dataclass
class PatchContent:
    """Patch content block for file revert tracking - aligned with OpenCode PatchPart"""

    type: str = field(default="patch", init=False)
    prev_hash: str = ""  # Git tree hash BEFORE changes (snapshot before tool execution)
    hash: str = ""  # Git tree hash AFTER changes
    files: List[str] = field(default_factory=list)  # List of changed file paths

    def to_api_format(self) -> Dict[str, Any]:
        return {
            "type": "patch",
            "prev_hash": self.prev_hash,
            "hash": self.hash,
            "files": self.files,
        }


@dataclass
class StepStartContent:
    """Step start content block for tracking tool execution start"""

    type: str = field(default="step_start", init=False)
    snapshot: str = ""  # Git tree hash before tool execution

    def to_api_format(self) -> Dict[str, Any]:
        return {
            "type": "step_start",
            "snapshot": self.snapshot,
        }


ContentBlock = Union[
    TextContent,
    ThinkingContent,
    ToolUseContent,
    ToolResultContent,
    PatchContent,
    StepStartContent,
]


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
    message: Optional[Dict[str, Any]] = None
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
            message={"role": "user", "content": text},
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
        msg = cls(
            type=MessageRole.ASSISTANT,
            content=content,
            message={
                "role": "assistant",
                "content": [block.to_api_format() for block in content],
            },
        )
        if usage:
            msg.message["usage"] = {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
            }
        if stop_reason:
            msg.message["stop_reason"] = stop_reason
        return msg

    @classmethod
    def system_message(cls, text: str, subtype: Optional[str] = None) -> "Message":
        """Create a system message"""
        msg = cls(
            type=MessageRole.SYSTEM,
            content=[TextContent(text=text)],
            message={"role": "system", "content": text},
        )
        if subtype:
            msg.message["subtype"] = subtype
        return msg

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
            message={
                "role": "tool",
                "content": content,
                "tool_call_id": tool_use_id,
            },
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
        usage = self.message.get("usage") if self.message else None
        if not isinstance(usage, dict):
            return None

        return Usage(
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )

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


@dataclass
class ToolCallState:
    """State for a tool call"""

    tool_use_id: str
    tool_name: str
    input: Dict[str, Any]
    status: str = "pending"
    result: Optional[str] = None
    error: Optional[str] = None


@dataclass
class QueryState:
    """State for a query session"""

    messages: List[Message] = field(default_factory=list)
    tool_calls: List[ToolCallState] = field(default_factory=list)
    current_turn: int = 0
    is_streaming: bool = False
    current_streaming_text: str = ""
    session_id: str = field(default_factory=generate_uuid)
    total_usage: Usage = field(default_factory=Usage)

    def add_message(self, message: Message) -> None:
        """Add a message to the state"""
        self.messages.append(message)

    def add_tool_call(self, tool_call: ToolCallState) -> None:
        """Add a tool call to the state"""
        self.tool_calls.append(tool_call)

    def get_last_message(self) -> Optional[Message]:
        """Get the last message"""
        return self.messages[-1] if self.messages else None

    def clear(self) -> None:
        """Clear the state"""
        self.messages = []
        self.tool_calls = []
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


@dataclass
class ThinkingEvent(QueryEvent):
    """Event for streaming thinking/reasoning content"""

    thinking: str = ""


@dataclass
class ToolUseEvent(QueryEvent):
    """Event for tool use"""

    tool_use_id: str = ""
    tool_name: str = ""
    input: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResultEvent(QueryEvent):
    """Event for tool result"""

    tool_use_id: str = ""
    result: str = ""
    is_error: bool = False


@dataclass
class MessageCompleteEvent(QueryEvent):
    """Event when a message is complete"""

    message: Optional[Message] = None


@dataclass
class TurnCompleteEvent(QueryEvent):
    """Event when a turn is complete"""

    turn: int = 0
    has_more_turns: bool = False
    stop_reason: Optional[str] = None


@dataclass
class ErrorEvent(QueryEvent):
    """Event for errors"""

    error: str = ""
    is_fatal: bool = False
