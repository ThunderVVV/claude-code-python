"""Message-related widgets for the TUI"""

from __future__ import annotations

from typing import List, Optional
from textual.app import ComposeResult
from textual.content import Content
from textual.containers import Container, VerticalGroup, ScrollableContainer
from textual.widgets import Collapsible, Label, Static

from claude_code.core.messages import (
    Message,
    MessageRole,
    TextContent,
    ToolUseContent,
    ToolResultContent,
)
from claude_code.ui.utils import (
    sanitize_terminal_text,
    summarize_tool_result,
    summarize_tool_use,
    format_tool_input_details,
)


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
        self._result_output_lines: List[str] = []
        self._result_is_error = False
        self._details_collapsible: Optional[Collapsible] = None
        self._details_container: Optional[VerticalGroup] = None
        self.add_class("tool-use-block")

    def compose(self) -> ComposeResult:
        with Collapsible(
            title=self._collapsible_title(),
            collapsed=True,
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
        if self._details_container and self._details_container.is_mounted:
            self._render_detail_widgets()

    def on_mount(self) -> None:
        """Refresh the single collapsible after mount in case results arrived early."""
        if self._details_collapsible:
            self._details_collapsible.title = self._collapsible_title()
        if self._details_container and self._details_container.is_mounted:
            self._render_detail_widgets()

    def _collapsible_title(self) -> Content:
        """Return the current single-line title for the tool call."""
        if self._result_summary is None:
            return Content.from_text(
                sanitize_terminal_text(
                    summarize_tool_use(self.tool_name, self.tool_input)
                ),
                markup=False,
            )
        prefix = "[ERR]" if self._result_is_error else "[OK]"
        return Content.from_text(
            sanitize_terminal_text(f"{prefix} {self._result_summary}"),
            markup=False,
        )

    def _compose_detail_widgets(self) -> ComposeResult:
        detail_lines = format_tool_input_details(self.tool_input)
        if detail_lines:
            for line in detail_lines:
                yield Static(line, classes="tool-param", markup=False)
        elif self._result_summary is None:
            yield Static("No input parameters", classes="tool-param", markup=False)

        if self._result_summary is not None:
            yield Static("Output:", classes="tool-output-label", markup=False)
            if self._result_output_lines:
                for line in self._result_output_lines:
                    yield Static(line, classes="tool-result-preview", markup=False)
            else:
                yield Static("(no output)", classes="tool-result-preview", markup=False)

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
        except Exception:
            pass

    def _on_content_scroll(self, _scroll_y: float) -> None:
        """Disable auto-follow when the user scrolls away from the bottom."""
        if self._suppress_scroll_tracking:
            return
        try:
            content_area = self.screen.query_one("#content-area", ScrollableContainer)
            self._auto_follow_output = content_area.scroll_y >= max(
                content_area.max_scroll_y - 1, 0
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
        """Add a fallback tool result using the same single-collapsible tool UI."""
        widget = ToolUseWidget(tool_name=tool_name, tool_input=tool_input, tool_use_id="")
        widget.set_result(result, is_error)
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
