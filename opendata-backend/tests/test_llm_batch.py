"""Unit test dell'helper Batches (`llm.batch.batch_complete`) con client mockato.

La vera Batches API non è raggiungibile nei test: mockiamo l'interfaccia async
(`messages.batches.create/retrieve/results`) e verifichiamo il contratto —
mapping custom_id→testo, skip dei risultati non riusciti, gating claude, fail-safe.
"""

from __future__ import annotations

import pytest

from opendata_backend.config import Settings
from opendata_backend.llm.batch import BatchPrompt, batch_complete


def _settings(provider: str = "claude", key: str | None = "sk-test") -> Settings:
    return Settings(llm_provider=provider, anthropic_api_key=key)


class _Block:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _Msg:
    def __init__(self, text: str) -> None:
        self.content = [_Block(text)]


class _Result:
    def __init__(self, custom_id: str, text: str | None, rtype: str = "succeeded") -> None:
        self.custom_id = custom_id
        self.result = type("R", (), {"type": rtype, "message": _Msg(text or "")})()


class _Batch:
    def __init__(self, status: str = "ended") -> None:
        self.id = "msgbatch_test"
        self.processing_status = status


class _AsyncResults:
    def __init__(self, results: list[_Result]) -> None:
        self._results = results

    def __aiter__(self):  # noqa: ANN204
        async def _gen():  # noqa: ANN202
            for r in self._results:
                yield r

        return _gen()


class _Batches:
    def __init__(self, results: list[_Result]) -> None:
        self._results = results
        self.created_requests: list[dict] | None = None

    async def create(self, *, requests):  # noqa: ANN001, ANN201
        self.created_requests = requests
        return _Batch("ended")

    async def retrieve(self, _id):  # noqa: ANN001, ANN201
        return _Batch("ended")

    async def results(self, _id):  # noqa: ANN001, ANN201
        return _AsyncResults(self._results)


class _FakeClient:
    def __init__(self, results: list[_Result]) -> None:
        self.messages = type("M", (), {"batches": _Batches(results)})()


@pytest.mark.asyncio
async def test_batch_complete_maps_custom_ids_to_text() -> None:
    client = _FakeClient([
        _Result("072021:idee", "JSON idee"),
        _Result("072006:idee", "JSON idee 2"),
    ])
    out = await batch_complete(
        _settings(),
        prompts=[BatchPrompt("072021:idee", "p1"), BatchPrompt("072006:idee", "p2")],
        system="ISTRUZIONI",
        client=client,
        poll_interval=0.0,
    )
    assert out == {"072021:idee": "JSON idee", "072006:idee": "JSON idee 2"}
    # system condiviso con cache_control + un messaggio utente per richiesta
    reqs = client.messages.batches.created_requests
    assert len(reqs) == 2
    assert reqs[0]["params"]["system"][0]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_batch_complete_skips_failed_results() -> None:
    client = _FakeClient([
        _Result("a:idee", "ok"),
        _Result("b:idee", None, rtype="errored"),
    ])
    out = await batch_complete(
        _settings(), prompts=[BatchPrompt("a:idee", "p"), BatchPrompt("b:idee", "p")],
        system="S", client=client, poll_interval=0.0,
    )
    assert out == {"a:idee": "ok"}  # la errored è saltata


@pytest.mark.asyncio
async def test_batch_complete_non_claude_returns_empty() -> None:
    # provider ollama → niente batch (Anthropic-specific), nessun client toccato
    out = await batch_complete(
        _settings(provider="ollama", key=None),
        prompts=[BatchPrompt("x", "p")], system="S",
    )
    assert out == {}


@pytest.mark.asyncio
async def test_batch_complete_failsafe_on_error() -> None:
    class _Boom:
        def __init__(self) -> None:
            self.messages = type("M", (), {"batches": self})()

        async def create(self, **_):  # noqa: ANN003, ANN201
            raise RuntimeError("API down")

    out = await batch_complete(
        _settings(), prompts=[BatchPrompt("x", "p")], system="S", client=_Boom(),
    )
    assert out == {}  # eccezione → {} (il chiamante ricade sul live)
