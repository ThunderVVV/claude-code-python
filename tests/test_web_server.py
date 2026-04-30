from __future__ import annotations

from fastapi.testclient import TestClient

from cc_code.core.snapshot import DiffSummary, RevertResult
from cc_code.core.messages import (
    Message,
    MessageCompleteEvent,
    SessionState,
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
    assert "/api/revert" in paths
    assert "/api/debug/{session_id}" in paths
    assert "/api/sessions" in paths
    assert "/api/workspace/browse" in paths
    assert "/health" in paths


def test_create_api_app_can_build_unprefixed_routes():
    app = create_api_app(api_prefix="")

    paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/chat" in paths
    assert "/interrupt" in paths
    assert "/debug/{session_id}" in paths
    assert "/sessions" in paths
    assert "/workspace/browse" in paths
    assert "/health" in paths
    assert "/api/chat" not in paths


def test_workspace_browser_lists_directories(tmp_path):
    child_a = tmp_path / "alpha"
    child_b = tmp_path / "beta"
    file_path = tmp_path / "notes.txt"
    child_a.mkdir()
    child_b.mkdir()
    file_path.write_text("ignore me", encoding="utf-8")

    app = create_api_app()
    client = TestClient(app)
    response = client.get("/api/workspace/browse", params={"path": str(tmp_path)})

    assert response.status_code == 200
    data = response.json()

    assert data["path"] == str(tmp_path)
    assert data["parent_path"] == str(tmp_path.parent)
    assert [item["name"] for item in data["directories"]] == ["alpha", "beta"]
    assert all("path" in item for item in data["directories"])


def test_workspace_browser_rejects_missing_directory(tmp_path):
    missing = tmp_path / "missing-dir"

    app = create_api_app()
    client = TestClient(app)
    response = client.get("/api/workspace/browse", params={"path": str(missing)})

    assert response.status_code == 404
    assert response.json()["detail"] == "Directory not found"


def test_chat_rejects_invalid_working_directory(tmp_path):
    missing = tmp_path / "missing-dir"

    app = create_api_app()
    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={
            "user_text": "hello",
            "working_directory": str(missing),
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Directory not found"


def test_revert_restores_persisted_session_engine(tmp_path, monkeypatch):
    app = create_api_app()
    session_manager = app.state.session_manager
    persisted = SessionState(
        session_id="session-1",
        working_directory=str(tmp_path),
        messages=[Message.user_message("hello")],
    )

    class _FakeEngine:
        async def revert(self, target_message_id=None, target_part_id=None):
            assert target_message_id == "msg-1"
            assert target_part_id is None
            return RevertResult(
                success=True,
                message="reverted",
                summary=DiffSummary(additions=1, deletions=2, files=1),
            )

    fake_engine = _FakeEngine()

    monkeypatch.setattr(
        session_manager._session_store,
        "load_session",
        lambda session_id: persisted if session_id == "session-1" else None,
    )
    monkeypatch.setattr(session_manager, "get_engine", lambda session_id: None)

    async def _fake_get_or_create_engine(session_id, working_directory="", model_id=None):
        assert session_id == "session-1"
        assert working_directory == str(tmp_path)
        assert model_id is None
        return fake_engine

    monkeypatch.setattr(
        session_manager,
        "get_or_create_engine",
        _fake_get_or_create_engine,
    )

    client = TestClient(app)
    response = client.post(
        "/api/revert",
        json={
            "session_id": "session-1",
            "target_message_id": "msg-1",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "reverted",
        "summary": {
            "additions": 1,
            "deletions": 2,
            "files": 1,
        },
    }
