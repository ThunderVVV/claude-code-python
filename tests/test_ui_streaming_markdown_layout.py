from __future__ import annotations

import asyncio

from textual.app import App

from cc_code.core.messages import TextEvent, ToolUseEvent
from cc_code.ui.message_widgets import MessageList
from cc_code.ui.screens import REPLScreen
from cc_code.ui.styles import TUI_CSS


class _StreamingMarkdownLayoutApp(App[None]):
    CSS = TUI_CSS

    def __init__(self) -> None:
        super().__init__()
        self._screen = REPLScreen(
            client=object(),
            session_id="test-session",
            working_directory=".",
        )

    async def on_mount(self) -> None:
        await self.push_screen(self._screen)


async def _run_streaming_markdown_layout_test() -> None:
    app = _StreamingMarkdownLayoutApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        message_list = screen.query_one("#message-list", MessageList)

        screen._hide_welcome_widget()
        await pilot.pause()

        widget = await message_list.create_streaming_widget(
            auto_follow=False,
        )
        await widget.append_text("# hello\n\nworld\n")
        await pilot.pause()

        markdown = widget._streaming_widget
        assert markdown is not None
        assert markdown.parent is not None
        assert "markdown-host" in markdown.parent.classes
        content_area = screen.query_one("#content-area")

        assert markdown.size.height == markdown.virtual_size.height
        assert markdown.virtual_size.height == 4
        assert markdown.size.height < content_area.size.height
        assert markdown.focus_on_click() is False


def test_streaming_markdown_widget_keeps_content_height_in_transcript() -> None:
    asyncio.run(_run_streaming_markdown_layout_test())


async def _run_tool_use_flushes_pending_markdown_test() -> None:
    app = _StreamingMarkdownLayoutApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        message_list = screen.query_one("#message-list", MessageList)
        screen._hide_welcome_widget()
        await pilot.pause()

        await screen._handle_query_event(TextEvent(text="hello"), message_list)
        await pilot.pause()
        await screen._handle_query_event(TextEvent(text=" world"), message_list)
        await screen._handle_query_event(
            ToolUseEvent(
                tool_use_id="tool-1",
                tool_name="Read",
                input={"file_path": "README.md"},
            ),
            message_list,
        )
        await pilot.pause()

        assistant_widget = screen._current_assistant_widget
        assert assistant_widget is not None
        markdown = assistant_widget._streaming_widget
        assert markdown is not None
        assert markdown.source == "hello world"
        assert "tool-1" in assistant_widget.get_tool_widgets()


def test_tool_use_event_flushes_pending_markdown_before_mounting_tool() -> None:
    asyncio.run(_run_tool_use_flushes_pending_markdown_test())
