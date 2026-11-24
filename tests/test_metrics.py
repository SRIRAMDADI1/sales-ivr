import pytest
from prometheus_client import generate_latest

from sales_ivr.models.session import LLMUsage
from sales_ivr.web.metrics import REGISTRY, start_metrics_server
from sales_ivr.web.pulse_ledger import estimate_cost_usd, record_usage


def test_record_usage_exports_prometheus_series(tmp_path, monkeypatch):
    ledger = tmp_path / "pulse_usage.jsonl"
    monkeypatch.setenv("PULSE_LEDGER_PATH", str(ledger))
    usage = LLMUsage(
        agent_name="MetricsProbeAgent",
        model="gpt-4o-mini",
        prompt_tokens=1000,
        completion_tokens=200,
        total_tokens=1200,
        latency_ms=450,
        tool_calls=2,
    )
    record_usage(usage)

    labels = {"agent": "MetricsProbeAgent", "model": "gpt-4o-mini"}
    calls = REGISTRY.get_sample_value("llm_calls_total", labels)
    prompt = REGISTRY.get_sample_value("llm_tokens_total", {**labels, "type": "prompt"})
    completion = REGISTRY.get_sample_value("llm_tokens_total", {**labels, "type": "completion"})
    cost = REGISTRY.get_sample_value("llm_cost_usd_total", labels)
    tools = REGISTRY.get_sample_value("llm_tool_calls_total", labels)
    latency = REGISTRY.get_sample_value("llm_latency_ms_count", labels)

    assert calls == 1
    assert prompt == 1000
    assert completion == 200
    assert cost == pytest.approx(estimate_cost_usd("gpt-4o-mini", 1000, 200))
    assert tools == 2
    assert latency == 1
    body = generate_latest(REGISTRY).decode()
    assert "llm_calls_total" in body
    assert ledger.exists()


def test_metrics_port_zero_does_not_bind():
    start_metrics_server()
    start_metrics_server()
