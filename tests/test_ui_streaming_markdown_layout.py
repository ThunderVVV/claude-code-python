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


async def _run_streaming_table_flush_deferred_until_finish_test() -> None:
    app = _StreamingMarkdownLayoutApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        message_list = screen.query_one("#message-list", MessageList)
        screen._hide_welcome_widget()
        await pilot.pause()

        widget = await message_list.create_streaming_widget(auto_follow=False)
        await widget.append_text("| Name | Value |\n")
        await widget.append_text("| --- | --- |\n")
        await widget.append_text("| alpha | 1 |\n")
        await pilot.pause()

        markdown = widget._streaming_widget
        assert markdown is not None
        # Keep trailing table updates buffered during streaming to avoid
        # repeated re-layout flicker while rows are still arriving.
        assert markdown.source == ""

        await widget.finish_streaming()
        await pilot.pause()

        assert "| Name | Value |" in markdown.source
        assert "| alpha | 1 |" in markdown.source


def test_streaming_table_flush_deferred_until_finish() -> None:
    asyncio.run(_run_streaming_table_flush_deferred_until_finish_test())


async def _run_streaming_text_pauses_when_not_at_bottom_test() -> None:
    app = _StreamingMarkdownLayoutApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        message_list = screen.query_one("#message-list", MessageList)
        screen._hide_welcome_widget()
        await pilot.pause()

        original_should_follow = screen._should_follow_transcript
        screen._should_follow_transcript = lambda: False
        try:
            await screen._handle_query_event(TextEvent(text="| Name | Value |\n"), message_list)
            await screen._handle_query_event(TextEvent(text="| --- | --- |\n"), message_list)
            await pilot.pause()

            assistant_widget = screen._current_assistant_widget
            assert assistant_widget is not None
            assert assistant_widget._streaming_widget is None
            assert "".join(screen._buffered_assistant_chunks) == "| Name | Value |\n| --- | --- |\n"

            screen._should_follow_transcript = lambda: True
            await screen._handle_query_event(TextEvent(text="| alpha | 1 |\n"), message_list)
            await pilot.pause()

            markdown = assistant_widget._streaming_widget
            assert markdown is not None
            assert "| Name | Value |" in markdown.source
            assert "| alpha | 1 |" in markdown.source
            assert screen._buffered_assistant_char_count == 0
        finally:
            screen._should_follow_transcript = original_should_follow


def test_streaming_text_pauses_when_not_at_bottom() -> None:
    asyncio.run(_run_streaming_text_pauses_when_not_at_bottom_test())


async def _run_streaming_text_continues_without_user_scroll_test() -> None:
    app = _StreamingMarkdownLayoutApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        message_list = screen.query_one("#message-list", MessageList)
        screen._hide_welcome_widget()
        screen._is_processing = True
        await pilot.pause()

        await screen._handle_query_event(TextEvent(text="hello "), message_list)
        await screen._handle_query_event(TextEvent(text="world "), message_list)
        await screen._handle_query_event(TextEvent(text="again"), message_list)
        await pilot.pause()

        assistant_widget = screen._current_assistant_widget
        assert assistant_widget is not None
        markdown = assistant_widget._streaming_widget
        assert markdown is not None
        assert markdown.source == "hello world again"
        assert screen._buffered_assistant_char_count == 0


def test_streaming_text_continues_without_user_scroll() -> None:
    asyncio.run(_run_streaming_text_continues_without_user_scroll_test())


async def _run_streaming_table_column_widths_stay_fixed_test() -> None:
    app = _StreamingMarkdownLayoutApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        message_list = screen.query_one("#message-list", MessageList)
        screen._hide_welcome_widget()
        await pilot.pause()

        widget = await message_list.create_streaming_widget(auto_follow=False)
        await widget.append_text("| Name | Description |\n")
        await widget.append_text("| --- | --- |\n")
        await widget.append_text("| a | b |\n\n")
        await widget.flush_pending_streaming_text()
        await pilot.pause()

        markdown = widget._streaming_widget
        assert markdown is not None
        first_table = markdown._table_strips.get(0)
        assert first_table is not None
        first_top_border = "".join(segment.text for segment in first_table[0])

        await widget.append_text(
            "| a | this is an extremely long streamed cell that should wrap without widening old columns |\n\n"
        )
        await widget.flush_pending_streaming_text()
        await pilot.pause()

        second_table = markdown._table_strips.get(0)
        assert second_table is not None
        second_top_border = "".join(segment.text for segment in second_table[0])

        assert first_top_border == second_top_border


def test_streaming_table_column_widths_stay_fixed() -> None:
    asyncio.run(_run_streaming_table_column_widths_stay_fixed_test())


async def _run_scroll_anchor_requests_are_coalesced_test() -> None:
    app = _StreamingMarkdownLayoutApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        message_list = screen.query_one("#message-list", MessageList)
        screen._hide_welcome_widget()
        await pilot.pause()

        calls = {"count": 0}
        original = message_list._scroll_to_latest

        def tracked(force: bool = False) -> None:
            calls["count"] += 1
            original(force=force)

        message_list._scroll_to_latest = tracked  # type: ignore[method-assign]
        message_list.schedule_scroll_to_latest(auto_follow=True)
        message_list.schedule_scroll_to_latest(auto_follow=True)
        message_list.schedule_scroll_to_latest(auto_follow=True)
        await pilot.pause()

        assert calls["count"] == 1


def test_scroll_anchor_requests_are_coalesced() -> None:
    asyncio.run(_run_scroll_anchor_requests_are_coalesced_test())


async def _run_markdown_append_uses_incremental_tail_reparse_test() -> None:
    app = _StreamingMarkdownLayoutApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        message_list = screen.query_one("#message-list", MessageList)
        screen._hide_welcome_widget()
        await pilot.pause()

        widget = await message_list.create_streaming_widget(auto_follow=False)
        await widget.append_text("# H\n\nfirst\n\nsecond\n")
        await widget.flush_pending_streaming_text()
        await pilot.pause()

        markdown = widget._streaming_widget
        assert markdown is not None

        calls: list[tuple[int, int]] = []
        original = markdown._build_blocks_for_slice

        def tracked(markdown_text: str, *, line_offset: int = 0, normalize_first_block_margin: bool = True):
            calls.append((len(markdown_text), line_offset))
            return original(
                markdown_text,
                line_offset=line_offset,
                normalize_first_block_margin=normalize_first_block_margin,
            )

        markdown._build_blocks_for_slice = tracked  # type: ignore[method-assign]
        await widget.append_text("third\n")
        await widget.flush_pending_streaming_text()
        await pilot.pause()

        assert calls
        # Incremental append should reparse from a tail line, not always from 0.
        assert any(line_offset > 0 for _, line_offset in calls)
        assert any(length < len(markdown.source) for length, _ in calls)


def test_markdown_append_uses_incremental_tail_reparse() -> None:
    asyncio.run(_run_markdown_append_uses_incremental_tail_reparse_test())
