from sales_ivr.web import chat_service
from sales_ivr.web.chat_service import (
    ConversationTurn,
    _build_call_session,
    create_chat,
    handle_user_message,
    run_pending_quote,
    speak_money,
    spoken_quote_reply,
)


def _result(monthly: float, details: str) -> dict:
    return {
        "status": "quote_accepted",
        "quote": {"monthly": monthly, "annual": monthly * 12},
        "customer_reply": f"Updated quote for {details}: ${monthly:.2f}/month",
        "customer_summary": {"headline": "Your quote is ready"},
        "session_json": {"channel": "web_chat"},
    }


def test_agent_handles_arbitrary_message_without_scripted_steps(monkeypatch):
    chat = create_chat()
    monkeypatch.setattr(
        chat_service,
        "run_conversation_agent",
        lambda _: ConversationTurn(
            reply="I can help with insurance, and yes—California has many coastal climates.",
        )
    )

    out = handle_user_message(chat, "Is California always warm?")

    assert out["reply"].startswith("I can help")
    assert out["done"] is False
    assert out["quote_ready"] is False
    assert out["pipeline_pending"] is False
    assert out["step"] == "agent_online"
    assert chat.messages[-2]["content"] == "Is California always warm?"


def test_agent_can_collect_everything_in_one_message_and_run_quote(monkeypatch):
    chat = create_chat()
    monkeypatch.setattr(
        chat_service,
        "run_conversation_agent",
        lambda _: ConversationTurn(
            reply="I have everything I need.",
            phone="555-123-4001",
            state="California",
            zip_code="90210",
            insurance_need="A preliminary personal auto insurance quote",
            quote_details="Driver age 40, 2019 vehicle, 9,000 annual miles",
            run_pipeline=True,
        ),
    )

    def fake_pipeline(current):
        call = _build_call_session(current)
        transcript = " ".join(item.text for item in call.utterances)
        assert "2019 vehicle" in transcript
        return _result(123.84, current.quote_details or "")

    monkeypatch.setattr(chat_service, "run_pipeline_for_chat", fake_pipeline)

    pending = handle_user_message(
        chat,
        "Quote me for auto: I am 40, have a 2019 car, drive 9,000 miles, "
        "live at 90210 CA, and my phone is 555-123-4001.",
    )

    assert pending["pipeline_pending"] is True
    assert pending["quote_ready"] is False
    assert pending["result"] is None
    assert pending["step"] == "preparing_quote"
    assert chat.context()["phone"] == "15551234001"

    out = run_pending_quote(chat)

    assert out["quote_ready"] is True
    assert out["pipeline_pending"] is False
    assert out["quote_revision"] == 1
    assert out["step"] == "quote_ready"
    assert out["result"]["quote"]["monthly"] == 123.84
    assert "on the right" in out["reply"].lower()


def test_agent_modifies_details_and_reruns_full_quote(monkeypatch):
    chat = create_chat()
    turns = iter(
        [
            ConversationTurn(
                reply="Running your first quote.",
                phone="555-123-4001",
                state="CA",
                zip_code="90210",
                insurance_need="Personal auto insurance quote",
                quote_details="Driver age 40, 2019 vehicle, 9,000 annual miles",
                run_pipeline=True,
            ),
            ConversationTurn(
                reply="I updated the vehicle and mileage.",
                phone="15551234001",
                state="CA",
                zip_code="90210",
                insurance_need="Personal auto insurance quote",
                quote_details="Driver age 40, 2022 vehicle, 15,000 annual miles",
                run_pipeline=True,
                change_summary="Vehicle year 2019 → 2022; mileage 9,000 → 15,000",
            ),
        ]
    )
    monkeypatch.setattr(chat_service, "run_conversation_agent", lambda _: next(turns))

    calls: list[str] = []

    def fake_pipeline(current):
        call = _build_call_session(current)
        transcript = " ".join(item.text for item in call.utterances)
        calls.append(transcript)
        monthly = 140.0 if "2022 vehicle" in transcript else 123.84
        return _result(monthly, current.quote_details or "")

    monkeypatch.setattr(chat_service, "run_pipeline_for_chat", fake_pipeline)

    first_pending = handle_user_message(chat, "Please make my quote.")
    assert first_pending["pipeline_pending"] is True
    first = run_pending_quote(chat)

    revised_pending = handle_user_message(
        chat, "Actually it is a 2022 vehicle and I drive 15,000 miles. Re-run it."
    )
    assert revised_pending["pipeline_pending"] is True
    revised = run_pending_quote(chat)

    assert first["result"]["quote"]["monthly"] == 123.84
    assert revised["result"]["quote"]["monthly"] == 140.0
    assert revised["quote_revision"] == 2
    assert len(chat.quote_history) == 1
    assert chat.quote_history[0]["quote"]["monthly"] == 123.84
    assert "2022 vehicle" in calls[1]
    assert "2019 vehicle" not in calls[1]
    assert revised["done"] is False


def test_pipeline_request_is_blocked_until_required_context_exists(monkeypatch):
    chat = create_chat()
    monkeypatch.setattr(
        chat_service,
        "run_conversation_agent",
        lambda _: ConversationTurn(
            reply="Let me quote that.",
            insurance_need="Renters insurance",
            run_pipeline=True,
        ),
    )

    out = handle_user_message(chat, "Give me a renters quote")

    assert out["quote_ready"] is False
    assert out["pipeline_pending"] is False
    assert out["result"] is None
    assert "phone number" in out["reply"]
    assert "state" in out["reply"]
    assert "ZIP code" in out["reply"]


def test_speak_money_reads_dollars_and_cents():
    assert speak_money(1) == "1 dollar"
    assert speak_money(123.84) == "123 dollars and 84 cents"
    assert speak_money(10.5) == "10 dollars and 50 cents"


def test_voice_session_speaks_the_quote_and_marks_the_call_channel(monkeypatch):
    chat = create_chat(channel="voice")
    assert "What can I help you with?" in chat.messages[-1]["content"]
    monkeypatch.setattr(
        chat_service,
        "run_conversation_agent",
        lambda _: ConversationTurn(
            reply="I have what I need. I'll price auto coverage for you.",
            phone="555-123-4001",
            state="CA",
            zip_code="90210",
            insurance_need="Personal auto insurance",
            quote_details="2020 sedan, 12000 miles a year",
            run_pipeline=True,
        ),
    )
    monkeypatch.setattr(
        chat_service,
        "run_pipeline_for_chat",
        lambda current: _result(118.4, current.quote_details or ""),
    )

    pending = handle_user_message(chat, "Quote my car", channel="voice")
    assert pending["pipeline_pending"] is True
    assert chat.channel == "voice"

    out = run_pending_quote(chat)
    assert _build_call_session(chat).channel.value == "voice"
    assert "118 dollars and 40 cents" in out["reply"]
    assert "a month" in out["reply"]
    assert "on the right" not in out["reply"].lower()
    assert "preliminary estimate" in out["reply"].lower()


def test_voice_start_endpoint_uses_a_spoken_greeting():
    from fastapi.testclient import TestClient

    from sales_ivr.web.app import app

    client = TestClient(app)
    voice = client.post("/api/chat/start?channel=voice")
    assert voice.status_code == 200
    assert "What can I help you with?" in voice.json()["reply"]

    typed = client.post("/api/chat/start")
    assert typed.status_code == 200
    assert "Welcome to Firstpass Quotes" in typed.json()["reply"]

    rejected = client.post("/api/chat/start?channel=sms")
    assert rejected.status_code == 422


def test_spoken_quote_without_a_price_stays_short():
    text = spoken_quote_reply(
        {
            "customer_summary": {"headline": "Quote pipeline unavailable — returning your input"},
            "quote": None,
        }
    )
    assert "priced quote" in text
    assert "audit" not in text.lower()
