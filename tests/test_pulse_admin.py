import pytest
from fastapi.testclient import TestClient

from sales_ivr.models.session import LLMUsage
from sales_ivr.web.app import app
from sales_ivr.web.pulse_ledger import agent_usage, recent_calls, record_usage, summary


@pytest.fixture
def ledger_path(tmp_path, monkeypatch):
    path = tmp_path / "pulse_usage.jsonl"
    monkeypatch.setenv("PULSE_LEDGER_PATH", str(path))
    return path


def test_ledger_rolls_up_tokens_cost_and_agents(ledger_path):
    record_usage(
        LLMUsage(
            agent_name="FirstpassConversationAgent",
            model="gpt-4o-mini",
            prompt_tokens=1000,
            completion_tokens=200,
            total_tokens=1200,
            latency_ms=400,
        )
    )
    record_usage(
        LLMUsage(
            agent_name="QuoteGenerationAgent",
            model="gpt-4o-mini",
            prompt_tokens=500,
            completion_tokens=100,
            total_tokens=600,
            latency_ms=800,
        )
    )

    rollup = summary()

    assert rollup["call_count"] == 2
    assert rollup["total_tokens"] == 1800
    assert rollup["prompt_tokens"] == 1500
    assert rollup["completion_tokens"] == 300
    assert rollup["cost_usd"] > 0
    assert rollup["p95_latency_ms"] == 800
    assert rollup["agents"][0]["agent_name"] == "FirstpassConversationAgent"
    assert ledger_path.exists()


def test_admin_pulse_requires_password(ledger_path):
    record_usage(
        LLMUsage(
            agent_name="FirstpassConversationAgent",
            model="gpt-4o-mini",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            latency_ms=20,
        )
    )
    client = TestClient(app)

    denied = client.post("/api/admin/pulse", json={"password": "nope"})
    assert denied.status_code == 401

    allowed = client.post("/api/admin/pulse", json={"password": "12345"})
    assert allowed.status_code == 200
    body = allowed.json()
    assert body["call_count"] == 1
    assert body["total_tokens"] == 15
    assert body["agents"][0]["agent_name"] == "FirstpassConversationAgent"


def test_recent_calls_are_newest_first_and_capped(ledger_path):
    for index in range(3):
        record_usage(
            LLMUsage(
                agent_name="QuoteGenerationAgent",
                model="gpt-4o-mini",
                prompt_tokens=index + 1,
                completion_tokens=1,
                total_tokens=index + 2,
                latency_ms=100 * (index + 1),
            )
        )

    newest = recent_calls(1)
    assert len(newest) == 1
    assert newest[0]["prompt_tokens"] == 3
    assert recent_calls(0)[0]["prompt_tokens"] == 3
    assert len(recent_calls(100)) == 3
    assert ledger_path.exists()


def test_agent_usage_matches_one_agent_or_suggests_names(ledger_path):
    record_usage(
        LLMUsage(
            agent_name="FirstpassConversationAgent",
            model="gpt-4o-mini",
            prompt_tokens=100,
            completion_tokens=20,
            total_tokens=120,
            latency_ms=300,
            tool_calls=2,
        )
    )
    record_usage(
        LLMUsage(
            agent_name="QuoteGenerationAgent",
            model="gpt-4o",
            prompt_tokens=50,
            completion_tokens=10,
            total_tokens=60,
            latency_ms=900,
        )
    )

    match = agent_usage("quotegenerationagent", recent_limit=5)
    assert match["found"] is True
    assert match["agent_name"] == "QuoteGenerationAgent"
    assert match["calls"] == 1
    assert match["total_tokens"] == 60
    assert match["avg_latency_ms"] == 900
    assert match["models"][0]["model"] == "gpt-4o"
    assert match["recent"][0]["total_tokens"] == 60

    missing = agent_usage("quote")
    assert missing["found"] is False
    assert missing["suggestions"] == ["QuoteGenerationAgent"]
    assert "FirstpassConversationAgent" in missing["agents"]
    assert ledger_path.exists()
