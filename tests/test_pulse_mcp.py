import asyncio
import json

from sales_ivr.mcp.pulse import pulse_agent, pulse_recent, pulse_summary, server
from sales_ivr.models.session import LLMUsage
from sales_ivr.web.pulse_ledger import record_usage


def test_pulse_tools_are_read_only():
    tools = asyncio.run(server.list_tools())
    by_name = {tool.name: tool for tool in tools}

    assert set(by_name) == {"pulse_summary", "pulse_recent", "pulse_agent"}
    for tool in by_name.values():
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.open_world_hint is False


def test_pulse_tools_read_the_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("PULSE_LEDGER_PATH", str(tmp_path / "pulse_usage.jsonl"))
    record_usage(
        LLMUsage(
            agent_name="QuoteGenerationAgent",
            model="gpt-4o-mini",
            prompt_tokens=40,
            completion_tokens=10,
            total_tokens=50,
            latency_ms=250,
        )
    )

    rollup = pulse_summary()
    assert rollup["call_count"] == 1
    assert rollup["total_tokens"] == 50

    recent = pulse_recent(limit=5)
    assert recent["count"] == 1
    assert recent["calls"][0]["agent_name"] == "QuoteGenerationAgent"

    missing = pulse_agent(agent_name="billing")
    assert missing["found"] is False
    assert missing["suggestions"] == []

    found = pulse_agent(agent_name="quotegenerationagent")
    assert found["found"] is True
    assert found["calls"] == 1


def test_pulse_summary_tool_call_returns_json(tmp_path, monkeypatch):
    monkeypatch.setenv("PULSE_LEDGER_PATH", str(tmp_path / "pulse_usage.jsonl"))
    record_usage(
        LLMUsage(
            agent_name="FirstpassConversationAgent",
            model="gpt-4o-mini",
            prompt_tokens=8,
            completion_tokens=2,
            total_tokens=10,
            latency_ms=15,
        )
    )

    result = asyncio.run(server.call_tool("pulse_summary", {}))

    assert result.is_error is False
    payload = json.loads(result.content[0].text)
    assert payload["call_count"] == 1
    assert payload["total_tokens"] == 10
    assert payload["agents"][0]["agent_name"] == "FirstpassConversationAgent"
