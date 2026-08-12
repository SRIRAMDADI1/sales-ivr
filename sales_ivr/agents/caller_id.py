"""CallerIdentificationAgent — LLM agent with CRM lookup tool."""

from __future__ import annotations

from pydantic import BaseModel, Field

from sales_ivr.agents.context import session_snapshot
from sales_ivr.llm import run_structured_agent
from sales_ivr.models import (
    AgentHandoff,
    CallerProfile,
    ExistingPolicy,
    IVRResponse,
    IVRState,
)
from sales_ivr.models.enums import CallerType, OrchestratorNode, ProductLine


class CallerIdResult(BaseModel):
    verified: bool = False
    verification_failed: bool = False
    customer_id: str | None = None
    caller_type: CallerType = CallerType.NEW_PROSPECT
    state: str | None = None
    zip_code: str | None = None
    age_band: str | None = None
    household_size: int | None = None
    policies: list[dict] = Field(default_factory=list)
    ivr_message: str = ""
    notes: str = ""


SYSTEM = """You are CallerIdentificationAgent for an insurance sales IVR.
Use the lookup_crm tool with the caller phone to find the customer.
If found, verify the provided ZIP against the CRM ZIP.
If ZIP mismatches, set verification_failed=true and verified=false.
If not found, treat as new_prospect with verified=false and keep provided state/zip.
Populate policies from CRM when present (policy_id, product_line, status, state).
Return JSON only.
"""


def caller_id(state: IVRState) -> IVRState:
    session = state.session
    result = run_structured_agent(
        agent_name="CallerIdentificationAgent",
        system_prompt=SYSTEM,
        user_payload=session_snapshot(state),
        output_model=CallerIdResult,
        state=state,
        enable_tools=True,
    )

    state.verification_attempts += 1
    state.verification_failed = result.verification_failed
    if result.verification_failed:
        state.route_to_handoff = True

    policies = []
    for p in result.policies:
        try:
            policies.append(
                ExistingPolicy(
                    policy_id=p["policy_id"],
                    product_line=ProductLine(p["product_line"]),
                    status=p.get("status", "active"),
                    state=p["state"],
                )
            )
        except Exception:
            continue

    session.existing_policies = policies
    session.caller_type = result.caller_type
    session.caller_profile = CallerProfile(
        customer_id=result.customer_id,
        verified=result.verified,
        state=result.state or session.caller_profile.state,
        age_band=result.age_band,
        household_size=result.household_size,
        zip_code=result.zip_code or session.caller_profile.zip_code,
    )
    session.ivr_responses.append(
        IVRResponse(
            text=result.ivr_message
            or (
                "I couldn't verify your account."
                if result.verification_failed
                else "Thanks, I have your information."
            ),
            node=OrchestratorNode.CALLER_ID,
            prompt_type="handoff" if result.verification_failed else "information",
        )
    )
    status = "failed" if result.verification_failed else "success"
    state.append_audit(
        OrchestratorNode.CALLER_ID,
        status,
        result.notes or f"verified={result.verified}",
    )
    to_node = (
        OrchestratorNode.HANDOFF
        if result.verification_failed
        else OrchestratorNode.INTENT_ROUTER
    )
    state.handoffs.append(
        AgentHandoff(
            from_node=OrchestratorNode.CALLER_ID,
            to_node=to_node,
            reason="verification_failed" if result.verification_failed else "caller_identified",
        )
    )
    return state
