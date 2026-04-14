from __future__ import annotations

import asyncio
from textual.app import App, ComposeResult
from textual.events import Click

from claude_code.ui.message_widgets import (
    FlushCollapsibleTitle,
    ToolResultBlockWidget,
    ToolUseWidget,
)


class ToolResultBlockTestApp(App[None]):
    def __init__(self, output_lines: list[str]):
        super().__init__()
        self._output_lines = output_lines

    def compose(self) -> ComposeResult:
        yield ToolResultBlockWidget(self._output_lines, id="tool-result-block")


class ToolUseResultTestApp(App[None]):
    def compose(self) -> ComposeResult:
        widget = ToolUseWidget(tool_name="Bash", tool_input={}, tool_use_id="tool-1")
        widget.set_result("\n".join(f"line {index}" for index in range(12)), False)
        yield widget


def test_flush_collapsible_title_allows_selection():
    assert FlushCollapsibleTitle.ALLOW_SELECT is True


def test_tool_result_block_defaults():
    widget = ToolResultBlockWidget([f"line {i}" for i in range(3)])

    assert widget.VISIBLE_LINE_LIMIT == 5
    assert "tool-result-block" in widget.classes
    assert "tool-result-static" in widget.classes


async def _run_tool_result_block_starts_with_preview_for_long_output() -> None:
    async with ToolResultBlockTestApp(
        [f"line {index}" for index in range(12)]
    ).run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        block = pilot.app.query_one(ToolResultBlockWidget)

        assert str(block.content) == (
            "Output:\n"
            "line 0\nline 1\nline 2\nline 3\nline 4\n"
            "... 7 lines (Click to expand)"
        )


def test_tool_result_block_starts_with_preview_for_long_output() -> None:
    asyncio.run(_run_tool_result_block_starts_with_preview_for_long_output())


async def _run_tool_result_block_click_toggles_expand_and_collapse() -> None:
    async with ToolResultBlockTestApp(
        [f"line {index}" for index in range(12)]
    ).run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        block = pilot.app.query_one(ToolResultBlockWidget)

        block.on_click(Click(block, 0, 0, 0, 0, 1, False, False, False))
        await pilot.pause()

        assert str(block.content) == "Output:\n" + "\n".join(
            f"line {index}" for index in range(12)
        )

        block.on_click(Click(block, 0, 0, 0, 0, 1, False, False, False))
        await pilot.pause()

        assert str(block.content) == (
            "Output:\n"
            "line 0\nline 1\nline 2\nline 3\nline 4\n"
            "... 7 lines (Click to expand)"
        )


def test_tool_result_block_click_toggles_expand_and_collapse() -> None:
    asyncio.run(_run_tool_result_block_click_toggles_expand_and_collapse())


async def _run_tool_result_block_short_output_has_no_expand_hint() -> None:
    async with ToolResultBlockTestApp(
        [f"line {index}" for index in range(2)]
    ).run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        block = pilot.app.query_one(ToolResultBlockWidget)

        assert str(block.content) == "Output:\nline 0\nline 1"


def test_tool_result_block_short_output_has_no_expand_hint() -> None:
    asyncio.run(_run_tool_result_block_short_output_has_no_expand_hint())


def test_tool_use_widget_compose_output_branch_structure():
    widget = ToolUseWidget(tool_name="Bash", tool_input={}, tool_use_id="tool-1")

    parts = list(widget._compose_output_branch())

    assert len(parts) == 1
    assert isinstance(parts[0], ToolResultBlockWidget)


def test_tool_use_widget_title_highlights_leading_action_word():
    widget = ToolUseWidget(tool_name="Bash", tool_input={}, tool_use_id="tool-1")
    widget._result = ("Ran: git status", False)

    title = widget._build_title()
    title_text = str(title)

    assert any(
        span.style == "$text-primary" and title_text[span.start:span.end] == "Ran"
        for span in title.spans
    )


async def _run_tool_use_widget_renders_static_result_preview() -> None:
    async with ToolUseResultTestApp().run_test(size=(80, 24)) as pilot:
        await pilot.pause()

        block = pilot.app.query_one(ToolResultBlockWidget)
        assert str(block.content) == (
            "Output:\n"
            "line 0\nline 1\nline 2\nline 3\nline 4\n"
            "... 7 lines (Click to expand)"
        )


def test_tool_use_widget_renders_static_result_preview() -> None:
    asyncio.run(_run_tool_use_widget_renders_static_result_preview())
