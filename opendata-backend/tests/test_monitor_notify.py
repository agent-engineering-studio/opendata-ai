"""Test degli adapter di notifica webhook/email — outward-facing, fail-safe (#88)."""

from __future__ import annotations

from opendata_backend.config import Settings
from opendata_backend.monitor import notify


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *exc) -> None:
        pass

    async def post(self, url: str, json: dict) -> _FakeResponse:
        _FakeAsyncClient.last_call = (url, json)
        return _FakeResponse(_FakeAsyncClient.status_code)


async def test_send_webhook_success(monkeypatch) -> None:
    _FakeAsyncClient.status_code = 200
    # Rete-free (come test_proxy.py): salta la vera risoluzione DNS/anti-SSRF.
    monkeypatch.setattr(notify, "_validate_proxy_url", lambda u: u)
    monkeypatch.setattr(notify.httpx, "AsyncClient", _FakeAsyncClient)
    ok = await notify.send_webhook("https://hooks.example.com/x", {"esito": "critico"})
    assert ok is True
    assert _FakeAsyncClient.last_call == ("https://hooks.example.com/x", {"esito": "critico"})


async def test_send_webhook_http_error_status(monkeypatch) -> None:
    _FakeAsyncClient.status_code = 500
    monkeypatch.setattr(notify, "_validate_proxy_url", lambda u: u)
    monkeypatch.setattr(notify.httpx, "AsyncClient", _FakeAsyncClient)
    ok = await notify.send_webhook("https://hooks.example.com/x", {})
    assert ok is False


async def test_send_webhook_network_error_is_failsafe(monkeypatch) -> None:
    import httpx as httpx_mod

    class _Raising:
        def __init__(self, *a, **k) -> None:
            pass

        async def __aenter__(self) -> "_Raising":
            return self

        async def __aexit__(self, *exc) -> None:
            pass

        async def post(self, *a, **k):
            raise httpx_mod.ConnectTimeout("timeout")

    monkeypatch.setattr(notify, "_validate_proxy_url", lambda u: u)
    monkeypatch.setattr(notify.httpx, "AsyncClient", _Raising)
    ok = await notify.send_webhook("https://hooks.example.com/x", {})
    assert ok is False  # non solleva


async def test_send_webhook_rejects_private_targets() -> None:
    # Nessun monkeypatch: la vera validazione anti-SSRF deve rifiutare il loopback.
    ok = await notify.send_webhook("http://127.0.0.1:9999/x", {})
    assert ok is False


def test_send_email_skipped_without_smtp_config() -> None:
    settings = Settings(auth_enabled=False)  # type: ignore[call-arg]
    assert settings.smtp_host is None
    ok = notify.send_email("ente@example.it", "Oggetto", "Corpo", settings)
    assert ok is False


def test_send_email_sent_when_configured(monkeypatch) -> None:
    sent: dict = {}

    class _FakeSMTP:
        def __init__(self, host, port, timeout=10) -> None:
            sent["host"] = host
            sent["port"] = port

        def __enter__(self) -> "_FakeSMTP":
            return self

        def __exit__(self, *exc) -> None:
            pass

        def starttls(self) -> None:
            sent["tls"] = True

        def login(self, user, password) -> None:
            sent["login"] = (user, password)

        def send_message(self, msg) -> None:
            sent["message"] = msg

    monkeypatch.setattr(notify.smtplib, "SMTP", _FakeSMTP)
    settings = Settings(
        auth_enabled=False, smtp_host="smtp.example.it", smtp_from="noreply@example.it",
        smtp_user="u", smtp_password="p",
    )  # type: ignore[call-arg]
    ok = notify.send_email("ente@example.it", "Oggetto", "Corpo", settings)
    assert ok is True
    assert sent["host"] == "smtp.example.it"
    assert sent["tls"] is True
    assert sent["login"] == ("u", "p")
    assert sent["message"]["To"] == "ente@example.it"


def test_send_email_failsafe_on_smtp_error(monkeypatch) -> None:
    import smtplib

    class _RaisingSMTP:
        def __init__(self, *a, **k) -> None:
            raise smtplib.SMTPConnectError(421, "down")

    monkeypatch.setattr(notify.smtplib, "SMTP", _RaisingSMTP)
    settings = Settings(auth_enabled=False, smtp_host="smtp.example.it", smtp_from="noreply@example.it")  # type: ignore[call-arg]
    ok = notify.send_email("ente@example.it", "Oggetto", "Corpo", settings)
    assert ok is False  # non solleva


def test_build_email_body_lists_nuovi_e_risolti() -> None:
    target = {"url": "https://x.it/a.csv"}
    run_result = {"esito": "attenzione"}
    diff = {"nuovi": [{"livello": "medio", "codice": "stantio", "messaggio": "non aggiornato"}], "risolti": ["link_rotto"]}
    body = notify.build_email_body(target, run_result, diff)
    assert "ATTENZIONE" in body
    assert "non aggiornato" in body
    assert "link_rotto" in body
