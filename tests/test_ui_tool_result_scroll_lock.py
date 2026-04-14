from __future__ import annotations

import asyncio

import pytest
from textual.app import App
from textual import events

from claude_code.ui.screens import REPLScreen, TranscriptContainer
from claude_code.ui.styles import TUI_CSS
from claude_code.ui.transcript_mode_modal import ProgressStatusModal


class _StubToolResultLog:
    def __init__(self, enabled: bool):
        self.pointer_scroll_enabled = enabled
        self.deactivated = False

    def deactivate_pointer_scroll(self):
        self.pointer_scroll_enabled = False
        self.deactivated = True


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


class _StubKeyEvent:
    def __init__(self, key: str):
        self.key = key
        self.stopped = False

    def stop(self):
        self.stopped = True


class _StubCollapsible:
    def __init__(self, classes: set[str], collapsed: bool):
        self.classes = classes
        self.collapsed = collapsed


class _StubModeWidget:
    def __init__(self):
        self.applied = 0

    def apply_transcript_collapsible_mode(self):
        self.applied += 1


def _build_scroll_event(event_cls):
    return event_cls(None, 0, 0, 0, 1, 0, False, False, False)


def test_repl_screen_blocks_outer_scroll_when_tool_result_lock_is_active(monkeypatch):
    screen = REPLScreen(client=object(), session_id="session-1")
    monkeypatch.setattr(
        screen,
        "query",
        lambda widget_type: [_StubToolResultLog(True)],
    )

    down_event = _build_scroll_event(events.MouseScrollDown)
    up_event = _build_scroll_event(events.MouseScrollUp)

    screen.on_mouse_scroll_down(down_event)
    screen.on_mouse_scroll_up(up_event)

    assert down_event._stop_propagation is True
    assert up_event._stop_propagation is True


def test_repl_screen_allows_outer_scroll_without_tool_result_lock(monkeypatch):
    screen = REPLScreen(client=object(), session_id="session-1")
    monkeypatch.setattr(
        screen,
        "query",
        lambda widget_type: [_StubToolResultLog(False)],
    )

    down_event = _build_scroll_event(events.MouseScrollDown)
    up_event = _build_scroll_event(events.MouseScrollUp)

    screen.on_mouse_scroll_down(down_event)
    screen.on_mouse_scroll_up(up_event)

    assert down_event._stop_propagation is False
    assert up_event._stop_propagation is False


def test_repl_screen_collapsible_toggle_clears_all_tool_result_locks(monkeypatch):
    screen = REPLScreen(client=object(), session_id="session-1")
    widgets = [_StubToolResultLog(True), _StubToolResultLog(False)]
    monkeypatch.setattr(
        screen,
        "query",
        lambda widget_type: widgets,
    )
    monkeypatch.setattr(screen, "_schedule_input_focus", lambda: None)
    event = _StubToggleEvent()

    screen.on_collapsible_toggled(event)

    assert event.stopped is True
    assert widgets[0].deactivated is True
    assert widgets[0].pointer_scroll_enabled is False
    assert widgets[1].deactivated is True


def test_repl_screen_collapsible_title_focus_clears_all_tool_result_locks(monkeypatch):
    screen = REPLScreen(client=object(), session_id="session-1")
    widgets = [_StubToolResultLog(True), _StubToolResultLog(False)]
    monkeypatch.setattr(
        screen,
        "query",
        lambda widget_type: widgets,
    )
    monkeypatch.setattr(screen, "_schedule_input_focus", lambda: None)

    screen.on_descendant_focus(_StubDescendantFocusEvent(_StubCollapsibleTitle()))

    assert widgets[0].deactivated is True
    assert widgets[0].pointer_scroll_enabled is False
    assert widgets[1].deactivated is True


@pytest.mark.asyncio
async def test_repl_screen_ctrl_e_clears_all_tool_result_locks(monkeypatch):
    screen = REPLScreen(client=object(), session_id="session-1")
    widgets = [_StubToolResultLog(True), _StubToolResultLog(False)]
    monkeypatch.setattr(
        screen,
        "query",
        lambda widget_type: widgets,
    )
    event = _StubKeyEvent("ctrl+e")

    await screen.on_key(event)

    assert event.stopped is True
    assert widgets[0].deactivated is True
    assert widgets[0].pointer_scroll_enabled is False
    assert widgets[1].deactivated is True


def test_transcript_container_blocks_scroll_when_tool_result_lock_is_active(monkeypatch):
    container = TranscriptContainer()
    monkeypatch.setattr(
        container,
        "_tool_result_scroll_locked",
        lambda: True,
    )

    down_event = _build_scroll_event(events.MouseScrollDown)
    up_event = _build_scroll_event(events.MouseScrollUp)

    container.on_mouse_scroll_down(down_event)
    container.on_mouse_scroll_up(up_event)

    assert container.allow_vertical_scroll is False
    assert down_event._stop_propagation is True
    assert up_event._stop_propagation is True


def test_transcript_container_allows_scroll_without_tool_result_lock(monkeypatch):
    container = TranscriptContainer()
    monkeypatch.setattr(
        container,
        "_tool_result_scroll_locked",
        lambda: False,
    )

    down_event = _build_scroll_event(events.MouseScrollDown)
    up_event = _build_scroll_event(events.MouseScrollUp)

    container.on_mouse_scroll_down(down_event)
    container.on_mouse_scroll_up(up_event)

    assert down_event._stop_propagation is False
    assert up_event._stop_propagation is False


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
        assert not any(isinstance(node, ProgressStatusModal) for node in screen.app.screen_stack)


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
        assert not any(isinstance(node, ProgressStatusModal) for node in screen.app.screen_stack)


def test_repl_screen_reuses_progress_modal_for_loading_states() -> None:
    asyncio.run(_run_progress_modal_helper_test())
