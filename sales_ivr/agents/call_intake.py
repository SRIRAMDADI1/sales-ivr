"""CallIntakeAgent — LLM agent that structures simulated call input."""

from __future__ import annotations

from pydantic import BaseModel, Field

from sales_ivr.agents.context import session_snapshot
from sales_ivr.llm import run_structured_agent
from sales_ivr.models import AgentHandoff, IVRResponse, IVRState
from sales_ivr.models.enums import CallerType, OrchestratorNode


class IntakeResult(BaseModel):
    caller_type: CallerType = CallerType.NEW_PROSPECT
    after_hours: bool = False
    ivr_message: str = "Thanks for calling. Let me pull up your information."
    notes: str = ""


SYSTEM = """You are CallIntakeAgent for an insurance sales IVR.
Parse the simulated caller utterances and DTMF into structured fields.
Infer caller_type: new_prospect, returning_customer, policyholder, or unknown.
Set after_hours if the call is outside business hours given in context (or guess evenings as after hours if unclear).
Return concise JSON only. Do not invent phone numbers.
Tools are optional; you usually do not need them for intake.
"""


def call_intake(state: IVRState) -> IVRState:
    session = state.session
    result = run_structured_agent(
        agent_name="CallIntakeAgent",
        system_prompt=SYSTEM,
        user_payload=session_snapshot(state),
        output_model=IntakeResult,
        state=state,
        enable_tools=False,
    )

    session.caller_type = result.caller_type
    session.after_hours = result.after_hours
    session.utterances = [u for u in session.utterances if u.text and u.text.strip()]
    session.ivr_responses.append(
        IVRResponse(
            text=result.ivr_message,
            node=OrchestratorNode.CALL_INTAKE,
            prompt_type="information",
        )
    )
    state.append_audit(
        OrchestratorNode.CALL_INTAKE,
        "success",
        result.notes or f"caller_type={session.caller_type.value}",
        after_hours=session.after_hours,
    )
    state.handoffs.append(
        AgentHandoff(
            from_node=OrchestratorNode.CALL_INTAKE,
            to_node=OrchestratorNode.CALLER_ID,
            reason="session_parsed",
        )
    )
    return state
