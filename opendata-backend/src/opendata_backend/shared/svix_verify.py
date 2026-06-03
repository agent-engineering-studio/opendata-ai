"""Verify Clerk webhook signatures via svix.

Clerk signs every webhook payload with HMAC-SHA256 using the per-endpoint
`whsec_…` secret. Verification uses the official `svix` library which also
enforces a 5-minute timestamp tolerance window (replay-protection).
"""

from __future__ import annotations

from typing import Mapping

from svix.webhooks import Webhook, WebhookVerificationError


class SvixSignatureError(Exception):
    """Raised when a webhook's svix signature cannot be verified."""


def verify_clerk_webhook(
    *,
    payload: bytes,
    headers: Mapping[str, str],
    secret: str,
) -> None:
    """Validate the svix headers against the payload + secret.

    Raises `SvixSignatureError` with a short reason on failure. On success
    returns None — the verified payload is the original `payload` argument.
    """
    if not secret:
        raise SvixSignatureError("webhook secret is not configured")

    # svix expects standard headers (svix-id / svix-timestamp / svix-signature).
    # The svix library accepts dict-like headers and is happy with lowercase
    # keys, which is what FastAPI surfaces via `request.headers`.
    try:
        wh = Webhook(secret)
        wh.verify(payload, dict(headers))
    except WebhookVerificationError as exc:
        raise SvixSignatureError(str(exc)) from exc
