"""BDAP (Banca Dati delle Amministrazioni Pubbliche) — bilanci/spesa dei comuni."""

from .client import BdapError, fetch_bilancio_comune

__all__ = ["fetch_bilancio_comune", "BdapError"]
