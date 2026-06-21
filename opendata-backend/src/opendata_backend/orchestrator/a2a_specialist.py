"""A2A-backed specialist that participates in the orchestrator fan-out.

This is the "Import" side of the A2A integration (Phase 3). Given a URL to
a remote A2A-compliant agent, we present it to the orchestrator with the
same surface as `agent_framework.Agent`:

  - `name: str`
  - `await agent.run(query) -> AgentResponse` where `.text` is set
  - async context manager for setup/teardown

The orchestrator's `_worker` in factory.py uses exactly that interface, so
no changes are required there — the new specialist plugs in as a peer.

Round-trip demo: point `A2A_SPECIALIST_URL` at our own A2A endpoint
(http://localhost:18000) and the orchestrator will fan out to itself via
A2A, validating the full export+import loop.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, SendMessageRequest, TextPart

log = logging.getLogger("orchestrator.a2a_specialist")


@dataclass
class _RemoteResponse:
    """Minimal AgentResponse-shape consumed by `orchestrator.synth`."""

    text: str
    messages: list[Any] = field(default_factory=list)


class A2ARemoteAgent:
    """Pretend-to-be an `agent_framework.Agent` that delegates to a remote A2A peer."""

    def __init__(
        self,
        name: str,
        url: str,
        *,
        bearer: str | None = None,
        skill: str = "search_open_data",
    ) -> None:
        self.name = name
        self._url = url.rstrip("/")
        self._bearer = bearer
        self._skill = skill
        self._client = None  # populated in __aenter__
        self._http = None

    async def __aenter__(self) -> "A2ARemoteAgent":
        import httpx

        headers: dict[str, str] = {}
        if self._bearer:
            headers["Authorization"] = f"Bearer {self._bearer}"
        self._http = httpx.AsyncClient(timeout=60.0, headers=headers)

        try:
            resolver = A2ACardResolver(self._http, self._url)
            card = await resolver.get_agent_card()
        except Exception as exc:
            await self._http.aclose()
            self._http = None
            raise RuntimeError(f"A2A AgentCard resolution failed for {self._url}: {exc}") from exc

        factory = ClientFactory(ClientConfig(httpx_client=self._http))
        self._client = factory.create(card)
        log.info("A2ARemoteAgent connected | name=%s url=%s skills=%d",
                 self.name, self._url, len(card.skills))
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._http is not None:
            try:
                await self._http.aclose()
            finally:
                self._http = None
                self._client = None

    async def run(self, query: str) -> _RemoteResponse:
        """Send `query` to the remote agent and aggregate the streaming reply."""
        if self._client is None:
            raise RuntimeError("A2ARemoteAgent must be used as an async context manager")

        message = Message(
            role=Role.USER,
            parts=[Part(root=TextPart(text=query))],
            metadata={"skill": self._skill},
        )
        request = SendMessageRequest(message=message)

        # Aggregate every text artifact emitted by the remote into a single reply.
        # Different remotes may stream multiple updates; we want only the final
        # artifact-bearing chunk(s) in the returned `.text`.
        collected: list[str] = []
        try:
            async for event in self._client.send_message(request):
                text = _extract_text(event)
                if text:
                    collected.append(text)
        except Exception as exc:
            log.exception("A2ARemoteAgent.run failed | name=%s", self.name)
            raise RuntimeError(f"A2A remote {self.name} failed: {exc}") from exc

        joined = "\n".join(collected).strip()
        return _RemoteResponse(text=joined or "(remote A2A returned no text)")


def _extract_text(event: Any) -> str | None:
    """Best-effort: pull text out of whatever StreamResponse shape we got.

    The A2A protocol returns a discriminated union (Task, Message, status
    updates, artifact updates). We're conservative — just look for `.parts`
    with `.text` recursively, and skip everything else.
    """
    parts = getattr(event, "parts", None) or _nested_parts(event)
    if not parts:
        return None
    chunks: list[str] = []
    for p in parts:
        root = getattr(p, "root", p)
        text = getattr(root, "text", None)
        if isinstance(text, str) and text.strip():
            chunks.append(text)
    return "\n".join(chunks) if chunks else None


def _nested_parts(event: Any) -> list[Any]:
    """Reach into common A2A wrappers (artifact updates, message events)."""
    for attr in ("artifact", "message", "result"):
        inner = getattr(event, attr, None)
        if inner is not None:
            parts = getattr(inner, "parts", None)
            if parts:
                return list(parts)
    return []
