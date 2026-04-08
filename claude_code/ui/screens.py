"""Screen definitions for the TUI"""

from __future__ import annotations

import asyncio
import os
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, VerticalGroup
from textual.widgets import Input, Label, LoadingIndicator
from textual.screen import Screen

from claude_code.core.messages import (
    Message,
    MessageRole,
    TextContent,
    ToolUseContent,
    QueryEvent,
    TextEvent,
    ToolUseEvent,
    ToolResultEvent,
    MessageCompleteEvent,
    TurnCompleteEvent,
    ErrorEvent,
)
from claude_code.core.query_engine import QueryEngine
from claude_code.ui.widgets import WelcomeWidget
from claude_code.ui.message_widgets import (
    MessageList,
    AssistantMessageWidget,
    ToolUseWidget,
)


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
                id="welcome-widget", model_name=self.model_name, cwd=os.getcwd()
            )
            # Message list (initially empty)
            yield MessageList(id="message-list")

        # Input area - always visible at bottom
        with VerticalGroup(id="input-area"):
            with Horizontal(id="processing-row"):
                yield LoadingIndicator(id="processing-indicator")
                yield Label("Working...", id="processing-label", markup=False)
            yield Input(
                placeholder="Type your message and press Enter", id="user-input"
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

    async def _handle_query_event(
        self, event: QueryEvent, message_list: MessageList
    ) -> None:
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
                    self._tool_widget_context.update(
                        assistant_widget.get_tool_widgets()
                    )
                    self._current_text = event.message.get_text()
                    message_list.schedule_scroll_to_latest(auto_follow)
                elif event.message.type != MessageRole.TOOL:
                    message_list.add_message(event.message, auto_follow=auto_follow)

        elif isinstance(event, TurnCompleteEvent):
            self._reset_streaming_state()

        elif isinstance(event, ErrorEvent):
            error_msg = Message.system_message(f"Error: {event.error}")
            message_list.add_message(error_msg)
