"""LLM access gate + per-user orchestrator resolution.

Policy: the paid gate applies only when the SYSTEM provider bills per use
(Anthropic Claude in production). There an authenticated user may run the
LLM-backed surfaces (territorio analysis, dataset search/synthesis, usecases,
classify) only if they either (a) configured their OWN LLM key (BYOK), or
(b) hold a paid subscription tier — otherwise the endpoint returns 402.

When the system provider is a self-hosted Ollama (`LLM_PROVIDER=ollama`, e.g.
`make up-host-ollama` locally or a remote inference container in production)
there is no per-use cost to meter, so the gate is open to every authenticated
user. The metered system providers — Claude and Ollama Cloud (the latter when
OLLAMA_CLOUD_API_KEY is set) — keep the paid gate.

A user's own BYOK credential (Claude / Ollama Cloud / their own Ollama server)
overrides the system provider entirely and is always allowed.

- `require_llm_access` is the FastAPI dependency that enforces the gate and
  resolves the user's BYOK credential (decrypted) once per request.
- `acquire_orchestrator` yields the right OrchestratorSession: a fresh per-user
  one bound to the BYOK credential, or the shared system session for paying
  subscribers (whose usage runs on the system provider).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from fastapi import Depends, HTTPException, status

from .auth import ClerkUser
from .auth.dependencies import require_user
from .byok import BYOKCreds, BYOKError, decrypt_key
from .config import Settings, get_settings, resolve_provider
from .factory import OrchestratorSession
from .state import session_holder

log = logging.getLogger("opendata-backend.llm_access")

_PAID_TIERS_EXCLUDED = {"", "free"}


@dataclass(frozen=True)
class LLMAccess:
    """Resolved LLM-access decision for the current request."""

    clerk_user_id: str
    byok: BYOKCreds | None
    tier: str
    is_dev: bool

    @property
    def uses_byok(self) -> bool:
        return self.byok is not None


def _is_paid(tier: str | None) -> bool:
    return bool(tier) and tier not in _PAID_TIERS_EXCLUDED


async def _resolve_byok(user_row, settings: Settings) -> BYOKCreds | None:
    """Decrypt the user's stored BYOK credential, or None if not configured."""
    provider = getattr(user_row, "byok_provider", None)
    enc = getattr(user_row, "byok_key_encrypted", None)
    if not provider or not enc:
        return None
    try:
        plaintext = decrypt_key(enc, encryption_key=settings.byok_encryption_key or "")
    except BYOKError as exc:
        # A rotated/missing encryption key shouldn't 500 — treat as "no usable
        # key" so the gate falls back to the subscription check and the user is
        # told (via the account endpoint) to re-enter the key.
        log.warning("BYOK decrypt failed for %s: %s", user_row.clerk_user_id, exc)
        return None
    return BYOKCreds(
        provider=provider,  # type: ignore[arg-type]
        secret=plaintext,
        model=getattr(user_row, "byok_model", None),
    )


async def require_llm_access(
    user: ClerkUser = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> LLMAccess:
    """Gate dependency. Resolution order:

      1. dev mode (auth disabled) → always allowed on the system provider;
      2. the user's OWN key (BYOK) → wins over the system provider entirely;
      3. self-hosted Ollama as the system provider → free → open to all;
      4. metered system provider (Claude / Ollama Cloud) → paid tier required,
         otherwise 402.
    """
    if user.claims.get("dev_mode") or user.claims.get("auth_method") == "dev":
        return LLMAccess(clerk_user_id=user.subject, byok=None, tier="dev", is_dev=True)

    # Load the user row to read BYOK + tier FIRST: a configured BYOK key must
    # override the system provider logic (incl. local Ollama). Without a DB we
    # can't gate by key, so fall back to the tier carried in the token.
    byok: BYOKCreds | None = None
    tier = str(user.claims.get("subscription_tier") or "free")
    try:
        from .db.repositories import users as users_repo
        from .db.session import get_session_factory

        factory = get_session_factory()
        async with factory() as db:
            row = await users_repo.get_by_clerk_id(db, clerk_user_id=user.subject)
            if row is not None:
                tier = row.subscription_tier or tier
                byok = await _resolve_byok(row, settings)
    except RuntimeError:
        # DATABASE_URL not configured — keep whatever the token told us.
        log.debug("require_llm_access: DB unavailable, using token tier=%s", tier)

    # 2) User's own credential wins, whatever the system provider is.
    if byok is not None:
        return LLMAccess(clerk_user_id=user.subject, byok=byok, tier=tier, is_dev=False)

    # 3) Self-hosted Ollama as the SYSTEM provider has no per-use cost to meter,
    # so there's nothing to gate: every authenticated user runs on the shared
    # local model. Ollama Cloud and Claude are metered → they fall through.
    if resolve_provider(settings) == "ollama":
        return LLMAccess(clerk_user_id=user.subject, byok=None, tier=tier, is_dev=False)

    # 4) Metered system provider (Claude / Ollama Cloud): a paid tier is required.
    if _is_paid(tier):
        return LLMAccess(clerk_user_id=user.subject, byok=None, tier=tier, is_dev=False)

    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail=(
            "Per usare l'analisi servono o una tua chiave LLM (Claude o Ollama Cloud) "
            "configurata nel profilo, oppure un abbonamento attivo."
        ),
    )


@asynccontextmanager
async def acquire_orchestrator(
    access: LLMAccess, settings: Settings
) -> AsyncIterator[OrchestratorSession]:
    """Yield the OrchestratorSession to serve this request.

    BYOK users get a FRESH per-user session bound to their credential (it opens
    its own MCP connections for the request lifetime — acceptable for the
    minutes-long analysis). Everyone else (paying subscribers, dev) reuses the
    shared system session, which must NOT be closed here.
    """
    if access.uses_byok:
        session = OrchestratorSession(settings, byok=access.byok)
        await session.__aenter__()
        try:
            yield session
        finally:
            await session.__aexit__(None, None, None)
        return

    shared = session_holder.session
    if shared is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestratore non inizializzato.",
        )
    yield shared
