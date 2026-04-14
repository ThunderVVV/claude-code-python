from __future__ import annotations

import asyncio

from textual.app import App

from claude_code.ui.screens import REPLScreen, TranscriptContainer
from claude_code.ui.styles import TUI_CSS
from claude_code.ui.transcript_mode_modal import ProgressStatusModal


class _StubToggleEvent:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


class _StubDescendantFocusEvent:
    def __init__(self, widget):
        self.widget = widget


class _StubCollapsibleTitle:
    pass


class _StubCollapsible:
    def __init__(self, classes: set[str], collapsed: bool):
        self.classes = classes
        self.collapsed = collapsed


class _StubModeWidget:
    def __init__(self):
        self.applied = 0

    def apply_transcript_collapsible_mode(self):
        self.applied += 1


def test_transcript_container_does_not_focus_on_click():
    container = TranscriptContainer()
    assert container.FOCUS_ON_CLICK is False


def test_repl_screen_collapsible_toggle_stops_event(monkeypatch):
    screen = REPLScreen(client=object(), session_id="session-1")
    monkeypatch.setattr(screen, "_schedule_input_focus", lambda: None)
    event = _StubToggleEvent()

    screen.on_collapsible_toggled(event)

    assert event.stopped is True


def test_repl_screen_collapsible_title_focus_schedules_input_focus(monkeypatch):
    screen = REPLScreen(client=object(), session_id="session-1")
    called = {"focus_scheduled": False}

    def _schedule():
        called["focus_scheduled"] = True

    monkeypatch.setattr(screen, "_schedule_input_focus", _schedule)

    screen.on_descendant_focus(_StubDescendantFocusEvent(_StubCollapsibleTitle()))

    assert called["focus_scheduled"] is True


def test_repl_screen_ctrl_o_toggles_target_collapsibles_via_dedicated_state(monkeypatch):
    screen = REPLScreen(client=object(), session_id="session-1")
    thinking = _StubModeWidget()
    tool = _StubModeWidget()

    def fake_query(widget_type):
        name = getattr(widget_type, "__name__", "")
        if name == "ThinkingBlockWidget":
            return [thinking]
        if name == "ToolUseWidget":
            return [tool]
        return []

    monkeypatch.setattr(screen, "query", fake_query)

    screen._toggle_transcript_collapsibles()

    assert screen._transcript_collapsible_mode_expanded is True
    assert thinking.applied == 1
    assert tool.applied == 1

    screen._toggle_transcript_collapsibles()

    assert screen._transcript_collapsible_mode_expanded is False
    assert thinking.applied == 2
    assert tool.applied == 2


class _TranscriptModeModalApp(App[None]):
    CSS = TUI_CSS

    def __init__(self) -> None:
        super().__init__()
        self._screen = REPLScreen(client=object(), session_id="session-1")

    async def on_mount(self) -> None:
        await self.push_screen(self._screen)


async def _run_transcript_mode_modal_toggle_test() -> None:
    app = _TranscriptModeModalApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        modal_seen = asyncio.Event()
        original_push_screen = screen.app.push_screen

        async def tracked_push_screen(*args, **kwargs):
            result = await original_push_screen(*args, **kwargs)
            if isinstance(args[0], ProgressStatusModal):
                modal_seen.set()
            return result

        screen.app.push_screen = tracked_push_screen

        await screen._toggle_transcript_collapsibles_with_modal()
        await pilot.pause()

        assert modal_seen.is_set()
        assert screen._transcript_collapsible_mode_expanded is True
        assert screen._transcript_mode_switch_in_progress is False
        assert not any(
            isinstance(node, ProgressStatusModal) for node in screen.app.screen_stack
        )


def test_repl_screen_ctrl_o_uses_transient_modal_during_toggle() -> None:
    asyncio.run(_run_transcript_mode_modal_toggle_test())


async def _run_progress_modal_helper_test() -> None:
    app = _TranscriptModeModalApp()

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        seen_statuses: list[str] = []
        original_push_screen = screen.app.push_screen

        async def tracked_push_screen(*args, **kwargs):
            result = await original_push_screen(*args, **kwargs)
            modal = args[0]
            if isinstance(modal, ProgressStatusModal):
                seen_statuses.append(modal.status_text)
            return result

        screen.app.push_screen = tracked_push_screen

        async def do_nothing() -> None:
            return None

        await screen._run_async_with_progress_modal("Loading session...", do_nothing)
        await pilot.pause()

        assert seen_statuses == ["Loading session..."]
        assert not any(
            isinstance(node, ProgressStatusModal) for node in screen.app.screen_stack
        )


def test_repl_screen_reuses_progress_modal_for_loading_states() -> None:
    asyncio.run(_run_progress_modal_helper_test())
