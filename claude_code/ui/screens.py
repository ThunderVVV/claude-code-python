"""Screen definitions for the TUI"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, VerticalGroup
from textual.widgets import Label, LoadingIndicator
from textual.screen import Screen
from textual import events
from textual.worker import Worker

from claude_code.core.context_window import (
    CONTEXT_WINDOW_TOKENS_ENV_VAR,
    format_token_count,
    get_used_context_percentage,
    get_used_context_tokens,
)
from claude_code.core.messages import (
    Message,
    MessageRole,
    ThinkingContent,
    TextContent,
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
from claude_code.core.query_engine import QueryEngine
from claude_code.core.query_engine import EngineStateSnapshot
from claude_code.core.session_store import PersistedSession, SessionStore, SessionSummary
from claude_code.ui.widgets import WelcomeWidget, InputTextArea
from claude_code.ui.message_widgets import (
    MessageList,
    AssistantMessageWidget,
    ToolUseWidget,
)
from claude_code.ui.session_resume_modal import SessionResumeModal


@dataclass
class FrontendSnapshot:
    """UI/query state captured before a new assistant turn starts."""

    engine_state_snapshot: EngineStateSnapshot
    snapshot_message_count: int
    snapshot_usage: object
    snapshot_input_text: Optional[str]


class REPLScreen(Screen):
    """Main REPL screen - aligned with TypeScript REPL.tsx"""

    def __init__(
        self,
        query_engine: QueryEngine,
        model_name: str = "claude-sonnet-4-6",
        context_window_tokens: Optional[int] = None,
        save_history: bool = True,
        session_store: SessionStore | None = None,
        initial_session: PersistedSession | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.query_engine = query_engine
        self.model_name = model_name
        self._context_window_tokens = context_window_tokens
        self._latest_usage = None
        self._is_processing = False
        self._current_assistant_widget: Optional[AssistantMessageWidget] = None
        self._current_thinking = ""
        self._current_text = ""
        self._show_welcome = True
        self._tool_use_context: dict[str, ToolUseContent] = {}
        self._tool_widget_context: dict[str, ToolUseWidget] = {}
        self._save_history_enabled = save_history
        self._query_worker: Optional[Worker] = None
        self._active_submission_id = 0
        self._current_submission_id: Optional[int] = None
        self._cancelled_submission_ids: set[int] = set()
        self._frontend_snapshot: Optional[FrontendSnapshot] = None
        self._session_store = session_store
        self._initial_session = initial_session
        self._session_title = initial_session.title if initial_session else None
        self._session_created_at = initial_session.created_at if initial_session else None

        # History management
        self._history: list[str] = []
        self._history_index: int = -1
        self._current_draft: str = ""
        self._history_file = Path.home() / ".claude-code-python/input_history.json"
        if save_history:
            self._load_history()

    def _load_history(self) -> None:
        """Load history from file"""
        if self._history_file.exists():
            try:
                with open(self._history_file, "r", encoding="utf-8") as f:
                    self._history = json.load(f)
            except Exception:
                self._history = []

    def _save_history(self) -> None:
        """Save history to file"""
        if not self._save_history_enabled:
            return
        try:
            with open(self._history_file, "w", encoding="utf-8") as f:
                json.dump(self._history, f, ensure_ascii=False)
        except Exception:
            pass

    def _add_to_history(self, text: str) -> bool:
        """Add text to history, avoiding duplicates"""
        added = False
        if text.strip() and (not self._history or self._history[-1] != text):
            self._history.append(text)
            # Keep only last 1000 entries
            if len(self._history) > 1000:
                self._history = self._history[-1000:]
            self._save_history()
            added = True
        self._history_index = -1
        self._current_draft = ""
        return added

    def compose(self) -> ComposeResult:
        # Scrollable content area
        with ScrollableContainer(id="content-area"):
            # Welcome widget - shown initially, hidden after first message
            yield WelcomeWidget(
                id="welcome-widget",
                model_name=self.model_name,
                cwd=self.query_engine.get_working_directory(),
            )
            # Message list (initially empty)
            yield MessageList(id="message-list")

        # Input area - always visible at bottom
        with VerticalGroup(id="input-area"):
            with Horizontal(id="processing-row"):
                yield LoadingIndicator(id="processing-indicator")
                yield Label("Working... (esc to interrupt)", id="processing-label", markup=False)
            yield InputTextArea(
                placeholder=self._input_placeholder_text(),
                id="user-input",
                language="text",
                show_line_numbers=False,
                tab_behavior="indent",
            )
            yield Label(self._context_usage_text(), id="context-usage", markup=False)

    async def on_mount(self) -> None:
        """Called when screen is mounted"""
        input_widget = self.query_one("#user-input", InputTextArea)
        input_widget.set_on_submit(self._on_input_submit)
        input_widget.focus()
        await self._restore_initial_session()

    def _on_input_submit(self, text: str) -> None:
        """Handle submit from InputTextArea."""
        self._start_message_submission(text)

    async def on_key(self, event: events.Key) -> None:
        """Handle keyboard events for history navigation"""
        if event.key == "escape" and self._is_processing:
            event.stop()
            await self._cancel_current_submission()
            return

        input_widget = self.query_one("#user-input", InputTextArea)
        if input_widget.has_focus:
            if event.key == "up":
                event.stop()
                self._navigate_history(1)  # Go to older history (increase index)
            elif event.key == "down":
                event.stop()
                self._navigate_history(-1)  # Go to newer history (decrease index)

    def _navigate_history(self, direction: int) -> None:
        """Navigate history (direction: 1 for up/older, -1 for down/newer)"""
        input_widget = self.query_one("#user-input", InputTextArea)

        # Save current draft when starting navigation
        if self._history_index == -1:
            self._current_draft = input_widget.text

        # Calculate new index
        # _history_index: -1 = current draft, 0 = newest, 1 = second newest, etc.
        new_index = self._history_index + direction

        # Clamp to valid range
        if new_index < -1:
            new_index = -1
        elif new_index >= len(self._history):
            new_index = len(self._history) - 1

        self._history_index = new_index

        if self._history_index == -1:
            # Restore draft
            input_widget.text = self._current_draft
        else:
            # Show from history (0 = newest = last item in list)
            input_widget.text = self._history[-(self._history_index + 1)]

        # Move cursor to end
        input_widget.move_cursor(input_widget.document.end)

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
        input_widget = self.query_one("#user-input", InputTextArea)
        processing_row = self.query_one("#processing-row", Horizontal)
        input_widget.disabled = is_processing
        processing_row.display = is_processing

        # When starting processing, ensure input collapses to single line
        if is_processing:
            input_widget.set_styles("height: 3;")
        else:
            # Reset height to auto when processing completes
            input_widget.set_styles("height: auto;")

        input_widget.refresh()

        input_widget.placeholder = (
            "Claude is responding..."
            if is_processing
            else self._input_placeholder_text()
        )

    def _input_placeholder_text(self) -> str:
        """Build the input hint shown below the transcript."""
        return (
            "Type your message and press Enter "
            "(Shift+Enter for new line)"
        )

    def _context_usage_text(self) -> str:
        """Build the context usage status line shown under the input box."""
        if not self._context_window_tokens:
            return (
                "Context: unavailable "
                f"(set {CONTEXT_WINDOW_TOKENS_ENV_VAR} in .env)"
            )

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
        """Refresh the context usage line after new usage data arrives."""
        label = self.query_one("#context-usage", Label)
        label.update(self._context_usage_text())

    def _reset_streaming_state(self) -> None:
        """Prepare for a fresh assistant response."""
        self._current_thinking = ""
        self._current_text = ""
        self._current_assistant_widget = None

    def _capture_frontend_snapshot(
        self,
        message_list: MessageList,
        submitted_text: str,
    ) -> None:
        """Capture transcript/query state so Escape can rewind the active turn."""
        widget_count = message_list.get_message_count()
        
        self._frontend_snapshot = FrontendSnapshot(
            engine_state_snapshot=self.query_engine.create_state_snapshot(),
            snapshot_message_count=widget_count,
            snapshot_usage=self._clone_usage(self._latest_usage),
            snapshot_input_text=submitted_text,
        )
        logger.debug(f"Captured frontend snapshot: message_count={widget_count}, "
                    f"snapshot_usage={self._frontend_snapshot.snapshot_usage}, "
                    f"snapshot_input_text={self._frontend_snapshot.snapshot_input_text}"
        )

    def _clear_frontend_snapshot(self) -> None:
        """Drop the active turn snapshot after the worker finishes."""
        self._frontend_snapshot = None

    @staticmethod
    def _clone_usage(usage):
        """Create a detached Usage copy when usage data is available."""
        if usage is None:
            return None
        return type(usage)(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )   

    def _update_and_save_snapshot(self) -> None:
        """Remember the transcript prefix to restore when Escape cancels the active node."""
        snapshot = self._frontend_snapshot

        if snapshot is None:
            return
        
        logger.debug(f"_update_and_save_snapshot:  "
                    f"message_count {snapshot.snapshot_message_count} -> {len(self.query_engine.get_messages())}, "
                    f"latest_usage {snapshot.snapshot_usage} -> {self._latest_usage}"
        )

        snapshot.snapshot_message_count = len(self.query_engine.get_messages())
        snapshot.snapshot_usage = self._clone_usage(self._latest_usage)

        # save to persist session store
        self._persist_session_boundary(
            snapshot_message_count=snapshot.snapshot_message_count,
            snapshot_usage=snapshot.snapshot_usage,
            current_turn=self.query_engine.state.current_turn,
        )

    def _should_handle_submission(self, submission_id: int) -> bool:
        """Return True when streamed events still belong to the live submission."""
        return (
            self._current_submission_id == submission_id
            and submission_id not in self._cancelled_submission_ids
        )

    async def _cancel_current_submission(self) -> None:
        """Interrupt the active query and rewind the transcript to the last stable block."""
        submission_id = self._current_submission_id
        if submission_id is None or not self._is_processing:
            return

        self._cancelled_submission_ids.add(submission_id)
        self.query_engine.interrupt("user-cancel")

        if self._query_worker and not self._query_worker.is_finished:
            self._query_worker.cancel()

        await self._rollback_active_turn()
        self._set_processing_state(False)
        input_widget = self.query_one("#user-input", InputTextArea)
        input_widget.focus()

    async def _rollback_active_turn(self) -> None:
        """Remove partial assistant output and restore query state after cancellation."""
        snapshot = self._frontend_snapshot
        if snapshot is None:
            return

        message_list = self.query_one("#message-list", MessageList)
        await message_list.truncate(snapshot.snapshot_message_count)

        self.query_engine.rollback_to_snapshot(
            snapshot.engine_state_snapshot,
            message_count=snapshot.snapshot_message_count,
        )

        rollback_usage = self._clone_usage(snapshot.snapshot_usage)
        if rollback_usage is not None:
            self.query_engine.state.total_usage = rollback_usage
        self._latest_usage = rollback_usage
        self._refresh_context_usage_label()
        self._reset_streaming_state()
        self._tool_use_context = {}
        self._tool_widget_context = {}

        if snapshot.snapshot_input_text is not None:
            input_widget = self.query_one("#user-input", InputTextArea)
            input_widget.load_text(snapshot.snapshot_input_text)
            input_widget.move_cursor(input_widget.document.end)
            self._history_index = -1
            self._current_draft = snapshot.snapshot_input_text

    def _start_message_submission(self, submitted_value: str) -> None:
        """Queue a prompt submission without blocking the UI event loop."""
        if self._is_processing:
            return

        input_widget = self.query_one("#user-input", InputTextArea)
        user_text = submitted_value.strip()

        if not user_text:
            return

        # Only a literal "/exit" command should close the TUI.
        if user_text.lower() == "/exit":
            self.app.exit()
            return

        # Handle "/clear" or "/new" command to start a new session
        if user_text.lower() == "/clear" or user_text.lower() == "/new":
            self._start_new_session()
            return

        # Handle "/sessions" command to show session picker
        if user_text.lower() == "/sessions":
            self._show_session_picker()
            return

        self._hide_welcome_widget()

        # Add to history
        self._add_to_history(submitted_value)

        # Reset the document so the next prompt always starts from a clean single line.
        input_widget.load_text("")
        self._reset_streaming_state()
        self._tool_use_context = {}
        self._tool_widget_context = {}
        try:
            message_list = self.query_one("#message-list", MessageList)
            self._capture_frontend_snapshot(message_list, submitted_value)
            message_list.reset_auto_follow_output()
        except Exception as e:
            logger.error(f"Error capturing frontend snapshot: {str(e)}")
        self.query_engine.clear_interrupt()
        self._active_submission_id += 1
        submission_id = self._active_submission_id
        self._current_submission_id = submission_id
        self._cancelled_submission_ids.discard(submission_id)
        self._set_processing_state(True)
        self.refresh()
        self._query_worker = self.run_worker(
            self._process_message(user_text, submission_id),
            group="query",
            exclusive=True,
            exit_on_error=False,
        )

    def _start_new_session(self) -> None:
        """Clear the current session and start a fresh one.

        This clears all messages, resets the session ID, and shows the welcome widget.
        Equivalent to starting a new TUI session.
        """
        if self._is_processing:
            return

        # Clear the query engine state and generate new session ID
        self.query_engine.clear()

        # Clear the message list UI
        message_list = self.query_one("#message-list", MessageList)
        message_list.clear()

        # Reset session metadata
        self._session_title = None
        self._session_created_at = None
        self._latest_usage = None

        # Reset internal state
        self._reset_streaming_state()
        self._tool_use_context = {}
        self._tool_widget_context = {}
        self._frontend_snapshot = None
        self._cancelled_submission_ids.clear()

        # Clear input and show welcome widget
        input_widget = self.query_one("#user-input", InputTextArea)
        input_widget.load_text("")

        # Show welcome widget again
        self._show_welcome = True
        try:
            welcome_widget = self.query_one("#welcome-widget", WelcomeWidget)
            welcome_widget.display = True
        except Exception:
            pass

        # Refresh context usage label
        self._refresh_context_usage_label()

        # Focus input
        input_widget.focus()

    def _show_session_picker(self) -> None:
        """Show the session picker modal to switch between sessions."""
        if self._is_processing:
            return

        if self._session_store is None:
            return

        # Clear input
        input_widget = self.query_one("#user-input", InputTextArea)
        input_widget.load_text("")

        # Push the session resume modal
        self.app.push_screen(
            SessionResumeModal(
                self._session_store,
                current_session_id=self.query_engine.get_session_id(),
            ),
            callback=self._on_session_selected,
        )

    def _on_session_selected(self, session: Optional[SessionSummary]) -> None:
        """Handle session selection from the picker."""
        if session is None:
            return

        # Load the selected session
        self._load_session(session.session_id)

    def _load_session(self, session_id: str) -> None:
        """Load a session by ID and replace the current session."""
        if self._session_store is None:
            return

        session = self._session_store.load_session(session_id)
        if session is None:
            return

        # Reset the query engine state WITHOUT generating a new session_id
        self.query_engine.state.clear()
        self.query_engine.state.session_id = session.session_id
        self.query_engine._undo_operations = []
        self.query_engine.clear_interrupt()

        # Load messages into query engine
        for message in session.messages:
            self.query_engine.state.add_message(message)

        # Update session metadata
        self._session_title = session.title
        self._session_created_at = session.created_at
        self._latest_usage = session.total_usage

        # Clear and re-render the message list
        message_list = self.query_one("#message-list", MessageList)
        message_list.clear()

        # Reset internal state
        self._reset_streaming_state()
        self._tool_use_context = {}
        self._tool_widget_context = {}
        self._frontend_snapshot = None
        self._cancelled_submission_ids.clear()

        # Hide welcome widget
        self._hide_welcome_widget()

        # Refresh context usage label
        self._refresh_context_usage_label()

        # Schedule rendering of persisted messages
        self.run_worker(
            self._restore_session_messages(session),
            group="restore-session",
            exclusive=True,
        )

    async def _restore_session_messages(self, session: PersistedSession) -> None:
        """Restore session messages to the UI."""
        if not session.messages:
            return

        self._latest_usage = self._clone_usage(session.total_usage)
        self._refresh_context_usage_label()

        message_list = self.query_one("#message-list", MessageList)
        await self._render_persisted_messages(message_list, session.messages)

        # Focus input
        input_widget = self.query_one("#user-input", InputTextArea)
        input_widget.focus()

    async def _process_message(self, user_text: str, submission_id: int) -> None:
        """Run a query in the background so the TUI stays responsive."""
        message_list = self.query_one("#message-list", MessageList)
        try:
            async for event in self.query_engine.submit_message(user_text):
                if not self._should_handle_submission(submission_id):
                    break
                await self._handle_query_event(event, message_list, submission_id)
                await asyncio.sleep(0)

        except asyncio.CancelledError:
            if not self._should_handle_submission(submission_id):
                return
            raise
        except Exception as e:
            if self._should_handle_submission(submission_id):
                error_msg = Message.system_message(f"Error: {str(e)}")
                await message_list.add_message(error_msg)

        finally:
            if self._current_submission_id == submission_id:
                self._current_submission_id = None
                self._query_worker = None
                self._clear_frontend_snapshot()
                self._set_processing_state(False)
                input_widget = self.query_one("#user-input", InputTextArea)
                input_widget.focus()
            self._cancelled_submission_ids.discard(submission_id)

    async def _ensure_assistant_widget(
        self,
        message_list: MessageList,
        message: Optional[Message] = None,
        auto_follow: bool = True,
    ) -> AssistantMessageWidget:
        """Return the live assistant widget for the current response."""
        if not self._current_assistant_widget:
            self._current_assistant_widget = await message_list.create_assistant_widget(
                message=message,
                auto_follow=auto_follow,
            )
        elif message:
            await self._current_assistant_widget.sync_from_message(message)
        return self._current_assistant_widget

    async def _handle_query_event(
        self,
        event: QueryEvent,
        message_list: MessageList,
        submission_id: int,
    ) -> None:
        """
        Handle a query event - aligned with TypeScript handleMessageFromStream in messages.ts

        Key difference from before: we use AssistantMessageWidget which allows
        incremental updates without recreating the entire widget.
        """
        if not self._should_handle_submission(submission_id):
            return

        if isinstance(event, ThinkingEvent):
            auto_follow = message_list.should_auto_follow_output()
            # Accumulate thinking
            self._current_thinking += event.thinking

            # Create assistant widget on first thinking if not exists
            assistant_widget = await self._ensure_assistant_widget(
                message_list,
                auto_follow=auto_follow,
            )

            # Stream the thinking delta directly into the markdown widget.
            await assistant_widget.append_thinking(event.thinking)
            message_list.schedule_scroll_to_latest(auto_follow)

        elif isinstance(event, TextEvent):
            auto_follow = message_list.should_auto_follow_output()
            # Accumulate text
            self._current_text += event.text

            # Create assistant widget on first text if not exists
            assistant_widget = await self._ensure_assistant_widget(
                message_list,
                auto_follow=auto_follow,
            )

            # Stream the text delta directly into the markdown widget.
            await assistant_widget.append_text(event.text)
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
            # Ensure we have an assistant widget
            assistant_widget = await self._ensure_assistant_widget(
                message_list,
                auto_follow=auto_follow,
            )

            # Add tool use to the existing widget (no recreation)
            tool_widget = await assistant_widget.add_tool_use(tool_use)
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
                await message_list.add_tool_result(
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
                    assistant_widget = await self._ensure_assistant_widget(
                        message_list,
                        event.message,
                        auto_follow=auto_follow,
                    )
                    usage = event.message.get_usage()
                    if usage is not None:
                        self._latest_usage = usage
                        self._refresh_context_usage_label()
                    self._tool_widget_context.update(
                        assistant_widget.get_tool_widgets()
                    )
                    self._current_text = event.message.get_text()
                    message_list.schedule_scroll_to_latest(auto_follow)
                elif event.message.type != MessageRole.TOOL:
                    await message_list.add_message(
                        event.message,
                        auto_follow=auto_follow,
                    )

        elif isinstance(event, TurnCompleteEvent):
            logger.debug(f"TurnCompleteEvent: stop_reason={event.stop_reason}")
            if event.stop_reason == "stop":
                self._update_and_save_snapshot()
            self._tool_use_context = {}
            self._tool_widget_context = {}
            self._reset_streaming_state()

        elif isinstance(event, ErrorEvent):
            error_msg = Message.system_message(f"Error: {event.error}")
            await message_list.add_message(error_msg)

    async def _restore_initial_session(self) -> None:
        """Render a previously saved session into the transcript."""
        session = self._initial_session
        if session is None or not session.messages:
            return

        self._hide_welcome_widget()
        self._latest_usage = self._clone_usage(session.total_usage)
        self._refresh_context_usage_label()

        message_list = self.query_one("#message-list", MessageList)
        await self._render_persisted_messages(message_list, session.messages)

    async def _render_persisted_messages(
        self,
        message_list: MessageList,
        messages: list[Message],
    ) -> None:
        """Replay persisted messages through the same transcript structure as live turns."""
        assistant_widget: Optional[AssistantMessageWidget] = None
        tool_use_context: dict[str, ToolUseContent] = {}
        tool_widget_context: dict[str, ToolUseWidget] = {}

        for message in messages:
            auto_follow = message_list.should_auto_follow_output()
            
            if message.type == MessageRole.ASSISTANT:
                assistant_widget = await message_list.create_assistant_widget(
                    message=message,
                    auto_follow=auto_follow,
                )
                tool_widget_context = assistant_widget.get_tool_widgets()
                tool_use_context = {
                    tool_use.id: tool_use
                    for tool_use in message.get_tool_uses()
                    if tool_use.id
                }
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

                merged_result = False
                tool_widget = tool_widget_context.get(tool_result.tool_use_id)
                if tool_widget is not None:
                    tool_widget.set_result(tool_result.content, tool_result.is_error)
                    merged_result = True
                elif assistant_widget is not None:
                    merged_result = assistant_widget.add_tool_result(
                        tool_result.tool_use_id,
                        tool_result.content,
                        tool_result.is_error,
                    )

                if not merged_result:
                    tool_use = tool_use_context.get(tool_result.tool_use_id)
                    await message_list.add_tool_result(
                        tool_name=tool_use.name if tool_use else "Tool",
                        tool_input=tool_use.input if tool_use else {},
                        result=tool_result.content,
                        is_error=tool_result.is_error,
                        auto_follow=auto_follow,
                    )
                continue

            assistant_widget = None
            tool_use_context = {}
            tool_widget_context = {}
            await message_list.add_message(message, auto_follow=auto_follow)

    def _persist_session_boundary(
        self,
        *,
        snapshot_message_count: int,
        snapshot_usage: Optional[Usage],
        current_turn: int,
    ) -> None:
        """Persist the same stable prefix used by Escape rollback."""
        if self._session_store is None:
            return

        stable_messages = list(self.query_engine.get_messages()[:snapshot_message_count])
        usage = self._clone_usage(snapshot_usage) or self._clone_usage(
            self.query_engine.state.total_usage
        )

        try:
            session = self._session_store.save_snapshot(
                session_id=self.query_engine.get_session_id(),
                messages=stable_messages,
                working_directory=self.query_engine.get_working_directory(),
                current_turn=current_turn,
                title=self._session_title,
                created_at=self._session_created_at,
                model_name=self.model_name,
                total_usage=usage,
            )
        except Exception:
            return

        self._session_title = session.title
        self._session_created_at = session.created_at
