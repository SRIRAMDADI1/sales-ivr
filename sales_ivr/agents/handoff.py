"""HumanHandoffAgent — LLM agent that writes a warm-transfer summary."""

from __future__ import annotations

from pydantic import BaseModel, Field

from sales_ivr.agents.context import session_snapshot
from sales_ivr.llm import run_structured_agent
from sales_ivr.models import AgentHandoff, HandoffSummary, IVRResponse, IVRState
from sales_ivr.models.enums import HandoffQueue, Intent, OrchestratorNode, SessionStatus
from sales_ivr.transfer import HOLD_MESSAGE, human_transfer_payload, wants_human_agent


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

    transfer = human_transfer_payload() if _should_dial_human(session) else None
    session.handoff = HandoffSummary(
        summary=result.summary,
        recommended_queue=result.recommended_queue,
        priority=result.priority,
        on_hold=transfer is not None,
        transfer_phone=transfer["destination_e164"] if transfer else None,
    )
    session.status = SessionStatus.HANDOFF
    session.ivr_responses.append(
        IVRResponse(
            text=HOLD_MESSAGE if transfer else result.ivr_message,
            node=OrchestratorNode.HANDOFF,
            prompt_type="hold" if transfer else "handoff",
        )
    )
    state.append_audit(
        OrchestratorNode.HANDOFF,
        "success",
        result.notes
        or (
            f"On hold, dialing {transfer['destination_display']}"
            if transfer
            else f"Warm transfer to {result.recommended_queue.value} priority={result.priority}"
        ),
        summary=result.summary,
        transfer_phone=session.handoff.transfer_phone,
    )
    state.handoffs.append(
        AgentHandoff(
            from_node=OrchestratorNode.HANDOFF,
            to_node=OrchestratorNode.HANDOFF,
            reason="session_complete",
        )
    )
    return state


def _should_dial_human(session) -> bool:
    if session.intent == Intent.SPEAK_TO_AGENT:
        return True
    if (session.dtmf_digits or "").strip() == "0":
        return True
    spoken = " ".join(utterance.text for utterance in session.utterances)
    return wants_human_agent(spoken)
