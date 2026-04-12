from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from claude_code.ui.message_widgets import ToolResultLogWidget


class ToolResultLogTestApp(App[None]):
    def compose(self) -> ComposeResult:
        yield ToolResultLogWidget(id="tool-result-log")


def test_tool_result_log_widget_defaults_enable_wrapping():
    widget = ToolResultLogWidget()

    assert widget.wrap is True
    assert widget.min_width == 1
    assert widget.markup is False


@pytest.mark.asyncio
async def test_tool_result_log_widget_wraps_long_lines():
    async with ToolResultLogTestApp().run_test(size=(40, 12)) as pilot:
        await pilot.pause()
        widget = pilot.app.query_one(ToolResultLogWidget)

        widget.write_line("tool-result " + ("x" * 120))
        await pilot.pause()

        assert len(widget.lines) > 1
