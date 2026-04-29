from __future__ import annotations

import asyncio

from textual.app import App

from cc_code.core.messages import Message, ThinkingContent
from cc_code.ui.message_widgets import MessageList
from cc_code.ui.screens import REPLScreen
from cc_code.ui.styles import TUI_CSS


class _SessionRestoreMarkupSafetyApp(App[None]):
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


async def _run_session_restore_with_python_literal_thinking_test() -> None:
    app = _SessionRestoreMarkupSafetyApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        message_list = screen.query_one("#message-list", MessageList)
        screen._hide_welcome_widget()
        await pilot.pause()

        messages = [
            Message.assistant_message(
                [
                    ThinkingContent(
                        thinking='bindings = [Binding("copy_selection", "Copy", show=False, priority=True)]'
                    )
                ]
            )
        ]

        await screen._render_messages(message_list, messages)
        await pilot.pause()

        assert len(message_list._message_widgets) == 1


def test_session_restore_renders_thinking_with_python_literals_as_plain_text() -> None:
    asyncio.run(_run_session_restore_with_python_literal_thinking_test())
