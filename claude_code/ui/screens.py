"""Screen definitions for the TUI - stateless frontend, only handles display"""

from __future__ import annotations

import asyncio
import json
import os
import re
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
from claude_code.core.settings import SettingsStore
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
from claude_code.ui.rewind_modal import RewindModal
from claude_code.ui.model_select_modal import ModelSelectModal
from claude_code.ui.autocomplete import (
    AutocompletePopup,
    AutocompleteMode,
    Command,
    CommandRegistry,
    AtOption,
)
from claude_code.utils.logging_config import log_full_exception, tui_log

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
        self._snapshot_status: Optional[dict] = None

        self._history: list[str] = []
        self._history_index: int = 0
        self._nav_items: list[str] = []
        self._history_file = Path.home() / ".claude-code-python/input_history.json"
        self._load_history()

        self._session_title: Optional[str] = None
        self._settings_store = SettingsStore()
        self._settings = self._settings_store.ensure_settings()
        self._current_model_id = self._settings.current_model
        current_model = self._settings.get_current_model()
        self._current_model_name = current_model.model_name if current_model else "unconfigured"
        self._context_window_tokens = (
            get_configured_context_window_tokens(str(current_model.context))
            if current_model
            else None
        )

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
                model_name=self._current_model_name,
                cwd=self.working_directory,
            )
            yield MessageList(id="message-list")

        with VerticalGroup(id="input-area"):
            with Horizontal(id="processing-row"):
                yield LoadingIndicator(id="processing-indicator")
                yield Label(
                    "Working... (esc to interrupt)", id="processing-label", markup=False
                )
            yield AutocompletePopup(id="autocomplete-popup")
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

        autocomplete_popup = self.query_one("#autocomplete-popup", AutocompletePopup)
        autocomplete_popup.set_working_directory(self.working_directory)

    def _on_input_submit(self, text: str) -> None:
        tui_log(f"_on_input_submit: text={text!r}")
        self._start_message_submission(text)

    def on_text_area_changed(self, event: InputTextArea.Changed) -> None:
        """Handle text changes in the input area for autocomplete."""
        if event.text_area.id != "user-input":
            return

        input_widget = self.query_one("#user-input", InputTextArea)
        if not input_widget.has_focus:
            return

        cursor_pos = input_widget.cursor_location[1]
        line_text = input_widget.document.get_line(input_widget.cursor_location[0])
        text_before_cursor = line_text[:cursor_pos]

        tui_log(f"on_user_input_changed: text_before_cursor={text_before_cursor!r}")

        autocomplete_popup = self.query_one("#autocomplete-popup", AutocompletePopup)

        slash_match = re.match(r"^/(\S*)$", text_before_cursor)
        if slash_match:
            tui_log(f"Slash match: {slash_match.group(1)}")
            autocomplete_popup.show_slash_commands(slash_match.group(1))
            input_widget.set_autocomplete_active(True)
            self._schedule_autocomplete_scroll_adjustment()
            return

        at_match = re.search(r"@(\S*)$", text_before_cursor)
        if at_match:
            tui_log(f"At match: {at_match.group(1)}")
            autocomplete_popup.show_at_options(at_match.group(1))
            input_widget.set_autocomplete_active(True)
            self._schedule_autocomplete_scroll_adjustment()
            return

        if autocomplete_popup.is_visible():
            tui_log("Closing autocomplete")
            autocomplete_popup.hide()
            input_widget.set_autocomplete_active(False)

    def on_autocomplete_popup_selected(self, event: AutocompletePopup.Selected) -> None:
        """Handle selection from autocomplete popup."""
        tui_log(f"on_autocomplete_popup_selected: item={event.item}")
        self._handle_autocomplete_selection(event.item, event.mode)
        autocomplete_popup = self.query_one("#autocomplete-popup", AutocompletePopup)
        autocomplete_popup.hide()

    def _navigate_autocomplete_popup(self, direction: int) -> None:
        """Navigate autocomplete popup from InputTextArea."""
        tui_log(f"_navigate_autocomplete_popup: direction={direction}")
        autocomplete_popup = self.query_one("#autocomplete-popup", AutocompletePopup)
        if direction < 0:
            autocomplete_popup.navigate_up()
        else:
            autocomplete_popup.navigate_down()

    def _select_autocomplete_popup(self) -> None:
        """Select autocomplete item from InputTextArea."""
        tui_log("_select_autocomplete_popup")
        autocomplete_popup = self.query_one("#autocomplete-popup", AutocompletePopup)
        selected = autocomplete_popup.select_current()
        if selected:
            self._handle_autocomplete_selection(selected, autocomplete_popup.mode)
        autocomplete_popup.hide()

    def _handle_autocomplete_selection(
        self, item: Command | AtOption, mode: AutocompleteMode
    ) -> None:
        """Handle autocomplete item selection."""
        tui_log(f"_handle_autocomplete_selection: item={item}, mode={mode}")
        input_widget = self.query_one("#user-input", InputTextArea)

        if isinstance(item, Command):
            input_widget.insert_autocomplete(f"/{item.trigger} ", mode)
        elif isinstance(item, AtOption):
            if item.type == "web":
                input_widget.insert_autocomplete("@web ", mode)
            else:
                input_widget.insert_autocomplete(f"@{item.path or item.display} ", mode)

        input_widget.set_autocomplete_active(False)
        input_widget.focus()

    async def on_mouse_down(self, event: events.MouseDown) -> None:
        self._focus_input_if_needed()

    async def on_mouse_up(self, event: events.MouseUp) -> None:
        self._focus_input_if_needed()

    def _focus_input_if_needed(self) -> None:
        """Focus input widget if not already focused and not processing."""
        input_widget = self.query_one("#user-input", InputTextArea)
        if not input_widget.has_focus and not self._is_processing:
            input_widget.focus()

    def _scroll_content_area_to_bottom(self) -> None:
        """Pin the transcript to the bottom when autocomplete expands the input area."""
        try:
            content_area = self.query_one("#content-area", ScrollableContainer)
            content_area.refresh(layout=True)
            content_area.scroll_to(
                y=content_area.max_scroll_y,
                animate=False,
                force=True,
                immediate=True,
            )
        except Exception:
            pass

    def _schedule_autocomplete_scroll_adjustment(self) -> None:
        """Compensate scroll position after autocomplete expands the input area."""
        try:
            input_area = self.query_one("#input-area", VerticalGroup)
            content_area = self.query_one("#content-area", ScrollableContainer)
            self._autocomplete_scroll_baseline_height = input_area.outer_size.height
            self._autocomplete_scroll_was_near_bottom = (
                content_area.scroll_y >= max(content_area.max_scroll_y - 1, 0)
            )
        except Exception:
            self._autocomplete_scroll_baseline_height = 0
            self._autocomplete_scroll_was_near_bottom = False

        self.refresh(layout=True)
        self.call_after_refresh(self._apply_autocomplete_scroll_adjustment)
        self.set_timer(0.01, self._apply_autocomplete_scroll_adjustment)
        self.set_timer(0.05, self._apply_autocomplete_scroll_adjustment)

    def _apply_autocomplete_scroll_adjustment(self) -> None:
        """Shift transcript scroll by the popup height delta to keep the bottom anchored."""
        try:
            input_area = self.query_one("#input-area", VerticalGroup)
            content_area = self.query_one("#content-area", ScrollableContainer)
            new_height = input_area.outer_size.height
            delta = max(new_height - self._autocomplete_scroll_baseline_height, 0)

            if delta > 0:
                target_scroll = min(
                    content_area.max_scroll_y,
                    content_area.scroll_y + delta,
                )
                content_area.scroll_to(
                    y=target_scroll,
                    animate=False,
                    force=True,
                    immediate=True,
                )

            if self._autocomplete_scroll_was_near_bottom:
                self._scroll_content_area_to_bottom()
        except Exception:
            pass

    async def on_key(self, event: events.Key) -> None:
        if event.key == "escape" and self._is_processing:
            event.stop()
            await self._cancel_current_query()
            return

        autocomplete_popup = self.query_one("#autocomplete-popup", AutocompletePopup)
        if autocomplete_popup.is_visible():
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
        model_text = f"Model: {self._current_model_name}"

        if self._latest_usage and self._context_window_tokens:
            used_tokens = get_used_context_tokens(self._latest_usage)
            used_percentage = get_used_context_percentage(
                self._latest_usage,
                self._context_window_tokens,
            )
            context_text = (
                "Context: "
                f"{format_token_count(used_tokens)}/"
                f"{format_token_count(self._context_window_tokens)} "
                f"({used_percentage}%)"
            )
        else:
            context_text = "Context: unavailable (waiting for server)"

        snapshot_text = ""
        if self._snapshot_status and self._snapshot_status.get("available"):
            additions = self._snapshot_status.get("additions", 0)
            deletions = self._snapshot_status.get("deletions", 0)
            files = self._snapshot_status.get("files", 0)
            if files > 0:
                snapshot_text = (
                    f" | Modified: +{additions}/-{deletions} in {files} file(s)"
                )

        return f"{model_text} | {context_text}{snapshot_text}"

    def _refresh_context_usage_label(self) -> None:
        label = self.query_one("#context-usage", Label)
        label.update(self._context_usage_text())

    async def _refresh_snapshot_status(self) -> None:
        """Fetch snapshot status and update the context label."""
        try:
            status = await self.client.get_snapshot_status(self.session_id)
            self._snapshot_status = status
            self._refresh_context_usage_label()
        except Exception as e:
            tui_log(f"Failed to refresh snapshot status: {e}")

    def _reset_streaming_state(self) -> None:
        self._current_assistant_widget = None

    def _reset_tool_contexts(self) -> None:
        """Reset tool widget contexts."""
        self._tool_widget_context = {}

    def _start_message_submission(self, submitted_value: str) -> None:
        tui_log(f"_start_message_submission: {submitted_value!r}")
        if self._is_processing:
            return

        input_widget = self.query_one("#user-input", InputTextArea)
        user_text = submitted_value.strip()

        if not user_text:
            return

        user_text_lower = user_text.lower()

        if user_text_lower == "/exit":
            self.app.exit()
            return

        if user_text_lower in ("/clear", "/new"):
            asyncio.create_task(self._start_new_session())
            return

        if user_text_lower == "/sessions":
            self._show_sessions_modal()
            return

        if user_text_lower == "/rewind":
            tui_log("REWIND COMMAND DETECTED!")
            asyncio.create_task(self._show_rewind_modal())
            return

        if user_text_lower == "/help":
            self._show_help()
            return

        if user_text_lower == "/model":
            self._show_model_modal()
            return

        if user_text_lower.startswith("/model "):
            asyncio.create_task(self._handle_model_command(user_text))
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

    def _show_help(self) -> None:
        """Show help information."""
        registry = CommandRegistry.get_instance()
        commands = registry.get_commands()
        help_text = "Available commands:\n" + "\n".join(
            f"  {cmd.title} - {cmd.description or 'No description'}" for cmd in commands
        )
        message_list = self.query_one("#message-list", MessageList)
        help_msg = Message.system_message(help_text)
        asyncio.create_task(message_list.add_message(help_msg))

    def _show_model_modal(self) -> None:
        """Show the model selection modal."""
        if self._is_processing:
            return

        self._settings = self._settings_store.ensure_settings()
        modal = ModelSelectModal(
            settings=self._settings,
            current_model_id=self._current_model_id,
        )
        self.app.push_screen(modal, self._on_model_selected)

    async def _handle_model_command(self, user_text: str) -> None:
        """Show available models or switch to a configured model."""
        parts = user_text.split(maxsplit=1)
        if len(parts) == 1:
            current = self._current_model_id or "unconfigured"
            lines = [f"Current model: {current}"]
            if self._settings.models:
                lines.append("Available models:")
                lines.extend(f"  {model_id}" for model_id in self._settings.models)
            else:
                lines.append("No models configured in ~/.claude-code-python/settings.json")

            message_list = self.query_one("#message-list", MessageList)
            await message_list.add_message(Message.system_message("\n".join(lines)))
            return

        model_id = parts[1].strip()
        if not model_id:
            return

        result = await self.client.switch_model(self.session_id, model_id)
        message_list = self.query_one("#message-list", MessageList)
        if not result.get("success"):
            error_text = result.get("message") or f"Unknown model: {model_id}"
            await message_list.add_message(
                Message.system_message(f"Model switch failed: {error_text}")
            )
            return

        self._settings = self._settings_store.ensure_settings()
        self._current_model_id = result.get("model_id", model_id)
        self._current_model_name = result.get("model_name", self._current_model_name)
        context_value = result.get("context")
        self._context_window_tokens = (
            get_configured_context_window_tokens(str(context_value))
            if context_value is not None
            else None
        )
        input_widget = self.query_one("#user-input", InputTextArea)
        input_widget.load_text("")
        input_widget.focus()
        self._refresh_context_usage_label()
        self._update_welcome_model_name()
        await message_list.add_message(
            Message.system_message(
                f"Switched model to {self._current_model_id} ({self._current_model_name})"
            )
        )

    async def _on_model_selected(self, model_id: Optional[str]) -> None:
        """Handle model selection from the modal."""
        if not model_id:
            return
        await self._handle_model_command(f"/model {model_id}")

    def _update_welcome_model_name(self) -> None:
        """Refresh the welcome widget model label."""
        try:
            welcome_widget = self.query_one("#welcome-widget", WelcomeWidget)
            welcome_widget.set_model_name(self._current_model_name)
        except Exception:
            pass

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
        self._snapshot_status = None
        self._reset_streaming_state()
        self._reset_tool_contexts()
        self._settings = self._settings_store.ensure_settings()
        self._current_model_id = self._settings.current_model
        current_model = self._settings.get_current_model()
        self._current_model_name = current_model.model_name if current_model else "unconfigured"
        self._context_window_tokens = (
            get_configured_context_window_tokens(str(current_model.context))
            if current_model
            else None
        )

        input_widget = self.query_one("#user-input", InputTextArea)
        input_widget.load_text("")

        self._show_welcome = True
        try:
            welcome_widget = self.query_one("#welcome-widget", WelcomeWidget)
            welcome_widget.display = True
            welcome_widget.set_model_name(self._current_model_name)
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

    async def _show_rewind_modal(self) -> None:
        """Show the rewind modal for selecting a message to rewind to."""
        tui_log("_show_rewind_modal called")
        if self._is_processing:
            tui_log("_show_rewind_modal: processing, returning")
            return

        session_info = await self.client.get_session(self.session_id)
        tui_log(
            f"_show_rewind_modal: session_info={session_info is not None}, messages={len(session_info.messages) if session_info else 0}"
        )
        if session_info is None:
            return

        modal = RewindModal(
            messages=session_info.messages,
            client=self.client,
            session_id=self.session_id,
        )
        self.app.push_screen(modal, self._on_rewind_selected)

    async def _on_rewind_selected(self, result) -> None:
        """Handle rewind selection from the modal."""
        tui_log(f"_on_rewind_selected: result={result!r}")
        if result is None:
            return

        message_id, message_idx = result
        tui_log(
            f"_on_rewind_selected: message_id={message_id!r}, message_idx={message_idx}"
        )

        self._set_processing_state(True)
        try:
            session_info = await self.client.get_session(self.session_id)
            if not session_info:
                return

            revert_result = await self.client.revert(
                self.session_id,
                target_message_id=message_id,
            )

            if revert_result.get("success"):
                summary = revert_result.get("summary", {})
                additions = summary.get("additions", 0)
                deletions = summary.get("deletions", 0)
                files = summary.get("files", 0)

                message_list = self.query_one("#message-list", MessageList)
                message_list.clear()

                session_info = await self.client.get_session(self.session_id)
                if session_info and session_info.messages:
                    messages_to_render = (
                        session_info.messages[:-1]
                        if len(session_info.messages) > 0
                        else []
                    )
                    await self._render_messages(message_list, messages_to_render)

                    last_msg = (
                        session_info.messages[-1] if session_info.messages else None
                    )
                    if last_msg and last_msg.type == MessageRole.USER:
                        pending_text = last_msg.original_text or last_msg.get_text()
                        input_widget = self.query_one("#user-input", InputTextArea)
                        input_widget.load_text(pending_text)
                        line_count = input_widget.document.line_count
                        if line_count > 0:
                            last_line = line_count - 1
                            last_col = len(input_widget.document.get_line(last_line))
                            input_widget.move_cursor((last_line, last_col))

                info_msg = Message.system_message(
                    f"Rewound to message #{message_idx + 1}. "
                    f"Undid changes in {files} file(s): "
                    f"removed {additions} line(s), restored {deletions} line(s)."
                )
                await message_list.add_message(info_msg)
                await self._refresh_snapshot_status()
            else:
                error_msg = revert_result.get("message", "Unknown error")
                message_list = self.query_one("#message-list", MessageList)
                error_widget = Message.system_message(f"Rewind failed: {error_msg}")
                await message_list.add_message(error_widget)

        except Exception as e:
            log_full_exception(logger, "Rewind error", e)
            message_list = self.query_one("#message-list", MessageList)
            error_widget = Message.system_message(f"Rewind error: {str(e)}")
            await message_list.add_message(error_widget)

        finally:
            self._set_processing_state(False)
            input_widget = self.query_one("#user-input", InputTextArea)
            input_widget.focus()

    async def _on_session_selected(self, session_summary) -> None:
        """Handle session selection from the modal."""
        if session_summary is None:
            return

        session_info = await self.client.get_session(session_summary.session_id)
        if session_info is None:
            return

        self.session_id = session_summary.session_id
        self._settings = self._settings_store.ensure_settings()

        message_list = self.query_one("#message-list", MessageList)
        message_list.clear()

        self._session_title = session_info.title
        self._latest_usage = session_info.total_usage
        self._current_model_id = session_info.model_id or self._current_model_id
        self._current_model_name = session_info.model_name or self._current_model_name
        if self._current_model_id in self._settings.models:
            model_settings = self._settings.models[self._current_model_id]
            self._context_window_tokens = get_configured_context_window_tokens(
                str(model_settings.context)
            )
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
        await self._refresh_snapshot_status()

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
            asyncio.create_task(self._refresh_snapshot_status())

        elif isinstance(event, ErrorEvent):
            tui_log(f"ErrorEvent received: {event.error}")
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
