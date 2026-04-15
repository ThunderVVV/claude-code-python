from __future__ import annotations

from cc_code.core.messages import (
    Message,
    MessageCompleteEvent,
    message_to_api_dict,
    event_to_api_dict,
)
from cc_code.core.file_expansion import build_visible_file_expansions
from cc_code.api.server import create_app as create_api_app


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

    result = message_to_api_dict(message, working_directory=str(tmp_path))

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
    result = event_to_api_dict(event, working_directory=str(tmp_path))

    assert result["type"] == "message_complete"
    assert result["message"]["role"] == "user"
    assert result["message"]["original_text"] == "@example.py summarize"
    assert result["message"]["file_expansions"][0]["display_path"] == "example.py"


def test_create_api_app_uses_prefixed_routes_by_default():
    app = create_api_app()

    paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/api/chat" in paths
    assert "/api/interrupt" in paths
    assert "/api/debug/{session_id}" in paths
    assert "/api/sessions" in paths
    assert "/health" in paths


def test_create_api_app_can_build_unprefixed_routes():
    app = create_api_app(api_prefix="")

    paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/chat" in paths
    assert "/interrupt" in paths
    assert "/debug/{session_id}" in paths
    assert "/sessions" in paths
    assert "/health" in paths
    assert "/api/chat" not in paths
