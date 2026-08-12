"""LLM conversation agent → CallSession JSON → Sales IVR pipeline → customer summary."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from sales_ivr.agents.customer_presentation import (
    fallback_customer_summary,
    format_customer_reply,
    present_pipeline_result,
)
from sales_ivr.fixtures.loader import build_initial_state
from sales_ivr.llm import ChatMessage, get_llm_client, reset_llm_client
from sales_ivr.llm.client import get_llm_unavailable_reason, parse_json_content
from sales_ivr.models import CallSession, CallerProfile, CallerUtterance, IVRState
from sales_ivr.models.enums import CallChannel
from sales_ivr.orchestrator import run_session
from sales_ivr.runtime import clear_resource_cache


SUPPORTED_STATES = frozenset({"CA", "TX", "NY", "FL", "IL"})


PHONE_RE = re.compile(r"(\+?1?\s*[-.(]?\d{3}[-.)]?\s*\d{3}[-.]?\d{4})")
STATE_RE = re.compile(r"\b(CA|TX|NY|FL|IL|California|Texas|New York|Florida|Illinois)\b", re.I)
ZIP_RE = re.compile(r"\b(\d{5})(?:-\d{4})?\b")

STATE_MAP = {
    "california": "CA",
    "texas": "TX",
    "new york": "NY",
    "florida": "FL",
    "illinois": "IL",
}


class ConversationTurn(BaseModel):
    """Structured decision returned by the customer-facing conversation agent."""

    reply: str = Field(min_length=1)
    phone: str | None = None
    state: str | None = None
    zip_code: str | None = None
    insurance_need: str | None = None
    quote_details: str | None = None
    run_pipeline: bool = False
    change_summary: str | None = None


@dataclass
class ChatSession:
    session_id: str
    phone: str | None = None
    state: str | None = None
    zip_code: str | None = None
    insurance_need: str | None = None
    quote_details: str | None = None
    messages: list[dict[str, str]] = field(default_factory=list)
    pipeline_result: dict[str, Any] | None = None
    quote_history: list[dict[str, Any]] = field(default_factory=list)
    conversation_usage: list[dict[str, Any]] = field(default_factory=list)

    @property
    def step(self) -> str:
        """Compatibility field for API clients; the chat no longer has scripted steps."""

        return "quote_ready" if self.pipeline_result else "agent_online"

    def context(self) -> dict[str, Any]:
        return {
            "phone": self.phone,
            "state": self.state,
            "zip_code": self.zip_code,
            "insurance_need": self.insurance_need,
            "quote_details": self.quote_details,
            "has_quote": self.pipeline_result is not None,
            "quote_revision": len(self.quote_history) + (1 if self.pipeline_result else 0),
            "current_quote": (self.pipeline_result or {}).get("quote"),
        }


_SESSIONS: dict[str, ChatSession] = {}


def _normalize_phone(raw: str) -> str | None:
    match = PHONE_RE.search(raw)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    if len(digits) == 10:
        digits = "1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return digits
    return None


def _normalize_state(raw: str) -> str | None:
    match = STATE_RE.search(raw)
    if not match:
        return None
    token = match.group(1)
    if len(token) == 2:
        return token.upper()
    return STATE_MAP.get(token.lower())


def _extract_zip(raw: str) -> str | None:
    match = ZIP_RE.search(raw)
    return match.group(1) if match else None


CONVERSATION_SYSTEM = """You are FirstpassConversationAgent, the customer-facing insurance
assistant. You are a real conversational agent, not a form or scripted state machine.

Conversation rules:
- Respond naturally to whatever the customer says. You may answer harmless general questions,
  but stay honest about being an insurance quote assistant and gently return to their goal.
- Never force a fixed question order. Collect information in whatever order the customer offers.
- For a quote, you need a US phone number, one supported state (CA, TX, NY, FL, IL), ZIP code,
  the kind of insurance/help requested, and any rating details the customer wants considered.
- The state object below is authoritative. Return its complete current values, preserving prior
  facts unless the customer explicitly corrects or replaces them.
- `quote_details` is a concise consolidated description of current rating facts. When a customer
  changes a fact after a quote (for example, 2019 vehicle to 2022, or 9,000 miles to 15,000),
  rewrite quote_details so it contains the new value and not the obsolete one.
- Set run_pipeline=true only when the customer asks to create, show, update, revise, recalculate,
  or rerun a quote and all required contact/need fields are known. If something is missing, ask
  for it and leave run_pipeline=false.
- After a quote, keep conversing. Answer questions, accept corrections, and rerun when asked.
- Do not claim a quote was calculated in `reply`; the pipeline result will be shown separately.
- Do not invent customer facts. Null means no new value was learned.
- Return ONLY one JSON object matching the supplied schema.
"""


def _conversation_messages(chat: ChatSession) -> list[ChatMessage]:
    schema = ConversationTurn.model_json_schema()
    system = (
        f"{CONVERSATION_SYSTEM}\n\n"
        f"Current normalized state:\n{json.dumps(chat.context(), default=str)}\n\n"
        f"Output schema:\n{json.dumps(schema)}"
    )
    messages = [ChatMessage(role="system", content=system)]
    # Bound context growth while retaining enough turns to resolve corrections and references.
    messages.extend(
        ChatMessage(role=item["role"], content=item["content"])
        for item in chat.messages[-20:]
    )
    return messages


def run_conversation_agent(chat: ChatSession) -> ConversationTurn:
    """Ask the web conversation agent to answer and update the normalized context."""

    client = get_llm_client()
    messages = _conversation_messages(chat)
    result = client.chat(
        agent_name="FirstpassConversationAgent",
        messages=messages,
        response_format={"type": "json_object"},
    )
    if result.usage:
        chat.conversation_usage.append(result.usage.model_dump(mode="json"))
    try:
        return ConversationTurn.model_validate(parse_json_content(result.content))
    except (json.JSONDecodeError, ValidationError):
        messages.extend(
            [
                ChatMessage(role="assistant", content=result.content or ""),
                ChatMessage(
                    role="user",
                    content="Return only valid JSON matching the schema. Preserve the known state.",
                ),
            ]
        )
        repair = client.chat(
            agent_name="FirstpassConversationAgent",
            messages=messages,
            response_format={"type": "json_object"},
        )
        if repair.usage:
            chat.conversation_usage.append(repair.usage.model_dump(mode="json"))
        try:
            return ConversationTurn.model_validate(parse_json_content(repair.content))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise RuntimeError("The conversation agent returned invalid structured output.") from exc


def _apply_turn(chat: ChatSession, turn: ConversationTurn) -> None:
    """Apply validated values from the agent without letting malformed fields corrupt state."""

    if turn.phone:
        normalized_phone = _normalize_phone(turn.phone)
        if normalized_phone:
            chat.phone = normalized_phone
    if turn.state:
        normalized_state = _normalize_state(turn.state)
        if normalized_state in SUPPORTED_STATES:
            chat.state = normalized_state
    if turn.zip_code:
        normalized_zip = _extract_zip(turn.zip_code)
        if normalized_zip:
            chat.zip_code = normalized_zip
    if turn.insurance_need and turn.insurance_need.strip():
        chat.insurance_need = turn.insurance_need.strip()
    if turn.quote_details and turn.quote_details.strip():
        chat.quote_details = turn.quote_details.strip()


def _missing_quote_fields(chat: ChatSession) -> list[str]:
    required = {
        "phone number": chat.phone,
        "state": chat.state,
        "ZIP code": chat.zip_code,
        "insurance need": chat.insurance_need,
    }
    return [label for label, value in required.items() if not value]


def _next_quote_revision(chat: ChatSession) -> int:
    return len(chat.quote_history) + (2 if chat.pipeline_result is not None else 1)


def create_chat() -> ChatSession:
    chat = ChatSession(session_id=str(uuid.uuid4()))
    welcome = (
        "Welcome to Firstpass Quotes. I’m your AI quote agent, and this is your first pass—"
        "tell me what you need in your own words. You can give details in any order, ask "
        "questions, or change information after I prepare a quote.\n\n"
        "When you’re ready, ask me to run a pass on your quote. "
        "Demo tip: 555-123-4001 is an existing customer."
    )
    chat.messages.append({"role": "assistant", "content": welcome})
    _SESSIONS[chat.session_id] = chat
    return chat


def get_chat(session_id: str) -> ChatSession | None:
    return _SESSIONS.get(session_id)


def _build_call_session(chat: ChatSession) -> CallSession:
    utterances: list[CallerUtterance] = []
    turn = 0
    if chat.insurance_need:
        utterances.append(
            CallerUtterance(turn=turn, text=chat.insurance_need, confidence=0.98)
        )
        turn += 1
    if chat.quote_details:
        utterances.append(
            CallerUtterance(turn=turn, text=chat.quote_details, confidence=0.96)
        )
        turn += 1
    utterances.append(
        CallerUtterance(
            turn=turn,
            text=(
                "Yes, prepare this preliminary quote using the details above. "
                "I want to proceed with this estimate."
            ),
            confidence=0.99,
        )
    )

    phone = chat.phone or "15559876543"
    return CallSession(
        session_id=f"web-{chat.session_id[:8]}-r{_next_quote_revision(chat)}",
        caller_phone=phone,
        channel=CallChannel.WEB_CHAT,
        language="en-US",
        utterances=utterances,
        dtmf_digits="1",
        caller_profile=CallerProfile(
            zip_code=chat.zip_code,
            state=chat.state,
        ),
    )


def _coerce_state(result: IVRState | dict) -> IVRState:
    if isinstance(result, IVRState):
        return result
    return IVRState.model_validate(result)


def _build_pipeline_payload(result: IVRState, call: CallSession) -> dict[str, Any]:
    session = result.session
    payload: dict[str, Any] = {
        "status": session.status.value,
        "intent": session.intent.value,
        "intent_confidence": session.intent_confidence,
        "caller_type": session.caller_type.value,
        "customer_id": session.caller_profile.customer_id,
        "verified": session.caller_profile.verified,
        "product_id": session.selected_product_id,
        "quote": None,
        "compliance_passed": (
            session.compliance.compliance_passed if session.compliance else None
        ),
        "handoff": None,
        "llm_calls": len(result.llm_usage),
        "total_tokens": sum(u.total_tokens for u in result.llm_usage),
        "audit": [
            {"node": e.node.value, "status": e.status, "message": e.message}
            for e in result.audit_trail
        ],
        "session_json": call.model_dump(mode="json"),
        "ivr_responses": [r.text for r in session.ivr_responses],
        "customer_summary": None,
    }
    if session.quote:
        payload["quote"] = {
            "monthly": session.quote.quote_amount_monthly,
            "annual": session.quote.quote_amount_annual,
            "summary": session.quote.coverage_summary,
            "script": session.quote.ivr_script,
            "product_line": session.quote.product_line.value,
        }
    if session.handoff:
        payload["handoff"] = {
            "queue": session.handoff.recommended_queue.value,
            "priority": session.handoff.priority,
            "summary": session.handoff.summary,
        }
    return payload


def run_pipeline_for_chat(chat: ChatSession) -> dict[str, Any]:
    clear_resource_cache()
    reset_llm_client()
    call = _build_call_session(chat)
    result = _coerce_state(run_session(build_initial_state(call)))
    payload = _build_pipeline_payload(result, call)

    try:
        summary = present_pipeline_result(payload, state=result)
    except Exception:
        summary = fallback_customer_summary(payload)

    payload["customer_summary"] = summary.model_dump(mode="json")
    payload["llm_calls"] = len(result.llm_usage)
    payload["total_tokens"] = sum(u.total_tokens for u in result.llm_usage)
    payload["customer_reply"] = format_customer_reply(summary)
    payload["quote_revision"] = _next_quote_revision(chat)
    payload["conversation_context"] = chat.context()
    payload["conversation_llm_calls"] = len(chat.conversation_usage)
    return payload


def handle_user_message(chat: ChatSession, text: str) -> dict[str, Any]:
    """Run one open-ended agent turn. Quote pipeline runs separately when pending."""

    text = (text or "").strip()
    chat.messages.append({"role": "user", "content": text})
    pipeline_pending = False
    try:
        turn = run_conversation_agent(chat)
        _apply_turn(chat, turn)
        reply = turn.reply
        if turn.run_pipeline:
            missing = _missing_quote_fields(chat)
            if missing:
                reply = (
                    f"I can prepare that quote once I have your {', '.join(missing)}. "
                    "You can send those details in any order."
                )
            else:
                pipeline_pending = True
    except RuntimeError:
        reason = get_llm_unavailable_reason() or "the configured language model is unavailable"
        reply = (
            "I can’t run the conversational quote agent right now. "
            f"Reason: {reason} Restart the app after restoring the Azure model connection."
        )

    chat.messages.append({"role": "assistant", "content": reply})
    return {
        "session_id": chat.session_id,
        "reply": reply,
        "step": "preparing_quote" if pipeline_pending else chat.step,
        "done": False,
        "quote_ready": False,
        "pipeline_pending": pipeline_pending,
        "quote_revision": len(chat.quote_history) + (1 if chat.pipeline_result else 0),
        "context": chat.context(),
        "result": None,
    }


def run_pending_quote(chat: ChatSession) -> dict[str, Any]:
    """Run the Sales IVR quote pipeline after the conversation agent has queued a pass."""

    missing = _missing_quote_fields(chat)
    if missing:
        reply = (
            f"I can prepare that quote once I have your {', '.join(missing)}. "
            "You can send those details in any order."
        )
        chat.messages.append({"role": "assistant", "content": reply})
        return {
            "session_id": chat.session_id,
            "reply": reply,
            "step": chat.step,
            "done": False,
            "quote_ready": False,
            "pipeline_pending": False,
            "quote_revision": len(chat.quote_history) + (1 if chat.pipeline_result else 0),
            "context": chat.context(),
            "result": None,
        }

    previous_result = chat.pipeline_result
    updated_result = run_pipeline_for_chat(chat)
    if previous_result is not None:
        chat.quote_history.append(previous_result)
    chat.pipeline_result = updated_result
    updated_result["conversation_context"] = chat.context()
    # Keep chat history short; the right-hand panel owns the full customer summary.
    reply = "Your quote pass is ready — the summary is on the right."
    chat.messages.append({"role": "assistant", "content": reply})
    return {
        "session_id": chat.session_id,
        "reply": reply,
        "step": chat.step,
        "done": False,
        "quote_ready": True,
        "pipeline_pending": False,
        "quote_revision": len(chat.quote_history) + 1,
        "context": chat.context(),
        "result": chat.pipeline_result,
    }
