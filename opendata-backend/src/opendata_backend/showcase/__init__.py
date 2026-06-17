"""Showcase-engine (Fase 3): interprete di file dichiarativi showcases/*.yaml."""

from .engine import ShowcaseError, get_showcase, list_showcases, run_showcase

__all__ = ["list_showcases", "get_showcase", "run_showcase", "ShowcaseError"]
