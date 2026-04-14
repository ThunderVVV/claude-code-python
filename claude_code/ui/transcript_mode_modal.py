"""Transient modal shown while the UI is rebuilding large transcript sections."""

from textual.app import ComposeResult
from textual.containers import Center, VerticalGroup
from textual.screen import ModalScreen
from textual.widgets import Static


class ProgressStatusModal(ModalScreen[None]):
    """Small blocking modal used to hide transcript relayout flicker."""

    CSS = """
    ProgressStatusModal {
        align: center middle;

        #container {
            width: 32;
            height: auto;
            padding: 1 3;
            background: $surface;
            border: none;
        }

        #status {
            width: 100%;
            content-align: center middle;
        }
    }
    """

    def __init__(self, status_text: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.status_text = status_text

    def compose(self) -> ComposeResult:
        with Center():
            with VerticalGroup(id="container"):
                yield Static(self.status_text, id="status", markup=False)
