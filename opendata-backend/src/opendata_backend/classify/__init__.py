"""Dataset classification with Claude Haiku 4.5.

Cache-aware orchestration of:
  Redis cache (24h)  →  Postgres `opendata.classifications`  →  Anthropic call

Used by `routers/datasets.py::classify`.
"""

from .service import ClassificationResult, classify_dataset

__all__ = ["ClassificationResult", "classify_dataset"]
