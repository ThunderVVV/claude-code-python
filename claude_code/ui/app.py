"""Main Claude Code TUI application - aligned with TypeScript App.tsx"""

from textual.app import App
from textual.binding import Binding
from textual.widget import Widget

from claude_code.core.query_engine import QueryEngine
from claude_code.ui.styles import TUI_CSS
from claude_code.ui.screens import REPLScreen


class ClaudeCodeApp(App):
    """Main Claude Code application - aligned with TypeScript App.tsx"""

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
        query_engine: QueryEngine,
        model_name: str = "claude-sonnet-4-6",
        context_window_tokens: int | None = None,
        save_history: bool = True,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.theme = self.DEFAULT_THEME
        self.query_engine = query_engine
        self.model_name = model_name
        self.context_window_tokens = context_window_tokens
        self.save_history = save_history

    async def on_mount(self) -> None:
        """Initialize and push the REPL screen on mount"""
        # Initialize the query engine (creates HTTP client)
        await self.query_engine.initialize()
        await self.push_screen(
            REPLScreen(
                self.query_engine,
                self.model_name,
                context_window_tokens=self.context_window_tokens,
                save_history=self.save_history,
            )
        )

    async def on_unmount(self) -> None:
        """Clean up resources on exit"""
        await self.query_engine.close()

    def action_copy_selection(self) -> None:
        """Copy the active Textual selection to the clipboard.

        This keeps clipboard behavior inside the TUI so copy doesn't fall back
        to terminal-specific selection handling.
        """
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
