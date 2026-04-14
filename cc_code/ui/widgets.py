"""UI widgets - Clawd and WelcomeWidget"""

from __future__ import annotations

import os
import re
import inspect

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalGroup
from textual.widgets import Label, Static, TextArea
from textual import events

from cc_code.ui.utils import sanitize_terminal_text
from cc_code.ui.autocomplete import AutocompleteMode
from cc_code.utils.logging_config import tui_log



class InputTextArea(TextArea):
    """Custom TextArea that handles Enter key for sending messages.

    - Enter: sends the message
    - Shift+Enter: inserts a new line
    """

    def __init__(self, **kwargs):
        # Older Textual versions accepted cursor_blink; newer ones removed it.
        if "cursor_blink" in inspect.signature(TextArea.__init__).parameters:
            kwargs.setdefault("cursor_blink", False)
        super().__init__(**kwargs)
        if hasattr(self, "cursor_blink"):
            self.cursor_blink = False
        self._on_submit = None
        self._autocomplete_active = False

    async def _on_key(self, event: events.Key) -> None:
        """Handle key events."""

        if self._autocomplete_active:
            if event.key in ("up", "ctrl+p"):
                event.stop()
                event.prevent_default()
                self._navigate_autocomplete(-1)
                return

            if event.key in ("down", "ctrl+n"):
                event.stop()
                event.prevent_default()
                self._navigate_autocomplete(1)
                return

            if event.key in ("enter", "tab"):
                event.stop()
                event.prevent_default()
                self._select_autocomplete()
                return

            if event.key == "escape":
                event.stop()
                event.prevent_default()
                self._autocomplete_active = False
                return

        if event.key == "enter":
            event.stop()
            event.prevent_default()
            tui_log(f"Enter pressed, text={self.text!r}, callback={self._on_submit is not None}")
            if self._on_submit:
                self._on_submit(self.text)
            return

        if event.key == "shift+enter":
            event.stop()
            event.prevent_default()
            self.insert("\n")
            return

        if event.key == "shift+up":
            event.stop()
            event.prevent_default()
            self.action_cursor_up()
            return

        if event.key == "shift+down":
            event.stop()
            event.prevent_default()
            self.action_cursor_down()
            return

        if event.key == "shift+left":
            event.stop()
            event.prevent_default()
            self.action_cursor_word_left()
            return

        if event.key == "shift+right":
            event.stop()
            event.prevent_default()
            self.action_cursor_word_right()
            return

        if event.key == "shift+backspace":
            event.stop()
            event.prevent_default()
            self.action_delete_word_left()
            return

        if event.key == "ctrl+shift+backspace":
            event.stop()
            event.prevent_default()
            self.action_delete_to_start_of_line()
            return

        await super()._on_key(event)

    def _navigate_autocomplete(self, direction: int) -> None:
        """Navigate autocomplete via screen method."""
        try:
            screen = self.screen
            if hasattr(screen, "_navigate_autocomplete_popup"):
                screen._navigate_autocomplete_popup(direction)
        except Exception:
            pass

    def _select_autocomplete(self) -> None:
        """Select autocomplete item via screen method."""
        try:
            screen = self.screen
            if hasattr(screen, "_select_autocomplete_popup"):
                screen._select_autocomplete_popup()
        except Exception:
            pass

    def set_autocomplete_active(self, active: bool) -> None:
        """Set whether autocomplete is currently active."""
        self._autocomplete_active = active

    def set_on_submit(self, callback) -> None:
        """Set callback for submit action."""
        self._on_submit = callback

    def insert_autocomplete(self, replacement: str, mode: AutocompleteMode) -> None:
        """Insert autocomplete selection into the text."""
        line = self.cursor_location[0]
        col = self.cursor_location[1]
        line_text = self.document.get_line(line)

        if mode == AutocompleteMode.SLASH:
            match = re.match(r"^/(\S*)$", line_text[:col])
            if match:
                start_col = 0
                end_col = col
                self.delete((line, start_col), (line, end_col))
                self.insert(replacement)
        elif mode == AutocompleteMode.AT:
            match = re.search(r"@(\S*)$", line_text[:col])
            if match:
                start_col = match.start()
                end_col = col
                self.delete((line, start_col), (line, end_col))
                self.insert(replacement)

        self._autocomplete_active = False


class Clawd(VerticalGroup):
    """Clawd the cat - ASCII art aligned with TypeScript Clawd.tsx"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        # Standard terminal Clawd (9 cols wide)
        # Default pose with bottom pupils - matches TypeScript POSES.default
        yield Static(" ▐▛███▜▌ ", classes="clawd-line", markup=False)
        yield Static(" ▝▜█████▛▘ ", classes="clawd-line", markup=False)
        yield Static("   ▘▘ ▝▝   ", classes="clawd-line", markup=False)


class WelcomeWidget(Container):
    """Welcome widget aligned with TypeScript LogoV2.tsx - rendered as part of scrollable content"""

    def __init__(
        self,
        model_name: str = "claude-sonnet-4-6",
        cwd: str = "",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.model_name = model_name
        self.cwd = cwd or os.getcwd()

    def compose(self) -> ComposeResult:
        # Main horizontal layout - aligned with TypeScript LogoV2.tsx
        with Horizontal(classes="welcome-horizontal"):
            # Left panel with welcome message and Clawd
            with Container(id="left-panel"):
                yield Label("Welcome back!", classes="welcome-message", markup=False)
                yield Clawd()
                yield Label(
                    sanitize_terminal_text(f"{self.model_name} · API Usage Billing"),
                    classes="model-info",
                    id="welcome-model-info",
                    markup=False,
                )
                yield Label(
                    sanitize_terminal_text(self._truncate_cwd(self.cwd)),
                    classes="cwd-info",
                    markup=False,
                )

            # Right panel with tips
            with Container(id="right-panel"):
                yield Label(
                    "Tips for getting started", classes="section-title", markup=False
                )
                yield Label(
                    "/new to create a new session, /exit to quit, /sessions to view all sessions",
                    classes="section-content",
                    markup=False,
                )
                yield Label(
                    "@web to enable web search and extract skills",
                    classes="section-content",
                    markup=False,
                )
                yield Label(
                    "Shift+Left/Right: move by word",
                    classes="section-content",
                    markup=False,
                )
                yield Label(
                    "Shift+Backspace: delete word",
                    classes="section-content",
                    markup=False,
                )
                yield Label(
                    "Ctrl+Shift+Backspace: delete to line start",
                    classes="section-content",
                    markup=False,
                )
                yield Label("Recent activity", classes="section-title", markup=False)
                yield Label(
                    "No recent activity", classes="section-content", markup=False
                )

    def _truncate_cwd(self, path: str, max_len: int = 50) -> str:
        """Truncate path if too long"""
        if len(path) <= max_len:
            return path
        return "..." + path[-(max_len - 3) :]

    def set_model_name(self, model_name: str) -> None:
        """Update the displayed model name."""
        self.model_name = model_name
        try:
            label = self.query_one("#welcome-model-info", Label)
            label.update(
                sanitize_terminal_text(f"{self.model_name} · API Usage Billing")
            )
        except Exception:
            pass
