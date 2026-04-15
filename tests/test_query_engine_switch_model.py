from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from cc_code.core.messages import Message
from cc_code.core.query_engine import QueryEngine
from cc_code.core.tools import ToolRegistry
from cc_code.services.openai_client import OpenAIClientConfig


class _SessionStoreSpy:
    def __init__(self) -> None:
        self.save_calls = 0
        self.last_kwargs: dict[str, Any] = {}

    def save_snapshot(self, **kwargs: Any) -> Any:
        self.save_calls += 1
        self.last_kwargs = kwargs
        return SimpleNamespace(title="test", created_at="2026-01-01T00:00:00")


async def _run_switch_model_persists_session_test() -> None:
    first_config = OpenAIClientConfig(
        api_url="https://api.example.com/v1",
        api_key="test-key",
        model_name="model-a",
        model_id="model-a",
    )
    second_config = OpenAIClientConfig(
        api_url="https://api.example.com/v1",
        api_key="test-key",
        model_name="model-b",
        model_id="model-b",
    )
    session_store = _SessionStoreSpy()
    engine = QueryEngine(
        first_config,
        ToolRegistry(),
        session_store=session_store,
    )
    engine.state.add_message(Message.user_message("hello"))

    await engine.initialize()
    try:
        await engine.switch_model(second_config)
        assert engine.client_config.model_id == "model-b"
        assert session_store.save_calls == 1
        assert session_store.last_kwargs["model_id"] == "model-b"
    finally:
        await engine.close()


def test_switch_model_persists_session_without_missing_private_method() -> None:
    asyncio.run(_run_switch_model_persists_session_test())
