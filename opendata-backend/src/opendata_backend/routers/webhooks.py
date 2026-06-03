"""Clerk webhook receiver — verifies svix signature, logs + acks."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..config import Settings, get_settings
from ..db.repositories import users as users_repo
from ..db.session import get_session_factory
from ..shared.svix_verify import SvixSignatureError, verify_clerk_webhook

log = logging.getLogger("opendata-backend.webhooks")
router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/clerk")
async def clerk(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Validate svix signature, structured-log the event, return 200.

    Persistence into `opendata.users` arrives in step 4 — for now we ack
    every well-signed event so Clerk doesn't retry into our face.
    """
    body = await request.body()

    if not settings.clerk_webhook_secret:
        log.warning("clerk webhook hit but CLERK_WEBHOOK_SECRET is not set; rejecting")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="webhook receiver is not configured",
        )

    try:
        verify_clerk_webhook(
            payload=body,
            headers=request.headers,
            secret=settings.clerk_webhook_secret,
        )
    except SvixSignatureError as exc:
        log.info("clerk webhook signature rejected: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid svix signature",
        ) from exc

    try:
        event = json.loads(body or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid JSON body") from exc

    event_type = event.get("type")
    data = event.get("data") or {}
    clerk_user_id = data.get("id")
    email = _primary_email(data)
    log.info(
        "clerk webhook event=%s user_id=%s primary_email=%s",
        event_type, clerk_user_id, email,
    )

    # Best-effort persistence — if the DB isn't configured yet, just ack.
    if clerk_user_id and event_type in {"user.created", "user.updated", "user.deleted"}:
        try:
            factory = get_session_factory()
        except RuntimeError:
            log.warning("DB not configured; skipping persistence for %s", event_type)
            return {"status": "ok"}
        async with factory() as session:
            if event_type == "user.deleted":
                await users_repo.soft_delete(session, clerk_user_id=clerk_user_id)
            else:
                display_name = " ".join(
                    p for p in (data.get("first_name"), data.get("last_name")) if p
                ) or None
                await users_repo.get_or_create(
                    session,
                    clerk_user_id=clerk_user_id,
                    email=email,
                    display_name=display_name,
                )
            await session.commit()

    return {"status": "ok"}


def _primary_email(data: dict) -> str | None:
    primary_id = data.get("primary_email_address_id")
    for addr in data.get("email_addresses") or []:
        if addr.get("id") == primary_id:
            return addr.get("email_address")
    return None
