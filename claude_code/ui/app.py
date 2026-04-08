"""Main Claude Code TUI application - aligned with TypeScript App.tsx"""

from textual.app import App

from claude_code.core.query_engine import QueryEngine
from claude_code.ui.styles import TUI_CSS
from claude_code.ui.screens import REPLScreen


class ClaudeCodeApp(App):
    """Main Claude Code application - aligned with TypeScript App.tsx"""

    CSS = TUI_CSS
    BINDINGS = []

    SCREENS = {"repl": REPLScreen}

    def __init__(
        self, query_engine: QueryEngine, model_name: str = "claude-sonnet-4-6", **kwargs
    ):
        super().__init__(**kwargs)
        self.query_engine = query_engine
        self.model_name = model_name

    async def on_mount(self) -> None:
        """Initialize and push the REPL screen on mount"""
        # Initialize the query engine (creates HTTP client)
        await self.query_engine.initialize()
        await self.push_screen(REPLScreen(self.query_engine, self.model_name))

    async def on_unmount(self) -> None:
        """Clean up resources on exit"""
        await self.query_engine.close()
