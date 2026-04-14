"""CC Code Python - AI programming assistant

A Python implementation of CC Code that helps with software engineering tasks.
Uses OpenAI-compatible APIs to connect to various LLM providers.
"""

__version__ = "0.1.0"
__author__ = "CC Code Python Port"

# Patch textual.widget.Widget.with_tooltip to disable tooltips globally
from textual.widget import Widget
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from textual.renders import Visual
    from typing_extensions import Self


def _patched_with_tooltip(self, tooltip: "Visual | str | None") -> "Self":
    """Chainable method to set a tooltip (disabled globally).

    Args:
        tooltip: New tooltip, or `None` to clear the tooltip.

    Returns:
        Self.
    """
    self.tooltip = None
    return self


Widget.with_tooltip = _patched_with_tooltip
