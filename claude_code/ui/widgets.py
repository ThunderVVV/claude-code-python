"""UI widgets - Clawd and WelcomeWidget"""

from __future__ import annotations

import os

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalGroup
from textual.widgets import Label, Static, TextArea
from textual import events

from claude_code.ui.utils import sanitize_terminal_text
from claude_code.utils.logging_config import tui_log


class InputTextArea(TextArea):
    """Custom TextArea that handles Enter key for sending messages.

    - Enter: sends the message
    - Shift+Enter: inserts a new line
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._on_submit = None

    async def _on_key(self, event: events.Key) -> None:
        """Handle Enter key for sending message, Shift+Enter for new line."""
        tui_log(f"InputTextArea._on_key: key={event.key!r}, text={self.text!r}")
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            tui_log(
                f"Enter pressed, text={self.text!r}, callback={self._on_submit is not None}"
            )
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

        await super()._on_key(event)

    def set_on_submit(self, callback) -> None:
        """Set callback for submit action."""
        self._on_submit = callback


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
                yield Label("Recent activity", classes="section-title", markup=False)
                yield Label(
                    "No recent activity", classes="section-content", markup=False
                )

    def _truncate_cwd(self, path: str, max_len: int = 50) -> str:
        """Truncate path if too long"""
        if len(path) <= max_len:
            return path
        return "..." + path[-(max_len - 3) :]
