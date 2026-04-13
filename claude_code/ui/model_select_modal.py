"""Model selection modal."""

from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Center, HorizontalGroup, VerticalGroup
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Markdown

from claude_code.core.settings import AppSettings

HELP = """\
# Model
"""


class ModelSelectModal(ModalScreen[Optional[str]]):
    """Dialog to select a configured model."""

    CSS = """
    ModelSelectModal {
        align: center middle;

        #container {
            margin: 2 4 1 4;
            padding: 1;
            max-width: 110;
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
        }
    }
    """

    BINDINGS = [("escape", "dismiss", "Dismiss")]

    def __init__(
        self,
        settings: AppSettings,
        current_model_id: str = "",
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.settings = settings
        self.current_model_id = current_model_id

    def compose(self) -> ComposeResult:
        with VerticalGroup(id="container"):
            yield Markdown(HELP)
            with Center(id="table-container"):
                yield DataTable(id="models", cursor_type="row")
            with HorizontalGroup(id="buttons"):
                yield Button(
                    "Select",
                    id="select",
                    variant="primary",
                    disabled=True,
                    compact=True,
                )
                yield Button("Cancel", id="cancel", compact=True)

    async def on_mount(self) -> None:
        table = self.query_one("#models", DataTable)
        table.add_columns("Model ID", "Model Name", "Context", "API URL")

        for model_id, model in self.settings.models.items():
            model_label = f"{'→ ' if model_id == self.current_model_id else ''}{model_id}"
            table.add_row(
                model_label,
                model.model_name,
                str(model.context),
                model.api_url,
                key=model_id,
            )

    async def dismiss_with_model(self, model_id: str) -> None:
        self.dismiss(model_id)

    @on(Button.Pressed, "#select")
    async def on_select_button(self) -> None:
        table = self.query_one("#models", DataTable)
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        if row_key is None or row_key.value is None:
            return
        await self.dismiss_with_model(row_key.value)

    @on(Button.Pressed, "#cancel")
    def on_cancel_button(self) -> None:
        self.dismiss()

    @on(DataTable.RowHighlighted)
    def on_data_table_row_highlighted(self) -> None:
        self.query_one("#select", Button).disabled = False

    @on(DataTable.RowSelected)
    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key is None or event.row_key.value is None:
            return
        await self.dismiss_with_model(event.row_key.value)
