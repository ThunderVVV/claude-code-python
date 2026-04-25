from __future__ import annotations

from cc_code.core.tools import ToolRegistry


def test_default_tool_definitions_are_strict() -> None:
    registry = ToolRegistry.create_default()

    definitions = registry.get_tool_definitions()

    assert definitions
    for tool in definitions:
        assert tool["type"] == "function"
        assert tool["function"]["strict"] is True
        assert tool["function"]["parameters"]["additionalProperties"] is False
