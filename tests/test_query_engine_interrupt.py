from __future__ import annotations

import asyncio

from cc_code.core.query_engine import QueryEngine
from cc_code.core.tools import ToolRegistry
from cc_code.services.openai_client import OpenAIClientConfig


def _build_engine(working_directory: str) -> QueryEngine:
    return QueryEngine(
        client_config=OpenAIClientConfig(
            api_url="http://localhost:1",
            api_key="test",
            model_name="test-model",
        ),
        tool_registry=ToolRegistry(),
        working_directory=working_directory,
    )


async def _run_interrupt_returns_before_query_settles_test(tmp_path) -> None:
    engine = _build_engine(str(tmp_path))
    engine._is_initialized = True

    started = asyncio.Event()
    cancelled = asyncio.Event()
    release = asyncio.Event()

    async def fake_query_loop(_run_control):
        started.set()
        try:
            while True:
                await asyncio.sleep(1)
                if False:
                    yield None
        except asyncio.CancelledError:
            cancelled.set()
            await release.wait()
            raise

    engine._query_loop = fake_query_loop

    async def consume() -> None:
        async for _ in engine.submit_message("continue"):
            pass

    query_task = asyncio.create_task(consume())
    await asyncio.wait_for(started.wait(), timeout=0.5)

    assert await engine.interrupt("user_interrupt") is True
    await asyncio.wait_for(cancelled.wait(), timeout=0.5)

    assert query_task.done() is False
    assert engine.get_interrupt_reason() == "user_interrupt"

    release.set()
    await asyncio.wait_for(query_task, timeout=0.5)

    assert engine.get_interrupt_reason() is None
    assert engine._active_task is None


async def _run_interrupt_state_isolated_per_submit_test(tmp_path) -> None:
    engine = _build_engine(str(tmp_path))
    engine._is_initialized = True

    loop_calls: list[str] = []
    first_started = asyncio.Event()
    second_started = asyncio.Event()

    async def fake_query_loop(_run_control):
        loop_calls.append("ran")
        if len(loop_calls) == 1:
            first_started.set()
            try:
                while True:
                    await asyncio.sleep(1)
                    if False:
                        yield None
            except asyncio.CancelledError:
                raise

        second_started.set()
        if False:
            yield None

    engine._query_loop = fake_query_loop

    async def consume(prompt: str) -> None:
        async for _ in engine.submit_message(prompt):
            pass

    first_task = asyncio.create_task(consume("first"))
    await asyncio.wait_for(first_started.wait(), timeout=0.5)
    assert await engine.interrupt("user_interrupt") is True
    await asyncio.wait_for(first_task, timeout=0.5)

    second_task = asyncio.create_task(consume("second"))
    await asyncio.wait_for(second_started.wait(), timeout=0.5)
    await asyncio.wait_for(second_task, timeout=0.5)

    assert loop_calls == ["ran", "ran"]
    assert engine.get_interrupt_reason() is None


def test_interrupt_returns_before_query_settles(tmp_path) -> None:
    asyncio.run(_run_interrupt_returns_before_query_settles_test(tmp_path))


def test_interrupt_state_isolated_per_submit(tmp_path) -> None:
    asyncio.run(_run_interrupt_state_isolated_per_submit_test(tmp_path))
