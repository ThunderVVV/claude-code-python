"""UI widgets - Clawd and WelcomeWidget"""

from __future__ import annotations

import os

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalGroup
from textual.widgets import Label, Static

from claude_code.ui.constants import CLAUDE_ORANGE
from claude_code.ui.utils import sanitize_terminal_text


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

    DEFAULT_CSS = f"""
    WelcomeWidget {{
        width: 100%;
        height: auto;
        border: round {CLAUDE_ORANGE};
        padding: 0 1;
        margin: 0 1 1 1;
    }}

    WelcomeWidget .welcome-title {{
        color: {CLAUDE_ORANGE};
        text-style: bold;
    }}

    WelcomeWidget .welcome-version {{
        color: rgb(153,153,153);
    }}

    WelcomeWidget #left-panel {{
        width: 1fr;
        height: auto;
        align: center top;
        padding: 0 1;
    }}

    WelcomeWidget #right-panel {{
        width: 1fr;
        height: auto;
        min-height: 7;
        padding: 0 0 0 1;
        margin-left: 1;
        border-left: solid {CLAUDE_ORANGE};
    }}

    WelcomeWidget #left-panel {{
        min-height: 7;
    }}

    WelcomeWidget .welcome-horizontal {{
        width: 100%;
        height: auto;
    }}
    """

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
                    "Run /init to create a CLAUDE.md file with instructions for Claude",
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
