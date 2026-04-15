"""Debug modal for displaying QueryEngine runtime state."""

from __future__ import annotations

from rich.cells import cell_len
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Center, VerticalGroup
from textual.screen import ModalScreen
from textual.selection import Selection
from textual.strip import Strip
from textual.widgets import RichLog, Static

from cc_code.ui.utils import sanitize_terminal_text


class SelectableRichLog(RichLog):
    """RichLog variant that preserves selection offsets for line API rendering."""

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset
        strip = self._render_line_with_selection(scroll_y + y, scroll_x, self.size.width)
        strip = strip.apply_style(self.rich_style)
        return strip.apply_offsets(scroll_x, scroll_y + y)

    def _render_line_with_selection(self, y: int, scroll_x: int, width: int) -> Strip:
        rich_style = self.rich_style
        if y >= len(self.lines):
            return Strip.blank(width, rich_style)

        line_text = self.lines[y].text
        rendered_text = Text(line_text, no_wrap=True)

        selection = self.text_selection
        if selection is not None:
            select_span = selection.get_span(y)
            if select_span is not None:
                start, end = select_span
                if end == -1:
                    end = len(line_text)
                selection_style = self.screen.get_component_rich_style(
                    "screen--selection"
                )
                rendered_text.stylize(selection_style, start, end)
        line_strip = Strip(rendered_text.render(self.app.console), cell_len(line_text))

        return line_strip.crop_extend(scroll_x, scroll_x + width, rich_style)

    def get_selection(self, selection: Selection) -> tuple[str, str] | None:
        if not self.lines:
            return None
        plain_text = "\n".join(line.text.rstrip() for line in self.lines)
        return selection.extract(plain_text), "\n"

    def selection_updated(self, selection: Selection | None) -> None:
        self._line_cache.clear()
        self.refresh()

    def _on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        self.scroll_relative(y=-3, animate=False)
        event.stop()

    def _on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        self.scroll_relative(y=3, animate=False)
        event.stop()


class DebugStateModal(ModalScreen[None]):
    """Modal dialog that shows serialized debug state in a RichLog."""

    CSS = """
    DebugStateModal {
        align: center middle;

        #container {
            width: 120;
            max-width: 95%;
            height: 30;
            max-height: 90%;
            padding: 1 2;
            background: $surface;
            border: none;
        }

        #title {
            width: 100%;
            margin-bottom: 1;
            content-align: center middle;
            text-style: bold;
        }

        #debug-log {
            width: 100%;
            height: 1fr;
            background: $surface;
            color: $foreground;
            overflow-y: auto;
            overflow-x: hidden;
            scrollbar-size: 1 1;
            scrollbar-background: $surface;
            scrollbar-background-hover: $surface;
            scrollbar-background-active: $surface;
            scrollbar-color: $primary-muted;
            scrollbar-color-hover: $primary;
            scrollbar-color-active: $primary;
            scrollbar-corner-color: $surface;

            &:focus {
                background-tint: 0%;
            }
        }

        #hint {
            width: 100%;
            margin-top: 1;
            content-align: right middle;
            color: $text-muted;
        }
    }
    """

    BINDINGS = [
        ("escape", "dismiss", "Dismiss"),
        ("q", "dismiss", "Dismiss"),
    ]

    def __init__(self, debug_text: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._debug_text = debug_text

    def compose(self) -> ComposeResult:
        with Center():
            with VerticalGroup(id="container"):
                yield Static("QueryEngine Debug State", id="title", markup=False)
                yield SelectableRichLog(
                    id="debug-log",
                    auto_scroll=False,
                    highlight=False,
                    markup=False,
                    wrap=True,
                )
                yield Static("Press Esc or q to close", id="hint", markup=False)

    def on_mount(self) -> None:
        log_widget = self.query_one("#debug-log", SelectableRichLog)
        sanitized = sanitize_terminal_text(self._debug_text)
        lines = sanitized.splitlines() or ["<empty debug payload>"]
        for line in lines:
            log_widget.write(line if line else " ")
        log_widget.refresh()
        log_widget.focus()
