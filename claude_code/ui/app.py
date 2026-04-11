"""Main Claude Code TUI application - aligned with TypeScript App.tsx"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from textual.app import App
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import Label

from claude_code.ui.styles import TUI_CSS
from claude_code.ui.screens import REPLScreen

if TYPE_CHECKING:
    from claude_code.client.grpc_client import ClaudeCodeClient


class ClaudeCodeApp(App):
    CSS = TUI_CSS
    DEFAULT_THEME = "tokyo-night"
    ALLOW_SELECT = True
    BINDINGS = [
        Binding(
            "ctrl+c,ctrl+shift+c,super+c",
            "copy_selection",
            "Copy selected text",
            show=False,
            priority=True,
        ),
    ]

    SCREENS = {"repl": REPLScreen}

    def __init__(
        self,
        client: "ClaudeCodeClient",
        working_directory: str = "",
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.theme = self.DEFAULT_THEME
        self.client = client
        self.working_directory = working_directory

    async def on_mount(self) -> None:
        await self.client.connect()
        session_id = await self.client.create_session(self.working_directory)
        await self.push_screen(
            REPLScreen(
                client=self.client,
                session_id=session_id,
                working_directory=self.working_directory,
            )
        )

    async def on_unmount(self) -> None:
        """Clean up resources on exit."""
        await self.client.close()

    def action_copy_selection(self) -> None:
        """Copy the active Textual selection to the clipboard."""
        selection = self._get_selected_text()
        if not selection:
            return
        self.copy_to_clipboard(selection)
        self.notify(
            "Copied to clipboard",
            title="Clipboard",
            timeout=1.5,
            markup=False,
        )

    def _get_selected_text(self) -> str:
        """Return text selected in the focused widget or active screen."""
        focused = getattr(self.screen, "focused", None)
        if focused is not None:
            if selected_text := self._extract_widget_selection(focused):
                return selected_text

        screen_selection = self.screen.get_selected_text()
        return screen_selection or ""

    @staticmethod
    def _extract_widget_selection(widget: Widget) -> str:
        """Read selection text from widgets that manage their own selection."""
        selected_text = getattr(widget, "selected_text", None)
        if isinstance(selected_text, str) and selected_text:
            return selected_text
        return ""
