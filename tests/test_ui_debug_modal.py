from __future__ import annotations

import asyncio

from textual.app import App
from textual.geometry import Offset
from textual.selection import Selection
from textual.widgets import RichLog

from cc_code.ui.debug_modal import DebugStateModal, SelectableRichLog
from cc_code.ui.styles import TUI_CSS


class _DebugModalApp(App[None]):
    CSS = TUI_CSS

    async def on_mount(self) -> None:
        await self.push_screen(DebugStateModal(""))


def test_debug_modal_shows_non_empty_fallback_line() -> None:
    async def _run() -> None:
        app = _DebugModalApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            modal = app.screen
            log = modal.query_one("#debug-log", RichLog)
            assert len(log.lines) >= 1

    asyncio.run(_run())


def test_selectable_rich_log_get_selection_extracts_text() -> None:
    async def _run() -> None:
        app = _DebugModalApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            modal = app.screen
            log = modal.query_one("#debug-log", SelectableRichLog)
            selection = Selection.from_offsets(Offset(0, 0), Offset(7, 0))
            result = log.get_selection(selection)
            assert result is not None
            assert result[0] == "<empty "

    asyncio.run(_run())


def test_debug_modal_mouse_drag_creates_screen_selection() -> None:
    async def _run() -> None:
        app = _DebugModalApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            modal = app.screen
            log = modal.query_one("#debug-log", SelectableRichLog)

            await pilot.mouse_down(log, offset=(1, 0))
            await pilot.hover(log, offset=(8, 0))
            await pilot.mouse_up(log, offset=(8, 0))
            await pilot.pause()

            assert modal.selections
            selected_text = modal.get_selected_text()
            assert selected_text is not None
            assert selected_text.strip()

    asyncio.run(_run())
