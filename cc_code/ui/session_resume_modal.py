"""Session resume modal - allows selecting and switching between sessions."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Center, HorizontalGroup, VerticalGroup
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Markdown

from cc_code.core.session_store import SessionSummary

if TYPE_CHECKING:
    from cc_code.client.http_client import CCCodeHttpClient

HELP = """\
# Session Resume
"""


class SessionResumeModal(ModalScreen[Optional[SessionSummary]]):
    """Dialog to select a session to resume."""

    CSS = """
    SessionResumeModal {
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
                background: $surface;
                scrollbar-corner-color: $surface;
                DataTable {
                    width: 1fr;
                    height: 12;
                    scrollbar-background: $surface;
                    scrollbar-background-hover: $surface;
                    scrollbar-background-active: $surface;
                    scrollbar-color: $surface;
                    scrollbar-color-hover: $surface;
                    scrollbar-color-active: $surface;
                    background: $surface;
                    scrollbar-corner-color: $surface;
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
        }
    }
    """

    BINDINGS = [("escape", "dismiss", "Dismiss")]

    def __init__(
        self,
        client: "CCCodeHttpClient",
        current_session_id: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.client = client
        self.current_session_id = current_session_id
        self._sessions: list[SessionSummary] = []

    def compose(self) -> ComposeResult:
        with VerticalGroup(id="container"):
            yield Markdown(HELP)
            with Center(id="table-container"):
                yield DataTable(id="sessions", cursor_type="row")
            with HorizontalGroup(id="buttons"):
                yield Button(
                    "Resume",
                    id="resume",
                    variant="primary",
                    disabled=True,
                    compact=True,
                )
                yield Button("Cancel", id="cancel", compact=True)

    @staticmethod
    def friendly_time_ago(iso_timestamp: str) -> str:
        """
        Convert ISO timestamp to friendly time description.

        Args:
            iso_timestamp: ISO format timestamp string (e.g., '2024-01-30T15:30:00')

        Returns:
            - "just now" if < 1 minute ago
            - "X minute(s) ago" if < 1 hour ago
            - "X hour(s) ago" if < 24 hours ago
            - Local datetime string if >= 24 hours ago
        """
        try:
            past_dt = datetime.fromisoformat(iso_timestamp)
        except Exception:
            return iso_timestamp

        # Get current time in appropriate timezone
        if past_dt.tzinfo is not None:
            # Timezone-aware: use UTC for comparison
            now = datetime.now(timezone.utc)
        else:
            # Naive datetime: use naive now
            now = datetime.now()

        # Calculate time difference
        diff = now - past_dt
        total_seconds = diff.total_seconds()

        # Less than 1 minute
        if total_seconds < 60:
            return "just now"

        # Less than 1 hour (3600 seconds)
        if total_seconds < 3600:
            minutes = int(total_seconds // 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"

        # Less than 24 hours (86400 seconds)
        if total_seconds < 86400:
            hours = int(total_seconds // 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"

        # 24 hours or more - return as local time
        if past_dt.tzinfo is not None:
            local_dt = past_dt.astimezone()  # Convert to local timezone
        else:
            local_dt = past_dt  # Already naive, assume local

        return local_dt.strftime("%Y-%m-%d %H:%M")

    async def on_mount(self) -> None:
        table = self.query_one("#sessions", DataTable)
        table.add_columns("Updated", "Session", "Path")

        self._sessions = await self.client.list_sessions()

        for session in self._sessions:
            is_current = session.session_id == self.current_session_id
            session_display = f"{'→ ' if is_current else '  '}{session.title}"

            table.add_row(
                self.friendly_time_ago(session.updated_at),
                session_display,
                session.working_directory,
                key=session.session_id,
            )

    async def dismiss_with_session(self, session_id: str) -> None:
        """Dismiss modal with the selected session."""
        for session in self._sessions:
            if session.session_id == session_id:
                self.dismiss(session)
                return
        self.dismiss()

    @on(Button.Pressed, "#resume")
    async def on_resume_button(self) -> None:
        table = self.query_one("#sessions", DataTable)
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        if row_key is None or row_key.value is None:
            return
        await self.dismiss_with_session(row_key.value)

    @on(Button.Pressed, "#cancel")
    def on_cancel_button(self) -> None:
        self.dismiss()

    @on(DataTable.RowHighlighted)
    def on_data_table_row_highlighted(self) -> None:
        self.query_one("#resume", Button).disabled = False

    @on(DataTable.RowSelected)
    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key is None or event.row_key.value is None:
            return
        await self.dismiss_with_session(event.row_key.value)
