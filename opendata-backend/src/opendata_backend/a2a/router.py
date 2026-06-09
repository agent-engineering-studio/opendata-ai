"""Mount A2A routes (AgentCard + JSON-RPC) on the FastAPI app.

We use the SDK's `add_a2a_routes_to_fastapi` helper so the routes show up in
the OpenAPI schema at /docs alongside the rest of the API. The JSON-RPC
endpoint lives under `/a2a/`; AgentCard discovery is at the protocol-standard
`/.well-known/agent.json`.
"""

from __future__ import annotations

import logging

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from fastapi import FastAPI

from ..config import Settings
from .agent_card import build_agent_card
from .executor import OpenDataAgentExecutor

log = logging.getLogger("opendata-backend.a2a")


def register_a2a(app: FastAPI, settings: Settings) -> None:
    """Attach AgentCard + JSON-RPC endpoints to the given FastAPI app."""
    if not settings.a2a_enabled:
        log.info("A2A disabled (settings.a2a_enabled=False)")
        return

    agent_card = build_agent_card(public_url=settings.a2a_public_url)
    request_handler = DefaultRequestHandler(
        agent_executor=OpenDataAgentExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )
    # `enable_v0_3_compat=True` lets clients use both naming schemes:
    #   - SDK 1.0:  SendMessage, GetTask, CancelTask (PascalCase)
    #   - SDK 0.3:  message/send, tasks/get, tasks/cancel  (slash-case)
    # Many third-party clients and inspectors still default to the v0.3 names.
    #
    # Publish the AgentCard at BOTH the v1.0 well-known path (with dash, the
    # SDK default) and the legacy v0.3 path (without dash). Old discovery
    # clients hardcoded the latter; the duplication is cheap and harmless.
    card_routes = [
        *create_agent_card_routes(agent_card),
        *create_agent_card_routes(agent_card, card_url="/.well-known/agent.json"),
    ]
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=card_routes,
        jsonrpc_routes=create_jsonrpc_routes(
            request_handler, rpc_url="/a2a/", enable_v0_3_compat=True,
        ),
    )
    log.info(
        "A2A mounted | public_url=%s skills=%d",
        settings.a2a_public_url, len(agent_card.skills),
    )
