from __future__ import annotations

import asyncio

import cc_code.core.snapshot as snapshot_module
from cc_code.core.query_engine import QueryEngine
from cc_code.core.snapshot import build_snapshot_project_id
from cc_code.services.openai_client import OpenAIClientConfig


def _build_engine(working_directory: str, session_id: str) -> QueryEngine:
    config = OpenAIClientConfig(
        api_url="http://localhost",
        api_key="test",
        model_name="test-model",
        model_id="test-model",
    )
    return QueryEngine(
        client_config=config,
        tool_registry=object(),
        working_directory=working_directory,
        session_id=session_id,
    )


def test_build_snapshot_project_id_is_session_scoped(tmp_path):
    cwd = str(tmp_path)
    sid1 = "session-1"
    sid2 = "session-2"

    id1 = build_snapshot_project_id(cwd, sid1)
    id2 = build_snapshot_project_id(cwd, sid2)
    legacy = build_snapshot_project_id(cwd, None)

    assert id1 != id2
    assert id1 != legacy
    assert id2 != legacy


def test_query_engine_initializes_snapshot_with_session_scoped_project_id(
    monkeypatch, tmp_path
):
    captured: dict[str, str] = {}

    class _FakeSnapshotManager:
        def __init__(self, working_directory: str, project_id: str | None = None):
            captured["working_directory"] = working_directory
            captured["project_id"] = project_id or ""

    monkeypatch.setattr(snapshot_module, "SnapshotManager", _FakeSnapshotManager)

    session_id = "session-unique-123"
    engine = _build_engine(str(tmp_path), session_id)

    async def _run() -> None:
        await engine.initialize()
        await engine.close()

    asyncio.run(_run())

    assert captured["working_directory"] == str(tmp_path)
    assert captured["project_id"] == build_snapshot_project_id(str(tmp_path), session_id)
