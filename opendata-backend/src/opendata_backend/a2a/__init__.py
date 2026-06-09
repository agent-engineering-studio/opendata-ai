"""A2A (Agent-to-Agent) protocol integration.

Exposes the orchestrator as an A2A-compliant agent so other agents can call it
as a peer (vs MCP, which exposes tools to LLMs). Three skills are published:
- `search_open_data`   : multi-source fan-out (CKAN + ISTAT + …)
- `find_geo_resources` : same as above with prefer_geo bias and geo-only filtering
- `classify_dataset`   : taxonomy classifier (cached)

Mounted via `register_a2a` on the FastAPI app when `settings.a2a_enabled`.
"""

from .agent_card import build_agent_card
from .executor import OpenDataAgentExecutor
from .router import register_a2a

__all__ = ["build_agent_card", "OpenDataAgentExecutor", "register_a2a"]
