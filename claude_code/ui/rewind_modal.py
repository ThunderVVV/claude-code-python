"""Rewind modal - allows selecting a user message to rewind to."""

from typing import TYPE_CHECKING, List, Optional, Tuple

from textual import on
from textual.app import ComposeResult
from textual.containers import Center, HorizontalGroup, VerticalGroup
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Markdown, Static

from claude_code.core.messages import Message, MessageRole
from claude_code.utils.logging_config import tui_log

if TYPE_CHECKING:
    from claude_code.client.http_client import ClaudeCodeHttpClient

# Module load time log
tui_log("rewind_modal.py MODULE LOADED")

HELP = """\
# Rewind
"""


class RewindModal(ModalScreen[Optional[Tuple[str, int]]]):
    """Dialog to select a user message to rewind to.

    Returns a tuple of (message_id, message_index) when a message is selected,
    or None if cancelled.
    """

    CSS = """
    RewindModal {
        align: center middle;

        #container {
            margin: 2 4 1 4;
            padding: 1;
            max-width: 100;
            height: auto;
            border: none;
            background: $surface;

            Markdown {
                MarkdownH1 {
                    margin: 1 0;
                }
            }

            #table-container {
                height: auto;
                padding: 0;
                DataTable {
                    width: 1fr;
                    height: 12;
                    scrollbar-background: transparent;
                    scrollbar-background-hover: transparent;
                    scrollbar-background-active: transparent;
                    scrollbar-color: transparent;
                    scrollbar-color-hover: transparent;
                    scrollbar-color-active: transparent;
                    scrollbar-corner-color: transparent;
                }
            }
            #buttons {
                margin-top: 1;
                align: right top;
            }

            #buttons Button {
                margin-left: 1;
                min-width: 0;
                width: auto;
                padding: 0 1;
            }

            #revert-info {
                padding: 0 1;
                height: auto;
                color: $text-muted;
            }
        }
    }
    """

    BINDINGS = [("escape", "dismiss", "Dismiss")]

    def __init__(
        self,
        messages: List[Message],
        client: "ClaudeCodeHttpClient",
        session_id: str,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.messages = messages
        self.client = client
        self.session_id = session_id
        self._user_messages: List[Tuple[int, Message]] = []

    def compose(self) -> ComposeResult:
        with VerticalGroup(id="container"):
            yield Markdown(HELP)
            with Center(id="table-container"):
                yield DataTable(id="messages", cursor_type="row")
            yield Static("", id="revert-info")
            with HorizontalGroup(id="buttons"):
                yield Button(
                    "Rewind",
                    id="rewind",
                    variant="warning",
                    disabled=True,
                    compact=True,
                )
                yield Button("Cancel", id="cancel", compact=True)

    @staticmethod
    def truncate_text(text: str, max_length: int = 60) -> str:
        """Truncate text to max_length characters."""
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    async def on_mount(self) -> None:
        table = self.query_one("#messages", DataTable)
        table.add_columns("#", "Message")

        self._user_messages = []
        for idx, message in enumerate(self.messages):
            if message.type == MessageRole.USER:
                self._user_messages.append((idx, message))

        for msg_idx, (original_idx, message) in enumerate(self._user_messages):
            text = message.get_text()
            original_text = getattr(message, "original_text", text) or text
            truncated = self.truncate_text(original_text.replace("\n", " "))

            table.add_row(
                str(msg_idx + 1),
                truncated,
                key=str(original_idx),
            )

        info = self.query_one("#revert-info", Static)
        if not self._user_messages:
            info.update("No user messages found to rewind to.")
        else:
            info.update(
                f"Found {len(self._user_messages)} user message(s). "
                "Select one to rewind to that point."
            )

    async def dismiss_with_message(self, original_idx: str) -> None:
        """Dismiss modal with the selected message index."""
        tui_log(f"dismiss_with_message: original_idx={original_idx!r}")
        try:
            idx = int(original_idx)
            message = self.messages[idx]
            tui_log(f"dismiss_with_message: uuid={message.uuid!r}, idx={idx}")
            self.dismiss((message.uuid, idx))
        except (ValueError, IndexError) as e:
            tui_log(f"dismiss_with_message failed: {e}")
            self.dismiss()

    @on(Button.Pressed, "#rewind")
    async def on_rewind_button(self) -> None:
        tui_log("on_rewind_button called")
        table = self.query_one("#messages", DataTable)
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        tui_log(f"on_rewind_button: row_key.value={row_key.value if row_key else None}")
        if row_key is None or row_key.value is None:
            return
        await self.dismiss_with_message(row_key.value)

    @on(Button.Pressed, "#cancel")
    def on_cancel_button(self) -> None:
        tui_log("on_cancel_button called")
        self.dismiss()

    @on(DataTable.RowHighlighted)
    def on_data_table_row_highlighted(self) -> None:
        self.query_one("#rewind", Button).disabled = False

    @on(DataTable.RowSelected)
    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        tui_log(
            f"on_data_table_row_selected: event.row_key.value={event.row_key.value if event.row_key else None}"
        )
        if event.row_key is None or event.row_key.value is None:
            return
        await self.dismiss_with_message(event.row_key.value)
