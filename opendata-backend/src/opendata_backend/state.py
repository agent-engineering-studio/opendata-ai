"""Module-level state shared between routers.

The FastAPI app lifespan in `main.py` populates `session` and `settings` at
startup. Routers read them via `from .state import session_holder`.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from .db.session import Database
from .factory import OrchestratorSession


@dataclass
class _Holder:
    session: OrchestratorSession | None = None
    settings: Settings | None = None
    database: Database | None = None


session_holder = _Holder()
