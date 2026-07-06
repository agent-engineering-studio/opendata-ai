"""Connettore MEF — Dipartimento delle Finanze (dichiarazioni IRPEF per comune)."""

from .redditi import fetch_redditi_comune

__all__ = ["fetch_redditi_comune"]
