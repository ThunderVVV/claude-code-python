from __future__ import annotations

import asyncio

from cc_code.client.http_client import CCCodeHttpClient


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, payload: dict):
        self._payload = payload
        self.last_url: str = ""

    async def get(self, url: str):
        self.last_url = url
        return _FakeResponse(self._payload)


def test_get_debug_state_calls_debug_endpoint():
    payload = {"success": True, "debug": {"members": {}}}
    fake_client = _FakeAsyncClient(payload)

    client = CCCodeHttpClient()
    client._client = fake_client

    result = asyncio.run(client.get_debug_state("sess-1"))

    assert result == payload
    assert fake_client.last_url.endswith("/api/debug/sess-1")
