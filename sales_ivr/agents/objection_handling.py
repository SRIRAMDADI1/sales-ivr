"""ObjectionHandlingAgent — LLM agent that may loop quotes or escalate."""

from __future__ import annotations

from pydantic import BaseModel, Field

from sales_ivr.agents.context import session_snapshot
from sales_ivr.llm import run_structured_agent
from sales_ivr.models import AgentHandoff, IVRResponse, IVRState
from sales_ivr.models.enums import OrchestratorNode, SessionStatus
from sales_ivr.runtime import get_config


class ObjectionResult(BaseModel):
    objection_type: str | None = None  # price | coverage | competitor | none
    quote_accepted: bool = False
    recalculate_quote: bool = False
    route_to_handoff: bool = False
    ivr_message: str = ""
    notes: str = ""


SYSTEM = """You are ObjectionHandlingAgent for an insurance sales IVR.
Detect objections from caller utterances (price, coverage, competitor) or acceptance.
If the caller accepts (yes/proceed/sounds good/I'll take it), set quote_accepted=true.
If price objection and objection_loop_count is below max allowed, set recalculate_quote=true
(and optionally use load_objection_playbook).
Otherwise escalate with route_to_handoff=true.
Return JSON only.
"""


def objection_handling(state: IVRState) -> IVRState:
    session = state.session
    payload = session_snapshot(state)
    payload["max_objection_loops"] = get_config().runtime.max_objection_loops

    result = run_structured_agent(
        agent_name="ObjectionHandlingAgent",
        system_prompt=SYSTEM,
        user_payload=payload,
        output_model=ObjectionResult,
        state=state,
        enable_tools=True,
    )

    session.ivr_responses.append(
        IVRResponse(
            text=result.ivr_message or "Thank you.",
            node=OrchestratorNode.OBJECTION_HANDLING,
            prompt_type=(
                "confirmation"
                if result.quote_accepted
                else "objection"
                if result.recalculate_quote
                else "handoff"
            ),
        )
    )

    if result.quote_accepted:
        session.status = SessionStatus.QUOTE_ACCEPTED
        state.recalculate_quote = False
        state.route_to_handoff = False
        state.append_audit(
            OrchestratorNode.OBJECTION_HANDLING,
            "success",
            result.notes or "quote accepted",
        )
        state.handoffs.append(
            AgentHandoff(
                from_node=OrchestratorNode.OBJECTION_HANDLING,
                to_node=OrchestratorNode.OBJECTION_HANDLING,
                reason="quote_accepted",
            )
        )
        return state

    max_loops = get_config().runtime.max_objection_loops
    if result.recalculate_quote and state.objection_loop_count < max_loops:
        state.objection_loop_count += 1
        state.recalculate_quote = True
        state.route_to_handoff = False
        state.append_audit(
            OrchestratorNode.OBJECTION_HANDLING,
            "success",
            result.notes or f"recalculating quote loop={state.objection_loop_count}",
        )
        state.handoffs.append(
            AgentHandoff(
                from_node=OrchestratorNode.OBJECTION_HANDLING,
                to_node=OrchestratorNode.QUOTE_GENERATION,
                reason="recalculate_quote",
            )
        )
        return state

    state.recalculate_quote = False
    state.route_to_handoff = True
    state.append_audit(
        OrchestratorNode.OBJECTION_HANDLING,
        "success",
        result.notes or "escalating objection to handoff",
        objection_type=result.objection_type,
    )
    state.handoffs.append(
        AgentHandoff(
            from_node=OrchestratorNode.OBJECTION_HANDLING,
            to_node=OrchestratorNode.HANDOFF,
            reason=f"objection_{result.objection_type or 'unknown'}",
        )
    )
    return state
