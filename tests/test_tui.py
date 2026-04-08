"""Headless tests for the Textual TUI."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from textual.widgets import Collapsible
from textual.widgets import LoadingIndicator
from textual.containers import Horizontal

from claude_code.core.messages import (
    Message,
    MessageCompleteEvent,
    TextContent,
    TextEvent,
    ToolResultEvent,
    ToolUseContent,
    ToolUseEvent,
    TurnCompleteEvent,
)
from claude_code.ui.app import ClaudeCodeApp
from claude_code.ui.message_widgets import (
    AssistantMessageWidget,
    MessageList,
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

            await pilot.pause(0.15)
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
            await pilot.pause(0.08)

            input_widget.text = "second"
            input_widget._on_submit(input_widget.text)
            await pilot.pause(0.08)

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

    async def test_manual_scroll_up_during_stream_does_not_snap_back(self) -> None:
        first_chunk = "\n".join(f"line {index}" for index in range(12))
        second_chunk = "\n".join(f"next {index}" for index in range(12))
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
            await pilot.pause(0.06)

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

            tool_input_toggle = screen.query_one(".tool-use-details", Collapsible)
            output_preview_toggle = screen.query_one(
                ".tool-result-preview-toggle",
                Collapsible,
            )
            self.assertTrue(tool_input_toggle.collapsed)
            self.assertTrue(output_preview_toggle.collapsed)

            screenshot = app.export_screenshot(simplify=True).replace("&#160;", " ")
            self.assertIn("Ran: rg --files | head", screenshot)
            self.assertIn("Output Preview (2 lines)", screenshot)
            self.assertNotIn("README.md", screenshot)
            self.assertNotIn("claude_code/ui/app.py", screenshot)

            tool_input_toggle.collapsed = False
            output_preview_toggle.collapsed = False
            await pilot.pause(0.05)

            detail_contents = [
                str(widget.content)
                for widget in tool_input_toggle.query(".tool-param")
                if hasattr(widget, "content")
            ]
            self.assertIn("command: rg --files | head", "\n".join(detail_contents))

            preview_contents = [
                str(widget.content)
                for widget in output_preview_toggle.query(".tool-result-preview")
                if hasattr(widget, "content")
            ]
            self.assertIn("README.md", "\n".join(preview_contents))
            self.assertIn("claude_code/ui/app.py", "\n".join(preview_contents))

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


if __name__ == "__main__":
    unittest.main()
