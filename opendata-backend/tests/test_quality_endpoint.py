"""Test dell'endpoint /quality/profile (Data Quality Lab)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from opendata_backend.auth import ClerkUser
from opendata_backend.auth import dependencies as auth_dep
from opendata_backend.config import Settings, get_settings
from opendata_backend.routers import quality


def _client() -> TestClient:
    user = ClerkUser(subject="u_quality", email=None, claims={})

    async def _user() -> ClerkUser:
        return user

    app = FastAPI()
    app.include_router(quality.router)
    app.dependency_overrides[get_settings] = lambda: Settings(auth_enabled=False)  # type: ignore[call-arg]
    app.dependency_overrides[auth_dep.require_user] = _user
    return TestClient(app)


def test_profile_content_ok() -> None:
    client = _client()
    res = client.post(
        "/quality/profile",
        json={"content": "comune,popolazione\nGioia del Colle,27889\nBari,320475\n"},
    )
    assert res.status_code == 200
    rep = res.json()
    assert rep["format"] == "CSV"
    assert rep["colonne"] == 2
    assert rep["righe"] == 2
    assert "punteggio" in rep
    assert any(c["nome"] == "popolazione" and c["tipo"] == "intero" for c in rep["colonne_profilo"])


def test_profile_requires_input() -> None:
    res = _client().post("/quality/profile", json={})
    assert res.status_code == 400


def test_profile_unsupported_format() -> None:
    res = _client().post("/quality/profile", json={"content": "x", "format": "xlsx"})
    assert res.status_code == 415


def test_fix_content_ok() -> None:
    client = _client()
    res = client.post("/quality/fix", json={"content": "a;b\n1.234,5;01/02/2023\n"})
    assert res.status_code == 200
    rep = res.json()
    assert "content" in rep and "changes" in rep
    assert "1234.5" in rep["content"]      # decimale IT → punto
    assert "2023-02-01" in rep["content"]  # data gg/mm → ISO


def test_fix_requires_input() -> None:
    assert _client().post("/quality/fix", json={}).status_code == 400
