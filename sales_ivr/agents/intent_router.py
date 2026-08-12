"""IntentRouterAgent — LLM classification of caller intent and routing."""

from __future__ import annotations

from pydantic import BaseModel, Field

from sales_ivr.agents.context import session_snapshot
from sales_ivr.llm import run_structured_agent
from sales_ivr.models import AgentHandoff, IVRResponse, IVRState
from sales_ivr.models.enums import Intent, OrchestratorNode, ProductLine


class IntentResult(BaseModel):
    intent: Intent = Intent.UNKNOWN
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    product_line_hint: ProductLine | None = None
    route_to_handoff: bool = False
    next_node: str = "product_recommendation"
    ivr_message: str = ""
    notes: str = ""


SYSTEM = """You are IntentRouterAgent for an insurance sales IVR.
Classify intent as one of: new_quote, policy_change, claims_inquiry, billing, speak_to_agent, unknown.
If dtmf_digits is "0", prefer speak_to_agent.
If verification_failed is true, set route_to_handoff=true and next_node=handoff.
Route speak_to_agent, claims_inquiry, billing, policy_change to handoff.
Route new_quote to product_recommendation.
Infer product_line_hint when the caller mentions a product (auto, home, life, renters, etc.).
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

    if state.verification_failed or result.route_to_handoff:
        state.route_to_handoff = True
        to_node = OrchestratorNode.HANDOFF
        reason = "fast_path_handoff"
    else:
        state.route_to_handoff = False
        to_node = OrchestratorNode.PRODUCT_RECOMMENDATION
        reason = "sales_path"

    state.next_node = to_node
    session.ivr_responses.append(
        IVRResponse(
            text=result.ivr_message
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
