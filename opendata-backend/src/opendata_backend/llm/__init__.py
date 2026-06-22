"""Provider-agnostic one-shot LLM helpers (narrative / semantic / classify)."""

from .complete import complete, llm_configured

__all__ = ["complete", "llm_configured"]
