from __future__ import annotations

from cc_code.ui.autocomplete import CommandRegistry


def test_command_registry_includes_debug_command():
    commands = CommandRegistry.get_instance().get_commands()
    titles = {command.title for command in commands}
    assert "/debug" in titles
