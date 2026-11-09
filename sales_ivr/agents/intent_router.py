"""IntentRouterAgent — LLM classification of caller intent and routing."""

from __future__ import annotations

from pydantic import BaseModel, Field

from sales_ivr.agents.context import session_snapshot
from sales_ivr.llm import run_structured_agent
from sales_ivr.models import AgentHandoff, IVRResponse, IVRState
from sales_ivr.models.enums import Intent, OrchestratorNode, ProductLine
from sales_ivr.transfer import HOLD_MESSAGE, wants_human_agent


class IntentResult(BaseModel):
    intent: Intent = Intent.UNKNOWN
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    product_line_hint: ProductLine | None = None
    route_to_handoff: bool = False
    next_node: str = "product_recommendation"
    ivr_message: str = ""
    notes: str = ""


SYSTEM = f"""You are IntentRouterAgent for an insurance sales IVR.
Classify intent as one of: new_quote, policy_change, claims_inquiry, billing, speak_to_agent, unknown.
If dtmf_digits is "0", prefer speak_to_agent.
If verification_failed is true, set route_to_handoff=true and next_node=handoff.
Route speak_to_agent, claims_inquiry, billing, policy_change to handoff.
A caller who asks for a human, person, agent, representative, or operator is speak_to_agent.
Route new_quote to product_recommendation.
When the caller names a coverage, set product_line_hint to the closest line.
Lines: {", ".join(line.value for line in ProductLine)}.
Leave product_line_hint null when the caller does not name a coverage.
Return JSON only. Tools optional.
"""


def intent_router(state: IVRState) -> IVRState:
    session = state.session
    result = run_structured_agent(
        agent_name="IntentRouterAgent",
        system_prompt=SYSTEM,
        user_payload=session_snapshot(state),
        output_model=IntentResult,
        state=state,
        enable_tools=False,
    )

    session.intent = result.intent
    session.intent_confidence = result.confidence
    session.product_line_hint = result.product_line_hint
    asked_for_human = _caller_asked_for_human(session)

    if asked_for_human:
        session.intent = Intent.SPEAK_TO_AGENT
        session.intent_confidence = max(session.intent_confidence, 0.95)

    if state.verification_failed or result.route_to_handoff or asked_for_human:
        state.route_to_handoff = True
        to_node = OrchestratorNode.HANDOFF
        reason = "human_agent_requested" if asked_for_human else "fast_path_handoff"
    else:
        state.route_to_handoff = False
        to_node = OrchestratorNode.PRODUCT_RECOMMENDATION
        reason = "sales_path"

    state.next_node = to_node
    session.ivr_responses.append(
        IVRResponse(
            text=HOLD_MESSAGE
            if asked_for_human
            else result.ivr_message
            or (
                "I'll connect you with someone who can help."
                if state.route_to_handoff
                else "I can help you with a quote."
            ),
            node=OrchestratorNode.INTENT_ROUTER,
            prompt_type="handoff" if state.route_to_handoff else "information",
        )
    )
    state.append_audit(
        OrchestratorNode.INTENT_ROUTER,
        "success",
        result.notes or f"intent={session.intent.value} confidence={session.intent_confidence:.2f}",
        next_node=to_node.value,
    )
    state.handoffs.append(
        AgentHandoff(
            from_node=OrchestratorNode.INTENT_ROUTER,
            to_node=to_node,
            reason=reason,
        )
    )
    return state


def _caller_asked_for_human(session) -> bool:
    """DTMF 0 and spoken requests both leave the automated path."""

    if (session.dtmf_digits or "").strip() == "0":
        return True
    spoken = " ".join(utterance.text for utterance in session.utterances)
    return wants_human_agent(spoken)
