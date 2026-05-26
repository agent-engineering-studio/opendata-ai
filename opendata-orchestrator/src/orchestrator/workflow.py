"""Build the ConcurrentBuilder workflow that runs the enabled specialists in parallel."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from agent_framework import Agent
from agent_framework.orchestrations import ConcurrentBuilder

log = logging.getLogger("orchestrator.workflow")


AggregatorCallback = Callable[[list[Any]], Awaitable[Any]]


def build_workflow(
    participants: list[Agent],
    aggregator: AggregatorCallback,
) -> Any:
    """Return a workflow that fans out the same input to N participants in parallel.

    `aggregator` is invoked with the list of per-participant `AgentExecutorResponse`
    objects and must return a single `AgentResponse`-like object whose `.text` (or
    `messages[-1].text`) becomes the workflow's final output.
    """
    if not participants:
        raise ValueError("build_workflow requires at least one participant")
    builder = ConcurrentBuilder(participants=participants)
    if hasattr(builder, "with_aggregator"):
        builder = builder.with_aggregator(aggregator)
    else:  # pragma: no cover — future-proof against API rename
        log.warning(
            "ConcurrentBuilder has no 'with_aggregator' method; "
            "the framework API may have changed."
        )
    return builder.build()
