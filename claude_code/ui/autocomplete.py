"""Autocomplete functionality for slash commands and @ mentions.

Implements:
- Slash command autocomplete (triggered when / is the first character)
- @ mention autocomplete for files and web search
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from textual.containers import VerticalGroup
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Label

from claude_code.utils.logging_config import tui_log


class AutocompleteMode(Enum):
    """Autocomplete mode."""

    SLASH = "slash"
    AT = "at"


@dataclass
class Command:
    """Represents a slash command."""

    id: str
    trigger: str
    title: str
    description: Optional[str] = None
    keybind: Optional[str] = None

    def matches(self, query: str) -> bool:
        """Check if command matches query (fuzzy match)."""
        query_lower = query.lower()
        trigger_lower = self.trigger.lower()

        if not query:
            return True

        if trigger_lower.startswith(query_lower):
            return True

        return fuzzy_match(query_lower, trigger_lower)


@dataclass
class AtOption:
    """Represents an @ mention option."""

    type: str  # "file", "web", "directory"
    display: str
    path: Optional[str] = None
    recent: bool = False

    def matches(self, query: str) -> bool:
        """Check if option matches query."""
        query_lower = query.lower()
        display_lower = self.display.lower()

        if not query:
            return True

        if display_lower.startswith(query_lower):
            return True

        return fuzzy_match(query_lower, display_lower)


def fuzzy_match(query: str, text: str) -> bool:
    """Simple fuzzy match - checks if all query chars appear in order in text."""
    query_idx = 0
    for char in text:
        if query_idx < len(query) and char == query[query_idx]:
            query_idx += 1
    return query_idx == len(query)


class CommandRegistry:
    """Registry for slash commands."""

    _instance: Optional["CommandRegistry"] = None

    def __init__(self):
        self._commands: dict[str, Command] = {}
        self._register_default_commands()

    @classmethod
    def get_instance(cls) -> "CommandRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _register_default_commands(self) -> None:
        """Register default commands."""
        default_commands = [
            Command(
                id="exit",
                trigger="exit",
                title="/exit",
                description="Exit the application",
            ),
            Command(
                id="new",
                trigger="new",
                title="/new",
                description="Create a new session",
            ),
            Command(
                id="clear",
                trigger="clear",
                title="/clear",
                description="Clear and start a new session",
            ),
            Command(
                id="sessions",
                trigger="sessions",
                title="/sessions",
                description="View and switch between sessions",
            ),
            Command(
                id="rewind",
                trigger="rewind",
                title="/rewind",
                description="Rewind to a previous message",
            ),
            Command(
                id="help",
                trigger="help",
                title="/help",
                description="Show help information",
            ),
            Command(
                id="model",
                trigger="model",
                title="/model",
                description="Show or switch the active model",
            ),
            Command(
                id="compact",
                trigger="compact",
                title="/compact",
                description="Compress conversation history to save context",
            ),
            Command(
                id="summarize",
                trigger="summarize",
                title="/summarize",
                description="Alias for /compact - compress conversation history",
            ),
        ]
        for cmd in default_commands:
            self._commands[cmd.id] = cmd

    def register(self, command: Command) -> None:
        """Register a command."""
        self._commands[command.id] = command

    def unregister(self, command_id: str) -> None:
        """Unregister a command."""
        self._commands.pop(command_id, None)

    def get_commands(self) -> list[Command]:
        """Get all commands."""
        return list(self._commands.values())

    def filter_commands(self, query: str) -> list[Command]:
        """Filter commands by query."""
        results = []
        for cmd in self._commands.values():
            if cmd.matches(query):
                results.append(cmd)
        return results


class AutocompletePopup(VerticalGroup):
    """Popup widget for displaying autocomplete suggestions."""

    DEFAULT_CSS = """
    AutocompletePopup {
        height: auto;
        max-height: 6;
        width: 1fr;
        background: transparent;
        border: none;
        margin: 0;
        padding: 0;
        overflow-y: auto;
        display: none;
        scrollbar-background: transparent;
        scrollbar-background-hover: transparent;
        scrollbar-background-active: transparent;
        scrollbar-color: transparent;
        scrollbar-color-hover: transparent;
        scrollbar-color-active: transparent;
        scrollbar-corner-color: transparent;
    }
    
    AutocompletePopup.visible {
        display: block !important;
    }
    
    .autocomplete-empty {
        color: $text-secondary;
        padding: 0 1;
        height: 1;
    }

    .autocomplete-item {
        width: 1fr;
        height: 1;
        padding: 0 1;
        margin: 0;
        color: $foreground;
        background: transparent;
        text-align: left;
    }
    
    .autocomplete-item:hover {
        background: transparent;
    }
    
    .autocomplete-item.selected {
        color: $primary;
        text-style: bold;
    }
    """

    mode: reactive[Optional[AutocompleteMode]] = reactive(None)
    query: reactive[str] = reactive("")
    selected_index: reactive[int] = reactive(0)

    class Selected(Message):
        """Message sent when an item is selected."""

        def __init__(self, item: Command | AtOption, mode: AutocompleteMode) -> None:
            self.item = item
            self.mode = mode
            super().__init__()

    class Cancelled(Message):
        """Message sent when autocomplete is cancelled."""

        pass

    def __init__(
        self,
        working_directory: str = "",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._commands = CommandRegistry.get_instance()
        self._working_directory = working_directory
        self._filtered_commands: list[Command] = []
        self._filtered_options: list[AtOption] = []
        self._recent_files: list[str] = []

    def set_working_directory(self, cwd: str) -> None:
        """Set the working directory for file search."""
        self._working_directory = cwd

    def show_slash_commands(self, query: str = "") -> None:
        """Show slash command autocomplete."""
        tui_log(f"show_slash_commands: query={query!r}")
        self.mode = AutocompleteMode.SLASH
        self.query = query.lstrip("/")
        self.selected_index = 0
        self._filtered_commands = self._commands.filter_commands(self.query)
        tui_log(
            f"show_slash_commands: filtered {len(self._filtered_commands)} commands"
        )
        self._update_display()
        self.add_class("visible")

    def show_at_options(self, query: str = "") -> None:
        """Show @ mention autocomplete."""
        self.mode = AutocompleteMode.AT
        self.query = query.lstrip("@")
        self.selected_index = 0
        self._filtered_options = self._get_at_options()
        self._update_display()
        self.add_class("visible")

    def hide(self) -> None:
        """Hide the popup."""
        self.mode = None
        self.query = ""
        self.remove_class("visible")
        self._filtered_commands = []
        self._filtered_options = []

    def is_visible(self) -> bool:
        """Check if popup is visible."""
        return self.has_class("visible")

    def update_query(self, query: str) -> None:
        """Update the filter query."""
        if self.mode == AutocompleteMode.SLASH:
            self.query = query.lstrip("/")
            self._filtered_commands = self._commands.filter_commands(self.query)
        elif self.mode == AutocompleteMode.AT:
            self.query = query.lstrip("@")
            self._filtered_options = self._get_at_options()
        self.selected_index = 0
        self._update_display()

    def _get_at_options(self) -> list[AtOption]:
        """Get @ mention options based on query."""
        options: list[AtOption] = []

        options.append(
            AtOption(
                type="web",
                display=" @web",
            )
        )

        if not self.query or self.query.lower().startswith("w"):
            pass

        if self._working_directory:
            try:
                search_path = self._working_directory
                if self.query:
                    potential_path = os.path.join(self._working_directory, self.query)
                    if os.path.exists(potential_path):
                        search_path = potential_path

                if os.path.isdir(search_path):
                    entries = os.listdir(search_path)
                    for entry in sorted(entries)[:20]:
                        full_path = os.path.join(search_path, entry)
                        rel_path = os.path.relpath(full_path, self._working_directory)
                        if os.path.isdir(full_path):
                            options.append(
                                AtOption(
                                    type="directory",
                                    display=rel_path + "/",
                                    path=rel_path,
                                )
                            )
                        else:
                            options.append(
                                AtOption(
                                    type="file",
                                    display=rel_path,
                                    path=rel_path,
                                )
                            )
            except (OSError, PermissionError):
                pass

        if self.query:
            options = [opt for opt in options if opt.matches(self.query)]

        return options

    def _update_display(self) -> None:
        """Update the display with current items."""
        self.remove_children()

        if self.mode == AutocompleteMode.SLASH:
            items = self._filtered_commands
            if not items:
                self.mount(
                    Label(
                        "No commands found", classes="autocomplete-empty", markup=False
                    )
                )
                return

            for i, cmd in enumerate(items):
                item = Label(
                    f"{cmd.title}  {cmd.description or ''}",
                    markup=False,
                    name=str(i),
                    classes=f"autocomplete-item{' selected' if i == self.selected_index else ''}",
                )
                item.tooltip = cmd.description
                self.mount(item)

        elif self.mode == AutocompleteMode.AT:
            items = self._filtered_options
            if not items:
                self.mount(
                    Label("No files found", classes="autocomplete-empty", markup=False)
                )
                return

            for i, opt in enumerate(items):
                item = Label(
                    opt.display,
                    markup=False,
                    name=str(i),
                    classes=f"autocomplete-item{' selected' if i == self.selected_index else ''}",
                )
                self.mount(item)

        if self.is_visible():
            self.call_after_refresh(self._scroll_selected_into_view)

    def _scroll_selected_into_view(self) -> None:
        """Keep the selected autocomplete row visible while navigating."""
        children = list(self.children)
        if 0 <= self.selected_index < len(children):
            self.scroll_to_widget(
                children[self.selected_index], animate=False, immediate=True
            )

    def navigate_up(self) -> None:
        """Move selection up."""
        if self.mode == AutocompleteMode.SLASH:
            max_idx = len(self._filtered_commands) - 1
        else:
            max_idx = len(self._filtered_options) - 1

        if max_idx >= 0:
            self.selected_index = max(0, self.selected_index - 1)
            self._update_display()

    def navigate_down(self) -> None:
        """Move selection down."""
        if self.mode == AutocompleteMode.SLASH:
            max_idx = len(self._filtered_commands) - 1
        else:
            max_idx = len(self._filtered_options) - 1

        if max_idx >= 0:
            self.selected_index = min(max_idx, self.selected_index + 1)
            self._update_display()

    def select_current(self) -> Optional[Command | AtOption]:
        """Select the current item."""
        if self.mode == AutocompleteMode.SLASH:
            if self._filtered_commands and 0 <= self.selected_index < len(
                self._filtered_commands
            ):
                return self._filtered_commands[self.selected_index]
        elif self.mode == AutocompleteMode.AT:
            if self._filtered_options and 0 <= self.selected_index < len(
                self._filtered_options
            ):
                return self._filtered_options[self.selected_index]
        return None

    def get_item_count(self) -> int:
        """Get the number of items in the current list."""
        if self.mode == AutocompleteMode.SLASH:
            return len(self._filtered_commands)
        elif self.mode == AutocompleteMode.AT:
            return len(self._filtered_options)
        return 0


def detect_autocomplete_trigger(
    text: str, cursor_position: int
) -> tuple[Optional[AutocompleteMode], str]:
    """Detect if autocomplete should be triggered based on input.

    Returns:
        Tuple of (mode, query) where mode is None if no trigger detected.
    """
    if not text:
        return None, ""

    text_before_cursor = text[:cursor_position]

    slash_match = re.match(r"^/(\S*)$", text_before_cursor)
    if slash_match:
        return AutocompleteMode.SLASH, slash_match.group(1)

    at_match = re.search(r"@(\S*)$", text_before_cursor)
    if at_match:
        return AutocompleteMode.AT, at_match.group(1)

    return None, ""
