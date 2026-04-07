"""TUI interface using Textual - aligned with TypeScript REPL.tsx"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import List, Optional

from textual.app import App, ComposeResult
from textual.containers import (
    Container,
    Horizontal,
    ScrollableContainer,
    VerticalGroup,
)
from textual.widgets import (
    Collapsible,
    Input,
    Label,
    LoadingIndicator,
    Static,
)
from textual.screen import Screen

from claude_code.core.messages import (
    Message,
    MessageRole,
    TextContent,
    ToolUseContent,
    ToolResultContent,
    QueryEvent,
    TextEvent,
    ToolUseEvent,
    ToolResultEvent,
    MessageCompleteEvent,
    TurnCompleteEvent,
    ErrorEvent,
)
from claude_code.core.query_engine import QueryEngine


# Claude Orange color - matches TypeScript theme.ts
CLAUDE_ORANGE = "rgb(215,119,87)"
CLAUDE_ORANGE_LIGHT = "rgb(235,159,127)"


# Embedded CSS for reliability - matches TypeScript theme
# Dark theme colors from TypeScript theme.ts
# text: rgb(255,255,255), inactive: rgb(153,153,153), subtle: rgb(80,80,80)
# background: dark terminal default

ANSI_ESCAPE_RE = re.compile(
    r"\x1b(?:\][^\x07\x1b]*(?:\x07|\x1b\\)|\[[0-?]*[ -/]*[@-~]|[@-Z\\-_])"
)
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_terminal_text(text: str) -> str:
    """Strip ANSI/control sequences that can corrupt terminal rendering."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = ANSI_ESCAPE_RE.sub("", normalized)
    normalized = CONTROL_CHAR_RE.sub("", normalized)
    return normalized


def truncate_preview_line(text: str, max_width: int = 88) -> str:
    """Trim a single preview line to a stable width."""
    expanded = sanitize_terminal_text(text).expandtabs(2)
    if len(expanded) <= max_width:
        return expanded
    return expanded[: max_width - 3] + "..."


def summarize_tool_result(
    tool_name: str,
    tool_input: dict,
    result: str,
    is_error: bool,
) -> tuple[str, List[str]]:
    """Build a compact, always-visible summary for a tool result."""
    lines = sanitize_terminal_text(result).splitlines()
    trimmed_lines = [line for line in lines if line.strip()]

    if is_error:
        summary = truncate_preview_line(trimmed_lines[0] if trimmed_lines else "Tool failed")
        preview = [truncate_preview_line(line) for line in trimmed_lines[1:5]]
        return summary, preview

    if tool_name == "Read":
        match = re.search(r"Lines:\s*(\d+)-(\d+)\s+of\s+(\d+)", result)
        file_name = os.path.basename(tool_input.get("file_path", "")) or "file"
        if match:
            start_line = int(match.group(1))
            end_line = int(match.group(2))
            total_lines = int(match.group(3))
            count = end_line - start_line + 1
            summary = f"Read {count} line{'s' if count != 1 else ''} from {file_name} ({start_line}-{end_line} of {total_lines})"
        else:
            summary = f"Read {file_name}"
        preview_source = lines[3:] if len(lines) > 3 else []
        preview = [truncate_preview_line(line) for line in preview_source[:5] if line.strip()]
        return summary, preview

    if tool_name in {"Glob", "Grep"}:
        summary = truncate_preview_line(trimmed_lines[0] if trimmed_lines else f"{tool_name} completed")
        preview = [truncate_preview_line(line) for line in trimmed_lines[1:6]]
        return summary, preview

    if tool_name in {"Write", "Edit"}:
        summary = truncate_preview_line(trimmed_lines[0] if trimmed_lines else f"{tool_name} completed")
        return summary, []

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if command:
            summary = f"Ran: {truncate_preview_line(command, 64)}"
        else:
            summary = "Command completed"
        preview = [truncate_preview_line(line) for line in trimmed_lines[:6]]
        if len(trimmed_lines) > 6:
            preview.append(f"... ({len(trimmed_lines) - 6} more lines)")
        return summary, preview

    summary = truncate_preview_line(trimmed_lines[0] if trimmed_lines else f"{tool_name} completed")
    preview = [truncate_preview_line(line) for line in trimmed_lines[1:5]]
    return summary, preview


def summarize_tool_use(tool_name: str, tool_input: dict) -> str:
    """Build a compact one-line summary for a tool invocation."""
    if "command" in tool_input:
        return f"{tool_name}: {truncate_preview_line(str(tool_input['command']), 64)}"
    if "file_path" in tool_input:
        file_path = str(tool_input["file_path"])
        file_name = os.path.basename(file_path) or file_path
        return f"{tool_name}: {truncate_preview_line(file_name, 64)}"
    if "pattern" in tool_input:
        return f"{tool_name}: {truncate_preview_line(str(tool_input['pattern']), 64)}"
    if tool_input:
        keys = list(tool_input.keys())
        preview = ", ".join(keys[:3])
        if len(keys) > 3:
            preview += ", ..."
        return f"{tool_name}: {preview}"
    return tool_name


def format_tool_input_details(tool_input: dict) -> List[str]:
    """Format tool input parameters for a collapsible details section."""
    detail_lines: List[str] = []

    for key, value in tool_input.items():
        if isinstance(value, (dict, list, bool, int, float)) or value is None:
            raw_value = json.dumps(value, ensure_ascii=True)
        else:
            raw_value = str(value)

        value_lines = sanitize_terminal_text(raw_value).splitlines() or [""]
        detail_lines.append(f"{key}: {truncate_preview_line(value_lines[0], 104)}")

        for line in value_lines[1:4]:
            detail_lines.append(f"  {truncate_preview_line(line, 102)}")

        if len(value_lines) > 4:
            detail_lines.append("  ...")

    return detail_lines

TUI_CSS = """
/* Claude Code Python TUI Styles */
/* Color theme aligned with TypeScript version: rgb(215,119,87) - Claude Orange */

/* App-level styles */
ClaudeCodeApp {
    background: #1a1a1a;
    color: #ffffff;
}

REPLScreen {
    background: #1a1a1a;
    color: #ffffff;
}

/* Main content scrollable area */
#content-area {
    height: 1fr;
    overflow-y: auto;
    padding: 0 1;
}

/* Scrollbar styling - Claude Orange theme */
ScrollableContainer {
    scrollbar-size: 1 1;
    scrollbar-background: #2a2a2a;
    scrollbar-background-hover: #3a3a3a;
    scrollbar-color: rgb(215,119,87);
    scrollbar-color-hover: rgb(235,159,127);
}

ScrollableContainer:focus {
    scrollbar-color: rgb(235,159,127);
    scrollbar-color-hover: rgb(255,179,147);
}

/* Welcome widget with border */
WelcomeWidget {
    width: 100%;
    height: auto;
    border: round rgb(215,119,87);
    padding: 0 1;
    margin: 0 1 1 1;
}

WelcomeWidget:focus {
    border: round rgb(235,159,127);
}

/* Left panel */
#left-panel {
    width: 1fr;
    height: auto;
    align: center top;
    padding: 0 1;
    min-height: 7;
}

/* Right panel */
#right-panel {
    width: 1fr;
    height: auto;
    min-height: 7;
    padding: 0 0 0 1;
    margin-left: 1;
    border-left: solid rgb(215,119,87);
}

/* Horizontal layout for welcome */
.welcome-horizontal {
    width: 100%;
    height: auto;
}

/* Welcome message */
.welcome-message {
    color: #ffffff;
    text-style: bold;
    text-align: center;
    margin: 0 0 1 0;
}

/* Clawd ASCII art */
.clawd-line {
    color: rgb(215,119,87);
    text-align: center;
}

/* Model info line */
.model-info {
    color: rgb(153,153,153);
    text-align: center;
}

/* CWD line */
.cwd-info {
    color: rgb(153,153,153);
    text-align: center;
}

/* Section title */
.section-title {
    color: rgb(215,119,87);
    text-style: bold;
    margin-top: 0;
}

/* Section content */
.section-content {
    color: rgb(153,153,153);
    margin-left: 1;
}

/* Message list container */
#message-list {
    height: auto;
    padding: 0 2;
}

/* Input area - fixed at bottom */
#input-area {
    height: auto;
    dock: bottom;
    padding: 1 2;
    background: #1a1a1a;
    border-top: solid rgb(215,119,87);
}

#user-input {
    width: 1fr;
    background: #2a2a2a;
}

#processing-row {
    width: 100%;
    height: 1;
    margin: 0 0 1 0;
    display: none;
}

#processing-indicator {
    width: 3;
    height: 1;
    min-width: 3;
    color: rgb(215,119,87);
    margin-right: 1;
}

#processing-label {
    width: auto;
    color: rgb(153,153,153);
}

/* Message roles */
.message-role {
    text-style: bold;
    width: auto;
    margin: 0;
    padding: 0 1;
    background: #262626;
}

.role-user {
    color: rgb(78,186,101);
    background: #1b2b1f;
}

.role-assistant {
    color: rgb(215,119,87);
    background: transparent;
}

.role-system {
    color: rgb(255,193,7);
    background: #2c2816;
}

.role-tool {
    color: rgb(235,159,127);
    background: #2d221d;
}

.message-block {
    width: 100%;
    height: auto;
    margin: 0 0 1 0;
    padding: 1 1;
    background: #171717;
}

.user-message-block {
    background: #2a2d31;
}

.assistant-message-block {
    margin: 0;
    padding: 0;
    background: transparent;
}

.system-message-block {
    border-left: solid rgb(255,193,7);
    background: #211f12;
}

.tool-result-block {
    border-left: solid rgb(235,159,127);
    background: #171a20;
}

.tool-use-block {
    width: 100%;
    height: auto;
    margin: 0 0 1 0;
    padding: 0 1;
    background: #141414;
}

.tool-inline-result {
    width: 100%;
    height: auto;
    margin-left: 0;
    margin-top: 0;
}

.tool-inline-summary {
    margin: 0;
}

/* Message content */
.message-content {
    margin-left: 0;
    margin-bottom: 0;
    padding: 0;
}

/* Streaming message content - inline update */
.streaming-content {
    width: 100%;
    margin-left: 0;
    margin-bottom: 1;
    padding: 0 1;
    color: #ffffff;
    background: transparent;
}

/* Tool styling */
.tool-header {
    color: rgb(235,159,127);
    text-style: bold;
}

.tool-param {
    color: rgb(153,153,153);
    margin-left: 1;
}

.tool-collapsible {
    background: transparent;
    border-top: none;
    padding: 0;
    margin: 0;
}

.tool-collapsible > Contents {
    padding: 0 0 0 1;
}

.tool-collapsible CollapsibleTitle {
    padding: 0;
    background: transparent;
}

.tool-use-details CollapsibleTitle {
    color: rgb(235,159,127);
}

.tool-result-preview-toggle CollapsibleTitle {
    color: rgb(153,153,153);
    margin-left: 2;
}

.tool-result {
    margin-left: 0;
    margin-bottom: 0;
    padding: 0 1;
}

.tool-success {
    color: rgb(78,186,101);
}

.tool-error {
    color: rgb(255,107,128);
}

.tool-result-summary {
    color: #ffffff;
    text-style: bold;
    margin: 0;
}

.tool-result-preview {
    color: rgb(210,210,210);
    margin-left: 2;
}

/* Focus styles */
Input:focus {
    border: tall rgb(215,119,87);
}

/* Header */
Header {
    background: #1a1a1a;
    color: rgb(215,119,87);
}

MessageList {
    width: 100%;
    height: auto;
}

MessageWidget, AssistantMessageWidget, ToolResultWidget {
    width: 100%;
    height: auto;
}

ToolUseWidget {
    width: 100%;
    height: auto;
}

.tool-result-body {
    width: 100%;
    height: auto;
}
"""


class Clawd(VerticalGroup):
    """Clawd the cat - ASCII art aligned with TypeScript Clawd.tsx"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        # Standard terminal Clawd (9 cols wide)
        # Default pose with bottom pupils - matches TypeScript POSES.default
        yield Static(" ▐▛███▜▌ ", classes="clawd-line", markup=False)
        yield Static(" ▝▜█████▛▘ ", classes="clawd-line", markup=False)
        yield Static("   ▘▘ ▝▝   ", classes="clawd-line", markup=False)


class WelcomeWidget(Container):
    """Welcome widget aligned with TypeScript LogoV2.tsx - rendered as part of scrollable content"""

    DEFAULT_CSS = """
    WelcomeWidget {
        width: 100%;
        height: auto;
        border: round rgb(215,119,87);
        padding: 0 1;
        margin: 0 1 1 1;
    }

    WelcomeWidget .welcome-title {
        color: rgb(215,119,87);
        text-style: bold;
    }

    WelcomeWidget .welcome-version {
        color: rgb(153,153,153);
    }

    WelcomeWidget #left-panel {
        width: 1fr;
        height: auto;
        align: center top;
        padding: 0 1;
    }

    WelcomeWidget #right-panel {
        width: 1fr;
        height: auto;
        min-height: 7;
        padding: 0 0 0 1;
        margin-left: 1;
        border-left: solid rgb(215,119,87);
    }

    WelcomeWidget #left-panel {
        min-height: 7;
    }

    WelcomeWidget .welcome-horizontal {
        width: 100%;
        height: auto;
    }
    """

    def __init__(
        self,
        model_name: str = "claude-sonnet-4-6",
        cwd: str = "",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.model_name = model_name
        self.cwd = cwd or os.getcwd()

    def compose(self) -> ComposeResult:
        # Main horizontal layout - aligned with TypeScript LogoV2.tsx
        with Horizontal(classes="welcome-horizontal"):
            # Left panel with welcome message and Clawd
            with Container(id="left-panel"):
                yield Label("Welcome back!", classes="welcome-message", markup=False)
                yield Clawd()
                yield Label(
                    sanitize_terminal_text(f"{self.model_name} · API Usage Billing"),
                    classes="model-info",
                    markup=False,
                )
                yield Label(
                    sanitize_terminal_text(self._truncate_cwd(self.cwd)),
                    classes="cwd-info",
                    markup=False,
                )

            # Right panel with tips
            with Container(id="right-panel"):
                yield Label("Tips for getting started", classes="section-title", markup=False)
                yield Label(
                    "Run /init to create a CLAUDE.md file with instructions for Claude",
                    classes="section-content",
                    markup=False,
                )
                yield Label("Recent activity", classes="section-title", markup=False)
                yield Label("No recent activity", classes="section-content", markup=False)

    def _truncate_cwd(self, path: str, max_len: int = 50) -> str:
        """Truncate path if too long"""
        if len(path) <= max_len:
            return path
        return "..." + path[-(max_len - 3):]


class ToolUseWidget(VerticalGroup):
    """Widget for displaying tool use information"""

    def __init__(
        self,
        tool_name: str,
        tool_input: dict,
        tool_use_id: str,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.tool_name = tool_name
        self.tool_input = tool_input
        self.tool_use_id = tool_use_id
        self._result_summary: Optional[str] = None
        self._result_preview_lines: List[str] = []
        self._result_is_error = False
        self._result_container: Optional[VerticalGroup] = None
        self.add_class("tool-use-block")

    def compose(self) -> ComposeResult:
        detail_lines = format_tool_input_details(self.tool_input)
        with Collapsible(
            title=sanitize_terminal_text(summarize_tool_use(self.tool_name, self.tool_input)),
            collapsed=True,
            collapsed_symbol=">",
            expanded_symbol="v",
            classes="tool-collapsible tool-use-details",
        ):
            if detail_lines:
                for line in detail_lines:
                    yield Static(line, classes="tool-param", markup=False)
            else:
                yield Static("No input parameters", classes="tool-param", markup=False)
        with VerticalGroup(classes="tool-inline-result") as container:
            self._result_container = container
            if self._result_summary is not None:
                yield from self._compose_result_widgets()

    def set_result(self, result: str, is_error: bool) -> None:
        """Attach the tool result to the existing tool-use block."""
        self._result_is_error = is_error
        self._result_summary, self._result_preview_lines = summarize_tool_result(
            self.tool_name,
            self.tool_input,
            result,
            is_error,
        )
        if self._result_container:
            self._render_result_widgets()

    def _compose_result_widgets(self) -> ComposeResult:
        status_class = "tool-error" if self._result_is_error else "tool-success"
        prefix = "[ERR]" if self._result_is_error else "[OK]"
        yield Label(
            f"{prefix} {self._result_summary}",
            classes=f"tool-inline-summary {status_class}",
            markup=False,
        )
        if self._result_preview_lines:
            preview_count = len(self._result_preview_lines)
            preview_title = (
                f"Output Preview ({preview_count} line{'s' if preview_count != 1 else ''})"
            )
            yield Collapsible(
                *[
                    Static(
                        line,
                        classes="tool-result-preview",
                        markup=False,
                    )
                    for line in self._result_preview_lines
                ],
                title=preview_title,
                collapsed=not self._result_is_error,
                collapsed_symbol=">",
                expanded_symbol="v",
                classes="tool-collapsible tool-result-preview-toggle",
            )

    def _render_result_widgets(self) -> None:
        if not self._result_container:
            return
        for child in list(self._result_container.children):
            child.remove()
        for widget in self._compose_result_widgets():
            self._result_container.mount(widget)


class StreamingTextWidget(Static):
    """Widget for streaming text content - updates in place without recreating."""

    def __init__(self, initial_text: str = "", **kwargs):
        super().__init__(
            sanitize_terminal_text(initial_text),
            classes="streaming-content",
            markup=False,
            **kwargs,
        )
        self._text = initial_text

    def update_text(self, text: str) -> None:
        """Update the displayed text."""
        self._text = text
        self.update(sanitize_terminal_text(text))


class AssistantMessageWidget(VerticalGroup):
    """
    Widget for displaying an assistant message with streaming support.
    This widget allows incremental updates of text and tool uses without recreating the entire widget.
    Aligned with TypeScript's approach to streaming message display.
    """

    def __init__(self, message: Optional[Message] = None, **kwargs):
        super().__init__(**kwargs)
        self._text_content: str = ""
        self._tool_uses: List[ToolUseContent] = []
        self._tool_use_ids: set[str] = set()
        self._tool_widgets_by_id: dict[str, ToolUseWidget] = {}
        self._streaming_widget: Optional[StreamingTextWidget] = None
        self._tool_widgets: List[ToolUseWidget] = []
        self._content_container: Optional[VerticalGroup] = None
        self.add_class("message-block")
        self.add_class("assistant-message-block")
        if message:
            self.sync_from_message(message)

    def compose(self) -> ComposeResult:
        # Content container - will hold text and tool widgets
        with VerticalGroup(classes="message-content") as container:
            self._content_container = container
            if self._text_content:
                self._streaming_widget = StreamingTextWidget(self._text_content)
                yield self._streaming_widget
            for tool_use in self._tool_uses:
                tool_widget = ToolUseWidget(
                    tool_name=tool_use.name,
                    tool_input=tool_use.input,
                    tool_use_id=tool_use.id,
                )
                self._tool_widgets.append(tool_widget)
                if tool_use.id:
                    self._tool_widgets_by_id[tool_use.id] = tool_widget
                yield tool_widget

    def update_text(self, text: str) -> None:
        """Update the streaming text content"""
        self._text_content = text
        if self._streaming_widget:
            self._streaming_widget.update_text(text)
        elif text and self._content_container:
            self._streaming_widget = StreamingTextWidget(text)
            before_widget = self._tool_widgets[0] if self._tool_widgets else None
            self._content_container.mount(self._streaming_widget, before=before_widget)

    def add_tool_use(self, tool_use: ToolUseContent) -> Optional[ToolUseWidget]:
        """Add a tool use to the message and return its widget."""
        if tool_use.id and tool_use.id in self._tool_use_ids:
            return self._tool_widgets_by_id.get(tool_use.id)
        self._tool_uses.append(tool_use)
        if tool_use.id:
            self._tool_use_ids.add(tool_use.id)
        if self._content_container:
            tool_widget = ToolUseWidget(
                tool_name=tool_use.name,
                tool_input=tool_use.input,
                tool_use_id=tool_use.id,
            )
            self._content_container.mount(tool_widget)
            self._tool_widgets.append(tool_widget)
            if tool_use.id:
                self._tool_widgets_by_id[tool_use.id] = tool_widget
            return tool_widget
        return None

    def add_tool_result(
        self,
        tool_use_id: str,
        result: str,
        is_error: bool,
    ) -> bool:
        """Attach a tool result to an existing tool-use widget."""
        tool_widget = self._tool_widgets_by_id.get(tool_use_id)
        if not tool_widget:
            return False
        tool_widget.set_result(result, is_error)
        return True

    def get_tool_widgets(self) -> dict[str, ToolUseWidget]:
        """Expose rendered tool widgets by tool-use id."""
        return dict(self._tool_widgets_by_id)

    def sync_from_message(self, message: Message) -> None:
        """Ensure widget state matches the finalized assistant message."""
        for block in message.content:
            if isinstance(block, TextContent):
                self.update_text(block.text)
            elif isinstance(block, ToolUseContent):
                self.add_tool_use(block)

    def get_message(self) -> Message:
        """Build the current message from accumulated content"""
        content: List = []
        if self._text_content:
            content.append(TextContent(text=self._text_content))
        content.extend(self._tool_uses)
        return Message.assistant_message(content)


class ToolResultWidget(VerticalGroup):
    """Compact tool result widget inspired by the TypeScript tool UI components."""

    def __init__(
        self,
        tool_name: str,
        tool_input: dict,
        result: str,
        is_error: bool,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.tool_name = tool_name
        self.tool_input = tool_input
        self.result = result
        self.is_error = is_error
        self.add_class("message-block")
        self.add_class("tool-result-block")

    def compose(self) -> ComposeResult:
        status_class = "tool-error" if self.is_error else "tool-success"
        summary, preview_lines = summarize_tool_result(
            self.tool_name,
            self.tool_input,
            self.result,
            self.is_error,
        )

        yield Label("Tool", classes="message-role role-tool", markup=False)
        with VerticalGroup(classes="message-content tool-result-body"):
            prefix = "[ERR]" if self.is_error else "[OK]"
            yield Label(
                f"  {prefix} {summary}",
                classes=f"tool-result-summary {status_class}",
                markup=False,
            )
            if preview_lines:
                preview_count = len(preview_lines)
                preview_title = f"Output Preview ({preview_count} line{'s' if preview_count != 1 else ''})"
                with Collapsible(
                    title=preview_title,
                    collapsed=not self.is_error,
                    collapsed_symbol=">",
                    expanded_symbol="v",
                    classes="tool-collapsible tool-result-preview-toggle",
                ):
                    for line in preview_lines:
                        yield Static(
                            line,
                            classes="tool-result-preview",
                            markup=False,
                        )


class MessageWidget(VerticalGroup):
    """Widget for displaying a single message"""

    def __init__(self, message: Message, **kwargs):
        super().__init__(**kwargs)
        self.message = message
        self._streaming_widget: Optional[StreamingTextWidget] = None
        self.add_class("message-block")
        self.add_class(self._get_role_block_class())

    def compose(self) -> ComposeResult:
        # Role label with styling
        role_label, role_class = self._get_role_label()
        if self.message.type not in {MessageRole.USER, MessageRole.ASSISTANT}:
            yield Label(role_label, classes=f"message-role {role_class}", markup=False)

        # Content
        for block in self.message.content:
            if isinstance(block, TextContent):
                if block.text.strip():
                    # Use StreamingTextWidget for assistant messages to allow updates
                    if self.message.type == MessageRole.ASSISTANT:
                        self._streaming_widget = StreamingTextWidget(block.text)
                        yield self._streaming_widget
                    else:
                        yield Static(
                            sanitize_terminal_text(block.text),
                            classes="message-content",
                            markup=False,
                        )
            elif isinstance(block, ToolUseContent):
                yield ToolUseWidget(
                    tool_name=block.name,
                    tool_input=block.input,
                    tool_use_id=block.id,
                )
            elif isinstance(block, ToolResultContent):
                # Truncate long results
                content = block.content
                if len(content) > 500:
                    content = content[:500] + f"\n... ({len(block.content) - 500} more chars)"
                summary, preview_lines = summarize_tool_result(
                    "Tool",
                    {},
                    content,
                    block.is_error,
                )
                yield Static(
                    sanitize_terminal_text(summary),
                    classes="tool-result",
                    markup=False,
                )
                for line in preview_lines:
                    yield Static(
                        line,
                        classes="tool-result-preview",
                        markup=False,
                    )

    def update_streaming_text(self, text: str) -> None:
        """Update streaming text content for assistant messages"""
        if self._streaming_widget:
            self._streaming_widget.update_text(text)

    def _get_role_label(self) -> tuple[str, str]:
        role_map = {
            MessageRole.USER: ("You", "role-user"),
            MessageRole.ASSISTANT: ("Claude", "role-assistant"),
            MessageRole.SYSTEM: ("System", "role-system"),
            MessageRole.TOOL: ("Tool", "role-tool"),
        }
        return role_map.get(self.message.type, ("Unknown", "role-unknown"))

    def _get_role_block_class(self) -> str:
        role_map = {
            MessageRole.USER: "user-message-block",
            MessageRole.ASSISTANT: "assistant-message-block",
            MessageRole.SYSTEM: "system-message-block",
            MessageRole.TOOL: "tool-result-block",
        }
        return role_map.get(self.message.type, "assistant-message-block")


class MessageList(VerticalGroup):
    """Widget for displaying a list of messages"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._message_widgets: List[Container] = []  # Can be MessageWidget or AssistantMessageWidget
        self._auto_follow_output = True
        self._suppress_scroll_tracking = False

    def on_mount(self) -> None:
        """Track manual scrolling so auto-follow only applies while pinned to bottom."""
        try:
            content_area = self.screen.query_one("#content-area", ScrollableContainer)
            self.watch(content_area, "scroll_y", self._on_content_scroll, init=False)
        except Exception:
            pass

    def _on_content_scroll(self, _scroll_y: float) -> None:
        """Disable auto-follow when the user scrolls away from the bottom."""
        if self._suppress_scroll_tracking:
            return
        try:
            content_area = self.screen.query_one("#content-area", ScrollableContainer)
            self._auto_follow_output = (
                content_area.scroll_y >= max(content_area.max_scroll_y - 1, 0)
            )
        except Exception:
            self._auto_follow_output = True

    def _scroll_to_latest(self) -> None:
        """Keep the parent scroll container pinned to the latest output."""
        try:
            content_area = self.screen.query_one("#content-area", ScrollableContainer)
            self._suppress_scroll_tracking = True
            content_area.scroll_end(
                animate=False,
                force=True,
                immediate=True,
                x_axis=False,
            )
            self.set_timer(0.001, self._finish_programmatic_scroll)
        except Exception:
            # Layout may not be ready on the first streamed chunk.
            self._suppress_scroll_tracking = False

    def _finish_programmatic_scroll(self) -> None:
        """Re-enable manual scroll tracking after an automatic scroll."""
        self._auto_follow_output = True
        self._suppress_scroll_tracking = False

    def should_auto_follow_output(self) -> bool:
        """Return True when streaming output should keep following the bottom."""
        return self._auto_follow_output

    def reset_auto_follow_output(self) -> None:
        """Re-enable transcript auto-follow for a fresh user request."""
        self._auto_follow_output = True

    def schedule_scroll_to_latest(self, auto_follow: bool = True) -> None:
        """Scroll after the current DOM/layout update flushes."""
        if auto_follow:
            self.call_after_refresh(
                lambda: self.call_after_refresh(self._scroll_to_latest)
            )

    def add_message(self, message: Message, auto_follow: bool = True) -> None:
        """Add a message to the list"""
        widget = MessageWidget(message)
        self.mount(widget)
        self._message_widgets.append(widget)
        self.schedule_scroll_to_latest(auto_follow)

    def add_tool_result(
        self,
        tool_name: str,
        tool_input: dict,
        result: str,
        is_error: bool,
        auto_follow: bool = True,
    ) -> None:
        """Add a compact tool result widget."""
        widget = ToolResultWidget(
            tool_name=tool_name,
            tool_input=tool_input,
            result=result,
            is_error=is_error,
        )
        self.mount(widget)
        self._message_widgets.append(widget)
        self.schedule_scroll_to_latest(auto_follow)

    def create_assistant_widget(
        self,
        message: Optional[Message] = None,
        auto_follow: bool = True,
    ) -> AssistantMessageWidget:
        """Create a new assistant message widget for streaming"""
        widget = AssistantMessageWidget(message=message)
        self.mount(widget)
        self._message_widgets.append(widget)
        self.schedule_scroll_to_latest(auto_follow)
        return widget

    def clear(self) -> None:
        """Clear all messages"""
        for widget in self._message_widgets:
            widget.remove()
        self._message_widgets = []


class REPLScreen(Screen):
    """Main REPL screen - aligned with TypeScript REPL.tsx"""

    def __init__(
        self,
        query_engine: QueryEngine,
        model_name: str = "claude-sonnet-4-6",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.query_engine = query_engine
        self.model_name = model_name
        self._is_processing = False
        self._current_assistant_widget: Optional[AssistantMessageWidget] = None
        self._current_text = ""
        self._show_welcome = True
        self._tool_use_context: dict[str, ToolUseContent] = {}
        self._tool_widget_context: dict[str, ToolUseWidget] = {}

    def compose(self) -> ComposeResult:
        # Scrollable content area
        with ScrollableContainer(id="content-area"):
            # Welcome widget - shown initially, hidden after first message
            yield WelcomeWidget(
                id="welcome-widget",
                model_name=self.model_name,
                cwd=os.getcwd()
            )
            # Message list (initially empty)
            yield MessageList(id="message-list")

        # Input area - always visible at bottom
        with VerticalGroup(id="input-area"):
            with Horizontal(id="processing-row"):
                yield LoadingIndicator(id="processing-indicator")
                yield Label("Working...", id="processing-label", markup=False)
            yield Input(
                placeholder="Type your message and press Enter",
                id="user-input"
            )

    async def on_mount(self) -> None:
        """Called when screen is mounted"""
        input_widget = self.query_one("#user-input", Input)
        input_widget.focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission"""
        if event.input.id == "user-input":
            event.stop()
            self._start_message_submission(event.value)

    def _hide_welcome_widget(self) -> None:
        """Hide the welcome widget after the first prompt."""
        if not self._show_welcome:
            return
        try:
            welcome_widget = self.query_one("#welcome-widget", WelcomeWidget)
            welcome_widget.display = False
        except Exception:
            pass
        self._show_welcome = False

    def _set_processing_state(self, is_processing: bool) -> None:
        """Update prompt input state while a query is running."""
        self._is_processing = is_processing
        input_widget = self.query_one("#user-input", Input)
        processing_row = self.query_one("#processing-row", Horizontal)
        input_widget.disabled = is_processing
        processing_row.display = is_processing
        input_widget.placeholder = (
            "Claude is responding..."
            if is_processing
            else "Type your message and press Enter"
        )

    def _reset_streaming_state(self) -> None:
        """Prepare for a fresh assistant response."""
        self._current_text = ""
        self._current_assistant_widget = None

    def _start_message_submission(self, submitted_value: str) -> None:
        """Queue a prompt submission without blocking the UI event loop."""
        if self._is_processing:
            return

        input_widget = self.query_one("#user-input", Input)
        user_text = submitted_value.strip()

        if not user_text:
            return

        # Only a literal "exit" command should close the TUI.
        if user_text.lower() == "exit":
            self.app.exit()
            return

        self._hide_welcome_widget()
        input_widget.value = ""
        self._reset_streaming_state()
        self._tool_use_context = {}
        self._tool_widget_context = {}
        try:
            message_list = self.query_one("#message-list", MessageList)
            message_list.reset_auto_follow_output()
        except Exception:
            pass
        self._set_processing_state(True)
        self.refresh()
        self.run_worker(
            self._process_message(user_text),
            group="query",
            exclusive=True,
            exit_on_error=False,
        )

    async def _process_message(self, user_text: str) -> None:
        """Run a query in the background so the TUI stays responsive."""
        message_list = self.query_one("#message-list", MessageList)
        try:
            async for event in self.query_engine.submit_message(user_text):
                await self._handle_query_event(event, message_list)
                await asyncio.sleep(0)

        except Exception as e:
            error_msg = Message.system_message(f"Error: {str(e)}")
            message_list.add_message(error_msg)

        finally:
            self._set_processing_state(False)
            input_widget = self.query_one("#user-input", Input)
            input_widget.focus()

    def _ensure_assistant_widget(
        self,
        message_list: MessageList,
        message: Optional[Message] = None,
        auto_follow: bool = True,
    ) -> AssistantMessageWidget:
        """Return the live assistant widget for the current response."""
        if not self._current_assistant_widget:
            self._current_assistant_widget = message_list.create_assistant_widget(
                message=message,
                auto_follow=auto_follow,
            )
        elif message:
            self._current_assistant_widget.sync_from_message(message)
        return self._current_assistant_widget

    async def _handle_query_event(self, event: QueryEvent, message_list: MessageList) -> None:
        """
        Handle a query event - aligned with TypeScript handleMessageFromStream in messages.ts

        Key difference from before: we use AssistantMessageWidget which allows
        incremental updates without recreating the entire widget.
        """
        if isinstance(event, TextEvent):
            auto_follow = message_list.should_auto_follow_output()
            # Accumulate text
            self._current_text += event.text

            # Create assistant widget on first text if not exists
            assistant_widget = self._ensure_assistant_widget(
                message_list,
                auto_follow=auto_follow,
            )

            # Update the text in the existing widget (no recreation)
            assistant_widget.update_text(self._current_text)
            message_list.schedule_scroll_to_latest(auto_follow)

        elif isinstance(event, ToolUseEvent):
            auto_follow = message_list.should_auto_follow_output()
            # Create tool use content
            tool_use = ToolUseContent(
                id=event.tool_use_id,
                name=event.tool_name,
                input=event.input,
            )
            self._tool_use_context[event.tool_use_id] = tool_use
            existing_widget = self._tool_widget_context.get(event.tool_use_id)
            if existing_widget:
                message_list.schedule_scroll_to_latest(auto_follow)
                return
            # Ensure we have an assistant widget
            assistant_widget = self._ensure_assistant_widget(
                message_list,
                auto_follow=auto_follow,
            )

            # Add tool use to the existing widget (no recreation)
            tool_widget = assistant_widget.add_tool_use(tool_use)
            if tool_widget:
                self._tool_widget_context[event.tool_use_id] = tool_widget
            message_list.schedule_scroll_to_latest(auto_follow)

        elif isinstance(event, ToolResultEvent):
            auto_follow = message_list.should_auto_follow_output()
            tool_widget = self._tool_widget_context.get(event.tool_use_id)
            merged_result = False
            if tool_widget:
                tool_widget.set_result(event.result, event.is_error)
                merged_result = True
            elif self._current_assistant_widget:
                merged_result = self._current_assistant_widget.add_tool_result(
                    event.tool_use_id,
                    event.result,
                    event.is_error,
                )

            if merged_result:
                message_list.schedule_scroll_to_latest(auto_follow)
            else:
                tool_use = self._tool_use_context.get(event.tool_use_id)
                tool_name = tool_use.name if tool_use else "Tool"
                tool_input = tool_use.input if tool_use else {}
                message_list.add_tool_result(
                    tool_name=tool_name,
                    tool_input=tool_input,
                    result=event.result,
                    is_error=event.is_error,
                    auto_follow=auto_follow,
                )

        elif isinstance(event, MessageCompleteEvent):
            # Handle message complete - user messages get added here
            if event.message:
                auto_follow = message_list.should_auto_follow_output()
                if event.message.type == MessageRole.ASSISTANT:
                    assistant_widget = self._ensure_assistant_widget(
                        message_list,
                        event.message,
                        auto_follow=auto_follow,
                    )
                    self._tool_widget_context.update(assistant_widget.get_tool_widgets())
                    self._current_text = event.message.get_text()
                    message_list.schedule_scroll_to_latest(auto_follow)
                elif event.message.type != MessageRole.TOOL:
                    message_list.add_message(event.message, auto_follow=auto_follow)

        elif isinstance(event, TurnCompleteEvent):
            self._reset_streaming_state()

        elif isinstance(event, ErrorEvent):
            error_msg = Message.system_message(f"Error: {event.error}")
            message_list.add_message(error_msg)


class ClaudeCodeApp(App):
    """Main Claude Code application - aligned with TypeScript App.tsx"""

    CSS = TUI_CSS
    BINDINGS = []

    SCREENS = {"repl": REPLScreen}

    def __init__(
        self,
        query_engine: QueryEngine,
        model_name: str = "claude-sonnet-4-6",
        **kwargs
    ):
        super().__init__(**kwargs)
        self.query_engine = query_engine
        self.model_name = model_name

    async def on_mount(self) -> None:
        """Initialize and push the REPL screen on mount"""
        # Initialize the query engine (creates HTTP client)
        await self.query_engine.initialize()
        await self.push_screen(REPLScreen(self.query_engine, self.model_name))

    async def on_unmount(self) -> None:
        """Clean up resources on exit"""
        await self.query_engine.close()
