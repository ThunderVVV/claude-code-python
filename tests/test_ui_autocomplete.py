from __future__ import annotations

import asyncio

from textual.app import App
from cc_code.ui.autocomplete import AutocompletePopup, AutocompleteMode
from cc_code.ui.screens import REPLScreen
from cc_code.ui.widgets import InputTextArea


class _AutocompleteTestApp(App[None]):
    def __init__(self) -> None:
        super().__init__()
        self._screen = REPLScreen(
            client=object(),
            session_id="test-session",
            working_directory=".",
        )

    async def on_mount(self) -> None:
        await self.push_screen(self._screen)


async def _run_slash_autocomplete_test() -> None:
    app = _AutocompleteTestApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        screen = app.screen
        input_widget = screen.query_one("#user-input", InputTextArea)
        autocomplete_popup = screen.query_one("#autocomplete-popup", AutocompletePopup)

        input_widget.focus()
        await pilot.press("/", "n")
        await pilot.pause()

        assert autocomplete_popup.is_visible()
        assert autocomplete_popup.mode == AutocompleteMode.SLASH
        assert autocomplete_popup.get_item_count() > 0


async def _run_repl_autofocus_test() -> None:
    app = _AutocompleteTestApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        screen = app.screen
        input_widget = screen.query_one("#user-input", InputTextArea)
        content_area = screen.query_one("#content-area")

        assert screen.focused is input_widget
        assert content_area.focus_on_click() is False

        autocomplete_popup = screen.query_one("#autocomplete-popup", AutocompletePopup)
        input_widget.focus()
        await pilot.press("/", "n")
        await pilot.pause()

        assert autocomplete_popup.is_visible()
        assert screen.focused is input_widget


def test_slash_autocomplete_shows_on_input() -> None:
    asyncio.run(_run_slash_autocomplete_test())


def test_repl_screen_autofocuses_input() -> None:
    asyncio.run(_run_repl_autofocus_test())
