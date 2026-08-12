"""TelemetryBot bridge — soft-fail if SDK/collector unavailable."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

from sales_ivr.models.session import IVRState, LLMUsage
from sales_ivr.runtime import project_root

logger = logging.getLogger("sales_ivr.telemetry")

_client = None
_client_loaded = False


def _load_client():
    global _client, _client_loaded
    if _client_loaded:
        return _client
    _client_loaded = True
    try:
        from agentelemetry import TelemetryClient
    except ImportError:
        logger.debug("agentelemetry not installed — telemetry disabled")
        _client = None
        return None

    config_path = project_root() / "telemetry.yaml"
    if not config_path.exists():
        logger.debug("No telemetry.yaml at %s — telemetry disabled", config_path)
        _client = None
        return None
    try:
        _client = TelemetryClient.from_config(config_path)
    except Exception as exc:
        logger.warning("Could not init TelemetryClient: %s", exc)
        _client = None
    return _client


def get_telemetry_client():
    return _load_client()


def reset_telemetry_client() -> None:
    global _client, _client_loaded
    _client = None
    _client_loaded = False


def map_outcome(state: IVRState) -> str:
    status = state.session.status.value if state.session.status else "unknown"
    if state.session.quote is not None:
        return "quoted"
    if state.session.handoff is not None:
        return "handoff"
    if status in {"completed", "succeeded"}:
        return "succeeded"
    if status in {"failed", "error"}:
        return "failed"
    return status


@contextmanager
def telemetry_run(
    *,
    external_id: str | None,
    channel: str = "cli",
    experiment: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """Context manager around a Sales IVR workflow execution."""
    client = get_telemetry_client()
    if client is None:
        yield None
        return
    with client.start_run(
        external_id=external_id,
        channel=channel,
        experiment=experiment,
        metadata=metadata or {},
    ) as run:
        yield run


def emit_usage_as_span(usage: LLMUsage, *, parent_span_id: str | None = None) -> None:
    """Emit one agent span + LLM call from an LLMUsage record."""
    client = get_telemetry_client()
    if client is None:
        return
    try:
        from agentelemetry import context as tctx

        if tctx.get_run() is None:
            return
        with client.span(usage.agent_name, parent_span_id=parent_span_id) as span:
            client.record_llm_call(
                agent_name=usage.agent_name,
                model=usage.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                latency_ms=usage.latency_ms,
                finish_reason=usage.finish_reason,
                span_id=span.span_id,
            )
            for i in range(max(0, usage.tool_calls)):
                client.record_tool_call(
                    agent_name=usage.agent_name,
                    tool_name=f"tool_{i + 1}",
                    success=True,
                    span_id=span.span_id,
                )
    except Exception as exc:
        logger.warning("Failed to emit telemetry span for %s: %s", usage.agent_name, exc)


def emit_state_telemetry(state: IVRState, run: Any = None) -> None:
    """Flush all llm_usage entries on a completed IVRState as spans."""
    client = get_telemetry_client()
    if client is None:
        return
    try:
        from agentelemetry import context as tctx
        from agentelemetry.schemas import RunStatus

        if tctx.get_run() is None and run is None:
            return
        previous_span_id = None
        for usage in state.llm_usage:
            try:
                with client.span(usage.agent_name, parent_span_id=None) as span:
                    client.record_llm_call(
                        agent_name=usage.agent_name,
                        model=usage.model,
                        prompt_tokens=usage.prompt_tokens,
                        completion_tokens=usage.completion_tokens,
                        total_tokens=usage.total_tokens,
                        latency_ms=usage.latency_ms,
                        finish_reason=usage.finish_reason,
                        span_id=span.span_id,
                    )
                    for i in range(max(0, usage.tool_calls)):
                        client.record_tool_call(
                            agent_name=usage.agent_name,
                            tool_name=f"tool_{i + 1}",
                            success=True,
                            span_id=span.span_id,
                        )
                    if previous_span_id:
                        client.record_handoff(
                            from_span_id=previous_span_id,
                            to_span_id=span.span_id,
                            reason="orchestrator",
                        )
                    previous_span_id = span.span_id
            except Exception as exc:
                logger.warning("Span emit failed for %s: %s", usage.agent_name, exc)

        active = run or tctx.get_run()
        if active is not None:
            active.outcome = map_outcome(state)
            if state.session.status.value in {"failed", "error"}:
                active.status = RunStatus.FAILED
            else:
                active.status = RunStatus.SUCCEEDED
    except Exception as exc:
        logger.warning("emit_state_telemetry failed: %s", exc)


def emit_conversation_usage(
    *,
    agent_name: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    latency_ms: int,
    finish_reason: str | None = None,
) -> None:
    client = get_telemetry_client()
    if client is None:
        return
    try:
        from agentelemetry import context as tctx

        if tctx.get_run() is None:
            return
        with client.span(agent_name):
            client.record_llm_call(
                agent_name=agent_name,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                finish_reason=finish_reason,
            )
    except Exception as exc:
        logger.warning("conversation telemetry failed: %s", exc)
