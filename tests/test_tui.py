"""Headless tests for the Textual TUI."""

from __future__ import annotations

import asyncio
import unittest

from textual.widgets import Input
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
from claude_code.ui.app import (
    AssistantMessageWidget,
    ClaudeCodeApp,
    MessageList,
    ToolUseWidget,
    WelcomeWidget,
)


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
                    message=Message.assistant_message([TextContent(text="still running")]),
                ),
            ]

        app = ClaudeCodeApp(FakeQueryEngine(event_factory), model_name="test-model")

        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", Input)

            self.assertEqual(ClaudeCodeApp.BINDINGS, [])

            input_widget.value = "quit"
            await input_widget.action_submit()
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

        app = ClaudeCodeApp(FakeQueryEngine(event_factory), model_name="test-model")

        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", Input)
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

            input_widget.value = "ship it"
            await input_widget.action_submit()
            await pilot.pause(0.02)

            self.assertEqual(input_widget.value, "")
            self.assertTrue(input_widget.disabled)
            self.assertFalse(welcome_widget.display)
            self.assertTrue(processing_row.display)
            self.assertTrue(processing_indicator.display)
            self.assertTrue(processing_label.display)

            await pilot.pause(0.15)
            self.assertFalse(input_widget.disabled)
            self.assertFalse(processing_row.display)

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

        app = ClaudeCodeApp(FakeQueryEngine(event_factory), model_name="test-model")

        async with app.run_test(size=(80, 12)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", Input)
            input_widget.value = "inspect repo"
            await input_widget.action_submit()
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

        app = ClaudeCodeApp(FakeQueryEngine(event_factory), model_name="test-model")

        async with app.run_test(size=(80, 12)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", Input)
            content_area = screen.query_one("#content-area")

            input_widget.value = "stream please"
            await input_widget.action_submit()
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

        app = ClaudeCodeApp(FakeQueryEngine(event_factory), model_name="test-model")

        async with app.run_test(size=(90, 18)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", Input)
            input_widget.value = "inspect repo"
            await input_widget.action_submit()
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

        app = ClaudeCodeApp(FakeQueryEngine(event_factory), model_name="test-model")

        async with app.run_test(size=(90, 20)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", Input)
            input_widget.value = "inspect repo"
            await input_widget.action_submit()
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
            text_to_tool_gap = (
                first_tool_widget.region.y
                - (first_stream.region.y + first_stream.region.height)
            )
            tool_to_tool_gap = (
                second_tool_widget.region.y
                - (first_tool_widget.region.y + first_tool_widget.region.height)
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

        app = ClaudeCodeApp(FakeQueryEngine(event_factory), model_name="test-model")

        async with app.run_test(size=(80, 14)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", Input)
            input_widget.value = "explore repo"
            await input_widget.action_submit()
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

        app = ClaudeCodeApp(FakeQueryEngine(event_factory), model_name="test-model")

        async with app.run_test(size=(80, 12)) as pilot:
            await pilot.pause()
            screen = app.screen
            input_widget = screen.query_one("#user-input", Input)
            input_widget.value = "show me"
            await input_widget.action_submit()
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
