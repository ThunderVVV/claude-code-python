"""Message-related widgets for the TUI"""

from __future__ import annotations

import logging
from typing import List, Optional
from textual.app import ComposeResult
from textual.content import Content, Span
from textual.containers import Container, VerticalGroup, ScrollableContainer
from textual.widgets import Collapsible, Label, RichLog, Static

from claude_code.core.messages import (
    Message,
    MessageRole,
    TextContent,
    ThinkingContent,
    ToolUseContent,
    ToolResultContent,
)
from claude_code.ui.diff_view import DiffView
from claude_code.ui.streaming_markdown import StreamingMarkdownWidget
from claude_code.ui.utils import (
    sanitize_terminal_text,
    summarize_tool_result,
    summarize_tool_use,
    format_tool_input_details,
    TOOL_RESULT_TRUNCATE_LENGTH,
)
from claude_code.utils.logging_config import log_full_exception

logger = logging.getLogger(__name__)


# Role configuration - single source of truth
ROLE_CONFIG = {
    MessageRole.USER: {
        "label": "You",
        "role_class": "role-user",
        "block_class": "user-message-block",
    },
    MessageRole.ASSISTANT: {
        "label": "Claude",
        "role_class": "role-assistant",
        "block_class": "assistant-message-block",
    },
    MessageRole.SYSTEM: {
        "label": "System",
        "role_class": "role-system",
        "block_class": "system-message-block",
    },
    MessageRole.TOOL: {
        "label": "Tool",
        "role_class": "role-tool",
        "block_class": "tool-result-block",
    },
}


class ThinkingBlockWidget(VerticalGroup):
    """Collapsible widget for thinking/reasoning content."""

    def __init__(self, initial_thinking: str = "", **kwargs):
        super().__init__(**kwargs)
        self._thinking = initial_thinking
        self._content_widget: Optional[Static] = None
        self.add_class("thinking-block")

    def compose(self) -> ComposeResult:
        with Collapsible(
            title="Thinking...",
            collapsed=True,
            collapsed_symbol=">",
            expanded_symbol="v",
            classes="thinking-collapsible",
        ):
            self._content_widget = Static(
                sanitize_terminal_text(self._thinking),
                classes="thinking-content",
            )
            yield self._content_widget

    async def append_thinking(self, thinking: str) -> None:
        """Append streamed thinking content."""
        self._thinking += thinking
        if self._content_widget:
            self._content_widget.update(sanitize_terminal_text(self._thinking))

    async def update_thinking(self, thinking: str) -> None:
        """Update the thinking content."""
        self._thinking = thinking
        if self._content_widget:
            self._content_widget.update(sanitize_terminal_text(thinking))
            self.refresh(layout=True)

    async def finish_streaming(self) -> None:
        """No-op for plain text widget."""
        pass


class ToolResultLogWidget(RichLog):
    """Widget for displaying tool results with auto-scroll and syntax highlighting."""

    DEFAULT_CSS = """
    ToolResultLogWidget {
        width: 100%;
        height: auto;
        min-height: 1;
        max-height: 10;
        overflow-x: hidden;
        scrollbar-visibility: hidden;
        background: $surface;
        padding: 1 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(
            highlight=True,
            max_lines=1000,
            auto_scroll=True,
            wrap=True,
            markup=False,
            min_width=1,
            **kwargs,
        )
        self.add_class("tool-result-log")

    def write_line(
        self, line: str, scroll_end: bool | None = None
    ) -> "ToolResultLogWidget":
        """Compatibility helper matching Log.write_line."""
        return self.write(line, scroll_end=scroll_end)


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
        self._result: Optional[tuple[str, bool]] = None  # (summary, is_error)
        self._output_lines: List[str] = []
        self._collapsible: Optional[Collapsible] = None
        self._container: Optional[VerticalGroup] = None
        self._did_auto_expand = False
        self.add_class("tool-use-block")

    def compose(self) -> ComposeResult:
        with Collapsible(
            title=self._build_title(),
            collapsed=not self._should_auto_expand(),
            collapsed_symbol=">",
            expanded_symbol="v",
            classes="tool-collapsible tool-use-details",
        ) as collapsible:
            self._collapsible = collapsible
            with VerticalGroup(classes="tool-detail-body") as container:
                self._container = container
                yield from self._compose_details()

    def set_result(self, result: str, is_error: bool) -> None:
        """Attach the tool result to the existing tool-use block."""
        summary, output_lines = summarize_tool_result(
            self.tool_name,
            self.tool_input,
            result,
            is_error,
        )
        self._result = (summary, is_error)
        self._output_lines = output_lines

        if self._collapsible:
            self._collapsible.title = self._build_title()
            self._auto_expand_once()
        if self._container and self._container.is_mounted:
            self._render_details()

    def update_tool_input(self, tool_name: str, tool_input: dict) -> None:
        """Refresh the tool summary/details when fuller input arrives later."""
        self.tool_name = tool_name
        self.tool_input = tool_input
        if self._collapsible:
            self._collapsible.title = self._build_title()
            self._auto_expand_once()
        if self._container and self._container.is_mounted:
            self._render_details()

    def on_mount(self) -> None:
        """Refresh after mount in case results arrived early."""
        if self._collapsible:
            self._collapsible.title = self._build_title()
            self._auto_expand_once()
        if self._container and self._container.is_mounted and self._result:
            self._render_details()

    def _build_title(self) -> Content:
        """Return the current single-line title for the tool call."""
        if self._result is None:
            return Content.from_text(
                sanitize_terminal_text(
                    summarize_tool_use(self.tool_name, self.tool_input)
                ),
                markup=False,
            )
        summary, is_error = self._result
        summary = sanitize_terminal_text(summary)
        status_style = "$error" if is_error else "$success"
        return Content(f"● {summary}", spans=[Span(0, 1, status_style)])

    def _should_auto_expand(self) -> bool:
        """Return True when this tool block should start expanded."""
        return self.tool_name in {"Edit", "Write"}

    def _auto_expand_once(self) -> None:
        """Expand Edit blocks once without overriding later manual collapse."""
        if self._did_auto_expand or not self._should_auto_expand():
            return
        if self._collapsible:
            self._collapsible.collapsed = False
            self._did_auto_expand = True

    def _compose_details(self) -> ComposeResult:
        """Compose the detail widgets."""
        # Input parameters
        exclude_keys = self._get_input_exclusions()
        detail_lines = format_tool_input_details(self.tool_input, exclude_keys)
        if detail_lines:
            for line in detail_lines:
                yield Static(line, classes="tool-param", markup=False)
        elif self._result is None:
            yield Static("Waiting for parameters", classes="tool-param", markup=False)

        # Diff view or output
        diff_view = self._build_diff_view()
        if diff_view is not None:
            yield diff_view
        elif self._result is not None:
            yield Static("Output:", classes="tool-output-label", markup=False)
            if self._output_lines:
                log_widget = ToolResultLogWidget(classes="tool-result-log")
                yield log_widget
            else:
                yield Static("(no output)", classes="tool-result-preview", markup=False)

    def _get_input_exclusions(self) -> set[str]:
        """Hide raw diff payloads once a diff view is available."""
        if self._build_diff_view() is None:
            return set()
        if self.tool_name == "Edit":
            return {"old_string", "new_string"}
        if self.tool_name == "Write":
            return {"content"}
        return set()

    def _build_diff_view(self) -> DiffView | None:
        """Build an inline diff widget for successful file-editing tool calls."""
        if self._result is None or self._result[1]:
            return None

        file_path = str(self.tool_input.get("file_path", "")).strip()
        if not file_path:
            return None

        # Get base text
        if self.tool_name == "Edit":
            old_string = self.tool_input.get("old_string")
            new_string = self.tool_input.get("new_string")
            if not isinstance(old_string, str) or not isinstance(new_string, str):
                return None
            old_text, new_text = old_string, new_string
        elif self.tool_name == "Write":
            content = self.tool_input.get("content")
            if not isinstance(content, str):
                return None
            old_text, new_text = "", content
        else:
            return None

        # Try to get full file content
        try:
            from claude_code.tools.file_utils import expand_path

            full_path = expand_path(file_path)

            if self.tool_name == "Edit":
                replace_all = self.tool_input.get("replace_all", False)
                with open(full_path, "r", encoding="utf-8") as f:
                    current_content = f.read()

                # Reverse replacement to reconstruct original file
                test_old = current_content
                if replace_all:
                    test_old = test_old.replace(new_string, old_string)
                else:
                    test_old = test_old.replace(new_string, old_string, 1)

                if test_old != current_content:
                    old_text, new_text = test_old, current_content
        except Exception:
            pass

        try:
            return DiffView(
                file_path,
                file_path,
                sanitize_terminal_text(old_text),
                sanitize_terminal_text(new_text),
                classes="tool-edit-diff",
            )
        except Exception:
            return None

    def _render_details(self) -> None:
        """Re-render the detail widgets."""
        if not self._container:
            return
        for child in list(self._container.children):
            child.remove()
        for widget in self._compose_details():
            self._container.mount(widget)

        # Write output lines to the Log widget if present
        if self._output_lines:
            try:
                log_widget = self._container.query_one(ToolResultLogWidget)
                for line in self._output_lines:
                    log_widget.write_line(line)
            except Exception:
                pass


class MessageWidget(VerticalGroup):
    """
    Widget for displaying a message with optional streaming support.
    Consolidates both static and streaming message display.
    """

    def __init__(
        self, message: Optional[Message] = None, streaming: bool = False, **kwargs
    ):
        super().__init__(**kwargs)
        self._streaming = streaming
        self._message = message

        # Internal state for streaming
        self._thinking_content: str = ""
        self._text_content: str = ""
        self._tool_uses: List[ToolUseContent] = []
        self._tool_use_ids: set[str] = set()
        self._tool_widgets_by_id: dict[str, ToolUseWidget] = {}

        # Widget references
        self._thinking_widget: Optional[ThinkingBlockWidget] = None
        self._streaming_widget: Optional[StreamingMarkdownWidget] = None
        self._content_container: Optional[VerticalGroup] = None

        self.add_class("message-block")
        if message:
            role_config = ROLE_CONFIG.get(
                message.type, ROLE_CONFIG[MessageRole.ASSISTANT]
            )
            self.add_class(role_config["block_class"])
            self._load_message(message)
        else:
            self.add_class("assistant-message-block")

    def _load_message(self, message: Message) -> None:
        """Seed internal state from a message."""
        for block in message.content:
            if isinstance(block, ThinkingContent):
                self._thinking_content = block.thinking
            elif isinstance(block, TextContent):
                self._text_content = block.text
            elif isinstance(block, ToolUseContent):
                self._tool_uses.append(block)
                if block.id:
                    self._tool_use_ids.add(block.id)

    @property
    def message(self) -> Optional[Message]:
        """Backward compatibility property."""
        return self._message

    def compose(self) -> ComposeResult:
        if self._streaming:
            yield from self._compose_streaming_message()
        elif self._message:
            yield from self._compose_static_message(self._message)
        else:
            yield from self._compose_streaming_message()

    def _compose_static_message(self, message: Message) -> ComposeResult:
        """Compose a static (non-streaming) message."""
        role_config = ROLE_CONFIG.get(message.type, ROLE_CONFIG[MessageRole.ASSISTANT])

        # Role label
        if message.type not in {MessageRole.USER, MessageRole.ASSISTANT}:
            yield Label(
                role_config["label"],
                classes=f"message-role {role_config['role_class']}",
                markup=False,
            )

        # Web enabled flag for user messages
        if message.type == MessageRole.USER and getattr(message, "web_enabled", False):
            yield Label("@web enabled", classes="web-enabled-label", markup=False)

        # File expansions for user messages
        if message.type == MessageRole.USER and message.file_expansions:
            for expansion in message.file_expansions:
                # Use a simpler approach - format content first
                expansion_content = "\n".join(
                    self._format_file_expansion_lines(expansion)
                )
                with Collapsible(
                    title=f"@{expansion.display_path}",
                    collapsed=True,
                    collapsed_symbol=">",
                    expanded_symbol="v",
                    classes="file-expansion-collapsible",
                ):
                    yield Static(
                        sanitize_terminal_text(expansion_content),
                        classes="file-expansion-content",
                        markup=False,
                    )

        # Content blocks
        for block in message.content:
            if isinstance(block, ThinkingContent):
                if block.thinking.strip():
                    yield ThinkingBlockWidget(block.thinking)
            elif isinstance(block, TextContent):
                if block.text.strip():
                    if message.type == MessageRole.ASSISTANT:
                        self._streaming_widget = StreamingMarkdownWidget(block.text)
                        yield self._streaming_widget
                    else:
                        display_text = (
                            message.original_text
                            if message.file_expansions
                            else block.text
                        )
                        yield Static(
                            sanitize_terminal_text(display_text),
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
                content = block.content
                if len(content) > TOOL_RESULT_TRUNCATE_LENGTH:
                    content = (
                        content[:TOOL_RESULT_TRUNCATE_LENGTH]
                        + f"\n... ({len(block.content) - TOOL_RESULT_TRUNCATE_LENGTH} more chars)"
                    )
                summary, preview_lines = summarize_tool_result(
                    "Tool", {}, content, block.is_error
                )
                yield Static(
                    sanitize_terminal_text(summary), classes="tool-result", markup=False
                )
                if preview_lines:
                    log_widget = ToolResultLogWidget(classes="tool-result-log")
                    yield log_widget
                    for line in preview_lines:
                        log_widget.write_line(line)

    def _compose_streaming_message(self) -> ComposeResult:
        """Compose a streaming message container."""
        with VerticalGroup(classes="message-content") as container:
            self._content_container = container
            if self._thinking_content:
                self._thinking_widget = ThinkingBlockWidget(self._thinking_content)
                yield self._thinking_widget
            if self._text_content:
                self._streaming_widget = StreamingMarkdownWidget(self._text_content)
                yield self._streaming_widget
            for tool_use in self._tool_uses:
                tool_widget = ToolUseWidget(
                    tool_name=tool_use.name,
                    tool_input=tool_use.input,
                    tool_use_id=tool_use.id,
                )
                if tool_use.id:
                    self._tool_widgets_by_id[tool_use.id] = tool_widget
                yield tool_widget

    def _format_file_expansion_lines(self, expansion) -> List[str]:
        """Format file expansion content as lines for the tool result log widget."""
        lines = expansion.content.splitlines()
        formatted_lines = [f"@{expansion.display_path}:"]
        for i, line in enumerate(lines, start=1):
            formatted_lines.append(f"{i:6}\t{line}")
        return formatted_lines

    # Streaming API methods
    async def append_thinking(self, thinking: str) -> None:
        """Append streamed thinking content."""
        if not thinking:
            return
        self._thinking_content += thinking
        if self._thinking_widget:
            await self._thinking_widget.append_thinking(thinking)
        elif self._content_container:
            self._thinking_widget = ThinkingBlockWidget(self._thinking_content)
            await self._content_container.mount(self._thinking_widget)
            self.refresh(layout=True)

    async def update_thinking(self, thinking: str) -> None:
        """Update the streaming thinking content."""
        self._thinking_content = thinking
        if self._thinking_widget:
            await self._thinking_widget.update_thinking(thinking)
            self.refresh(layout=True)
        elif thinking and self._content_container:
            self._thinking_widget = ThinkingBlockWidget(thinking)
            await self._content_container.mount(self._thinking_widget)
            self.refresh(layout=True)

    async def append_text(self, text: str) -> None:
        """Append streamed text content."""
        if not text:
            return
        self._text_content += text
        if self._streaming_widget:
            await self._streaming_widget.append_text(text)
        elif self._content_container:
            self._streaming_widget = StreamingMarkdownWidget(self._text_content)
            await self._content_container.mount(self._streaming_widget)
            self.refresh(layout=True)

    async def update_text(self, text: str) -> None:
        """Update the streaming text content."""
        self._text_content = text
        if self._streaming_widget:
            await self._streaming_widget.set_markdown_text(text)
            self.refresh(layout=True)
        elif text and self._content_container:
            self._streaming_widget = StreamingMarkdownWidget(text)
            await self._content_container.mount(self._streaming_widget)
            self.refresh(layout=True)

    async def add_tool_use(self, tool_use: ToolUseContent) -> Optional[ToolUseWidget]:
        """Add a tool use to the message and return its widget."""
        if tool_use.id and tool_use.id in self._tool_use_ids:
            self._update_tool_use(tool_use)
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
            if tool_use.id:
                self._tool_widgets_by_id[tool_use.id] = tool_widget
            await self._content_container.mount(tool_widget)
            self.refresh(layout=True)
            return tool_widget
        return None

    def _update_tool_use(self, tool_use: ToolUseContent) -> None:
        """Apply fuller tool metadata to an existing streamed tool block."""
        if not tool_use.id:
            return
        for existing in self._tool_uses:
            if existing.id == tool_use.id:
                existing.name = tool_use.name
                existing.input = tool_use.input
                break
        widget = self._tool_widgets_by_id.get(tool_use.id)
        if widget:
            widget.update_tool_input(tool_use.name, tool_use.input)

    def get_tool_widgets(self) -> dict[str, ToolUseWidget]:
        """Expose rendered tool widgets by tool-use id."""
        return dict(self._tool_widgets_by_id)

    async def finish_streaming(self) -> None:
        """Flush and stop any active markdown streams."""
        if self._thinking_widget:
            await self._thinking_widget.finish_streaming()
        if self._streaming_widget:
            await self._streaming_widget.finish_streaming()


class MessageList(VerticalGroup):
    """Widget for displaying a list of messages"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._message_widgets: List[Container] = []
        self._auto_follow_output = True
        self._suppress_scroll_tracking = False

    def on_mount(self) -> None:
        """Track manual scrolling so auto-follow only applies while pinned to bottom."""
        try:
            content_area = self.screen.query_one("#content-area", ScrollableContainer)
            self.watch(content_area, "scroll_y", self._on_content_scroll, init=False)
        except Exception as e:
            log_full_exception(logger, "Failed to setup scroll tracking", e)

    def _on_content_scroll(self, _scroll_y: float) -> None:
        """Disable auto-follow when the user scrolls away from the bottom."""
        if self._suppress_scroll_tracking:
            return
        try:
            content_area = self.screen.query_one("#content-area", ScrollableContainer)
            self._auto_follow_output = content_area.scroll_y >= max(
                content_area.max_scroll_y - 1, 0
            )
        except Exception as e:
            log_full_exception(logger, "Failed to check scroll position", e)
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
        except Exception as e:
            log_full_exception(logger, "Failed to scroll to latest", e)
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
            self.call_after_refresh(self._scroll_to_latest)

    async def add_message(self, message: Message, auto_follow: bool = True) -> None:
        """Add a message to the list"""
        widget = MessageWidget(message)
        await self.mount(widget)
        self._message_widgets.append(widget)
        self.schedule_scroll_to_latest(auto_follow)

    async def create_streaming_widget(
        self,
        message: Optional[Message] = None,
        auto_follow: bool = True,
    ) -> MessageWidget:
        """Create a new streaming message widget for assistant responses"""
        widget = MessageWidget(message=message, streaming=True)
        await self.mount(widget)
        self._message_widgets.append(widget)
        self.schedule_scroll_to_latest(auto_follow)
        return widget

    def clear(self) -> None:
        """Clear all messages"""
        for widget in self._message_widgets:
            widget.remove()
        self._message_widgets.clear()
