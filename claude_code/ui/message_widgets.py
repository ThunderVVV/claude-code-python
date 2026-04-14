"""Message-related widgets for the TUI"""

from __future__ import annotations

import logging
import re
from typing import Callable, List, Optional
from textual.app import ComposeResult
from textual.content import Content, Span
from textual.containers import Container, VerticalGroup, ScrollableContainer
from textual.reactive import reactive
from textual.events import Click
from textual.widgets import Collapsible, Label, Static
from textual.widgets._collapsible import CollapsibleTitle

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


class FlushCollapsibleTitle(Static, can_focus=True):
    """Collapsible title that doesn't reserve leading space for an empty symbol."""

    BINDING_GROUP_TITLE = "Collapsible"
    ALLOW_SELECT = True
    collapsed = reactive(True)
    label = reactive(Content("Toggle"))

    def __init__(
        self,
        *,
        label: str | Content,
        collapsed_symbol: str,
        expanded_symbol: str,
        collapsed: bool,
    ) -> None:
        super().__init__()
        self.collapsed_symbol = collapsed_symbol
        self.expanded_symbol = expanded_symbol
        self.label = Content.from_text(label)
        self.collapsed = collapsed

    class Toggle(CollapsibleTitle.Toggle):
        """Request toggle."""

    async def _on_click(self, event) -> None:
        event.stop()
        self.post_message(self.Toggle())

    def action_toggle_collapsible(self) -> None:
        self.post_message(self.Toggle())

    def validate_label(self, label: str | Content) -> Content:
        return Content.from_text(label)

    def _update_label(self) -> None:
        assert isinstance(self.label, Content)
        symbol = self.collapsed_symbol if self.collapsed else self.expanded_symbol
        if symbol:
            self.update(Content.assemble(symbol, " ", self.label))
        else:
            self.update(self.label)

    def _watch_label(self) -> None:
        self._update_label()

    def _watch_collapsed(self, collapsed: bool) -> None:
        self._update_label()


class FlushCollapsible(Collapsible):
    """Collapsible that uses a title widget with no implicit left gap."""

    def __init__(
        self,
        *children,
        title: str = "Toggle",
        collapsed: bool = True,
        collapsed_symbol: str = "▶",
        expanded_symbol: str = "▼",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(
            *children,
            title=title,
            collapsed=collapsed,
            collapsed_symbol=collapsed_symbol,
            expanded_symbol=expanded_symbol,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )
        self._title = FlushCollapsibleTitle(
            label=title,
            collapsed_symbol=collapsed_symbol,
            expanded_symbol=expanded_symbol,
            collapsed=collapsed,
        )

    def _on_flush_collapsible_title_toggle(
        self, event: FlushCollapsibleTitle.Toggle
    ) -> None:
        event.stop()
        self.collapsed = not self.collapsed


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
        "label": "",
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
        self._collapsible: Optional[Collapsible] = None
        self.add_class("thinking-block")

    def compose(self) -> ComposeResult:
        with FlushCollapsible(
            title="● Thinking...",
            collapsed=True,
            collapsed_symbol="",
            expanded_symbol="",
            classes="thinking-collapsible",
        ) as collapsible:
            self._collapsible = collapsible
            self._content_widget = Static(
                sanitize_terminal_text(self._thinking),
                classes="thinking-content",
            )
            yield self._content_widget

    def on_mount(self) -> None:
        self.apply_transcript_collapsible_mode()

    def apply_transcript_collapsible_mode(self) -> None:
        """Enforce the current application-wide transcript collapsible mode."""
        if not self._collapsible:
            return
        desired_collapsed = not self._transcript_collapsible_mode_expanded()
        if self._collapsible.collapsed != desired_collapsed:
            self._collapsible.collapsed = desired_collapsed

    def _transcript_collapsible_mode_expanded(self) -> bool:
        """Read the application-wide transcript collapsible mode from the screen."""
        try:
            return bool(getattr(self.screen, "_transcript_collapsible_mode_expanded", False))
        except Exception:
            return False

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


class ToolResultBlockWidget(Static):
    """Plain static tool-result block that expands in place when clicked."""

    VISIBLE_LINE_LIMIT = 5

    def __init__(self, output_lines: List[str], **kwargs):
        super().__init__("", markup=False, **kwargs)
        self._output_lines = output_lines
        self._expanded = False
        self.add_class("tool-result-block")
        self.add_class("tool-result-static")

    def on_mount(self) -> None:
        self._refresh_text()

    def _current_text(self) -> str:
        if not self._output_lines:
            return "Output:\n(no output)"

        hidden_count = max(len(self._output_lines) - self.VISIBLE_LINE_LIMIT, 0)
        if self._expanded or hidden_count == 0:
            body_lines = self._output_lines
            tail = []
        else:
            body_lines = self._output_lines[: self.VISIBLE_LINE_LIMIT]
            tail = [f"... {hidden_count} lines (Click to expand)"]

        text_lines = ["Output:"]
        text_lines.extend(sanitize_terminal_text(line) for line in body_lines)
        text_lines.extend(tail)
        return "\n".join(text_lines)

    def on_click(self, event: Click) -> None:
        if len(self._output_lines) <= self.VISIBLE_LINE_LIMIT:
            return
        self._expanded = not self._expanded
        self._refresh_text()
        event.stop()

    def _refresh_text(self) -> None:
        self.update(self._current_text())


class ToolUseWidget(VerticalGroup):
    """Widget for displaying tool use information"""

    def __init__(
        self,
        tool_name: str,
        tool_input: dict,
        tool_use_id: str,
        streaming_context: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.tool_name = tool_name
        self.tool_input = tool_input
        self.tool_use_id = tool_use_id
        self._streaming_context = streaming_context
        self._result: Optional[tuple[str, bool]] = None  # (summary, is_error)
        self._output_lines: List[str] = []
        self._collapsible: Optional[Collapsible] = None
        self._container: Optional[VerticalGroup] = None
        self._did_auto_expand = False
        self._details_dirty = True
        self._details_rendered = False
        self.add_class("tool-use-block")

    def compose(self) -> ComposeResult:
        with FlushCollapsible(
            title=self._build_title(),
            collapsed=not self._should_auto_expand(),
            collapsed_symbol="",
            expanded_symbol="",
            classes="tool-collapsible tool-use-details",
        ) as collapsible:
            self._collapsible = collapsible
            with VerticalGroup(classes="tool-detail-body") as container:
                self._container = container
                # Details are mounted lazily only when expanded, to avoid
                # expensive diff/markdown rendering for collapsed tool blocks.
                yield Static("", classes="tool-detail-placeholder", markup=False)

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
            self.apply_transcript_collapsible_mode()
        self._details_dirty = True
        self._render_details_if_needed()

    def update_tool_input(self, tool_name: str, tool_input: dict) -> None:
        """Refresh the tool summary/details when fuller input arrives later."""
        self.tool_name = tool_name
        self.tool_input = tool_input
        if self._collapsible:
            self._collapsible.title = self._build_title()
            self._auto_expand_once()
            self.apply_transcript_collapsible_mode()
        self._details_dirty = True
        self._render_details_if_needed()

    def on_mount(self) -> None:
        """Refresh after mount in case results arrived early."""
        if self._collapsible:
            self._collapsible.title = self._build_title()
            self._auto_expand_once()
            self.apply_transcript_collapsible_mode()
        self._render_details_if_needed()

    def on_collapsible_expanded(self, event: Collapsible.Expanded) -> None:
        """Render deferred details when the tool block is expanded."""
        if not self._collapsible or event.collapsible is not self._collapsible:
            return
        self._render_details_if_needed()

    def _build_title(self) -> Content:
        """Return the current single-line title for the tool call."""
        if self._result is None:
            return Content.from_text(
                "● " + sanitize_terminal_text(
                    summarize_tool_use(self.tool_name, self.tool_input)
                ),
                markup=False,
            )
        summary, is_error = self._result
        summary = sanitize_terminal_text(summary)
        status_style = "$error" if is_error else "$success"
        title_text = f"● {summary}"
        spans = [Span(0, 1, status_style)]
        action_span = self._leading_action_span(summary, offset=2)
        if action_span is not None:
            spans.append(action_span)
        return Content(title_text, spans=spans)

    @staticmethod
    def _leading_action_span(summary: str, *, offset: int = 0) -> Span | None:
        """Highlight the leading action token in tool result summaries."""
        match = re.match(r"[A-Za-z]+", summary)
        if not match:
            return None
        return Span(offset + match.start(), offset + match.end(), "$text-primary")

    def _should_auto_expand(self) -> bool:
        """Return True when this tool block should start expanded."""
        return self._should_force_expand_for_streaming_mode()

    def _auto_expand_once(self) -> None:
        """Expand Edit blocks once without overriding later manual collapse."""
        if self._did_auto_expand or not self._should_auto_expand():
            return
        if self._collapsible:
            self._collapsible.collapsed = False
            self._did_auto_expand = True

    def apply_transcript_collapsible_mode(self) -> None:
        """Enforce the current application-wide transcript collapsible mode."""
        if not self._collapsible:
            return
        desired_collapsed = self._desired_collapsed_for_mode(
            self._transcript_collapsible_mode_expanded()
        )
        if self._collapsible.collapsed != desired_collapsed:
            self._collapsible.collapsed = desired_collapsed

    def _desired_collapsed_for_mode(self, expanded_mode: bool) -> bool:
        """Return the collapsed state required by the global transcript mode."""
        if self._should_force_expand_for_streaming_mode():
            return False
        return not expanded_mode

    def _should_force_expand_for_streaming_mode(self) -> bool:
        """Edit/Write tool blocks stay open while the assistant is streaming."""
        return self._streaming_context and self.tool_name in {"Edit", "Write"}

    def _transcript_collapsible_mode_expanded(self) -> bool:
        """Read the application-wide transcript collapsible mode from the screen."""
        try:
            return bool(getattr(self.screen, "_transcript_collapsible_mode_expanded", False))
        except Exception:
            return False

    def _compose_details(self) -> ComposeResult:
        """Compose the detail widgets."""
        diff_view = self._build_diff_view()

        # Input parameters
        exclude_keys = self._get_input_exclusions(diff_view)
        detail_lines = format_tool_input_details(self.tool_input, exclude_keys)
        if detail_lines:
            for line in detail_lines:
                yield Static(line, classes="tool-param", markup=False)
        elif self._result is None:
            yield Static("Waiting for parameters", classes="tool-param", markup=False)

        # Diff view or output
        if diff_view is not None:
            yield diff_view
        elif self._result is not None:
            if self._output_lines:
                yield from self._compose_output_branch()
            else:
                yield Static("(no output)", classes="tool-result-preview", markup=False)

    def _compose_output_branch(self) -> ComposeResult:
        """Compose the collapsible tool-result block."""
        yield ToolResultBlockWidget(self._output_lines)

    def _get_input_exclusions(self, diff_view: DiffView | None) -> set[str]:
        """Hide raw diff payloads once a diff view is available."""
        if diff_view is None:
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
                # Only attempt if new_string is non-empty and exists in current_content
                if new_string and new_string in current_content:
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
        self._details_rendered = True
        self._details_dirty = False

    def _render_details_if_needed(self) -> None:
        """Render details only when visible or explicitly expanded."""
        if not self._container or not self._container.is_mounted:
            return
        if not self._collapsible:
            return
        if self._collapsible.collapsed:
            return
        if self._details_rendered and not self._details_dirty:
            return
        self._render_details()


class MessageWidget(VerticalGroup):
    """
    Widget for displaying a message with optional streaming support.
    Consolidates both static and streaming message display.
    """

    def __init__(
        self,
        message: Optional[Message] = None,
        streaming: bool = False,
        should_stream_live: Callable[[], bool] | None = None,
        tool_streaming_context: bool = True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._streaming = streaming
        self._message = message
        self._should_stream_live = should_stream_live
        self._tool_streaming_context = tool_streaming_context

        # Internal state for streaming
        self._thinking_content: str = ""
        self._text_content: str = ""
        self._tool_uses: List[ToolUseContent] = []
        self._tool_use_ids: set[str] = set()
        self._tool_widgets_by_id: dict[str, ToolUseWidget] = {}

        # Widget references
        self._thinking_widget: Optional[ThinkingBlockWidget] = None
        self._streaming_widget: Optional[StreamingMarkdownWidget] = None
        self._streaming_host: Optional[Container] = None
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

    def _compose_markdown_block(self, text: str) -> ComposeResult:
        """Wrap assistant markdown in a host container that owns horizontal padding."""
        with Container(classes="markdown-host transcript-block") as host:
            self._streaming_host = host
            self._streaming_widget = StreamingMarkdownWidget(
                text,
                should_stream_live=self._should_stream_live,
                classes="streaming-content",
            )
            yield self._streaming_widget

    def _compose_static_message(self, message: Message) -> ComposeResult:
        """Compose a static (non-streaming) message."""
        role_config = ROLE_CONFIG.get(message.type, ROLE_CONFIG[MessageRole.ASSISTANT])

        # Role label
        if message.type not in {MessageRole.USER, MessageRole.ASSISTANT} and role_config["label"]:
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
                with FlushCollapsible(
                    title=f"@{expansion.display_path}",
                    collapsed=True,
                    collapsed_symbol="●",
                    expanded_symbol="●",
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
                        yield from self._compose_markdown_block(block.text)
                    else:
                        display_text = (
                            message.original_text
                            if message.file_expansions
                            else block.text
                        )
                        yield Static(
                            sanitize_terminal_text(display_text),
                            classes="message-content transcript-block",
                            markup=False,
                        )
            elif isinstance(block, ToolUseContent):
                yield ToolUseWidget(
                    tool_name=block.name,
                    tool_input=block.input,
                    tool_use_id=block.id,
                    streaming_context=False,
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
                    yield ToolResultBlockWidget(preview_lines)

    def _compose_streaming_message(self) -> ComposeResult:
        """Compose a streaming message container."""
        with VerticalGroup(classes="message-body") as container:
            self._content_container = container
            if self._thinking_content:
                self._thinking_widget = ThinkingBlockWidget(self._thinking_content)
                yield self._thinking_widget
            if self._text_content:
                yield from self._compose_markdown_block(self._text_content)
            for tool_use in self._tool_uses:
                tool_widget = ToolUseWidget(
                    tool_name=tool_use.name,
                    tool_input=tool_use.input,
                    tool_use_id=tool_use.id,
                    streaming_context=self._tool_streaming_context,
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
            self._streaming_host = Container(classes="markdown-host transcript-block")
            self._streaming_widget = StreamingMarkdownWidget(
                self._text_content,
                should_stream_live=self._should_stream_live,
                classes="streaming-content",
            )
            await self._content_container.mount(self._streaming_host)
            await self._streaming_host.mount(self._streaming_widget)
            self.refresh(layout=True)

    async def update_text(self, text: str) -> None:
        """Update the streaming text content."""
        self._text_content = text
        if self._streaming_widget:
            await self._streaming_widget.set_markdown_text(text)
            self.refresh(layout=True)
        elif text and self._content_container:
            self._streaming_host = Container(classes="markdown-host transcript-block")
            self._streaming_widget = StreamingMarkdownWidget(
                text,
                should_stream_live=self._should_stream_live,
                classes="streaming-content",
            )
            await self._content_container.mount(self._streaming_host)
            await self._streaming_host.mount(self._streaming_widget)
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
                streaming_context=self._tool_streaming_context,
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
        self._message_widgets: List[MessageWidget] = []

    def _get_content_area(self) -> ScrollableContainer | None:
        """Return the transcript scroll container when mounted."""
        try:
            return self.screen.query_one("#content-area", ScrollableContainer)
        except Exception:
            return None

    def _scroll_to_latest(self) -> None:
        """Anchor the transcript scroll container to the latest output."""
        content_area = self._get_content_area()
        if content_area is None:
            return
        try:
            content_area.anchor()
        except Exception as e:
            log_full_exception(logger, "Failed to anchor transcript", e)

    def should_auto_follow_output(self) -> bool:
        """Return True when the transcript is currently pinned near the bottom."""
        content_area = self._get_content_area()
        if content_area is None:
            return True
        return content_area.is_vertical_scroll_end

    def reset_auto_follow_output(self) -> None:
        """Re-enable transcript auto-follow for a fresh user request."""
        self._scroll_to_latest()

    def schedule_scroll_to_latest(self, auto_follow: bool = True) -> None:
        """Anchor after the current DOM/layout update flushes."""
        if auto_follow:
            self.call_after_refresh(self._scroll_to_latest)

    def first_message_widget(self) -> Optional[MessageWidget]:
        """Return the first mounted message widget, if any."""
        return self._message_widgets[0] if self._message_widgets else None

    async def _mount_message_widget(
        self,
        widget: MessageWidget,
        *,
        auto_follow: bool = True,
        before_widget: Optional[MessageWidget] = None,
    ) -> None:
        """Mount a message widget either at end or before an existing widget."""
        if before_widget and before_widget in self._message_widgets:
            await self.mount(widget, before=before_widget)
            insert_index = self._message_widgets.index(before_widget)
            self._message_widgets.insert(insert_index, widget)
        else:
            await self.mount(widget)
            self._message_widgets.append(widget)
        self.schedule_scroll_to_latest(auto_follow)

    async def add_message(
        self,
        message: Message,
        auto_follow: bool = True,
        before_widget: Optional[MessageWidget] = None,
    ) -> None:
        """Add a message to the list"""
        widget = MessageWidget(message)
        await self._mount_message_widget(
            widget,
            auto_follow=auto_follow,
            before_widget=before_widget,
        )

    async def create_streaming_widget(
        self,
        message: Optional[Message] = None,
        auto_follow: bool = True,
        should_stream_live: Callable[[], bool] | None = None,
        tool_streaming_context: bool = True,
        before_widget: Optional[MessageWidget] = None,
    ) -> MessageWidget:
        """Create a new streaming message widget for assistant responses"""
        widget = MessageWidget(
            message=message,
            streaming=True,
            should_stream_live=should_stream_live,
            tool_streaming_context=tool_streaming_context,
        )
        await self._mount_message_widget(
            widget,
            auto_follow=auto_follow,
            before_widget=before_widget,
        )
        return widget

    def clear(self) -> None:
        """Clear all messages"""
        for widget in self._message_widgets:
            widget.remove()
        self._message_widgets.clear()
