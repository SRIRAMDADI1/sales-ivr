"""HumanHandoffAgent — LLM agent that writes a warm-transfer summary."""

from __future__ import annotations

from pydantic import BaseModel, Field

from sales_ivr.agents.context import session_snapshot
from sales_ivr.llm import run_structured_agent
from sales_ivr.models import AgentHandoff, HandoffSummary, IVRResponse, IVRState
from sales_ivr.models.enums import HandoffQueue, OrchestratorNode, SessionStatus


class HandoffResult(BaseModel):
    summary: str
    recommended_queue: HandoffQueue = HandoffQueue.SERVICE
    priority: int = Field(default=3, ge=1, le=5)
    ivr_message: str = "Please stay on the line while I connect you to an agent."
    notes: str = ""


SYSTEM = """You are HumanHandoffAgent for an insurance sales IVR.
Produce a concise handoff summary for a licensed human agent including:
caller identity, verification status, intent, products/quote if any, compliance status, objections.
Choose recommended_queue: sales, service, claims, or billing.
Priority 1 (urgent) to 5 (low). Claims and verification failures should be higher priority (lower number).
Return JSON only.
"""


def handoff(state: IVRState) -> IVRState:
    session = state.session
    result = run_structured_agent(
        agent_name="HumanHandoffAgent",
        system_prompt=SYSTEM,
        user_payload=session_snapshot(state),
        output_model=HandoffResult,
        state=state,
        enable_tools=False,
        use_capable_model=True,
    )

    session.handoff = HandoffSummary(
        summary=result.summary,
        recommended_queue=result.recommended_queue,
        priority=result.priority,
    )
    session.status = SessionStatus.HANDOFF
    session.ivr_responses.append(
        IVRResponse(
            text=result.ivr_message,
            node=OrchestratorNode.HANDOFF,
            prompt_type="handoff",
        )
    )
    state.append_audit(
        OrchestratorNode.HANDOFF,
        "success",
        result.notes
        or f"Warm transfer to {result.recommended_queue.value} priority={result.priority}",
        summary=result.summary,
    )
    state.handoffs.append(
        AgentHandoff(
            from_node=OrchestratorNode.HANDOFF,
            to_node=OrchestratorNode.HANDOFF,
            reason="session_complete",
        )
    )
    return state
