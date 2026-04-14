from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.events import Click, MouseScrollDown, MouseScrollUp
from textual.widgets import Static

from claude_code.ui.message_widgets import ToolResultLogWidget, ToolUseWidget


class ToolResultLogTestApp(App[None]):
    def compose(self) -> ComposeResult:
        yield ToolResultLogWidget(id="tool-result-log")


class ToolUseTailTestApp(App[None]):
    def compose(self) -> ComposeResult:
        widget = ToolUseWidget(tool_name="Bash", tool_input={}, tool_use_id="tool-1")
        widget.set_result("\n".join(f"line {index}" for index in range(12)), False)
        yield widget


class ShortToolUseTailTestApp(App[None]):
    def compose(self) -> ComposeResult:
        widget = ToolUseWidget(tool_name="Bash", tool_input={}, tool_use_id="tool-1")
        widget.set_result("short line 1\nshort line 2", False)
        yield widget


def test_tool_result_log_widget_defaults_enable_wrapping():
    widget = ToolResultLogWidget()

    assert widget.wrap is True
    assert widget.min_width == 1
    assert widget.markup is False
    assert widget.highlight is False
    assert widget.focus_on_click() is False
    assert "padding: 0;" in widget.DEFAULT_CSS
    assert widget.SCROLL_ACTIVATION_LINE_LIMIT == 10
    assert widget.allow_vertical_scroll is False
    assert "-active-scroll-lock" not in widget.classes


def test_tool_result_log_widget_requires_activation_for_pointer_scroll(monkeypatch: pytest.MonkeyPatch):
    widget = ToolResultLogWidget()
    called = {"down": False, "up": False}

    def fake_scroll_down(*args, **kwargs):
        called["down"] = True
        return True

    def fake_scroll_up(*args, **kwargs):
        called["up"] = True
        return True

    monkeypatch.setattr(widget, "_scroll_down_for_pointer", fake_scroll_down)
    monkeypatch.setattr(widget, "_scroll_up_for_pointer", fake_scroll_up)

    widget._on_mouse_scroll_down(
        MouseScrollDown(widget, 0, 0, 0, -1, 0, False, False, False)
    )
    widget._on_mouse_scroll_up(
        MouseScrollUp(widget, 0, 0, 0, 1, 0, False, False, False)
    )

    assert called == {"down": False, "up": False}
    assert widget.allow_vertical_scroll is False


def test_tool_result_log_widget_consumes_scroll_at_bounds_when_activated(monkeypatch: pytest.MonkeyPatch):
    widget = ToolResultLogWidget()
    monkeypatch.setattr(widget, "can_activate_pointer_scroll", lambda: True)
    widget.activate_pointer_scroll()
    called = {"down": False, "up": False}

    def fake_scroll_down(*args, **kwargs):
        called["down"] = True
        return False

    def fake_scroll_up(*args, **kwargs):
        called["up"] = True
        return False

    monkeypatch.setattr(widget, "_scroll_down_for_pointer", fake_scroll_down)
    monkeypatch.setattr(widget, "_scroll_up_for_pointer", fake_scroll_up)

    down_event = MouseScrollDown(widget, 0, 0, 0, -1, 0, False, False, False)
    up_event = MouseScrollUp(widget, 0, 0, 0, 1, 0, False, False, False)

    widget._on_mouse_scroll_down(down_event)
    widget._on_mouse_scroll_up(up_event)

    assert called == {"down": True, "up": True}
    assert down_event._stop_propagation is True
    assert up_event._stop_propagation is True


@pytest.mark.asyncio
async def test_tool_result_log_widget_click_arms_pointer_scroll(monkeypatch: pytest.MonkeyPatch):
    async with ToolResultLogTestApp().run_test(size=(40, 12)) as pilot:
        await pilot.pause()
        widget = pilot.app.query_one(ToolResultLogWidget)
        called = {"down": False, "up": False}

        def fake_scroll_down(*args, **kwargs):
            called["down"] = True
            return True

        def fake_scroll_up(*args, **kwargs):
            called["up"] = True
            return True

        monkeypatch.setattr(widget, "_scroll_down_for_pointer", fake_scroll_down)
        monkeypatch.setattr(widget, "_scroll_up_for_pointer", fake_scroll_up)
        monkeypatch.setattr(widget, "can_activate_pointer_scroll", lambda: True)

        widget.on_click(Click(widget, 0, 0, 0, 0, 1, False, False, False))
        await pilot.pause()

        widget._on_mouse_scroll_down(
            MouseScrollDown(widget, 0, 0, 0, -1, 0, False, False, False)
        )
        widget._on_mouse_scroll_up(
            MouseScrollUp(widget, 0, 0, 0, 1, 0, False, False, False)
        )

        assert widget.pointer_scroll_enabled is True
        assert called == {"down": True, "up": True}


def test_tool_result_log_widget_explicit_deactivation_disables_pointer_scroll():
    widget = ToolResultLogWidget()
    widget.lines = [object()] * 11
    widget.activate_pointer_scroll()

    widget.deactivate_pointer_scroll()

    assert widget._pointer_scroll_enabled is False
    assert widget.allow_vertical_scroll is False
    assert "-active-scroll-lock" not in widget.classes


def test_tool_result_log_widget_activation_adds_active_class():
    widget = ToolResultLogWidget()
    widget.lines = [object()] * 11
    widget.activate_pointer_scroll()

    assert "-active-scroll-lock" in widget.classes
    assert widget.pointer_scroll_enabled is True


def test_tool_result_log_widget_does_not_activate_without_scrollable_content():
    widget = ToolResultLogWidget()
    widget.lines = [object()] * 2
    widget.activate_pointer_scroll()

    assert widget.pointer_scroll_enabled is False
    assert "-active-scroll-lock" not in widget.classes


@pytest.mark.asyncio
async def test_tool_result_log_widget_wraps_long_lines():
    async with ToolResultLogTestApp().run_test(size=(40, 12)) as pilot:
        await pilot.pause()
        widget = pilot.app.query_one(ToolResultLogWidget)

        widget.write_line("tool-result " + ("x" * 120))
        await pilot.pause()

        assert len(widget.lines) > 1


@pytest.mark.asyncio
async def test_tool_result_log_widget_click_updates_tail_hint():
    async with ToolUseTailTestApp().run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        widget = pilot.app.query_one(ToolUseWidget)
        log_widget = pilot.app.query_one(ToolResultLogWidget)
        tail_widget = widget.query_one(".tool-output-tail", Static)

        assert str(tail_widget.content) == "╰ 12 lines output (click and scroll to view)"

        log_widget.on_click(Click(log_widget, 0, 0, 0, 0, 1, False, False, False))
        await pilot.pause()
        await pilot.pause()

        assert str(tail_widget.content) == "╰ 12 lines output (Viewing , click here or ctrl+e to exit)"


@pytest.mark.asyncio
async def test_tool_result_log_widget_click_does_not_activate_when_not_scrollable():
    async with ShortToolUseTailTestApp().run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        widget = pilot.app.query_one(ToolUseWidget)
        log_widget = pilot.app.query_one(ToolResultLogWidget)
        tail_widget = widget.query_one(".tool-output-tail", Static)

        log_widget.on_click(Click(log_widget, 0, 0, 0, 0, 1, False, False, False))
        await pilot.pause()

        assert log_widget.pointer_scroll_enabled is False
        assert "-active-scroll-lock" not in log_widget.classes
        assert str(tail_widget.content) == "╰ 2 lines output"


def test_tool_use_widget_output_label_uses_branch_prefix():
    assert ToolUseWidget.OUTPUT_BRANCH_VERTICAL == "│"
    assert ToolUseWidget.OUTPUT_BRANCH_END == "╰"
    assert ToolUseWidget.OUTPUT_TAIL_SCROLL_HINT == "click and scroll to view"
    assert (
        ToolUseWidget.OUTPUT_TAIL_ACTIVE_SCROLL_HINT
        == "Viewing , click here or ctrl+e to exit"
    )
    assert ToolUseWidget.OUTPUT_VISIBLE_LINE_LIMIT == 10


def test_tool_use_widget_compose_output_branch_structure():
    widget = ToolUseWidget(tool_name="Bash", tool_input={}, tool_use_id="tool-1")

    parts = list(widget._compose_output_branch())

    assert len(parts) == 2
    assert isinstance(parts[0], ToolResultLogWidget)
    assert isinstance(parts[1], Static)


def test_tool_use_widget_formats_output_branch_inline():
    widget = ToolUseWidget(tool_name="Bash", tool_input={}, tool_use_id="tool-1")
    widget._output_lines = ["line 1", "line 2", "line 3"]

    assert widget._format_output_branch_lines() == [
        "│ line 1",
        "│ line 2",
        "│ line 3",
    ]


def test_tool_use_widget_tail_text_uses_output_wording():
    widget = ToolUseWidget(tool_name="Bash", tool_input={}, tool_use_id="tool-1")
    widget._output_lines = ["line 1", "line 2"]

    tail_text = widget._build_output_tail_text(
        len(widget._output_lines),
        scrollable=False,
        pointer_scroll_enabled=False,
    )

    assert tail_text == "╰ 2 lines output"


def test_tool_use_widget_tail_text_uses_inactive_scroll_hint():
    widget = ToolUseWidget(tool_name="Bash", tool_input={}, tool_use_id="tool-1")

    tail_text = widget._build_output_tail_text(
        12,
        scrollable=True,
        pointer_scroll_enabled=False,
    )

    assert tail_text == "╰ 12 lines output (click and scroll to view)"


def test_tool_use_widget_tail_text_uses_active_scroll_hint():
    widget = ToolUseWidget(tool_name="Bash", tool_input={}, tool_use_id="tool-1")

    tail_text = widget._build_output_tail_text(
        12,
        scrollable=True,
        pointer_scroll_enabled=True,
    )

    assert tail_text == "╰ 12 lines output (Viewing , click here or ctrl+e to exit)"


@pytest.mark.asyncio
async def test_tool_use_widget_collapse_clears_active_scroll_lock():
    async with ToolUseTailTestApp().run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        widget = pilot.app.query_one(ToolUseWidget)
        log_widget = pilot.app.query_one(ToolResultLogWidget)

        log_widget.activate_pointer_scroll()
        await pilot.pause()

        widget._deactivate_output_scroll_lock()

        assert log_widget.pointer_scroll_enabled is False
        assert "-active-scroll-lock" not in log_widget.classes
