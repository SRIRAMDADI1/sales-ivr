import importlib

from sales_ivr.agents.handoff import HandoffResult, handoff
from sales_ivr.agents.intent_router import IntentResult, intent_router
from sales_ivr.fixtures.loader import build_initial_state
from sales_ivr.models import CallSession, CallerUtterance
from sales_ivr.models.enums import HandoffQueue, Intent
import sales_ivr.transfer as transfer
from sales_ivr.transfer import human_transfer_payload, wants_human_agent


def _session(text: str, dtmf: str = "") -> CallSession:
    return CallSession(
        session_id="sess-transfer",
        caller_phone="15551234002",
        utterances=[CallerUtterance(turn=0, text=text)],
        dtmf_digits=dtmf,
    )


def test_transfer_payload_includes_links_the_website_can_open():
    payload = human_transfer_payload()
    assert payload["tel_url"] == "tel:+16108126519"
    assert payload["web_call_url"].startswith("https://teams.microsoft.com/l/call/0/0?users=4:")
    assert "16108126519" in payload["web_call_url"]


def test_human_phrases_are_recognized_and_quotes_are_not():
    assert wants_human_agent("I want to speak to a representative")
    assert wants_human_agent("Can you transfer me to a real person?")
    assert wants_human_agent("operator")
    assert wants_human_agent("0")
    assert not wants_human_agent("I need a quote for auto insurance")
    assert not wants_human_agent("My phone is 555-123-4001")


def test_intent_router_holds_a_human_request_even_if_the_model_disagrees(monkeypatch):
    intent_mod = importlib.import_module("sales_ivr.agents.intent_router")
    monkeypatch.setattr(
        intent_mod,
        "run_structured_agent",
        lambda **_: IntentResult(
            intent=Intent.NEW_QUOTE,
            confidence=0.4,
            route_to_handoff=False,
            ivr_message="I can help you with a quote.",
        ),
    )

    state = intent_router(build_initial_state(_session("Please let me talk to a human.")))

    assert state.route_to_handoff is True
    assert state.session.intent == Intent.SPEAK_TO_AGENT
    assert state.next_node.value == "handoff"
    assert "hold" in state.session.ivr_responses[-1].text.lower()


def test_handoff_puts_the_caller_on_hold_and_records_the_agent_number(monkeypatch):
    handoff_mod = importlib.import_module("sales_ivr.agents.handoff")
    monkeypatch.setattr(
        handoff_mod,
        "run_structured_agent",
        lambda **_: HandoffResult(
            summary="Caller asked to speak with a person.",
            recommended_queue=HandoffQueue.SALES,
            priority=2,
            ivr_message="Please stay on the line.",
        ),
    )
    session = _session("I need to speak to a real person.", dtmf="0")
    session.intent = Intent.SPEAK_TO_AGENT

    state = handoff(build_initial_state(session))

    assert state.session.handoff is not None
    assert state.session.handoff.on_hold is True
    assert state.session.handoff.transfer_phone == "+16108126519"
    assert state.session.ivr_responses[-1].text == "Please hold while I connect you to an agent."
    assert state.session.ivr_responses[-1].prompt_type == "hold"


def test_launch_human_call_opens_teams_when_it_is_installed(monkeypatch):
    opened = []
    monkeypatch.setattr(transfer, "_teams_installed", lambda: True)
    monkeypatch.setattr(transfer, "_bring_call_window_forward", lambda: None)
    monkeypatch.setattr(transfer.os, "startfile", lambda target: opened.append(target), raising=False)

    target = transfer.launch_human_call()

    assert target.startswith("msteams:")
    assert "+16108126519" in target
    assert opened == [target]


def test_launch_human_call_uses_tel_when_teams_is_missing(monkeypatch):
    opened = []
    monkeypatch.setattr(transfer, "_teams_installed", lambda: False)
    monkeypatch.setattr(transfer, "_bring_call_window_forward", lambda: None)
    monkeypatch.setattr(transfer.os, "startfile", lambda target: opened.append(target), raising=False)

    assert transfer.launch_human_call() == "tel:+16108126519"
    assert opened == ["tel:+16108126519"]


def test_call_button_endpoint_dials_the_agent_line(monkeypatch):
    from fastapi.testclient import TestClient

    from sales_ivr.web import app as web_app

    opened = []
    monkeypatch.setattr(
        web_app,
        "launch_human_call",
        lambda: opened.append("tel:+16108126519") or "tel:+16108126519",
    )
    response = TestClient(web_app.app).post("/api/call/human")

    assert response.status_code == 200
    assert response.json()["status"] == "calling"
    assert response.json()["destination_display"] == "610-812-6519"
    assert opened == ["tel:+16108126519"]
