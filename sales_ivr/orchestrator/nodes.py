"""Node name registry for the Sales IVR orchestrator."""

from sales_ivr.models.enums import OrchestratorNode

NODE_REGISTRY: dict[OrchestratorNode, str] = {
    OrchestratorNode.CALL_INTAKE: "call_intake",
    OrchestratorNode.CALLER_ID: "caller_id",
    OrchestratorNode.INTENT_ROUTER: "intent_router",
    OrchestratorNode.PRODUCT_RECOMMENDATION: "product_recommendation",
    OrchestratorNode.QUOTE_GENERATION: "quote_generation",
    OrchestratorNode.COMPLIANCE: "compliance",
    OrchestratorNode.OBJECTION_HANDLING: "objection_handling",
    OrchestratorNode.HANDOFF: "handoff",
}
