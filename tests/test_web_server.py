from __future__ import annotations

from claude_code.core.messages import Message, MessageCompleteEvent
from claude_code.web.server import (
    build_visible_file_expansions,
    event_to_dict,
    message_to_dict,
)


def test_build_visible_file_expansions_skips_web_marker(tmp_path):
    target = tmp_path / "example.py"
    target.write_text("print('hello')\n", encoding="utf-8")

    expansions = build_visible_file_expansions(
        "@example.py @web explain this file",
        str(tmp_path),
    )

    assert len(expansions) == 1
    assert expansions[0].display_path == "example.py"
    assert "print('hello')" in expansions[0].content


def test_message_to_dict_reconstructs_user_visible_metadata(tmp_path):
    target = tmp_path / "example.py"
    target.write_text("print('hello')\n", encoding="utf-8")

    message = Message.user_message(
        text="expanded prompt body",
        original_text="@example.py @web explain this file",
    )

    result = message_to_dict(message, working_directory=str(tmp_path))

    assert result["role"] == "user"
    assert result["original_text"] == "@example.py @web explain this file"
    assert result["web_enabled"] is True
    assert result["file_expansions"][0]["display_path"] == "example.py"
    assert "print('hello')" in result["file_expansions"][0]["content"]


def test_event_to_dict_includes_serialized_message_payload(tmp_path):
    target = tmp_path / "example.py"
    target.write_text("print('hello')\n", encoding="utf-8")

    message = Message.user_message(
        text="expanded prompt body",
        original_text="@example.py summarize",
    )

    event = MessageCompleteEvent(message=message)
    result = event_to_dict(event, working_directory=str(tmp_path))

    assert result["type"] == "message_complete"
    assert result["message"]["role"] == "user"
    assert result["message"]["original_text"] == "@example.py summarize"
    assert result["message"]["file_expansions"][0]["display_path"] == "example.py"
