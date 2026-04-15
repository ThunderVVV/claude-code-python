from __future__ import annotations

import asyncio

from cc_code.client.http_client import CCCodeHttpClient
from cc_code.core.messages import TextEvent


class _FakeStreamResponse:
    def __init__(self, chunks: list[bytes]):
        self._chunks = chunks

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def raise_for_status(self) -> None:
        return None

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class _FakeAsyncClient:
    def __init__(self, chunks: list[bytes]):
        self._chunks = chunks

    def stream(self, *args, **kwargs):
        return _FakeStreamResponse(self._chunks)


def test_stream_compact_skips_session_id_event():
    payload = (
        'data: {"type":"session_id","session_id":"sess-1"}\n\n'
        'data: {"type":"text","text":"summary"}\n\n'
    ).encode("utf-8")

    client = CCCodeHttpClient()
    client._client = _FakeAsyncClient([payload])

    async def _collect_events():
        events = []
        async for event in client.stream_compact(session_id="sess-1"):
            events.append(event)
        return events

    events = asyncio.run(_collect_events())

    assert len(events) == 1
    assert isinstance(events[0], TextEvent)
    assert events[0].text == "summary"
