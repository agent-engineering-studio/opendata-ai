"""Client di SCRITTURA verso il Knowledge Graph (FastAPI REST).

Usato SOLO lato server (backend) per ingestionare/eliminare documenti della PA
— mai esposto a un LLM/agente (la lettura passa dall'MCP read-only). Vedi
opendata-backend F2 (file manager documenti + tier documentale).
"""

from .client import KgClient, KgError

__all__ = ["KgClient", "KgError"]
