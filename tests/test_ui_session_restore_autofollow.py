from __future__ import annotations

import asyncio

from textual.app import App

from claude_code.core.messages import Message
from claude_code.ui.message_widgets import MessageList
from claude_code.ui.screens import REPLScreen
from claude_code.ui.styles import TUI_CSS


class _SessionRestoreAutofollowApp(App[None]):
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


async def _run_session_restore_autofollow_test() -> None:
    app = _SessionRestoreAutofollowApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        message_list = screen.query_one("#message-list", MessageList)
        screen._hide_welcome_widget()
        await pilot.pause()

        messages = [Message.user_message(f"message {index}") for index in range(60)]
        recorded_auto_follow: list[bool] = []

        original_add_message = message_list.add_message
        original_create_streaming_widget = message_list.create_streaming_widget

        async def tracked_add_message(message: Message, auto_follow: bool = True) -> None:
            recorded_auto_follow.append(auto_follow)
            await original_add_message(message, auto_follow=auto_follow)

        async def tracked_create_streaming_widget(
            message: Message | None = None,
            auto_follow: bool = True,
            should_stream_live=None,
        ):
            recorded_auto_follow.append(auto_follow)
            return await original_create_streaming_widget(
                message=message,
                auto_follow=auto_follow,
                should_stream_live=should_stream_live,
            )

        message_list.add_message = tracked_add_message
        message_list.create_streaming_widget = tracked_create_streaming_widget

        await screen._render_messages(message_list, messages)
        await pilot.pause()

        assert recorded_auto_follow
        assert any(recorded_auto_follow)

        content_area = screen.query_one("#content-area")
        assert content_area.is_vertical_scroll_end


def test_session_restore_keeps_transcript_pinned_to_bottom() -> None:
    asyncio.run(_run_session_restore_autofollow_test())


async def _run_session_restore_lazy_loading_test() -> None:
    app = _SessionRestoreAutofollowApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        message_list = screen.query_one("#message-list", MessageList)
        screen._hide_welcome_widget()
        await pilot.pause()

        messages = [
            Message.user_message(f"message {index}\nline 2\nline 3")
            for index in range(55)
        ]
        initial_messages = screen._prepare_session_restore_initial_messages(messages)

        await screen._render_messages(message_list, initial_messages)
        screen._anchor_transcript_after_refresh()
        await pilot.pause()

        assert len(message_list._message_widgets) == 20
        assert screen._session_restore_lazy_load_enabled is True

        content_area = screen.query_one("#content-area")
        content_area.scroll_to(
            y=0,
            animate=False,
            force=True,
            immediate=True,
        )
        await pilot.pause()
        await pilot.pause()

        assert len(message_list._message_widgets) == 40
        assert screen._session_restore_lazy_load_enabled is True

        content_area.scroll_to(
            y=0,
            animate=False,
            force=True,
            immediate=True,
        )
        await pilot.pause()
        await pilot.pause()

        assert len(message_list._message_widgets) == 55
        assert screen._session_restore_lazy_load_enabled is False


def test_session_restore_lazy_loads_history_while_scrolling_up() -> None:
    asyncio.run(_run_session_restore_lazy_loading_test())
