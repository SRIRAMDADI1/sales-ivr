from pathlib import Path

from sales_ivr.agents.call_intake import call_intake
from sales_ivr.agents.intent_router import intent_router
from sales_ivr.fixtures.loader import build_initial_state, load_session_fixture
from sales_ivr.llm import azure_llm_enabled, reset_llm_client
from sales_ivr.llm.client import get_llm_unavailable_reason
from sales_ivr.models import CallSession, CallerUtterance
from sales_ivr.runtime import clear_resource_cache


def test_llm_availability_matches_reported_reason():
    """Availability and the passthrough reason must agree, with or without credentials."""

    clear_resource_cache()
    reset_llm_client()
    if azure_llm_enabled():
        assert get_llm_unavailable_reason() is None
    else:
        assert get_llm_unavailable_reason()


def test_call_intake_requires_azure(monkeypatch):
    """Direct agent calls need Azure; without it get_llm_client fails."""

    clear_resource_cache()
    reset_llm_client()
    session = CallSession(
        session_id="t1",
        caller_phone="15551234001",
        utterances=[CallerUtterance(turn=0, text="I need a quote for auto insurance")],
        dtmf_digits="1",
    )
    if azure_llm_enabled():
        state = call_intake(build_initial_state(session))
        assert any(e.node.value == "call_intake" for e in state.audit_trail)
    else:
        try:
            call_intake(build_initial_state(session))
            raise AssertionError("expected RuntimeError without Azure")
        except RuntimeError as exc:
            assert "Azure" in str(exc)


def test_intent_router_requires_azure():
    clear_resource_cache()
    reset_llm_client()
    session = CallSession(
        session_id="t2",
        caller_phone="15551234001",
        utterances=[CallerUtterance(turn=0, text="I'd like an auto insurance quote please")],
    )
    if azure_llm_enabled():
        state = intent_router(build_initial_state(session))
        assert state.session.intent.value == "new_quote"
    else:
        try:
            intent_router(build_initial_state(session))
            raise AssertionError("expected RuntimeError without Azure")
        except RuntimeError as exc:
            assert "Azure" in str(exc)


def test_fixture_loads():
    path = (
        Path(__file__).resolve().parent.parent
        / "sales_ivr"
        / "fixtures"
        / "sessions"
        / "auto_quote_ca.json"
    )
    session = load_session_fixture(path)
    assert session.session_id.startswith("sess-")
