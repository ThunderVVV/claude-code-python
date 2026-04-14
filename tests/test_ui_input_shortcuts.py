from __future__ import annotations

import asyncio

from textual import events

from claude_code.ui.widgets import InputTextArea


async def _dispatch_key(widget: InputTextArea, key: str) -> None:
    await widget._on_key(events.Key(key, None))


async def _run_input_shortcuts_test() -> None:
    widget = InputTextArea(text="hello brave new world")
    widget.move_cursor((0, len(widget.text)))

    await _dispatch_key(widget, "shift+left")
    assert widget.cursor_location == (0, 16)

    await _dispatch_key(widget, "shift+backspace")
    assert widget.text == "hello brave world"
    assert widget.cursor_location == (0, 12)

    await _dispatch_key(widget, "ctrl+shift+backspace")
    assert widget.text == "world"
    assert widget.cursor_location == (0, 0)


def test_input_text_area_word_shortcuts() -> None:
    asyncio.run(_run_input_shortcuts_test())
