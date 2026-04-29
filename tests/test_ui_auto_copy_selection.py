from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.screen import Screen

import cc_code.ui.app as ui_app
from cc_code.ui.app import CCCodeApp
from cc_code.ui.debug_modal import SelectableRichLog


class _DummyClient:
    async def connect(self) -> None:
        pass

    async def create_session(self, working_directory: str) -> str:
        return "test-session"

    async def close(self) -> None:
        pass


class _SelectionScreen(Screen[None]):
    def __init__(
        self,
        client: object | None = None,
        session_id: str = "",
        working_directory: str = "",
    ) -> None:
        super().__init__()

    def compose(self) -> ComposeResult:
        yield SelectableRichLog(
            id="log",
            auto_scroll=False,
            highlight=False,
            markup=False,
            wrap=True,
        )

    def on_mount(self) -> None:
        log = self.query_one("#log", SelectableRichLog)
        log.write("copy me automatically")
        log.focus()


def test_mouse_selection_auto_copies_to_clipboard(monkeypatch) -> None:
    async def _run() -> None:
        monkeypatch.setattr(ui_app, "pyperclip", None)
        monkeypatch.setattr(ui_app, "REPLScreen", _SelectionScreen)
        app = CCCodeApp(client=_DummyClient(), working_directory="/tmp")
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.pause()
            log = app.screen.query_one("#log", SelectableRichLog)

            await pilot.mouse_down(log, offset=(0, 0))
            await pilot.hover(log, offset=(6, 0))
            await pilot.mouse_up(log, offset=(6, 0))
            await pilot.pause()

            assert app.clipboard == "copy me"
            notifications = list(app._notifications)
            assert len(notifications) == 1
            assert notifications[0].title == "Clipboard"
            assert notifications[0].message == "Copied to clipboard"

    asyncio.run(_run())


def test_plain_click_does_not_overwrite_clipboard(monkeypatch) -> None:
    async def _run() -> None:
        monkeypatch.setattr(ui_app, "pyperclip", None)
        monkeypatch.setattr(ui_app, "REPLScreen", _SelectionScreen)
        app = CCCodeApp(client=_DummyClient(), working_directory="/tmp")
        app.copy_to_clipboard("existing clipboard value")
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.pause()
            log = app.screen.query_one("#log", SelectableRichLog)

            await pilot.mouse_down(log, offset=(0, 0))
            await pilot.mouse_up(log, offset=(0, 0))
            await pilot.pause()

            assert app.clipboard == "existing clipboard value"

    asyncio.run(_run())


def test_ctrl_c_triggers_app_exit(monkeypatch) -> None:
    async def _run() -> None:
        monkeypatch.setattr(ui_app, "REPLScreen", _SelectionScreen)
        app = CCCodeApp(client=_DummyClient(), working_directory="/tmp")
        exit_called: list[bool] = []

        def _exit() -> None:
            exit_called.append(True)

        monkeypatch.setattr(app, "exit", _exit)

        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+c")
            await pilot.pause()

            assert exit_called == [True]

    asyncio.run(_run())
