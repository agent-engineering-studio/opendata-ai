"""Endpoint /account/* — self-service profile (the user's own LLM key, BYOK).

The user stores a Claude API key or an Ollama Cloud key here; the key is
encrypted at rest (Fernet) and never returned in any response — GET reports
only whether one is configured and which provider/model.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import ClerkUser
from ..auth.dependencies import require_user
from ..byok import BYOKError, encrypt_key, validate_key
from ..config import Settings, get_settings
from ..db.repositories import users as users_repo
from ..db.session import get_db_session

log = logging.getLogger("opendata-backend.account")

router = APIRouter(prefix="/account", tags=["account"])


class LLMKeyStatus(BaseModel):
    configured: bool
    provider: str | None = None
    model: str | None = None


class LLMKeyIn(BaseModel):
    provider: str = Field(description="'claude' | 'ollama_cloud' | 'ollama_local'")
    api_key: str = Field(
        min_length=1,
        description="Chiave del provider, o URL del server per ollama_local (mai restituita)",
    )
    model: str | None = Field(default=None, description="Modello (per i provider Ollama)")


@router.get("/llm-key", response_model=LLMKeyStatus)
async def get_llm_key(
    user: ClerkUser = Depends(require_user),
    db: AsyncSession = Depends(get_db_session),
) -> LLMKeyStatus:
    row = await users_repo.get_by_clerk_id(db, clerk_user_id=user.subject)
    if row is None or not row.byok_provider:
        return LLMKeyStatus(configured=False)
    return LLMKeyStatus(configured=True, provider=row.byok_provider, model=row.byok_model)


@router.put("/llm-key", response_model=LLMKeyStatus)
async def put_llm_key(
    body: LLMKeyIn,
    user: ClerkUser = Depends(require_user),
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> LLMKeyStatus:
    if not settings.byok_encryption_key:
        # Fail-closed: never store a key in the clear.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gestione chiavi non disponibile (cifratura non configurata sul server).",
        )
    try:
        provider = validate_key(body.provider, body.api_key)
        encrypted = encrypt_key(body.api_key.strip(), encryption_key=settings.byok_encryption_key)
    except BYOKError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    model = (body.model or "").strip() or None if provider.startswith("ollama") else None
    await users_repo.set_byok(
        db,
        clerk_user_id=user.subject,
        provider=provider,
        key_encrypted=encrypted,
        model=model,
        email=user.email,
    )
    await db.commit()
    log.info("BYOK key set for %s (provider=%s)", user.subject, provider)
    return LLMKeyStatus(configured=True, provider=provider, model=model)


@router.delete("/llm-key", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_key(
    user: ClerkUser = Depends(require_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await users_repo.clear_byok(db, clerk_user_id=user.subject)
    await db.commit()
    log.info("BYOK key cleared for %s", user.subject)
