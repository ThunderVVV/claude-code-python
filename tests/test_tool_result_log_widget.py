from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from claude_code.ui.message_widgets import ToolResultLogWidget, ToolUseWidget


class ToolResultLogTestApp(App[None]):
    def compose(self) -> ComposeResult:
        yield ToolResultLogWidget(id="tool-result-log")


def test_tool_result_log_widget_defaults_enable_wrapping():
    widget = ToolResultLogWidget()

    assert widget.wrap is True
    assert widget.min_width == 1
    assert widget.markup is False
    assert widget.highlight is False
    assert widget.focus_on_click() is False
    assert "padding: 0 1;" in widget.DEFAULT_CSS


@pytest.mark.asyncio
async def test_tool_result_log_widget_wraps_long_lines():
    async with ToolResultLogTestApp().run_test(size=(40, 12)) as pilot:
        await pilot.pause()
        widget = pilot.app.query_one(ToolResultLogWidget)

        widget.write_line("tool-result " + ("x" * 120))
        await pilot.pause()

        assert len(widget.lines) > 1


def test_tool_use_widget_output_label_uses_branch_prefix():
    assert ToolUseWidget.OUTPUT_BRANCH_VERTICAL == "│"
    assert ToolUseWidget.OUTPUT_BRANCH_END == "╰"
    assert ToolUseWidget.OUTPUT_TAIL_SCROLL_HINT == "scroll to view"
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

    suffix = "line" if len(widget._output_lines) == 1 else "lines"
    tail_text = f"{widget.OUTPUT_BRANCH_END} {len(widget._output_lines)} {suffix} output"

    assert tail_text == "╰ 2 lines output"
