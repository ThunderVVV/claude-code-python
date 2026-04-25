from __future__ import annotations

import asyncio

from textual.app import App
from textual.scrollbar import ScrollTo

from cc_code.core.messages import Message, ToolUseEvent
from cc_code.ui.message_widgets import MessageList
from cc_code.ui.screens import REPLScreen
from cc_code.ui.styles import TUI_CSS


class _StubMouseScrollUpEvent:
    def __init__(self) -> None:
        self.ctrl = False
        self.shift = False
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


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
            tool_streaming_context: bool = True,
            before_widget=None,
        ):
            recorded_auto_follow.append(auto_follow)
            return await original_create_streaming_widget(
                message=message,
                auto_follow=auto_follow,
                tool_streaming_context=tool_streaming_context,
                before_widget=before_widget,
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
        for expected in (25, 30, 35, 40, 45, 50, 55):
            content_area.scroll_to(
                y=2,
                animate=False,
                force=True,
                immediate=True,
            )
            await pilot.pause()
            content_area.scroll_to(
                y=0,
                animate=False,
                force=True,
                immediate=True,
            )
            await pilot.pause()
            await pilot.pause()
            assert len(message_list._message_widgets) == expected

        assert screen._session_restore_lazy_load_enabled is False


def test_session_restore_lazy_loads_history_while_scrolling_up() -> None:
    asyncio.run(_run_session_restore_lazy_loading_test())


async def _run_session_restore_top_scroll_event_test() -> None:
    app = _SessionRestoreAutofollowApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        message_list = screen.query_one("#message-list", MessageList)
        screen._hide_welcome_widget()
        await pilot.pause()

        messages = [Message.user_message(f"message {index}") for index in range(55)]
        initial_messages = screen._prepare_session_restore_initial_messages(messages)

        await screen._render_messages(message_list, initial_messages)
        screen._anchor_transcript_after_refresh()
        await pilot.pause()

        assert len(message_list._message_widgets) == 20

        content_area = screen.query_one("#content-area")
        content_area.scroll_to(y=0, animate=False, force=True, immediate=True)
        await pilot.pause()
        await pilot.pause()
        assert len(message_list._message_widgets) == 25

        # At top, another wheel-up should still request loading more history.
        content_area._on_mouse_scroll_up(_StubMouseScrollUpEvent())
        await pilot.pause()
        await pilot.pause()
        assert len(message_list._message_widgets) == 30


def test_session_restore_lazy_loads_when_mouse_wheels_up_at_top() -> None:
    asyncio.run(_run_session_restore_top_scroll_event_test())


async def _render_scrollable_transcript(screen: REPLScreen, pilot) -> None:
    message_list = screen.query_one("#message-list", MessageList)
    screen._hide_welcome_widget()
    await pilot.pause()

    messages = [
        Message.user_message(f"message {index}\nline 2\nline 3")
        for index in range(40)
    ]
    await screen._render_messages(message_list, messages)
    screen._anchor_transcript_after_refresh()
    await pilot.pause()
    await pilot.pause()


async def _run_upward_scroll_position_change_disables_autofollow_test() -> None:
    app = _SessionRestoreAutofollowApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        await _render_scrollable_transcript(screen, pilot)

        content_area = screen.query_one("#content-area")
        assert content_area.max_scroll_y > 0
        assert content_area.is_vertical_scroll_end

        screen._is_processing = True
        screen._follow_transcript_output = True
        content_area.scroll_to(
            y=max(content_area.scroll_y - 5, 0),
            animate=False,
            force=True,
            immediate=True,
        )
        await pilot.pause()

        assert screen._follow_transcript_output is False


def test_upward_scroll_position_change_disables_autofollow() -> None:
    asyncio.run(_run_upward_scroll_position_change_disables_autofollow_test())


async def _run_scrollbar_drag_up_disables_autofollow_immediately_test() -> None:
    app = _SessionRestoreAutofollowApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        await _render_scrollable_transcript(screen, pilot)

        content_area = screen.query_one("#content-area")
        screen._is_processing = True
        screen._follow_transcript_output = True

        content_area._on_scroll_to(
            ScrollTo(y=max(content_area.scroll_y - 5, 0), animate=False)
        )

        assert screen._follow_transcript_output is False


def test_scrollbar_drag_up_disables_autofollow_immediately() -> None:
    asyncio.run(_run_scrollbar_drag_up_disables_autofollow_immediately_test())


async def _run_keyboard_home_disables_autofollow_immediately_test() -> None:
    app = _SessionRestoreAutofollowApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        await _render_scrollable_transcript(screen, pilot)

        content_area = screen.query_one("#content-area")
        screen._is_processing = True
        screen._follow_transcript_output = True

        content_area.action_scroll_home()

        assert screen._follow_transcript_output is False


def test_keyboard_home_disables_autofollow_immediately() -> None:
    asyncio.run(_run_keyboard_home_disables_autofollow_immediately_test())


async def _run_expanded_mode_tool_use_does_not_restore_autofollow_test() -> None:
    app = _SessionRestoreAutofollowApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        message_list = screen.query_one("#message-list", MessageList)
        await _render_scrollable_transcript(screen, pilot)

        content_area = screen.query_one("#content-area")
        screen._transcript_collapsible_mode_expanded = True
        screen._is_processing = True
        screen._follow_transcript_output = True

        content_area.scroll_to(
            y=max(content_area.scroll_y - 20, 0),
            animate=False,
            force=True,
            immediate=True,
        )
        await pilot.pause()
        assert screen._follow_transcript_output is False

        await screen._handle_query_event(
            ToolUseEvent(
                tool_use_id="tool-1",
                tool_name="Read",
                input={"file_path": "README.md"},
            ),
            message_list,
        )
        await pilot.pause()
        await pilot.pause()

        assert content_area.is_vertical_scroll_end is False
        assert screen._follow_transcript_output is False


def test_expanded_mode_tool_use_does_not_restore_autofollow() -> None:
    asyncio.run(_run_expanded_mode_tool_use_does_not_restore_autofollow_test())


async def _run_horizontal_wheel_does_not_disable_autofollow_test() -> None:
    app = _SessionRestoreAutofollowApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        await _render_scrollable_transcript(screen, pilot)

        content_area = screen.query_one("#content-area")
        screen._is_processing = True
        screen._follow_transcript_output = True

        event = _StubMouseScrollUpEvent()
        event.shift = True
        content_area._on_mouse_scroll_up(event)

        assert screen._follow_transcript_output is True


def test_horizontal_wheel_does_not_disable_autofollow() -> None:
    asyncio.run(_run_horizontal_wheel_does_not_disable_autofollow_test())
