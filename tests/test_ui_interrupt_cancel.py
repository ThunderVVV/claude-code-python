from __future__ import annotations

import asyncio

from textual.app import App

from cc_code.ui.screens import REPLScreen
from cc_code.ui.styles import TUI_CSS


class _InterruptClient:
    def __init__(self) -> None:
        self.interrupt_release = asyncio.Event()
        self.second_stream_release = asyncio.Event()
        self.stream_calls: list[str] = []

    async def list_models(self):
        return {"models": [], "current_model": ""}

    async def list_skills(self):
        return {"skills": []}

    async def interrupt(self, session_id: str, reason: str = "user_interrupt") -> bool:
        await self.interrupt_release.wait()
        return True

    async def stream_chat(
        self,
        user_text: str,
        session_id: str,
        working_directory: str,
        model=None,
    ):
        self.stream_calls.append(user_text)
        if len(self.stream_calls) == 1:
            try:
                while True:
                    await asyncio.sleep(1)
                    if False:
                        yield None
            except asyncio.CancelledError:
                raise
        else:
            await self.second_stream_release.wait()
            if False:
                yield None


class _InterruptCancelApp(App[None]):
    CSS = TUI_CSS

    def __init__(self) -> None:
        super().__init__()
        self._client = _InterruptClient()
        self._screen = REPLScreen(
            client=self._client,
            session_id="test-session",
            working_directory=".",
        )

    async def on_mount(self) -> None:
        await self.push_screen(self._screen)


async def _run_cancel_allows_immediate_resubmit_test() -> None:
    app = _InterruptCancelApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        client = app._client

        screen._start_message_submission("first")
        await pilot.pause()

        first_generation = screen._active_query_generation
        assert screen._is_processing is True
        assert first_generation is not None

        await asyncio.wait_for(screen._cancel_current_query(), timeout=0.2)
        await pilot.pause()

        assert screen._is_processing is False
        assert screen._query_guard.is_active is False
        assert screen._interrupt_task is not None
        assert screen._interrupt_task.done() is False

        screen._start_message_submission("second")
        await pilot.pause()
        await pilot.pause()

        second_generation = screen._active_query_generation
        assert screen._is_processing is True
        assert second_generation is not None
        assert second_generation > first_generation
        assert client.stream_calls == ["first", "second"]

        client.second_stream_release.set()
        await pilot.pause()
        await pilot.pause()

        assert screen._is_processing is False
        assert screen._active_query_generation is None

        client.interrupt_release.set()
        interrupt_task = screen._interrupt_task
        if interrupt_task is not None:
            await asyncio.wait_for(interrupt_task, timeout=0.5)


def test_cancel_allows_immediate_resubmit() -> None:
    asyncio.run(_run_cancel_allows_immediate_resubmit_test())
