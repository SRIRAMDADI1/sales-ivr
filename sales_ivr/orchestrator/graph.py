from __future__ import annotations

from typing import Literal

from langgraph.graph import END, StateGraph

from sales_ivr.agents.call_intake import call_intake
from sales_ivr.agents.caller_id import caller_id
from sales_ivr.agents.compliance import compliance
from sales_ivr.agents.handoff import handoff
from sales_ivr.agents.intent_router import intent_router
from sales_ivr.agents.objection_handling import objection_handling
from sales_ivr.agents.product_recommendation import product_recommendation
from sales_ivr.agents.quote_generation import quote_generation
from sales_ivr.models import IVRState
from sales_ivr.models.enums import SessionStatus


def _route_after_intent(
    state: IVRState,
) -> Literal["product_recommendation", "handoff"]:
    if state.route_to_handoff or state.verification_failed:
        return "handoff"
    return "product_recommendation"


def _route_after_product(
    state: IVRState,
) -> Literal["quote_generation", "handoff"]:
    if state.route_to_handoff:
        return "handoff"
    return "quote_generation"


def _route_after_quote(
    state: IVRState,
) -> Literal["compliance", "handoff"]:
    if state.route_to_handoff:
        return "handoff"
    return "compliance"


def _route_after_compliance(
    state: IVRState,
) -> Literal["objection_handling", "handoff"]:
    if state.route_to_handoff:
        return "handoff"
    return "objection_handling"


def _route_after_objection(
    state: IVRState,
) -> Literal["quote_generation", "handoff", "__end__"]:
    if state.recalculate_quote:
        return "quote_generation"
    if state.route_to_handoff or state.session.status == SessionStatus.HANDOFF:
        return "handoff"
    return "__end__"


def build_graph() -> StateGraph:
    """Compile the IVR orchestrator with LLM agent nodes."""

    graph = StateGraph(IVRState)

    graph.add_node("call_intake", call_intake)
    graph.add_node("caller_id", caller_id)
    graph.add_node("intent_router", intent_router)
    graph.add_node("product_recommendation", product_recommendation)
    graph.add_node("quote_generation", quote_generation)
    graph.add_node("compliance", compliance)
    graph.add_node("objection_handling", objection_handling)
    graph.add_node("handoff", handoff)

    graph.set_entry_point("call_intake")
    graph.add_edge("call_intake", "caller_id")
    graph.add_edge("caller_id", "intent_router")
    graph.add_conditional_edges("intent_router", _route_after_intent)
    graph.add_conditional_edges("product_recommendation", _route_after_product)
    graph.add_conditional_edges("quote_generation", _route_after_quote)
    graph.add_conditional_edges("compliance", _route_after_compliance)
    graph.add_conditional_edges("objection_handling", _route_after_objection)
    graph.add_edge("handoff", END)

    return graph


def compile_graph():
    return build_graph().compile()


def run_session(state: IVRState):
    """Run the agent graph, or return input unchanged when Azure LLM is unavailable."""

    from sales_ivr.llm.client import (
        azure_llm_enabled,
        is_deployment_unavailable_error,
        mark_deployment_unavailable,
    )

    if not azure_llm_enabled():
        # Zero mock processing: echo the input state as the output.
        return state
    app = compile_graph()
    try:
        return app.invoke(state)
    except Exception as exc:
        if is_deployment_unavailable_error(exc):
            mark_deployment_unavailable(
                f"Azure OpenAI deployment failed during the pipeline ({type(exc).__name__}: {exc})."
            )
            # Return the original input — do not keep a partial/failed graph result.
            return state
        raise
