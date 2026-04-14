"""Main Claude Code TUI application - aligned with TypeScript App.tsx"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Mapping

from textual.app import App
from textual.binding import Binding
from textual.widget import Widget

from claude_code.core.settings import SettingsStore
from claude_code.ui.styles import TUI_CSS
from claude_code.ui.screens import REPLScreen

if TYPE_CHECKING:
    from claude_code.client.http_client import ClaudeCodeHttpClient


logger = logging.getLogger(__name__)

DEFAULT_THEME_NAME = "atom-one-dark"


def _resolve_theme_name(
    available_themes: Mapping[str, Any],
    requested_theme: str | None,
) -> str:
    """Return a valid theme name, falling back to the default when needed."""
    if not requested_theme:
        return DEFAULT_THEME_NAME

    theme_name = requested_theme.strip()
    if not theme_name:
        return DEFAULT_THEME_NAME

    if theme_name not in available_themes:
        return DEFAULT_THEME_NAME

    return theme_name


class ClaudeCodeApp(App):
    CSS = TUI_CSS
    DEFAULT_THEME = DEFAULT_THEME_NAME
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
        client: "ClaudeCodeHttpClient",
        working_directory: str = "",
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.settings_store = SettingsStore()
        self.settings = self.settings_store.ensure_settings()
        self.theme = _resolve_theme_name(
            self.available_themes,
            self.settings.theme,
        )
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
