"""BYOK — Bring Your Own Key.

A user can run the service with their OWN LLM credential instead of paying a
subscription: either an Anthropic Claude API key (`sk-ant-…`) or an Ollama
Cloud key. The provider is chosen by which key the user configured.

This module is PURE (no FastAPI, no DB import): it only knows how to
- validate a (provider, key) pair shape,
- encrypt/decrypt the key at rest with Fernet (symmetric, key from env), and
- describe the resolved credential as a small dataclass the factory consumes.

The encryption key comes from `Settings.byok_encryption_key` and is injected by
the caller, so this module never reaches into config or the environment itself.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger("opendata-backend.byok")

BYOKProvider = Literal["claude", "ollama_cloud", "ollama_local"]


@dataclass(frozen=True)
class BYOKCreds:
    """A user's resolved LLM credential, ready for the chat-client factory.

    The `secret` field carries:
      - ``claude``        → the Anthropic API key (``sk-ant-…``)
      - ``ollama_cloud``  → the Ollama Cloud API key
      - ``ollama_local``  → the base URL of a reachable Ollama server (no key)
    `model` is the chosen model for the two Ollama providers (the user picks it);
    for ``claude`` it stays the system default (``Settings.claude_model``).
    """

    provider: BYOKProvider
    secret: str
    model: str | None = None

    # Backwards-friendly alias: most callers think of `secret` as "the key".
    @property
    def api_key(self) -> str:
        return self.secret


class BYOKError(ValueError):
    """Raised when a (provider, key) pair is malformed — surfaced as HTTP 422."""


def validate_key(provider: str, api_key: str) -> BYOKProvider:
    """Validate the shape of a (provider, key) pair. Returns the normalised provider.

    We only check the *shape* — the real check is whether inference works, which
    happens lazily on the first LLM call. This catches obvious paste mistakes
    (wrong provider selected, empty value) before we store anything.
    """
    p = (provider or "").strip().lower()
    key = (api_key or "").strip()
    if not key:
        raise BYOKError("La chiave non può essere vuota.")
    if p == "claude":
        if not key.startswith("sk-ant-"):
            raise BYOKError(
                "Una chiave Claude valida inizia con 'sk-ant-'. "
                "Generala su console.anthropic.com."
            )
        return "claude"
    if p == "ollama_cloud":
        # Ollama Cloud keys don't carry a fixed, documented prefix; accept any
        # non-trivial token and let the first inference call be the real test.
        if len(key) < 8:
            raise BYOKError("La chiave Ollama Cloud sembra troppo corta.")
        return "ollama_cloud"
    if p == "ollama_local":
        # For a local/on-prem Ollama the "secret" is a reachable base URL.
        if not (key.startswith("http://") or key.startswith("https://")):
            raise BYOKError(
                "Per Ollama local indica l'URL del server (es. http://localhost:11434)."
            )
        return "ollama_local"
    raise BYOKError(
        f"Provider non supportato: {provider!r} "
        "(usa 'claude', 'ollama_cloud' o 'ollama_local')."
    )


def encrypt_key(plaintext: str, *, encryption_key: str) -> str:
    """Encrypt a raw API key for storage. `encryption_key` is a Fernet key (str)."""
    if not encryption_key:
        raise BYOKError(
            "BYOK_ENCRYPTION_KEY non configurata: impossibile salvare la chiave in modo sicuro."
        )
    token = Fernet(encryption_key.encode()).encrypt(plaintext.encode())
    return token.decode()


def decrypt_key(ciphertext: str, *, encryption_key: str) -> str:
    """Decrypt a stored API key. Raises BYOKError on a bad/rotated encryption key."""
    if not encryption_key:
        raise BYOKError("BYOK_ENCRYPTION_KEY non configurata: impossibile leggere la chiave.")
    try:
        return Fernet(encryption_key.encode()).decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:  # wrong/rotated key, or corrupted ciphertext
        raise BYOKError(
            "Impossibile decifrare la chiave salvata (BYOK_ENCRYPTION_KEY cambiata?). "
            "Reinserisci la chiave dal profilo."
        ) from exc


def generate_encryption_key() -> str:
    """Generate a fresh Fernet key — convenience for ops (`opendata-byok-keygen`)."""
    return Fernet.generate_key().decode()


def _keygen_cli() -> None:  # pragma: no cover — console-script entrypoint
    """`opendata-byok-keygen` → print a fresh BYOK_ENCRYPTION_KEY."""
    print(generate_encryption_key())
