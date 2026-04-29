"""Main CC Code TUI application - aligned with TypeScript App.tsx"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Mapping

from textual import events
from textual.app import App
from textual.binding import Binding
from textual.widget import Widget

from cc_code.core.settings import SettingsStore
from cc_code.ui.styles import TUI_CSS
from cc_code.ui.screens import REPLScreen

if TYPE_CHECKING:
    from cc_code.client.http_client import CCCodeHttpClient


logger = logging.getLogger(__name__)

try:
    import pyperclip
except ImportError:
    pyperclip = None

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


class CCCodeApp(App):
    CSS = TUI_CSS
    DEFAULT_THEME = DEFAULT_THEME_NAME
    ALLOW_SELECT = True
    BINDINGS = [
        Binding(
            "ctrl+c",
            "quit",
            "Quit",
            show=False,
            priority=True,
        ),
    ]

    SCREENS = {"repl": REPLScreen}

    def __init__(
        self,
        client: "CCCodeHttpClient",
        working_directory: str = "",
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.settings_store = SettingsStore()
        self.settings = self.settings_store.ensure_settings()
        self._last_auto_copied_selection = ""
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

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Auto-copy the current selection when the primary mouse button is released."""
        if event.button == 1:
            self.set_timer(0.01, self._auto_copy_selection_after_mouse_up)

    def _auto_copy_selection_after_mouse_up(self) -> None:
        """Copy the current selection after drag-selection has settled."""
        selection = self._get_selected_text()
        if not selection:
            self._last_auto_copied_selection = ""
            return
        if selection == self._last_auto_copied_selection:
            return
        if self._copy_text_to_clipboard(selection):
            self._last_auto_copied_selection = selection
            self.notify(
                "Copied to clipboard",
                title="Clipboard",
                timeout=1.5,
                markup=False,
            )

    def _copy_text_to_clipboard(self, text: str) -> bool:
        """Write text to the clipboard using pyperclip when available."""
        if pyperclip is not None:
            try:
                pyperclip.copy(text)
                return True
            except Exception:
                pass
        self.copy_to_clipboard(text)
        return True

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
