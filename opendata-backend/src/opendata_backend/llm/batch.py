"""Anthropic Message Batches helper (−50%, async) per la pre-generazione offline.

Claude-only: la Batches API è specifica di Anthropic (agent_framework non la
espone). Usata dalla pre-generazione batch dei report territorio (opzione B): il
fan-out gira LIVE per ogni comune per costruire il bundle, poi i prompt tool-less
synth/idee/programma di TUTTI i comuni vengono sottomessi come UN solo batch — 50%
più economico, asincrono (va bene off-peak), col system prompt CONDIVISO cacheato
tra le richieste (lo sconto batch e il caching si sommano).

NON sul path live `/programma` (streaming/interattivo: l'async romperebbe il feed).

Fail-safe per design: ritorna {} quando il provider non è claude / manca la key, o
su qualunque errore — così il chiamante ricade sul path live per-comune.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from ..config import Settings, resolve_provider

log = logging.getLogger("opendata-backend.llm")


@dataclass
class BatchPrompt:
    """Una richiesta del batch: `custom_id` per ricucire il risultato al comune/fase
    (es. "072021:idee"), `user_prompt` il turno utente. Il system è condiviso."""

    custom_id: str
    user_prompt: str


async def batch_complete(
    settings: Settings,
    *,
    prompts: list[BatchPrompt],
    system: str,
    model: str | None = None,
    max_tokens: int = 8192,
    poll_interval: float = 30.0,
    timeout: float = 24 * 3600.0,
    client: Any | None = None,
) -> dict[str, str]:
    """Sottomette N prompt one-shot (system condiviso) come Message Batch; ritorna
    `{custom_id: testo}` per le richieste riuscite. `client` è iniettabile nei test.

    Claude-only e fail-safe: `{}` se il provider non è claude/manca la key, su
    timeout, o su qualunque eccezione (il chiamante ricade sul path live).
    """
    if resolve_provider(settings) != "claude" or not settings.anthropic_api_key:
        return {}
    if not prompts:
        return {}
    try:
        if client is None:
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        mdl = model or settings.programma_model or settings.claude_model
        # System condiviso + cache_control: nel batch lo stesso prefisso si ripete
        # su tutte le richieste → caching (lo sconto −50% del batch resta comunque).
        shared_system = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        batch = await client.messages.batches.create(
            requests=[
                {
                    "custom_id": p.custom_id,
                    "params": {
                        "model": mdl,
                        "max_tokens": max_tokens,
                        "system": shared_system,
                        "messages": [{"role": "user", "content": p.user_prompt}],
                    },
                }
                for p in prompts
            ]
        )
        log.info("batch_complete: sottomesso batch %s con %d richieste", batch.id, len(prompts))
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while getattr(batch, "processing_status", None) != "ended":
            if loop.time() > deadline:
                log.warning("batch_complete: timeout su batch %s", batch.id)
                return {}
            await asyncio.sleep(poll_interval)
            batch = await client.messages.batches.retrieve(batch.id)
        out: dict[str, str] = {}
        async for res in await client.messages.batches.results(batch.id):
            if getattr(res.result, "type", None) != "succeeded":
                log.warning("batch_complete: richiesta %s non riuscita (%s)",
                            res.custom_id, getattr(res.result, "type", "?"))
                continue
            msg = res.result.message
            text = "".join(
                b.text for b in msg.content if getattr(b, "type", None) == "text"
            ).strip()
            if text:
                out[res.custom_id] = text
        log.info("batch_complete: batch %s concluso, %d/%d risultati", batch.id, len(out), len(prompts))
        return out
    except Exception as exc:  # noqa: BLE001 — best-effort, il chiamante ricade sul live
        log.warning("batch_complete fallito: %s", exc)
        return {}
