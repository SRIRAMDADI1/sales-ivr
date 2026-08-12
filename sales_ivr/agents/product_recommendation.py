"""ProductRecommendationAgent — LLM agent with catalog tools."""

from __future__ import annotations

from pydantic import BaseModel, Field

from sales_ivr.agents.context import session_snapshot
from sales_ivr.llm import run_structured_agent
from sales_ivr.models import AgentHandoff, IVRResponse, IVRState, RecommendedProduct
from sales_ivr.models.enums import OrchestratorNode, ProductLine


class ProductRecResult(BaseModel):
    recommended_products: list[RecommendedProduct] = Field(default_factory=list)
    selected_product_id: str | None = None
    route_to_handoff: bool = False
    ivr_message: str = ""
    notes: str = ""


SYSTEM = """You are ProductRecommendationAgent for an insurance sales IVR.
Use list_products filtered by caller state and product_line_hint.
Return a ranked recommended_products list (id, line, name, score 0-1, rationale).
Set selected_product_id to the top recommendation.
If nothing is eligible, set route_to_handoff=true.
Return JSON only.
"""


def product_recommendation(state: IVRState) -> IVRState:
    session = state.session
    result = run_structured_agent(
        agent_name="ProductRecommendationAgent",
        system_prompt=SYSTEM,
        user_payload=session_snapshot(state),
        output_model=ProductRecResult,
        state=state,
        enable_tools=True,
    )

    session.recommended_products = result.recommended_products[:5]
    session.selected_product_id = result.selected_product_id
    if result.route_to_handoff or not session.selected_product_id:
        state.route_to_handoff = True

    session.ivr_responses.append(
        IVRResponse(
            text=result.ivr_message
            or (
                "I couldn't find an eligible product."
                if state.route_to_handoff
                else f"I recommend product {session.selected_product_id}."
            ),
            node=OrchestratorNode.PRODUCT_RECOMMENDATION,
            prompt_type="handoff" if state.route_to_handoff else "recommendation",
        )
    )
    to_node = (
        OrchestratorNode.HANDOFF
        if state.route_to_handoff
        else OrchestratorNode.QUOTE_GENERATION
    )
    state.append_audit(
        OrchestratorNode.PRODUCT_RECOMMENDATION,
        "failed" if state.route_to_handoff else "success",
        result.notes or f"selected={session.selected_product_id}",
        count=len(session.recommended_products),
    )
    state.handoffs.append(
        AgentHandoff(
            from_node=OrchestratorNode.PRODUCT_RECOMMENDATION,
            to_node=to_node,
            reason="no_eligible_products" if state.route_to_handoff else "product_selected",
        )
    )
    return state
