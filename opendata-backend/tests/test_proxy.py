"""Regression tests for /datasets/proxy.

The proxy used to forward the upstream `content-length` header. But httpx with
`stream=True` transparently decompresses gzip/br/deflate bodies, so the bytes we
re-stream are LONGER than the advertised (compressed) length — uvicorn then
raises "Response content longer than Content-Length" (500). We must NOT forward
`content-length`; StreamingResponse uses chunked transfer encoding instead.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from opendata_backend.auth import ClerkUser
from opendata_backend.auth import dependencies as auth_dep
from opendata_backend.config import Settings, get_settings
from opendata_backend.routers import datasets


class _FakeUpstream:
    """Simulates a gzip upstream: short advertised length, longer decoded body."""

    def __init__(self) -> None:
        self.status_code = 200
        # `content-length` is the COMPRESSED size; the decoded body below is longer.
        self.headers = {"content-type": "application/json", "content-length": "5"}

    async def aiter_bytes(self, chunk_size: int = 65536):
        yield b'{"type":"FeatureCollection",'
        yield b'"features":[]}'

    async def aclose(self) -> None:
        pass


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def build_request(self, method: str, url: str):
        return (method, url)

    async def send(self, req, stream: bool = False):
        return _FakeUpstream()

    async def aclose(self) -> None:
        pass


def test_content_length_not_forwarded() -> None:
    # The header that caused the 500 must be absent from the forward allow-list.
    assert "content-length" not in datasets._PROXY_FORWARD_HEADERS
    assert "content-encoding" not in datasets._PROXY_FORWARD_HEADERS


def test_proxy_streams_decompressed_body_without_content_length_mismatch(monkeypatch) -> None:
    user = ClerkUser(subject="user_proxy_test", email=None, claims={})

    async def _user() -> ClerkUser:
        return user

    # Skip the real DNS/SSRF check (network-free, focused on the streaming path).
    monkeypatch.setattr(datasets, "_validate_proxy_url", lambda u: u)
    monkeypatch.setattr(datasets.httpx, "AsyncClient", _FakeAsyncClient)

    settings = Settings(auth_enabled=False)  # type: ignore[call-arg]
    app = FastAPI()
    app.include_router(datasets.router)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[auth_dep.require_user] = _user

    client = TestClient(app)
    res = client.get("/datasets/proxy", params={"url": "https://example.com/x.geojson"})

    assert res.status_code == 200
    # The full decoded body is delivered — longer than the advertised length of 5.
    assert res.content == b'{"type":"FeatureCollection","features":[]}'
    assert len(res.content) > 5
