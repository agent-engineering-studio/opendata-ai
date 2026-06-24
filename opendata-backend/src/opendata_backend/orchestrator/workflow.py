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
        # The framework introspects the callback arity (see
        # agent_framework_orchestrations._concurrent: `len(signature.parameters)`):
        # a 2-parameter callable is invoked as `(results, WorkflowContext)`. Our
        # aggregator's 2nd parameter is an `emit` callback — used ONLY by
        # run_streaming, which calls the aggregator directly — NOT a
        # WorkflowContext. Handing it to the framework as-is would bind `emit` to
        # the WorkflowContext, making `emit(...)` raise "'WorkflowContext' object
        # is not callable" and silently degrade synth to concatenated narratives.
        # Expose a strict 1-arg adapter so the framework stays on the `(results)`
        # signature (emit defaults to None) and the returned value is yielded.
        async def _aggregate(results: list[Any]) -> Any:
            return await aggregator(results)

        builder = builder.with_aggregator(_aggregate)
    else:  # pragma: no cover — future-proof against API rename
        log.warning(
            "ConcurrentBuilder has no 'with_aggregator' method; "
            "the framework API may have changed."
        )
    return builder.build()
