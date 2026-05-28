"""Clerk webhook receiver — stub until svix signature verification lands (step 3)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

log = logging.getLogger("opendata-backend.webhooks")
router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/clerk")
async def clerk(request: Request) -> dict[str, str]:
    """Accept and log the payload only. Signature verification arrives in step 3."""
    try:
        body = await request.json()
    except Exception:
        body = None
    log.info(
        "clerk webhook received (verification not yet enforced): event=%r",
        (body or {}).get("type") if isinstance(body, dict) else None,
    )
    return {"status": "accepted-noop"}
