"""Giudizio semantico via Claude Haiku: comprensibilità della descrizione (0–1).

È l'UNICO uso dell'LLM nel motore di maturità (tutto il resto è deterministico).
Fail-safe: senza ANTHROPIC_API_KEY, senza dataset, o su qualsiasi errore ritorna
{} → lo scoring procede con `semantic_clarity=None` (neutro). Così i test non
chiamano mai la rete.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

log = logging.getLogger("maturity-mcp.semantic")

DEFAULT_MODEL = os.getenv("CLAUDE_CLASSIFY_MODEL", "claude-haiku-4-5-20251001")
_MAX_ITEMS = 40

_PROMPT = (
    "Per ogni dataset valuta da 0 a 1 quanto la descrizione è chiara e comprensibile "
    "per un cittadino (0 = assente/incomprensibile, 1 = chiara e informativa). "
    "Rispondi SOLO con un oggetto JSON {id: punteggio}, nessun altro testo.\n\n"
)


async def semantic_clarity_map(
    items: list[dict[str, str]], *, model: str | None = None
) -> dict[str, float]:
    """`items`: [{"id","title","description"}] → {id: clarity ∈ [0,1]}. {} se non disponibile."""
    if not items or not os.getenv("ANTHROPIC_API_KEY"):
        return {}
    items = items[:_MAX_ITEMS]
    try:
        import anthropic

        client = anthropic.AsyncAnthropic()
        payload = [
            {"id": it["id"], "title": it.get("title", ""), "description": it.get("description", "")}
            for it in items
        ]
        msg = await client.messages.create(
            model=model or DEFAULT_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": _PROMPT + json.dumps(payload, ensure_ascii=False)}],
        )
        text = "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")
        data: Any = json.loads(text)
        if not isinstance(data, dict):
            return {}
        out: dict[str, float] = {}
        for key, val in data.items():
            try:
                out[str(key)] = max(0.0, min(1.0, float(val)))
            except (TypeError, ValueError):
                continue
        return out
    except Exception as exc:  # noqa: BLE001 — semantico best-effort, non blocca lo scoring
        log.warning("semantic clarity non disponibile: %s", exc)
        return {}
