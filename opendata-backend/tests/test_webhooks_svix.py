"""End-to-end webhook signature verification using svix's own Webhook helper."""

from __future__ import annotations

import base64
import json
import secrets

from fastapi.testclient import TestClient
from svix.webhooks import Webhook

from opendata_backend.config import Settings, get_settings
from opendata_backend.main import app

# Generate a fresh signing secret per test run.
_SECRET = "whsec_" + base64.b64encode(secrets.token_bytes(32)).decode()


def _override_settings_with_secret() -> Settings:
    return Settings(  # type: ignore[call-arg]
        auth_enabled=False,
        clerk_webhook_secret=_SECRET,
    )


def _signed_post(client: TestClient, payload: dict) -> tuple[int, dict]:
    body_str = json.dumps(payload)
    body = body_str.encode()
    wh = Webhook(_SECRET)
    msg_id = "msg_test_123"
    dt = _now_dt()
    # sign() expects the data as a `str`, not `bytes` — see standardwebhooks.
    signature = wh.sign(msg_id, dt, body_str)
    headers = {
        "svix-id": msg_id,
        "svix-timestamp": str(int(dt.timestamp())),
        "svix-signature": signature,
    }
    res = client.post("/webhooks/clerk", content=body, headers=headers)
    return res.status_code, res.json()


def _now_dt():
    from datetime import datetime, timezone

    return datetime.now(tz=timezone.utc)


def test_valid_signature_acks() -> None:
    app.dependency_overrides[get_settings] = _override_settings_with_secret
    try:
        client = TestClient(app)
        status_code, body = _signed_post(
            client,
            {
                "type": "user.created",
                "data": {
                    "id": "user_abc",
                    "primary_email_address_id": "ema_1",
                    "email_addresses": [
                        {"id": "ema_1", "email_address": "a@b.c"},
                    ],
                },
            },
        )
        assert status_code == 200
        assert body == {"status": "ok"}
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_unsigned_request_rejected() -> None:
    app.dependency_overrides[get_settings] = _override_settings_with_secret
    try:
        client = TestClient(app)
        res = client.post("/webhooks/clerk", json={"type": "user.created"})
        assert res.status_code == 401
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_missing_secret_returns_500() -> None:
    def _no_secret() -> Settings:
        return Settings(auth_enabled=False, clerk_webhook_secret=None)  # type: ignore[call-arg]

    app.dependency_overrides[get_settings] = _no_secret
    try:
        client = TestClient(app)
        res = client.post("/webhooks/clerk", json={"type": "user.created"})
        assert res.status_code == 500
    finally:
        app.dependency_overrides.pop(get_settings, None)
