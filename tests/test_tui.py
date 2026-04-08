"""Headless tests for the Textual TUI."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from textual.css.query import NoMatches
from textual.widgets import Collapsible
from textual.widgets import Label
from textual.widgets import LoadingIndicator
from textual.widgets import Markdown
from textual.widgets import _markdown as textual_markdown
from textual.containers import Horizontal
from textual.widgets._markdown import MarkdownH2, MarkdownH4

from claude_code.core.messages import (
    Message,
    MessageCompleteEvent,
    TextContent,
    TextEvent,
    ThinkingContent,
    ThinkingEvent,
    ToolResultEvent,
    ToolUseContent,
    ToolUseEvent,
    TurnCompleteEvent,
    Usage,
)
from claude_code.ui.app import ClaudeCodeApp
from textual.content import Span
from claude_code.ui.diff_view import DiffView
from claude_code.ui.message_widgets import (
    AssistantMessageWidget,
    MessageList,
    ThinkingBlockWidget,
    ToolUseWidget,
)
from claude_code.ui.widgets import WelcomeWidget, InputTextArea


class FakeQueryEngine:
    """Minimal async event source for TUI tests."""

    def __init__(self, event_factory):
        self._event_factory = event_factory

    async def initialize(self) -> None:
        """Match the real engine interface."""

    async def close(self) -> None:
        """Match the real engine interface."""

    async def submit_message(self, user_text: str):
        for item in self._event_factory(user_text):
            if isinstance(item, (int, float)):
                await asyncio.sleep(item)
                continue
            yield item


class TUITestCase(unittest.IsolatedAsyncioTestCase):
    """End-to-end TUI behavior tests."""

    @staticmethod
    def _label_text(label: Label) -> str:
        rendered = label.render()
        return rendered.plain if hasattr(rendered, "plain") else str(rendered)

    async def test_only_literal_exit_quits_tui(self) -> None:
        submitted_messages: list[str] = []

        def event_factory(user_text: str):
            submitted_messages.append(user_text)
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                MessageCompleteEvent(
                    message=Message.assistant_message(
                        [TextContent(text="still running")]
                    ),
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)

            binding_keys = {binding.key for binding in ClaudeCodeApp.BINDINGS}
            self.assertTrue(any("ctrl+c" in key for key in binding_keys))

            input_widget.text = "quit"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.05)

            self.assertEqual(submitted_messages, ["quit"])
            message_list = screen.query_one("#message-list", MessageList)
            self.assertEqual(len(list(message_list.children)), 2)

    async def test_submit_clears_input_immediately_and_hides_welcome(self) -> None:
        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                0.05,
                TextEvent(text="Hello"),
                0.05,
                MessageCompleteEvent(
                    message=Message.assistant_message([TextContent(text="Hello")]),
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            welcome_widget = screen.query_one("#welcome-widget", WelcomeWidget)
            processing_row = screen.query_one("#processing-row", Horizontal)
            processing_indicator = screen.query_one(
                "#processing-indicator",
                LoadingIndicator,
            )
            processing_label = screen.query_one("#processing-label")

            self.assertEqual(len(list(screen.query("#send-button"))), 0)
            self.assertEqual(len(list(screen.query("Footer"))), 0)
            self.assertFalse(processing_row.display)

            input_widget.text = "ship it"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.02)

            self.assertEqual(input_widget.text, "")
            self.assertTrue(input_widget.disabled)
            self.assertFalse(welcome_widget.display)
            self.assertTrue(processing_row.display)
            self.assertTrue(processing_indicator.display)
            self.assertTrue(processing_label.display)

            await pilot.pause(0.2)
            self.assertFalse(input_widget.disabled)
            self.assertFalse(processing_row.display)

    async def test_enter_submit_does_not_leave_newline_for_next_prompt(self) -> None:
        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                0.05,
                MessageCompleteEvent(
                    message=Message.assistant_message([TextContent(text="Done")]),
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)

            await pilot.press(*list("first"), "enter")
            await pilot.pause(0.02)

            self.assertEqual(input_widget.text, "")
            self.assertEqual(input_widget.cursor_location, (0, 0))

            await pilot.pause(0.12)
            self.assertFalse(input_widget.disabled)

            await pilot.press(*list("second"))
            self.assertEqual(input_widget.text, "second")
            self.assertEqual(input_widget.cursor_location, (0, 6))

    async def test_ctrl_c_copies_selected_input_text_via_app_binding(self) -> None:
        def event_factory(user_text: str):
            return []

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.focus()
            input_widget.text = "copy me"
            input_widget.action_select_all()

            with patch.object(app, "notify") as notify_mock:
                await pilot.press("ctrl+c")
                await pilot.pause(0.02)

            self.assertEqual(app.clipboard, "copy me")
            self.assertEqual(input_widget.text, "copy me")
            notify_mock.assert_called_once_with(
                "Copied to clipboard",
                title="Clipboard",
                timeout=1.5,
                markup=False,
            )

    async def test_copy_binding_uses_screen_selection_when_widget_has_none(self) -> None:
        def event_factory(user_text: str):
            return []

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.focus()
            input_widget.text = "draft"

            with patch.object(screen, "get_selected_text", return_value="stream output"):
                await pilot.press("ctrl+c")
                await pilot.pause(0.02)

            self.assertEqual(app.clipboard, "stream output")

    async def test_copy_binding_without_selection_does_not_interrupt_app(self) -> None:
        def event_factory(user_text: str):
            return []

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.focus()
            input_widget.text = "still here"
            app.copy_to_clipboard("baseline")

            with patch.object(app, "notify") as notify_mock:
                await pilot.press("ctrl+c")
                await pilot.pause(0.02)

            self.assertEqual(app.clipboard, "baseline")
            self.assertEqual(input_widget.text, "still here")
            self.assertIs(app.screen, screen)
            notify_mock.assert_not_called()

    async def test_processing_state_collapses_input_and_resets_after_response(self) -> None:
        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                0.5,
                MessageCompleteEvent(
                    message=Message.assistant_message([TextContent(text="Done")]),
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            processing_row = screen.query_one("#processing-row", Horizontal)

            input_widget.text = "Line 1\nLine 2\nLine 3"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.05)

            self.assertTrue(processing_row.display)
            self.assertTrue(input_widget.disabled)
            self.assertEqual(input_widget.text, "")
            self.assertEqual(input_widget.styles.height.value, 3.0)

            await pilot.pause(0.6)

            self.assertFalse(processing_row.display)
            self.assertFalse(input_widget.disabled)
            self.assertTrue(input_widget.styles.height.is_auto)

            input_widget.text = "Next line 1\nNext line 2"
            self.assertEqual(input_widget.text, "Next line 1\nNext line 2")

    async def test_input_cursor_line_style_matches_input_background(self) -> None:
        app = ClaudeCodeApp(
            FakeQueryEngine(lambda text: []), model_name="test-model", save_history=False
        )

        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)

            cursor_line_styles = input_widget.get_component_styles(
                "text-area--cursor-line"
            )

            self.assertEqual(
                cursor_line_styles.background,
                input_widget.styles.background,
            )

    async def test_context_usage_status_line_uses_assistant_usage(self) -> None:
        usage = Usage(
            input_tokens=45000,
            cache_creation_input_tokens=3000,
            cache_read_input_tokens=2000,
        )

        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                MessageCompleteEvent(
                    message=Message.assistant_message(
                        [TextContent(text="Done")],
                        usage=usage,
                    ),
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory),
            model_name="test-model",
            context_window_tokens=200000,
            save_history=False,
        )

        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            context_label = screen.query_one("#context-usage", Label)
            input_widget = screen.query_one("#user-input", InputTextArea)

            self.assertEqual(self._label_text(context_label), "Context: 0/200k (0%)")

            input_widget.text = "show usage"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.1)

            self.assertEqual(
                self._label_text(context_label),
                "Context: 50k/200k (25%)",
            )

    async def test_context_usage_status_line_requires_env_configuration(self) -> None:
        app = ClaudeCodeApp(
            FakeQueryEngine(lambda text: []), model_name="test-model", save_history=False
        )

        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            context_label = screen.query_one("#context-usage", Label)

            self.assertEqual(
                self._label_text(context_label),
                "Context: unavailable (set CLAUDE_CODE_MAX_CONTEXT_TOKENS in .env)",
            )

    async def test_history_navigation_restores_draft_after_browsing_history(self) -> None:
        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                0.01,
                MessageCompleteEvent(
                    message=Message.assistant_message([TextContent(text="Done")]),
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)

            input_widget.text = "first"
            input_widget._on_submit(input_widget.text)
            for _ in range(10):
                await pilot.pause(0.02)
                if not input_widget.disabled:
                    break

            input_widget.text = "second"
            input_widget._on_submit(input_widget.text)
            for _ in range(10):
                await pilot.pause(0.02)
                if not input_widget.disabled:
                    break

            input_widget.text = "draft"
            await pilot.press("up")
            self.assertEqual(input_widget.text, "second")

            await pilot.press("up")
            self.assertEqual(input_widget.text, "first")

            await pilot.press("down")
            self.assertEqual(input_widget.text, "second")

            await pilot.press("down")
            self.assertEqual(input_widget.text, "draft")

    async def test_streaming_tool_flow_and_scroll_stay_live(self) -> None:
        long_tail = "\n".join(f"line {index}" for index in range(20))
        tool_use = ToolUseContent(
            id="tool-1",
            name="Read",
            input={"file_path": "/tmp/demo.txt"},
        )

        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                0.01,
                TextEvent(text="Scanning"),
                0.01,
                TextEvent(text=" files"),
                0.01,
                MessageCompleteEvent(
                    message=Message.assistant_message(
                        [
                            TextContent(text="Scanning files"),
                            tool_use,
                        ],
                    ),
                ),
                ToolUseEvent(
                    tool_use_id="tool-1",
                    tool_name="Read",
                    input={"file_path": "/tmp/demo.txt"},
                ),
                0.01,
                ToolResultEvent(
                    tool_use_id="tool-1",
                    result="contents",
                    is_error=False,
                ),
                TurnCompleteEvent(
                    turn=1,
                    has_more_turns=True,
                    stop_reason="tool_use",
                ),
                0.01,
                TextEvent(text=long_tail),
                0.01,
                MessageCompleteEvent(
                    message=Message.assistant_message([TextContent(text=long_tail)]),
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test(size=(80, 12)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.text = "inspect repo"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.25)

            message_list = screen.query_one("#message-list", MessageList)
            assistant_widgets = [
                child
                for child in message_list.children
                if isinstance(child, AssistantMessageWidget)
            ]

            self.assertEqual(len(list(message_list.children)), 3)
            self.assertEqual(len(assistant_widgets), 2)
            self.assertEqual(len(list(screen.query(ToolUseWidget))), 1)

            content_area = screen.query_one("#content-area")
            self.assertGreater(content_area.max_scroll_y, 0)
            self.assertEqual(content_area.scroll_y, content_area.max_scroll_y)

    async def test_streaming_tool_preview_backfills_into_single_tool_block(self) -> None:
        finalized_tool = ToolUseContent(
            id="tool-1",
            name="Write",
            input={
                "file_path": "/tmp/demo.txt",
                "content": "hello world",
            },
        )

        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                0.01,
                TextEvent(text="I am "),
                0.01,
                ToolUseEvent(
                    tool_use_id="tool-1",
                    tool_name="Write",
                    input={},
                ),
                0.12,
                TextEvent(text="writing the file"),
                0.01,
                MessageCompleteEvent(
                    message=Message.assistant_message(
                        [
                            TextContent(text="I am writing the file"),
                            finalized_tool,
                        ],
                    ),
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test(size=(90, 16)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.text = "write it"
            input_widget._on_submit(input_widget.text)

            tool_toggle = None
            for _ in range(8):
                await pilot.pause(0.02)
                try:
                    tool_toggle = screen.query_one(".tool-use-details", Collapsible)
                except NoMatches:
                    continue
                break
            self.assertIsNotNone(tool_toggle)
            self.assertEqual(str(tool_toggle.title), "Write")

            mid_stream_screenshot = app.export_screenshot(simplify=True).replace(
                "&#160;", " "
            )
            self.assertIn("I am", mid_stream_screenshot)
            self.assertNotIn("demo.txt", mid_stream_screenshot)

            for _ in range(12):
                await pilot.pause(0.02)
                tool_toggle = screen.query_one(".tool-use-details", Collapsible)
                if str(tool_toggle.title) == "Write: demo.txt":
                    break
            self.assertEqual(str(tool_toggle.title), "Write: demo.txt")
            self.assertFalse(tool_toggle.collapsed)
            self.assertEqual(len(list(screen.query(ToolUseWidget))), 1)

            final_screenshot = app.export_screenshot(simplify=True).replace(
                "&#160;", " "
            )
            self.assertIn("I am writing the file", final_screenshot)
            self.assertIn("Write: demo.txt", final_screenshot)

    async def test_manual_scroll_up_during_stream_does_not_snap_back(self) -> None:
        first_chunk = "\n".join(f"line {index}" for index in range(20))
        second_chunk = "\n".join(f"next {index}" for index in range(20))
        full_text = f"{first_chunk}\n{second_chunk}"

        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                0.01,
                TextEvent(text=first_chunk),
                0.15,
                TextEvent(text=f"\n{second_chunk}"),
                0.01,
                MessageCompleteEvent(
                    message=Message.assistant_message([TextContent(text=full_text)]),
                ),
                TurnCompleteEvent(
                    turn=1,
                    has_more_turns=False,
                    stop_reason="end_turn",
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test(size=(80, 12)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            content_area = screen.query_one("#content-area")

            input_widget.text = "stream please"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.1)

            self.assertGreater(content_area.max_scroll_y, 0)
            content_area.scroll_end(
                animate=False,
                immediate=True,
                force=True,
                x_axis=False,
                y_axis=True,
            )
            await pilot.pause(0.02)
            self.assertEqual(content_area.scroll_y, content_area.max_scroll_y)

            content_area.scroll_home(
                animate=False,
                immediate=True,
                force=True,
                x_axis=False,
                y_axis=True,
            )
            await pilot.pause(0.02)
            self.assertEqual(content_area.scroll_y, 0)

            await pilot.pause(0.18)
            self.assertGreater(content_area.max_scroll_y, 0)
            self.assertLess(content_area.scroll_y, content_area.max_scroll_y)

    async def test_multi_tool_sequence_does_not_duplicate_tool_blocks(self) -> None:
        first_tool = ToolUseContent(
            id="tool-1",
            name="Bash",
            input={"command": "find . -maxdepth 2"},
        )
        second_tool = ToolUseContent(
            id="tool-2",
            name="Read",
            input={"file_path": "/tmp/demo.txt"},
        )

        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                MessageCompleteEvent(
                    message=Message.assistant_message(
                        [
                            TextContent(text="Checking the repo."),
                            first_tool,
                            second_tool,
                        ],
                    ),
                ),
                ToolUseEvent(
                    tool_use_id="tool-1",
                    tool_name="Bash",
                    input={"command": "find . -maxdepth 2"},
                ),
                ToolResultEvent(
                    tool_use_id="tool-1",
                    result="README.md\nAGENTS.md\n",
                    is_error=False,
                ),
                ToolUseEvent(
                    tool_use_id="tool-2",
                    tool_name="Read",
                    input={"file_path": "/tmp/demo.txt"},
                ),
                ToolResultEvent(
                    tool_use_id="tool-2",
                    result="Line 1\nLine 2\n",
                    is_error=False,
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test(size=(90, 18)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.text = "inspect repo"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.2)

            message_list = screen.query_one("#message-list", MessageList)
            assistant_widgets = [
                child
                for child in message_list.children
                if isinstance(child, AssistantMessageWidget)
            ]

            self.assertEqual(len(list(message_list.children)), 2)
            self.assertEqual(len(assistant_widgets), 1)
            self.assertEqual(len(list(screen.query(ToolUseWidget))), 2)

    async def test_followup_tool_only_turn_keeps_spacing_uniform(self) -> None:
        first_tool = ToolUseContent(
            id="tool-1",
            name="Bash",
            input={"command": "ls -la"},
        )
        second_tool = ToolUseContent(
            id="tool-2",
            name="Read",
            input={"file_path": "/tmp/demo.txt"},
        )

        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                MessageCompleteEvent(
                    message=Message.assistant_message(
                        [
                            TextContent(text="Checking the repo."),
                            first_tool,
                        ],
                    ),
                ),
                ToolUseEvent(
                    tool_use_id="tool-1",
                    tool_name="Bash",
                    input={"command": "ls -la"},
                ),
                ToolResultEvent(
                    tool_use_id="tool-1",
                    result="README.md\n",
                    is_error=False,
                ),
                TurnCompleteEvent(
                    turn=1,
                    has_more_turns=True,
                    stop_reason="tool_use",
                ),
                MessageCompleteEvent(
                    message=Message.assistant_message([second_tool]),
                ),
                ToolUseEvent(
                    tool_use_id="tool-2",
                    tool_name="Read",
                    input={"file_path": "/tmp/demo.txt"},
                ),
                ToolResultEvent(
                    tool_use_id="tool-2",
                    result="Line 1\n",
                    is_error=False,
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test(size=(90, 20)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.text = "inspect repo"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.2)

            message_list = screen.query_one("#message-list", MessageList)
            assistant_widgets = [
                child
                for child in message_list.children
                if isinstance(child, AssistantMessageWidget)
            ]

            self.assertEqual(len(assistant_widgets), 2)

            first_stream = assistant_widgets[0]._streaming_widget
            first_tool_widget = list(assistant_widgets[0].query(ToolUseWidget))[0]
            second_tool_widget = list(assistant_widgets[1].query(ToolUseWidget))[0]

            self.assertIsNotNone(first_stream)
            text_to_tool_gap = first_tool_widget.region.y - (
                first_stream.region.y + first_stream.region.height
            )
            tool_to_tool_gap = second_tool_widget.region.y - (
                first_tool_widget.region.y + first_tool_widget.region.height
            )

            self.assertEqual(text_to_tool_gap, 1)
            self.assertEqual(tool_to_tool_gap, 1)

    async def test_tool_only_response_renders_visible_result(self) -> None:
        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                ToolUseEvent(
                    tool_use_id="tool-1",
                    tool_name="Bash",
                    input={"command": "rg --files | head"},
                ),
                0.01,
                ToolResultEvent(
                    tool_use_id="tool-1",
                    result="README.md\nclaude_code/ui/app.py\n",
                    is_error=False,
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test(size=(80, 14)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.text = "explore repo"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.2)

            content_area = screen.query_one("#content-area")
            message_list = screen.query_one("#message-list", MessageList)
            self.assertEqual(content_area.scroll_y, content_area.max_scroll_y)
            self.assertEqual(len(list(message_list.children)), 2)
            self.assertEqual(len(list(screen.query(ToolUseWidget))), 1)
            self.assertEqual(len(list(screen.query(Collapsible))), 1)

            tool_toggle = screen.query_one(".tool-use-details", Collapsible)
            self.assertTrue(tool_toggle.collapsed)
            self.assertEqual(str(tool_toggle.title), "● Ran: rg --files | head")
            self.assertEqual(tool_toggle.title.spans, [Span(0, 1, "$success")])

            screenshot = app.export_screenshot(simplify=True).replace("&#160;", " ")
            self.assertIn("Ran: rg --files |", screenshot)
            self.assertNotIn("Bash: rg --files | head", screenshot)
            self.assertNotIn("Output Preview", screenshot)
            self.assertNotIn("README.md", screenshot)
            self.assertNotIn("claude_code/ui/app.py", screenshot)

            tool_toggle.collapsed = False
            await pilot.pause(0.05)

            detail_contents = [
                str(widget.content)
                for widget in tool_toggle.query(".tool-param")
                if hasattr(widget, "content")
            ]
            self.assertIn("command: rg --files | head", "\n".join(detail_contents))

            expanded_contents = [
                str(widget.content)
                for widget in tool_toggle.query(".tool-output-label, .tool-result-preview")
                if hasattr(widget, "content")
            ]
            self.assertIn("Output:", "\n".join(expanded_contents))
            self.assertIn("README.md", "\n".join(expanded_contents))
            self.assertIn("claude_code/ui/app.py", "\n".join(expanded_contents))

    async def test_tool_summary_title_strips_trailing_colon(self) -> None:
        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                ToolUseEvent(
                    tool_use_id="tool-1",
                    tool_name="Glob",
                    input={"pattern": "*.md"},
                ),
                ToolResultEvent(
                    tool_use_id="tool-1",
                    result="Found 3 files matching '*.md':\nREADME.md\nAGENTS.md\nCHANGELOG.md\n",
                    is_error=False,
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test(size=(80, 14)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.text = "find markdown"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.2)

            tool_toggle = screen.query_one(".tool-use-details", Collapsible)
            self.assertEqual(str(tool_toggle.title), "● Glob found 3 files matching '*.md'")
            self.assertEqual(tool_toggle.title.spans, [Span(0, 1, "$success")])

            screenshot = app.export_screenshot(simplify=True).replace("&#160;", " ")
            self.assertIn("Glob found 3 files matching", screenshot)
            self.assertNotIn("&#x27;*.md&#x27;:", screenshot)

    async def test_grep_tool_summary_title_includes_pattern_and_tool_name(self) -> None:
        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                ToolUseEvent(
                    tool_use_id="tool-1",
                    tool_name="Grep",
                    input={
                        "pattern": "Read.*Tool|read.*tool",
                        "path": "/tmp/project",
                        "output_mode": "files_with_matches",
                    },
                ),
                ToolResultEvent(
                    tool_use_id="tool-1",
                    result="Found 122 files\nREADME.md\nsrc/read_tool.py\n",
                    is_error=False,
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test(size=(100, 18)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.text = "grep it"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.2)

            tool_toggle = screen.query_one(".tool-use-details", Collapsible)
            self.assertEqual(
                str(tool_toggle.title),
                "● Grep found 122 files matching 'Read.*Tool|read.*tool'",
            )
            self.assertEqual(tool_toggle.title.spans, [Span(0, 1, "$success")])

            screenshot = app.export_screenshot(simplify=True).replace("&#160;", " ")
            self.assertIn("Grep found 122 files", screenshot)

    async def test_edit_tool_result_renders_diff_view_instead_of_raw_replacement_text(
        self,
    ) -> None:
        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                ToolUseEvent(
                    tool_use_id="tool-1",
                    tool_name="Edit",
                    input={
                        "file_path": "/tmp/demo.py",
                        "old_string": "print('old value')",
                        "new_string": "print('new value')",
                    },
                ),
                ToolResultEvent(
                    tool_use_id="tool-1",
                    result="Successfully edited /tmp/demo.py (replaced 1 occurrence)",
                    is_error=False,
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test(size=(100, 22)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.text = "edit it"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.2)

            tool_toggle = screen.query_one(".tool-use-details", Collapsible)
            self.assertFalse(tool_toggle.collapsed)
            self.assertEqual(
                str(tool_toggle.title),
                "● Successfully edited demo.py (replaced 1 occurrence)",
            )
            self.assertEqual(tool_toggle.title.spans, [Span(0, 1, "$success")])

            self.assertEqual(len(list(tool_toggle.query(DiffView))), 1)

            detail_contents = [
                str(widget.content)
                for widget in tool_toggle.query(".tool-param")
                if hasattr(widget, "content")
            ]
            joined_details = "\n".join(detail_contents)
            self.assertIn("file_path: /tmp/demo.py", joined_details)
            self.assertNotIn("old_string:", joined_details)
            self.assertNotIn("new_string:", joined_details)

            expanded_contents = [
                str(widget.content)
                for widget in tool_toggle.query(".tool-output-label, .tool-result-preview")
                if hasattr(widget, "content")
            ]
            self.assertEqual(expanded_contents, [])

    async def test_write_tool_result_renders_diff_view_instead_of_raw_content(
        self,
    ) -> None:
        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                ToolUseEvent(
                    tool_use_id="tool-1",
                    tool_name="Write",
                    input={
                        "file_path": "/tmp/read-tool-comparison.md",
                        "content": "# Python vs TypeScript\n\n## Overview\n",
                    },
                ),
                ToolResultEvent(
                    tool_use_id="tool-1",
                    result="Successfully wrote to /tmp/read-tool-comparison.md (3 lines, 36 bytes)",
                    is_error=False,
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test(size=(100, 22)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.text = "write it"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.2)

            tool_toggle = screen.query_one(".tool-use-details", Collapsible)
            self.assertFalse(tool_toggle.collapsed)
            self.assertEqual(
                str(tool_toggle.title),
                "● Successfully wrote to read-tool-comparison.md (3 lines, 36 bytes)",
            )
            self.assertEqual(tool_toggle.title.spans, [Span(0, 1, "$success")])

            self.assertEqual(len(list(tool_toggle.query(DiffView))), 1)

            detail_contents = [
                str(widget.content)
                for widget in tool_toggle.query(".tool-param")
                if hasattr(widget, "content")
            ]
            joined_details = "\n".join(detail_contents)
            self.assertIn("file_path: /tmp/read-tool-comparison.md", joined_details)
            self.assertNotIn("content:", joined_details)

            expanded_contents = [
                str(widget.content)
                for widget in tool_toggle.query(".tool-output-label, .tool-result-preview")
                if hasattr(widget, "content")
            ]
            self.assertEqual(expanded_contents, [])

    async def test_thinking_collapsible_focus_keeps_background_unchanged(self) -> None:
        def event_factory(user_text: str):
            return []

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test(size=(80, 12)) as pilot:
            await pilot.pause()
            screen = app.screen
            message_list = screen.query_one("#message-list", MessageList)
            await message_list.mount(ThinkingBlockWidget("Let me think"))
            await pilot.pause(0.05)

            thinking_toggle = screen.query_one(".thinking-collapsible", Collapsible)
            thinking_title = screen.query_one(".thinking-collapsible CollapsibleTitle")

            self.assertEqual(thinking_toggle.styles.border_top[0], "")
            self.assertEqual(thinking_toggle.styles.background_tint.a, 0)
            self.assertEqual(thinking_title.styles.background.a, 0)

            thinking_title.focus()
            await pilot.pause(0.05)

            self.assertEqual(thinking_toggle.styles.border_top[0], "")
            self.assertEqual(thinking_toggle.styles.background_tint.a, 0)
            self.assertEqual(thinking_title.styles.background.a, 0)

            thinking_toggle.collapsed = False
            await pilot.pause(0.05)

            self.assertEqual(thinking_toggle.styles.border_top[0], "")
            self.assertEqual(thinking_toggle.styles.background_tint.a, 0)
            self.assertEqual(thinking_title.styles.background.a, 0)

    async def test_streaming_thinking_updates_full_content(self) -> None:
        first_chunk = "Thinking"
        second_chunk = " through the full answer"
        full_thinking = first_chunk + second_chunk

        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                ThinkingEvent(thinking=first_chunk),
                0.02,
                ThinkingEvent(thinking=second_chunk),
                0.02,
                MessageCompleteEvent(
                    message=Message.assistant_message(
                        [ThinkingContent(thinking=full_thinking)]
                    ),
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test(size=(90, 16)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.text = "show thinking"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.2)

            thinking_toggle = screen.query_one(".thinking-collapsible", Collapsible)
            thinking_toggle.collapsed = False
            await pilot.pause(0.05)

            screenshot = app.export_screenshot(simplify=True).replace("&#160;", " ")
            self.assertIn("Thinking through the full answer", screenshot)

    async def test_streaming_markdown_uses_textual_stream_api(self) -> None:
        full_text = "Hello world!"
        stream_writes: list[str] = []

        class FakeMarkdownStream:
            def __init__(self, markdown_widget: Markdown):
                self._markdown_widget = markdown_widget

            async def write(self, markdown_fragment: str) -> None:
                stream_writes.append(markdown_fragment)
                await self._markdown_widget.append(markdown_fragment)

            async def stop(self) -> None:
                pass

        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                TextEvent(text="Hello"),
                0.02,
                TextEvent(text=" world"),
                0.02,
                TextEvent(text="!"),
                0.02,
                MessageCompleteEvent(
                    message=Message.assistant_message([TextContent(text=full_text)]),
                ),
                TurnCompleteEvent(turn=1, has_more_turns=False, stop_reason="end_turn"),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        with patch(
            "claude_code.ui.message_widgets.Markdown.get_stream",
            side_effect=lambda widget: FakeMarkdownStream(widget),
        ) as get_stream:
            async with app.run_test(size=(80, 14)) as pilot:
                await pilot.pause()
                screen = app.screen
                input_widget = screen.query_one("#user-input", InputTextArea)
                input_widget.text = "stream markdown"
                input_widget._on_submit(input_widget.text)
                await pilot.pause(0.25)

                screenshot = app.export_screenshot(simplify=True).replace("&#160;", " ")
                self.assertIn(full_text, screenshot)

        self.assertEqual(stream_writes, [" world", "!"])
        self.assertEqual(get_stream.call_count, 1)

    async def test_markdown_headings_and_links_do_not_use_underlines(self) -> None:
        markdown_text = "## Heading\n\n#### Minor\n\n[link](https://example.com)\n"

        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                MessageCompleteEvent(
                    message=Message.assistant_message([TextContent(text=markdown_text)]),
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test(size=(90, 16)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.text = "show headings"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.2)

            heading_two = screen.query_one(MarkdownH2)
            heading_four = screen.query_one(MarkdownH4)
            markdown_widget = screen.query_one(Markdown)

            self.assertNotIn("underline", str(heading_two.styles.text_style))
            self.assertNotIn("underline", str(heading_four.styles.text_style))
            self.assertEqual(str(markdown_widget.styles.link_style), "none")
            self.assertEqual(str(markdown_widget.styles.link_style_hover), "bold")

    async def test_untyped_code_fence_uses_plain_text_highlighting(self) -> None:
        markdown_text = "```\n.logs/claude-code-debug-<timestamp>.log\n```\n"

        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                MessageCompleteEvent(
                    message=Message.assistant_message([TextContent(text=markdown_text)]),
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test(size=(90, 16)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.text = "show code"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.2)

            fence = screen.query_one(textual_markdown.MarkdownFence)
            span_styles = [str(span.style) for span in fence._highlighted_code.spans]

            self.assertEqual(span_styles, ["$text"])

    async def test_markdown_code_fence_has_spacing_before_and_after(self) -> None:
        markdown_text = "before\n\n```python\nprint('hi')\n```\n\nafter\n"

        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                MessageCompleteEvent(
                    message=Message.assistant_message([TextContent(text=markdown_text)]),
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test(size=(90, 20)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.text = "show fence spacing"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.2)

            paragraphs = list(screen.query(textual_markdown.MarkdownParagraph))
            fence = screen.query_one(textual_markdown.MarkdownFence)

            self.assertGreaterEqual(len(paragraphs), 2)

            before_paragraph = paragraphs[0]
            after_paragraph = paragraphs[-1]
            gap_before = fence.region.y - (
                before_paragraph.region.y + before_paragraph.region.height
            )
            gap_after = after_paragraph.region.y - (
                fence.region.y + fence.region.height
            )

            self.assertGreaterEqual(gap_before, 1)
            self.assertGreaterEqual(gap_after, 1)

    async def test_tool_output_strips_terminal_control_sequences(self) -> None:
        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                ToolResultEvent(
                    tool_use_id="tool-1",
                    result="\x1b[2J\x1b[Hdanger\r\nnext\x07",
                    is_error=False,
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test(size=(80, 12)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.text = "show me"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.1)

            rendered_contents = [
                widget.content
                for widget in screen.query("#message-list *")
                if hasattr(widget, "content")
            ]
            joined = "\n".join(str(content) for content in rendered_contents)
            self.assertIn("danger", joined)
            self.assertIn("next", joined)
            self.assertNotIn("\x1b", joined)
            self.assertNotIn("\x07", joined)

    async def test_assistant_markdown_renders_and_keeps_strikethrough_literal(
        self,
    ) -> None:
        markdown_text = (
            "# Plan\n\n"
            "- first\n\n"
            "> quoted\n\n"
            "Inline `code`\n\n"
            "```python\nhi()\n```\n\n"
            "~~literal~~ and ~100\n"
        )

        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                MessageCompleteEvent(
                    message=Message.assistant_message([TextContent(text=markdown_text)]),
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test(size=(90, 24)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.text = "show markdown"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.2)
            content_area = screen.query_one("#content-area")
            content_area.scroll_home(animate=False, force=True, immediate=True)
            await pilot.pause(0.05)

            markdown_widgets = list(screen.query(Markdown))
            self.assertGreaterEqual(len(markdown_widgets), 1)

            screenshot = app.export_screenshot(simplify=True).replace("&#160;", " ")
            self.assertIn("Plan", screenshot)
            self.assertIn("first", screenshot)
            self.assertIn("quoted", screenshot)
            self.assertIn("code", screenshot)
            self.assertIn("hi", screenshot)
            self.assertIn("()", screenshot)
            self.assertIn("~~literal~~", screenshot)
            self.assertIn("~100", screenshot)
            self.assertNotIn("```", screenshot)
            self.assertNotIn("# Plan", screenshot)

    async def test_markdown_table_cells_do_not_expose_hover_tooltips(self) -> None:
        markdown_text = "| Name | Value |\n| --- | --- |\n| alpha | beta |\n"

        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                MessageCompleteEvent(
                    message=Message.assistant_message([TextContent(text=markdown_text)]),
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test(size=(90, 16)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.text = "show table"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.2)

            markdown_widget = next(
                widget for widget in screen.query(Markdown) if isinstance(widget, Markdown)
            )
            tooltips = [
                child.tooltip
                for child in markdown_widget.walk_children(with_self=True)
                if getattr(child, "tooltip", None) is not None
            ]
            self.assertEqual(tooltips, [])

    async def test_tool_output_keeps_raw_markdown_text(self) -> None:
        tool_output = "## raw\n- item\n`code`\n"

        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                ToolResultEvent(
                    tool_use_id="tool-1",
                    result=tool_output,
                    is_error=False,
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test(size=(80, 14)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.text = "show raw output"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.2)

            tool_toggle = screen.query_one(".tool-use-details", Collapsible)
            tool_toggle.collapsed = False
            await pilot.pause(0.05)
            self.assertIn("## raw", str(tool_toggle.title))

            expanded_contents = [
                str(widget.content)
                for widget in tool_toggle.query(".tool-output-label, .tool-result-preview")
                if hasattr(widget, "content")
            ]
            joined = "\n".join(expanded_contents)
            self.assertIn("- item", joined)
            self.assertIn("`code`", joined)

    async def test_tool_error_result_uses_error_status_dot(self) -> None:
        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                ToolUseEvent(
                    tool_use_id="tool-1",
                    tool_name="Bash",
                    input={
                        "command": "conda init",
                        "description": "Run conda init command",
                    },
                ),
                ToolResultEvent(
                    tool_use_id="tool-1",
                    result="Exit code: 127\n\n[stderr]\n/bin/bash: conda: command not found",
                    is_error=True,
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test(size=(90, 16)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.text = "try conda"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.2)

            tool_toggle = screen.query_one(".tool-use-details", Collapsible)
            self.assertEqual(str(tool_toggle.title), "● Failed to run conda init")
            self.assertEqual(tool_toggle.title.spans, [Span(0, 1, "$error")])

            tool_toggle.collapsed = False
            await pilot.pause(0.05)
            expanded_contents = [
                str(widget.content)
                for widget in tool_toggle.query(".tool-output-label, .tool-result-preview")
                if hasattr(widget, "content")
            ]
            joined = "\n".join(expanded_contents)
            self.assertIn("Exit code: 127", joined)
            self.assertIn("/bin/bash: conda: command not found", joined)

    async def test_file_tool_error_result_uses_action_summary(self) -> None:
        def event_factory(user_text: str):
            return [
                MessageCompleteEvent(message=Message.user_message(user_text)),
                ToolUseEvent(
                    tool_use_id="tool-1",
                    tool_name="Read",
                    input={"file_path": "/tmp/missing.txt"},
                ),
                ToolResultEvent(
                    tool_use_id="tool-1",
                    result="Error: File does not exist: /tmp/missing.txt",
                    is_error=True,
                ),
            ]

        app = ClaudeCodeApp(
            FakeQueryEngine(event_factory), model_name="test-model", save_history=False
        )

        async with app.run_test(size=(90, 16)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", InputTextArea)
            input_widget.text = "read missing"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.2)

            tool_toggle = screen.query_one(".tool-use-details", Collapsible)
            self.assertEqual(str(tool_toggle.title), "● Failed to read missing.txt")
            self.assertEqual(tool_toggle.title.spans, [Span(0, 1, "$error")])


if __name__ == "__main__":
    unittest.main()
