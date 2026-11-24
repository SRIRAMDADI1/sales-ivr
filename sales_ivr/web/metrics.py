"""Prometheus metrics for the same AI calls the Pulse ledger records.

Labels stay at agent and model. A session or customer label would create one
series per caller and make the dashboard unusable.
"""

from __future__ import annotations

import os
import threading

from prometheus_client import CollectorRegistry, Counter, Histogram, start_http_server

from sales_ivr.models.session import LLMUsage

# Buckets are milliseconds. LLM calls land between a few hundred ms and about a minute.
_LATENCY_BUCKETS = (50, 100, 250, 500, 1000, 2000, 5000, 10000, 30000, 60000)

REGISTRY = CollectorRegistry()

llm_calls = Counter(
    "llm_calls_total",
    "LLM calls completed.",
    ("agent", "model"),
    registry=REGISTRY,
)
llm_tokens = Counter(
    "llm_tokens_total",
    "Tokens reported by the provider.",
    ("agent", "model", "type"),
    registry=REGISTRY,
)
llm_cost_usd = Counter(
    "llm_cost_usd_total",
    "Estimated USD cost from the Pulse price table.",
    ("agent", "model"),
    registry=REGISTRY,
)
llm_tool_calls = Counter(
    "llm_tool_calls_total",
    "Tool calls returned on an LLM response.",
    ("agent", "model"),
    registry=REGISTRY,
)
llm_latency_ms = Histogram(
    "llm_latency_ms",
    "LLM call latency in milliseconds.",
    ("agent", "model"),
    buckets=_LATENCY_BUCKETS,
    registry=REGISTRY,
)

_START_LOCK = threading.Lock()
_server_started = False


def _label(value: str) -> str:
    text = " ".join((value or "").split())
    return text[:64] or "unknown"


def observe_llm(usage: LLMUsage, cost_usd: float) -> None:
    """Record one completed call. Safe to call after the ledger write."""

    agent = _label(usage.agent_name)
    model = _label(usage.model)
    llm_calls.labels(agent, model).inc()
    llm_tokens.labels(agent, model, "prompt").inc(max(0, usage.prompt_tokens))
    llm_tokens.labels(agent, model, "completion").inc(max(0, usage.completion_tokens))
    if cost_usd > 0:
        llm_cost_usd.labels(agent, model).inc(cost_usd)
    llm_latency_ms.labels(agent, model).observe(max(0, usage.latency_ms))
    if usage.tool_calls > 0:
        llm_tool_calls.labels(agent, model).inc(usage.tool_calls)


def start_metrics_server() -> None:
    """Serve /metrics on METRICS_PORT. METRICS_PORT=0 disables the socket."""

    global _server_started
    with _START_LOCK:
        if _server_started:
            return
        port = int(os.environ.get("METRICS_PORT", "8001"))
        if port <= 0:
            _server_started = True
            return
        start_http_server(port, addr="0.0.0.0", registry=REGISTRY)
        _server_started = True
