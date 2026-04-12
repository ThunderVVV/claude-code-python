"""Screen definitions for the TUI - stateless frontend, only handles display"""

from __future__ import annotations

import asyncio
import json
import os
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, VerticalGroup
from textual.widgets import Label, LoadingIndicator
from textual.screen import Screen
from textual import events
from textual.worker import Worker

from claude_code.core.context_window import (
    format_token_count,
    get_used_context_percentage,
    get_used_context_tokens,
    get_configured_context_window_tokens,
)
from claude_code.core.messages import (
    Message,
    MessageRole,
    ToolResultContent,
    ToolUseContent,
    Usage,
    QueryEvent,
    TextEvent,
    ThinkingEvent,
    ToolUseEvent,
    ToolResultEvent,
    MessageCompleteEvent,
    TurnCompleteEvent,
    ErrorEvent,
)
from claude_code.ui.widgets import WelcomeWidget, InputTextArea
from claude_code.ui.message_widgets import (
    MessageList,
    MessageWidget,
    ToolUseWidget,
)
from claude_code.ui.session_resume_modal import SessionResumeModal
from claude_code.utils.logging_config import log_full_exception

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from claude_code.client.http_client import ClaudeCodeHttpClient


class REPLScreen(Screen):
    """Main REPL screen - stateless frontend, only handles display.

    All state management is done by the API server.
    This screen only:
    - Sends user input to server
    - Receives and renders events
    - Handles UI-specific state (history, scroll position)
    """

    def __init__(
        self,
        client: "ClaudeCodeHttpClient",
        session_id: str,
        working_directory: str = "",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.client = client
        self.session_id = session_id
        self.working_directory = working_directory or ""

        self._latest_usage: Optional[Usage] = None
        self._is_processing = False
        self._current_assistant_widget: Optional[MessageWidget] = None
        self._show_welcome = True
        self._tool_widget_context: dict[str, ToolUseWidget] = {}
        self._query_worker: Optional[Worker] = None

        self._history: list[str] = []
        self._history_index: int = 0
        self._nav_items: list[str] = []
        self._history_file = Path.home() / ".claude-code-python/input_history.json"
        self._load_history()

        self._session_title: Optional[str] = None

        self._context_window_tokens = get_configured_context_window_tokens()

    def _load_history(self) -> None:
        if self._history_file.exists():
            try:
                with open(self._history_file, "r", encoding="utf-8") as f:
                    self._history = json.load(f)
            except Exception:
                self._history = []
        self._reset_nav_buffer()

    def _save_history(self) -> None:
        try:
            with open(self._history_file, "w", encoding="utf-8") as f:
                json.dump(self._history, f, ensure_ascii=False)
        except Exception:
            pass

    def _add_to_history(self, text: str) -> None:
        if text.strip() and (not self._history or self._history[-1] != text):
            self._history.append(text)
            if len(self._history) > 1000:
                self._history = self._history[-1000:]
            self._save_history()
        self._reset_nav_buffer()

    def _reset_nav_buffer(self) -> None:
        self._nav_items = self._history.copy() + [""]
        self._history_index = len(self._nav_items) - 1

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="content-area"):
            yield WelcomeWidget(
                id="welcome-widget",
                model_name=os.environ.get("CLAUDE_CODE_MODEL"),
                cwd=self.working_directory,
            )
            yield MessageList(id="message-list")

        with VerticalGroup(id="input-area"):
            with Horizontal(id="processing-row"):
                yield LoadingIndicator(id="processing-indicator")
                yield Label(
                    "Working... (esc to interrupt)", id="processing-label", markup=False
                )
            yield InputTextArea(
                placeholder=self._input_placeholder_text(),
                id="user-input",
                language="text",
                show_line_numbers=False,
                tab_behavior="indent",
            )
            yield Label(self._context_usage_text(), id="context-usage", markup=False)

    async def on_mount(self) -> None:
        input_widget = self.query_one("#user-input", InputTextArea)
        input_widget.set_on_submit(self._on_input_submit)
        input_widget.focus()

    def _on_input_submit(self, text: str) -> None:
        self._start_message_submission(text)

    async def on_mouse_down(self, event: events.MouseDown) -> None:
        self._focus_input_if_needed()

    async def on_mouse_up(self, event: events.MouseUp) -> None:
        self._focus_input_if_needed()

    def _focus_input_if_needed(self) -> None:
        """Focus input widget if not already focused and not processing."""
        input_widget = self.query_one("#user-input", InputTextArea)
        if not input_widget.has_focus and not self._is_processing:
            input_widget.focus()

    async def on_key(self, event: events.Key) -> None:
        if event.key == "escape" and self._is_processing:
            event.stop()
            await self._cancel_current_query()
            return

        input_widget = self.query_one("#user-input", InputTextArea)
        if input_widget.has_focus:
            if event.key == "up":
                event.stop()
                self._navigate_history(1)
            elif event.key == "down":
                event.stop()
                self._navigate_history(-1)

    def _navigate_history(self, direction: int) -> None:
        input_widget = self.query_one("#user-input", InputTextArea)

        self._nav_items[self._history_index] = input_widget.text

        if direction == 1:
            self._history_index = max(self._history_index - 1, 0)
        else:
            self._history_index = min(self._history_index + 1, len(self._nav_items) - 1)

        input_widget.text = self._nav_items[self._history_index]
        input_widget.move_cursor(input_widget.document.end)

    def _hide_welcome_widget(self) -> None:
        if not self._show_welcome:
            return
        try:
            welcome_widget = self.query_one("#welcome-widget", WelcomeWidget)
            welcome_widget.display = False
        except Exception:
            pass
        self._show_welcome = False

    def _set_processing_state(self, is_processing: bool) -> None:
        self._is_processing = is_processing
        input_widget = self.query_one("#user-input", InputTextArea)
        processing_row = self.query_one("#processing-row", Horizontal)
        input_widget.disabled = is_processing
        processing_row.display = is_processing

        if is_processing:
            input_widget.set_styles("height: 3;")
        else:
            input_widget.set_styles("height: auto;")

        input_widget.refresh()
        input_widget.placeholder = (
            "Agent is responding..."
            if is_processing
            else self._input_placeholder_text()
        )

    def _input_placeholder_text(self) -> str:
        return "Type your message and press Enter (Shift+Enter for new line)"

    def _context_usage_text(self) -> str:
        if not self._latest_usage:
            return "Context: unavailable (waiting for server)"
        used_tokens = get_used_context_tokens(self._latest_usage)
        used_percentage = get_used_context_percentage(
            self._latest_usage,
            self._context_window_tokens,
        )
        return (
            "Context: "
            f"{format_token_count(used_tokens)}/"
            f"{format_token_count(self._context_window_tokens)} "
            f"({used_percentage}%)"
        )

    def _refresh_context_usage_label(self) -> None:
        label = self.query_one("#context-usage", Label)
        label.update(self._context_usage_text())

    def _reset_streaming_state(self) -> None:
        self._current_assistant_widget = None

    def _reset_tool_contexts(self) -> None:
        """Reset tool widget contexts."""
        self._tool_widget_context = {}

    def _start_message_submission(self, submitted_value: str) -> None:
        if self._is_processing:
            return

        input_widget = self.query_one("#user-input", InputTextArea)
        user_text = submitted_value.strip()

        if not user_text:
            return

        if user_text.lower() == "/exit":
            self.app.exit()
            return

        if user_text.lower() in ("/clear", "/new"):
            asyncio.create_task(self._start_new_session())
            return

        if user_text.lower() == "/sessions":
            self._show_sessions_modal()
            return

        self._hide_welcome_widget()
        self._add_to_history(submitted_value)

        input_widget.load_text("")
        self._reset_streaming_state()
        self._reset_tool_contexts()

        self._set_processing_state(True)
        self.refresh()

        self._query_worker = self.run_worker(
            self._process_message(user_text),
            group="query",
            exclusive=True,
            exit_on_error=False,
        )

    async def _start_new_session(self) -> None:
        """Create a new session on server and reset UI."""
        if self._is_processing:
            return

        new_session_id = await self.client.create_session(self.working_directory)
        self.session_id = new_session_id

        message_list = self.query_one("#message-list", MessageList)
        message_list.clear()

        self._session_title = None
        self._latest_usage = None
        self._reset_streaming_state()
        self._reset_tool_contexts()

        input_widget = self.query_one("#user-input", InputTextArea)
        input_widget.load_text("")

        self._show_welcome = True
        try:
            welcome_widget = self.query_one("#welcome-widget", WelcomeWidget)
            welcome_widget.display = True
        except Exception:
            pass

        self._refresh_context_usage_label()
        input_widget.focus()

    def _show_sessions_modal(self) -> None:
        """Show the sessions modal for switching sessions."""
        if self._is_processing:
            return

        modal = SessionResumeModal(
            client=self.client,
            current_session_id=self.session_id,
        )
        self.app.push_screen(modal, self._on_session_selected)

    async def _on_session_selected(self, session_summary) -> None:
        """Handle session selection from the modal."""
        if session_summary is None:
            return

        session_info = await self.client.get_session(session_summary.session_id)
        if session_info is None:
            return

        self.session_id = session_summary.session_id

        message_list = self.query_one("#message-list", MessageList)
        message_list.clear()

        self._session_title = session_info.title
        self._latest_usage = session_info.total_usage
        self._reset_streaming_state()
        self._reset_tool_contexts()

        self._hide_welcome_widget()

        messages = session_info.messages
        pending_user_text: Optional[str] = None

        if messages and messages[-1].type == MessageRole.USER:
            last_message = messages[-1]
            pending_user_text = last_message.original_text or last_message.get_text()
            messages = messages[:-1]

        await self._render_messages(message_list, messages)

        self._refresh_context_usage_label()

        input_widget = self.query_one("#user-input", InputTextArea)
        input_widget.load_text(pending_user_text or "")
        input_widget.focus()

    async def _cancel_current_query(self) -> None:
        """Send interrupt to server and reset UI."""
        if not self._is_processing:
            return

        await self.client.interrupt(self.session_id, "user-cancel")

        if self._query_worker and not self._query_worker.is_finished:
            self._query_worker.cancel()

        self._set_processing_state(False)
        self._reset_streaming_state()
        self._reset_tool_contexts()

        message_list = self.query_one("#message-list", MessageList)
        message_list.reset_auto_follow_output()

        input_widget = self.query_one("#user-input", InputTextArea)
        input_widget.focus()

    async def _process_message(self, user_text: str) -> None:
        """Send message to server and process event stream."""
        message_list = self.query_one("#message-list", MessageList)
        try:
            # Don't create user message locally - wait for MessageCompleteEvent from server
            # This aligns behavior with Web UI

            async for event in self.client.stream_chat(
                user_text, self.session_id, self.working_directory
            ):
                if not self._is_processing:
                    break
                await self._handle_query_event(event, message_list)
                await asyncio.sleep(0)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            log_full_exception(logger, "Query error in _run_query", e)
            if self._is_processing:
                error_msg = Message.system_message(f"Error: {str(e)}")
                await message_list.add_message(error_msg)

        finally:
            self._query_worker = None
            self._set_processing_state(False)
            self._reset_streaming_state()
            self._reset_tool_contexts()

            input_widget = self.query_one("#user-input", InputTextArea)
            input_widget.focus()

    async def _ensure_assistant_widget(
        self,
        message_list: MessageList,
        auto_follow: bool = True,
    ) -> MessageWidget:
        if not self._current_assistant_widget:
            self._current_assistant_widget = await message_list.create_streaming_widget(
                auto_follow=auto_follow
            )
        return self._current_assistant_widget

    async def _handle_query_event(
        self,
        event: QueryEvent,
        message_list: MessageList,
    ) -> None:
        if isinstance(event, ThinkingEvent):
            auto_follow = message_list.should_auto_follow_output()

            assistant_widget = await self._ensure_assistant_widget(
                message_list, auto_follow=auto_follow
            )
            await assistant_widget.append_thinking(event.thinking)
            message_list.schedule_scroll_to_latest(auto_follow)

        elif isinstance(event, TextEvent):
            auto_follow = message_list.should_auto_follow_output()

            assistant_widget = await self._ensure_assistant_widget(
                message_list, auto_follow=auto_follow
            )
            await assistant_widget.append_text(event.text)
            message_list.schedule_scroll_to_latest(auto_follow)

        elif isinstance(event, ToolUseEvent):
            auto_follow = message_list.should_auto_follow_output()
            tool_use = ToolUseContent(
                id=event.tool_use_id,
                name=event.tool_name,
                input=event.input,
            )

            assistant_widget = await self._ensure_assistant_widget(
                message_list, auto_follow=auto_follow
            )
            tool_widget = await assistant_widget.add_tool_use(tool_use)
            if tool_widget:
                self._tool_widget_context[event.tool_use_id] = tool_widget
            message_list.schedule_scroll_to_latest(auto_follow)

        elif isinstance(event, ToolResultEvent):
            auto_follow = message_list.should_auto_follow_output()
            tool_widget = self._tool_widget_context.get(event.tool_use_id)
            if tool_widget:
                tool_widget.set_result(event.result, event.is_error)
                message_list.schedule_scroll_to_latest(auto_follow)

        elif isinstance(event, MessageCompleteEvent):
            if event.message:
                auto_follow = message_list.should_auto_follow_output()
                if event.message.type == MessageRole.USER:
                    # Handle user message from server (align with Web UI behavior)
                    await message_list.add_message(
                        event.message, auto_follow=auto_follow
                    )
                elif event.message.type == MessageRole.ASSISTANT:
                    usage = event.message.get_usage()
                    if usage is not None:
                        self._latest_usage = usage
                        self._refresh_context_usage_label()
                    self._tool_widget_context.update(
                        self._current_assistant_widget.get_tool_widgets()
                        if self._current_assistant_widget
                        else {}
                    )
                    message_list.schedule_scroll_to_latest(auto_follow)
                elif event.message.type != MessageRole.TOOL:
                    # tool message is already added in ToolResultEvent
                    await message_list.add_message(
                        event.message, auto_follow=auto_follow
                    )

        elif isinstance(event, TurnCompleteEvent):
            self._reset_tool_contexts()
            self._current_assistant_widget = None

        elif isinstance(event, ErrorEvent):
            logger.debug(f"ErrorEvent received: {event.error}")
            error_msg = Message.system_message(f"Error: {event.error}")
            await message_list.add_message(error_msg)

    async def _render_messages(
        self,
        message_list: MessageList,
        messages: list[Message],
    ) -> None:
        """Render a list of messages."""
        assistant_widget: Optional[MessageWidget] = None
        tool_widget_context: dict[str, ToolUseWidget] = {}

        for message in messages:
            auto_follow = message_list.should_auto_follow_output()

            if message.type == MessageRole.ASSISTANT:
                assistant_widget = await message_list.create_streaming_widget(
                    message=message, auto_follow=auto_follow
                )
                tool_widget_context = assistant_widget.get_tool_widgets()
                continue

            if message.type == MessageRole.TOOL:
                tool_result = next(
                    (
                        block
                        for block in message.content
                        if isinstance(block, ToolResultContent)
                    ),
                    None,
                )
                if tool_result is None:
                    continue

                tool_widget = tool_widget_context.get(tool_result.tool_use_id)
                if tool_widget is not None:
                    tool_widget.set_result(tool_result.content, tool_result.is_error)

                continue

            assistant_widget = None
            tool_widget_context = {}
            await message_list.add_message(message, auto_follow=auto_follow)
