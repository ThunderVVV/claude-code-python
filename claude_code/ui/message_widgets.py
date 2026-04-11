"""Message-related widgets for the TUI"""

from __future__ import annotations

import logging
from typing import List, Optional
from markdown_it import MarkdownIt
from textual.await_complete import AwaitComplete
from textual.app import ComposeResult
from textual.content import Content, Span
from textual.containers import Container, VerticalGroup, ScrollableContainer
from textual.highlight import highlight as highlight_code
from textual.widgets import _markdown as textual_markdown
from textual.widgets import Collapsible, Label, Markdown, Static

logger = logging.getLogger(__name__)

from claude_code.core.messages import (
    Message,
    MessageRole,
    TextContent,
    ThinkingContent,
    ToolUseContent,
    ToolResultContent,
)
from claude_code.ui.diff_view import DiffView
from claude_code.ui.utils import (
    sanitize_terminal_text,
    summarize_tool_result,
    summarize_tool_use,
    format_tool_input_details,
    truncate_preview_line,
)
from claude_code.utils.logging_config import log_full_exception


def _create_markdown_parser() -> MarkdownIt:
    """Build a Markdown parser aligned with the TypeScript implementation."""
    return MarkdownIt("gfm-like", {"linkify": False}).disable("strikethrough")


class TranscriptMarkdownFence(textual_markdown.MarkdownFence):
    """Markdown fence that treats untyped code blocks as plain text."""

    @classmethod
    def highlight(cls, code: str, language: str) -> Content:
        return highlight_code(code, language=language or "text")


class TranscriptMarkdownWidget(Markdown):
    """Markdown widget wrapper that disables hover tooltips in transcript content."""

    def __init__(self, initial_text: str = "", **kwargs):
        normalized = sanitize_terminal_text(initial_text)
        self._markdown_text = normalized
        self._stream: textual_markdown.MarkdownStream | None = None
        super().__init__(
            normalized,
            parser_factory=_create_markdown_parser,
            open_links = False,
            **kwargs,
        )

    def get_block_class(
        self,
        block_name: str,
    ) -> type[textual_markdown.MarkdownBlock]:
        """Use a plain-text fallback for fenced code blocks without a language."""
        if block_name in {"fence", "code_block"}:
            return TranscriptMarkdownFence
        return super().get_block_class(block_name)

    def update(self, markdown: str) -> AwaitComplete:
        """Update markdown content and strip any built-in hover tooltips."""
        normalized = sanitize_terminal_text(markdown)
        self._markdown_text = normalized
        update = super().update(normalized)
        return update

    def _get_stream(self) -> textual_markdown.MarkdownStream:
        """Lazily create a Textual markdown stream for high-frequency appends."""
        if self._stream is None:
            self._stream = Markdown.get_stream(self)
        return self._stream

    async def finish_streaming(self) -> None:
        """Stop the background markdown stream, flushing any queued fragments."""
        if self._stream is None:
            return
        stream = self._stream
        self._stream = None
        await stream.stop()

    async def append_markdown(self, markdown: str) -> None:
        """Append a markdown fragment using Textual's streaming helper."""
        normalized = sanitize_terminal_text(markdown)
        if not normalized:
            return
        self._markdown_text += normalized
        if not self.is_mounted:
            self._initial_markdown = self._markdown_text
            return
        await self._get_stream().write(normalized)

    async def set_markdown_text(self, text: str) -> None:
        """Reconcile the widget with the provided full markdown text."""
        normalized = sanitize_terminal_text(text)
        previous = self._markdown_text

        if normalized == previous:
            return

        if not self.is_mounted:
            self._markdown_text = normalized
            self._initial_markdown = normalized
            return

        if normalized.startswith(previous):
            await self.append_markdown(normalized[len(previous) :])
            return

        await self.finish_streaming()
        await self.update(normalized)

    async def _on_unmount(self) -> None:
        await self.finish_streaming()


class StreamingTextWidget(TranscriptMarkdownWidget):
    """Widget for assistant markdown content that updates in place."""

    def __init__(self, initial_text: str = "", **kwargs):
        super().__init__(
            classes="streaming-content",
            initial_text=initial_text,
            **kwargs,
        )

    async def append_text(self, text: str) -> None:
        """Append streamed text."""
        await self.append_markdown(text)

    async def update_text(self, text: str) -> None:
        """Update the displayed text."""
        await self.set_markdown_text(text)


class ThinkingWidget(Static):
    """Widget for displaying reasoning content as plain text (no markdown)."""

    def __init__(self, initial_thinking: str = "", **kwargs):
        super().__init__(
            sanitize_terminal_text(initial_thinking),
            classes="thinking-content",
            **kwargs,
        )
        self._thinking = initial_thinking

    async def append_thinking(self, thinking: str) -> None:
        """Append streamed thinking content."""
        self._thinking += thinking
        self.update(sanitize_terminal_text(self._thinking))

    async def update_thinking(self, thinking: str) -> None:
        """Update the displayed thinking content."""
        self._thinking = thinking
        self.update(sanitize_terminal_text(thinking))

    async def finish_streaming(self) -> None:
        """No-op for plain text widget."""
        pass


class ThinkingBlockWidget(VerticalGroup):
    """Collapsible widget for thinking/reasoning content."""

    def __init__(self, initial_thinking: str = "", **kwargs):
        super().__init__(**kwargs)
        self._thinking = initial_thinking
        self._thinking_widget: Optional[ThinkingWidget] = None
        self.add_class("thinking-block")

    def compose(self) -> ComposeResult:
        with Collapsible(
            title="Thinking...",
            collapsed=True,
            collapsed_symbol=">",
            expanded_symbol="v",
            classes="thinking-collapsible",
        ):
            self._thinking_widget = ThinkingWidget(self._thinking)
            yield self._thinking_widget

    async def append_thinking(self, thinking: str) -> None:
        """Append streamed thinking content."""
        self._thinking += thinking
        if self._thinking_widget:
            await self._thinking_widget.append_thinking(thinking)

    async def update_thinking(self, thinking: str) -> None:
        """Update the thinking content."""
        self._thinking = thinking
        if self._thinking_widget:
            await self._thinking_widget.update_thinking(thinking)
            self.refresh(layout=True)

    async def finish_streaming(self) -> None:
        """Flush and stop the markdown stream used by the thinking widget."""
        if self._thinking_widget:
            await self._thinking_widget.finish_streaming()


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
        self._did_auto_expand = False
        self._result_summary: Optional[str] = None
        self._result_output_lines: List[str] = []
        self._result_is_error = False
        self._details_collapsible: Optional[Collapsible] = None
        self._details_container: Optional[VerticalGroup] = None
        self._pending_result_render: bool = False
        self.add_class("tool-use-block")

    def compose(self) -> ComposeResult:
        with Collapsible(
            title=self._collapsible_title(),
            collapsed=not self._should_auto_expand(),
            collapsed_symbol=">",
            expanded_symbol="v",
            classes="tool-collapsible tool-use-details",
        ) as collapsible:
            self._details_collapsible = collapsible
            with VerticalGroup(classes="tool-detail-body") as container:
                self._details_container = container
                yield from self._compose_detail_widgets()

    def set_result(self, result: str, is_error: bool) -> None:
        """Attach the tool result to the existing tool-use block."""
        self._result_is_error = is_error
        self._result_summary, self._result_output_lines = summarize_tool_result(
            self.tool_name,
            self.tool_input,
            result,
            is_error,
        )
        if self._details_collapsible:
            self._details_collapsible.title = self._collapsible_title()
            self._maybe_auto_expand()
        if self._details_container:
            if self._details_container.is_mounted:
                self._render_detail_widgets()
            else:
                self._pending_result_render = True

    def update_tool_input(self, tool_name: str, tool_input: dict) -> None:
        """Refresh the tool summary/details when fuller input arrives later."""
        self.tool_name = tool_name
        self.tool_input = tool_input
        if self._details_collapsible:
            self._details_collapsible.title = self._collapsible_title()
            self._maybe_auto_expand()
        if self._details_container and self._details_container.is_mounted:
            self._render_detail_widgets()

    def on_mount(self) -> None:
        """Refresh the single collapsible after mount in case results arrived early."""
        if self._details_collapsible:
            self._details_collapsible.title = self._collapsible_title()
            self._maybe_auto_expand()
        if self._details_container and self._details_container.is_mounted:
            if self._pending_result_render or self._result_summary is not None:
                self._render_detail_widgets()
                self._pending_result_render = False

    def _collapsible_title(self) -> Content:
        """Return the current single-line title for the tool call."""
        if self._result_summary is None:
            return Content.from_text(
                sanitize_terminal_text(
                    summarize_tool_use(self.tool_name, self.tool_input)
                ),
                markup=False,
            )
        summary = sanitize_terminal_text(self._result_summary)
        status_style = "$error" if self._result_is_error else "$success"
        return Content(
            f"● {summary}",
            spans=[Span(0, 1, status_style)],
        )

    def _compose_detail_widgets(self) -> ComposeResult:
        detail_lines = format_tool_input_details(
            self.tool_input,
            exclude_keys=self._detail_input_exclusions(),
        )
        if detail_lines:
            for line in detail_lines:
                yield Static(line, classes="tool-param", markup=False)
        elif self._result_summary is None:
            yield Static("No input parameters", classes="tool-param", markup=False)

        diff_view = self._build_diff_view()
        if diff_view is not None:
            yield diff_view
        elif self._result_summary is not None:
            yield Static("Output:", classes="tool-output-label", markup=False)
            if self._result_output_lines:
                for line in self._result_output_lines:
                    yield Static(line, classes="tool-result-preview", markup=False)
            else:
                yield Static("(no output)", classes="tool-result-preview", markup=False)

    def _detail_input_exclusions(self) -> set[str]:
        """Hide raw diff payloads once a diff view is available."""
        diff_view = self._build_diff_view()
        if diff_view is None:
            return set()
        if self.tool_name == "Edit":
            return {"old_string", "new_string"}
        if self.tool_name == "Write":
            return {"content"}
        return set()

    def _should_auto_expand(self) -> bool:
        """Return True when this tool block should start expanded."""
        return self.tool_name in {"Edit", "Write"}

    def _maybe_auto_expand(self) -> None:
        """Expand Edit blocks once without overriding later manual collapse."""
        if self._did_auto_expand or not self._should_auto_expand():
            return
        if self._details_collapsible:
            self._details_collapsible.collapsed = False
            self._did_auto_expand = True

    def _build_diff_view(self) -> DiffView | None:
        """Build an inline diff widget for successful file-editing tool calls."""
        if self._result_summary is None or self._result_is_error:
            return None

        file_path = str(self.tool_input.get("file_path", "")).strip()
        if not file_path:
            return None

        old_text: str
        new_text: str

        if self.tool_name == "Edit":
            old_string = self.tool_input.get("old_string")
            new_string = self.tool_input.get("new_string")
            if not isinstance(old_string, str) or not isinstance(new_string, str):
                return None
            old_text = old_string
            new_text = new_string
        elif self.tool_name == "Write":
            content = self.tool_input.get("content")
            if not isinstance(content, str):
                return None
            old_text = ""
            new_text = content
        else:
            return None

        return DiffView(
            file_path,
            file_path,
            sanitize_terminal_text(old_text),
            sanitize_terminal_text(new_text),
            classes="tool-edit-diff",
        )

    def _render_detail_widgets(self) -> None:
        if not self._details_container:
            return
        for child in list(self._details_container.children):
            child.remove()
        for widget in self._compose_detail_widgets():
            self._details_container.mount(widget)


class AssistantMessageWidget(VerticalGroup):
    """
    Widget for displaying an assistant message with streaming support.
    This widget allows incremental updates of text and tool uses without recreating the entire widget.
    Aligned with TypeScript's approach to streaming message display.
    """

    def __init__(self, message: Optional[Message] = None, **kwargs):
        super().__init__(**kwargs)
        self._thinking_content: str = ""
        self._text_content: str = ""
        self._tool_uses: List[ToolUseContent] = []
        self._tool_use_ids: set[str] = set()
        self._tool_widgets_by_id: dict[str, ToolUseWidget] = {}
        self._thinking_widget: Optional[ThinkingBlockWidget] = None
        self._streaming_widget: Optional[StreamingTextWidget] = None
        self._tool_widgets: List[ToolUseWidget] = []
        self._content_container: Optional[VerticalGroup] = None
        self.add_class("message-block")
        self.add_class("assistant-message-block")
        if message:
            self._load_initial_message(message)

    def _load_initial_message(self, message: Message) -> None:
        """Seed internal state before mount from a finalized assistant message."""
        for block in message.content:
            if isinstance(block, ThinkingContent):
                self._thinking_content = block.thinking
            elif isinstance(block, TextContent):
                self._text_content = block.text
            elif isinstance(block, ToolUseContent):
                self._tool_uses.append(block)
                if block.id:
                    self._tool_use_ids.add(block.id)

    def compose(self) -> ComposeResult:
        # Content container - will hold thinking, text and tool widgets
        with VerticalGroup(classes="message-content") as container:
            self._content_container = container
            if self._thinking_content:
                self._thinking_widget = ThinkingBlockWidget(self._thinking_content)
                yield self._thinking_widget
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
        """Update the streaming thinking content"""
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
            self._streaming_widget = StreamingTextWidget(self._text_content)
            await self._content_container.mount(self._streaming_widget)
            self.refresh(layout=True)

    async def update_text(self, text: str) -> None:
        """Update the streaming text content"""
        self._text_content = text
        if self._streaming_widget:
            await self._streaming_widget.update_text(text)
            self.refresh(layout=True)
        elif text and self._content_container:
            self._streaming_widget = StreamingTextWidget(text)
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
            self._tool_widgets.append(tool_widget)
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
        for existing_tool_use in self._tool_uses:
            if existing_tool_use.id == tool_use.id:
                existing_tool_use.name = tool_use.name
                existing_tool_use.input = tool_use.input
                break
        tool_widget = self._tool_widgets_by_id.get(tool_use.id)
        if tool_widget:
            tool_widget.update_tool_input(tool_use.name, tool_use.input)

    def get_tool_widgets(self) -> dict[str, ToolUseWidget]:
        """Expose rendered tool widgets by tool-use id."""
        return dict(self._tool_widgets_by_id)

    async def finish_streaming(self) -> None:
        """Flush and stop any active markdown streams for this assistant message."""
        if self._thinking_widget:
            await self._thinking_widget.finish_streaming()
        if self._streaming_widget:
            await self._streaming_widget.finish_streaming()


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
            
        if self.message.type == MessageRole.USER and self.message.file_expansions:
            logger.debug(f"Rendering: {len(self.message.file_expansions)} file expansions found for message")
            for expansion in self.message.file_expansions:
                yield Static(
                    self._format_file_expansion(expansion),
                    classes="file-expansion",
                    markup=False,
                )

        # Content
        for block in self.message.content:
            if isinstance(block, ThinkingContent):
                if block.thinking.strip():
                    yield ThinkingBlockWidget(block.thinking)
            elif isinstance(block, TextContent):
                if block.text.strip():
                    # Use StreamingTextWidget for assistant messages to allow updates
                    if self.message.type == MessageRole.ASSISTANT:
                        self._streaming_widget = StreamingTextWidget(block.text)
                        yield self._streaming_widget
                    else:
                        # For user messages with file expansions, show only the original text
                        # (file expansions are already shown separately above)
                        display_text = (
                            self.message.original_text
                            if self.message.file_expansions
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
                # Truncate long results
                content = block.content
                if len(content) > 500:
                    content = (
                        content[:500] + f"\n... ({len(block.content) - 500} more chars)"
                    )
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

    def _format_file_expansion(self, expansion) -> str:
        """Format a file expansion for display with 5-line limit."""
        lines = expansion.content.splitlines()
        total_lines = len(lines)
        max_lines = 5

        # Format with line numbers like Read tool
        formatted_lines = []
        for i, line in enumerate(lines[:max_lines], start=1):
            formatted_lines.append(f"{i:6}\t{truncate_preview_line(line)}")

        result = f"@{expansion.display_path}:"
        result += "\n" + "\n".join(formatted_lines)

        if total_lines > max_lines:
            result += f"\n... ({total_lines - max_lines} more lines)"

        return result

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
        self._message_widgets: List[
            Container
        ] = []  # Can be MessageWidget or AssistantMessageWidget
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

    async def create_assistant_widget(
        self,
        message: Optional[Message] = None,
        auto_follow: bool = True,
    ) -> AssistantMessageWidget:
        """Create a new assistant message widget for streaming"""
        widget = AssistantMessageWidget(message=message)
        await self.mount(widget)
        self._message_widgets.append(widget)
        self.schedule_scroll_to_latest(auto_follow)
        return widget

    def clear(self) -> None:
        """Clear all messages"""
        for widget in self._message_widgets:
            widget.remove()
        self._message_widgets = []
