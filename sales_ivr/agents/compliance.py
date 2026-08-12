"""ComplianceDisclosureAgent — LLM agent with compliance tool."""

from __future__ import annotations

from pydantic import BaseModel, Field

from sales_ivr.agents.context import session_snapshot
from sales_ivr.llm import run_structured_agent
from sales_ivr.models import AgentHandoff, ComplianceResult, IVRResponse, IVRState
from sales_ivr.models.enums import OrchestratorNode


class ComplianceAgentResult(BaseModel):
    disclosures_read: list[str] = Field(default_factory=list)
    compliance_passed: bool = False
    violations: list[str] = Field(default_factory=list)
    spoken_disclosure: str = ""
    route_to_handoff: bool = False
    notes: str = ""


SYSTEM = """You are ComplianceDisclosureAgent for an insurance sales IVR.
Use load_compliance for the caller's state.
Deliver required disclosures and check the quote ivr_script for prohibited phrases.
If violations exist or disclosures cannot be loaded, set compliance_passed=false and route_to_handoff=true.
Return the disclosure texts and a spoken_disclosure combining them for the caller.
"""


def compliance(state: IVRState) -> IVRState:
    session = state.session
    result = run_structured_agent(
        agent_name="ComplianceDisclosureAgent",
        system_prompt=SYSTEM,
        user_payload=session_snapshot(state),
        output_model=ComplianceAgentResult,
        state=state,
        enable_tools=True,
    )

    session.compliance = ComplianceResult(
        disclosures_read=result.disclosures_read,
        compliance_passed=result.compliance_passed,
        violations=result.violations,
    )
    if result.route_to_handoff or not result.compliance_passed:
        state.route_to_handoff = True

    if result.spoken_disclosure:
        session.ivr_responses.append(
            IVRResponse(
                text=result.spoken_disclosure,
                node=OrchestratorNode.COMPLIANCE,
                prompt_type="disclosure",
            )
        )
    if state.route_to_handoff:
        session.ivr_responses.append(
            IVRResponse(
                text="I need to transfer you to a licensed agent to complete this quote.",
                node=OrchestratorNode.COMPLIANCE,
                prompt_type="handoff",
            )
        )

    to_node = (
        OrchestratorNode.HANDOFF
        if state.route_to_handoff
        else OrchestratorNode.OBJECTION_HANDLING
    )
    state.append_audit(
        OrchestratorNode.COMPLIANCE,
        "success" if result.compliance_passed else "failed",
        result.notes or f"compliance_passed={result.compliance_passed}",
        violations=result.violations,
    )
    state.handoffs.append(
        AgentHandoff(
            from_node=OrchestratorNode.COMPLIANCE,
            to_node=to_node,
            reason="disclosures_complete" if result.compliance_passed else "compliance_failed",
        )
    )
    return state
