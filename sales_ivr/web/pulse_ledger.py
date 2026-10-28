"""Local Pulse ledger: every AI call on this site, with cost and latency."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sales_ivr.models.session import LLMUsage

_LOCK = threading.Lock()

# Approximate list prices in USD per 1M tokens. Same idea as the Pulse SDK.
_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-5": (1.25, 10.00),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5-nano": (0.05, 0.40),
    "default": (1.00, 3.00),
}


def ledger_path() -> Path:
    raw = os.environ.get("PULSE_LEDGER_PATH")
    if raw:
        return Path(raw)
    azure_data = Path("/home/data")
    if azure_data.is_dir():
        return azure_data / "pulse_usage.jsonl"
    return Path(__file__).resolve().parents[2] / "data" / "pulse_usage.jsonl"


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    key = (model or "default").strip().lower()
    prices = _PRICES.get("default", (1.0, 3.0))
    if key in _PRICES:
        prices = _PRICES[key]
    else:
        for known in sorted((name for name in _PRICES if name != "default"), key=len, reverse=True):
            if known in key:
                prices = _PRICES[known]
                break
    input_per_1m, output_per_1m = prices
    cost = (prompt_tokens / 1_000_000) * input_per_1m
    cost += (completion_tokens / 1_000_000) * output_per_1m
    return round(cost, 8)


def record_usage(usage: LLMUsage) -> None:
    """Append one LLM call. Failures here must not break quoting."""

    event = {
        "id": uuid.uuid4().hex,
        "at": datetime.now(timezone.utc).isoformat(),
        "agent_name": usage.agent_name,
        "model": usage.model,
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "latency_ms": usage.latency_ms,
        "tool_calls": usage.tool_calls,
        "cost_usd": estimate_cost_usd(
            usage.model, usage.prompt_tokens, usage.completion_tokens
        ),
    }
    path = ledger_path()
    line = json.dumps(event, separators=(",", ":"))
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def _load_events() -> list[dict[str, Any]]:
    path = ledger_path()
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                events.append(item)
    return events


def _percentile(values: list[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction))))
    return int(ordered[index])


def summary() -> dict[str, Any]:
    """Roll up the ledger the way Pulse rolls up a project: cost, tokens, latency, agents."""

    events = _load_events()
    prompt = sum(int(item.get("prompt_tokens") or 0) for item in events)
    completion = sum(int(item.get("completion_tokens") or 0) for item in events)
    total = sum(int(item.get("total_tokens") or 0) for item in events)
    cost = round(sum(float(item.get("cost_usd") or 0) for item in events), 8)
    latencies = [int(item.get("latency_ms") or 0) for item in events]
    avg_latency = int(sum(latencies) / len(latencies)) if latencies else 0

    by_agent: dict[str, dict[str, Any]] = {}
    by_model: dict[str, dict[str, Any]] = {}
    for item in events:
        agent = str(item.get("agent_name") or "unknown")
        bucket = by_agent.setdefault(
            agent,
            {
                "agent_name": agent,
                "calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "latency_ms": 0,
                "tool_calls": 0,
            },
        )
        bucket["calls"] += 1
        bucket["prompt_tokens"] += int(item.get("prompt_tokens") or 0)
        bucket["completion_tokens"] += int(item.get("completion_tokens") or 0)
        bucket["total_tokens"] += int(item.get("total_tokens") or 0)
        bucket["cost_usd"] += float(item.get("cost_usd") or 0)
        bucket["latency_ms"] += int(item.get("latency_ms") or 0)
        bucket["tool_calls"] += int(item.get("tool_calls") or 0)

        model = str(item.get("model") or "unknown")
        mix = by_model.setdefault(
            model,
            {"model": model, "calls": 0, "total_tokens": 0, "cost_usd": 0.0},
        )
        mix["calls"] += 1
        mix["total_tokens"] += int(item.get("total_tokens") or 0)
        mix["cost_usd"] += float(item.get("cost_usd") or 0)

    agents = []
    for bucket in by_agent.values():
        calls = bucket["calls"] or 1
        agents.append(
            {
                "agent_name": bucket["agent_name"],
                "calls": bucket["calls"],
                "prompt_tokens": bucket["prompt_tokens"],
                "completion_tokens": bucket["completion_tokens"],
                "total_tokens": bucket["total_tokens"],
                "cost_usd": round(bucket["cost_usd"], 8),
                "avg_latency_ms": int(bucket["latency_ms"] / calls),
                "tool_calls": bucket["tool_calls"],
            }
        )
    agents.sort(key=lambda row: row["cost_usd"], reverse=True)

    models = []
    for mix in by_model.values():
        models.append(
            {
                "model": mix["model"],
                "calls": mix["calls"],
                "total_tokens": mix["total_tokens"],
                "cost_usd": round(mix["cost_usd"], 8),
            }
        )
    models.sort(key=lambda row: row["total_tokens"], reverse=True)

    recent = list(reversed(events[-12:]))
    return {
        "call_count": len(events),
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "cost_usd": cost,
        "avg_latency_ms": avg_latency,
        "p95_latency_ms": _percentile(latencies, 0.95),
        "agents": agents,
        "models": models,
        "recent": recent,
    }
