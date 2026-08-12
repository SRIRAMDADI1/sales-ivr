"""QuoteGenerationAgent — LLM agent that collects factors and calls pricing tool."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from sales_ivr.agents.context import session_snapshot
from sales_ivr.llm import run_structured_agent
from sales_ivr.models import AgentHandoff, IVRResponse, IVRState, QuoteResult
from sales_ivr.models.enums import OrchestratorNode, ProductLine


class QuoteAgentResult(BaseModel):
    product_id: str
    product_line: ProductLine
    tier_id: str
    quote_amount_monthly: float
    quote_amount_annual: float
    coverage_summary: str
    ivr_script: str
    collected_factors: dict[str, float] = Field(default_factory=dict)
    route_to_handoff: bool = False
    notes: str = ""


SYSTEM = """You are QuoteGenerationAgent for an insurance sales IVR.
1) Use list_products to inspect the selected product, its tiers, and its required_factors.
2) Read the caller's real-world details out of the utterances and CRM record: a driver age in
   years, a vehicle model year, annual miles driven, a year built, and so on. Omit anything the
   caller never told you instead of guessing at it.
3) Choose the tier that fits what the caller asked for.
4) Call calculate_premium with product_id, tier_id, and rating_attributes holding those
   real-world values. Pass measurements, never multipliers: driver_age 40, vehicle_year 2019,
   annual_mileage 9000. Pricing owns the conversion to multipliers.
5) If recalculate_quote is true, lower the price by choosing a cheaper tier. Never restate the
   caller's attributes to make the number come out lower.
6) Use the returned rating_breakdown to explain what drove the price when it helps the caller.
7) Write an IVR-friendly spoken script under ~60 seconds, including monthly and annual amounts,
   and a non-binding disclaimer.
Report quote_amount_monthly and quote_amount_annual exactly as calculate_premium returned them,
and put the real-world values you used in collected_factors. Do not invent premiums.
"""


def quote_generation(state: IVRState) -> IVRState:
    session = state.session
    result = run_structured_agent(
        agent_name="QuoteGenerationAgent",
        system_prompt=SYSTEM,
        user_payload=session_snapshot(state),
        output_model=QuoteAgentResult,
        state=state,
        enable_tools=True,
        use_capable_model=True,
    )

    if result.route_to_handoff:
        state.route_to_handoff = True
        state.append_audit(
            OrchestratorNode.QUOTE_GENERATION,
            "failed",
            result.notes or "quote failed",
        )
        state.handoffs.append(
            AgentHandoff(
                from_node=OrchestratorNode.QUOTE_GENERATION,
                to_node=OrchestratorNode.HANDOFF,
                reason="quote_failed",
            )
        )
        return state

    session.selected_product_id = result.product_id
    session.quote = QuoteResult(
        product_id=result.product_id,
        product_line=result.product_line,
        quote_amount_monthly=result.quote_amount_monthly,
        quote_amount_annual=result.quote_amount_annual,
        coverage_summary=result.coverage_summary,
        ivr_script=result.ivr_script,
        collected_factors=result.collected_factors,
    )
    state.recalculate_quote = False
    session.ivr_responses.append(
        IVRResponse(
            text=result.ivr_script,
            node=OrchestratorNode.QUOTE_GENERATION,
            prompt_type="quote",
        )
    )
    state.append_audit(
        OrchestratorNode.QUOTE_GENERATION,
        "success",
        result.notes
        or f"Quote ${result.quote_amount_monthly:.2f}/mo for {result.product_id}",
        monthly=result.quote_amount_monthly,
        annual=result.quote_amount_annual,
    )
    state.handoffs.append(
        AgentHandoff(
            from_node=OrchestratorNode.QUOTE_GENERATION,
            to_node=OrchestratorNode.COMPLIANCE,
            reason="quote_ready",
        )
    )
    return state
