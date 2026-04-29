from __future__ import annotations

import asyncio

from textual.app import App

from cc_code.ui.screens import REPLScreen
from cc_code.ui.styles import TUI_CSS


class _HangingInterruptClient:
    async def list_models(self):
        return {"models": [], "current_model": ""}

    async def list_skills(self):
        return {"skills": []}

    async def interrupt(self, session_id: str, reason: str = "user_interrupt") -> bool:
        await asyncio.Event().wait()
        return True


class _StubWorker:
    def __init__(self) -> None:
        self.is_finished = False
        self.cancel_called = False

    def cancel(self) -> None:
        self.cancel_called = True
        self.is_finished = True


class _InterruptCancelApp(App[None]):
    CSS = TUI_CSS

    def __init__(self) -> None:
        super().__init__()
        self._screen = REPLScreen(
            client=_HangingInterruptClient(),
            session_id="test-session",
            working_directory=".",
        )

    async def on_mount(self) -> None:
        await self.push_screen(self._screen)


async def _run_cancel_does_not_block_ui_on_hanging_interrupt_test() -> None:
    app = _InterruptCancelApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        worker = _StubWorker()
        screen._query_worker = worker
        screen._set_processing_state(True)

        await asyncio.wait_for(screen._cancel_current_query(), timeout=0.2)
        await pilot.pause()

        assert worker.cancel_called is True
        assert screen._is_processing is False
        assert screen._interrupt_task is not None
        assert screen._interrupt_task.done() is False

        screen._interrupt_task.cancel()
        try:
            await screen._interrupt_task
        except asyncio.CancelledError:
            pass


def test_cancel_does_not_block_ui_on_hanging_interrupt() -> None:
    asyncio.run(_run_cancel_does_not_block_ui_on_hanging_interrupt_test())
