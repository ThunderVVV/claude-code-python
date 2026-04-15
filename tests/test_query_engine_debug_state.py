from __future__ import annotations

import json

from cc_code.core.query_engine import QueryEngine
from cc_code.services.openai_client import OpenAIClientConfig


def _build_engine(working_directory: str) -> QueryEngine:
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
        session_id="debug-session",
    )


def test_query_engine_debug_state_serializes_members(tmp_path):
    engine = _build_engine(str(tmp_path))

    debug_state = engine.get_debug_state()

    assert debug_state["class"] == "QueryEngine"
    assert debug_state["member_count"] > 0
    assert "_snapshot_manager" in debug_state["members"]
    assert "_cancel_event" in debug_state["members"]

    # Must be JSON-serializable for /api/debug responses.
    json.dumps(debug_state, ensure_ascii=False)
