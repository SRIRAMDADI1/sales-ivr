from pathlib import Path

from sales_ivr.fixtures.loader import build_initial_state, list_fixtures, load_session_fixture
from sales_ivr.llm import azure_llm_enabled, reset_llm_client
from sales_ivr.models import IVRState
from sales_ivr.models.enums import SessionStatus
from sales_ivr.orchestrator import compile_graph, run_session
from sales_ivr.runtime import clear_resource_cache


def _fixtures_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "sales_ivr" / "fixtures" / "sessions"


def _coerce(result: IVRState | dict) -> IVRState:
    if isinstance(result, IVRState):
        return result
    return IVRState.model_validate(result)


def _run(name: str) -> IVRState:
    clear_resource_cache()
    reset_llm_client()
    fixture = _fixtures_dir() / name
    return _coerce(run_session(build_initial_state(load_session_fixture(fixture))))


def test_graph_compiles():
    assert compile_graph() is not None


def test_passthrough_without_azure():
    """No Azure key → input session returned unchanged (zero mock processing)."""

    clear_resource_cache()
    reset_llm_client()
    if azure_llm_enabled():
        return
    result = _run("auto_quote_ca.json")
    assert result.session.status == SessionStatus.IN_PROGRESS
    assert result.session.quote is None
    assert result.llm_usage == []
    assert result.audit_trail == []


def test_auto_quote_happy_path_when_azure():
    if not azure_llm_enabled():
        return
    result = _run("auto_quote_ca.json")
    assert result.session.status == SessionStatus.QUOTE_ACCEPTED
    assert result.session.quote is not None
    assert result.session.quote.quote_amount_monthly > 0
    assert len(result.llm_usage) >= 1


def test_handoff_passthrough_or_azure():
    result = _run("speak_to_agent_tx.json")
    if azure_llm_enabled():
        assert result.session.status == SessionStatus.HANDOFF
        assert result.session.handoff is not None
    else:
        assert result.session.status == SessionStatus.IN_PROGRESS
        assert result.llm_usage == []


def test_list_fixtures():
    fixtures = list_fixtures(_fixtures_dir())
    assert len(fixtures) >= 8


def test_passthrough_when_deployment_missing(monkeypatch):
    """Key present but deployment missing → input returned unchanged."""

    clear_resource_cache()
    reset_llm_client()

    monkeypatch.setattr(
        "sales_ivr.llm.client.resolve_azure_credentials",
        lambda: ("fake-key", "https://example.openai.azure.com/"),
    )

    def fake_probe() -> bool:
        from sales_ivr.llm.client import mark_deployment_unavailable

        mark_deployment_unavailable(
            "Azure OpenAI deployment 'gpt-4o-mini' is not available (DeploymentNotFound)."
        )
        return False

    monkeypatch.setattr("sales_ivr.llm.client._probe_deployment", fake_probe)

    from sales_ivr.llm import client as llm_client

    llm_client._deployment_ok = None
    llm_client._unavailable_reason = None

    assert azure_llm_enabled() is False

    fixture = _fixtures_dir() / "auto_quote_ca.json"
    initial = build_initial_state(load_session_fixture(fixture))
    result = _coerce(run_session(initial))
    assert result.session.status == SessionStatus.IN_PROGRESS
    assert result.session.quote is None
    assert result.llm_usage == []
    assert result.session.session_id == initial.session.session_id

