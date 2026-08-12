from enum import StrEnum


class CallerType(StrEnum):
    NEW_PROSPECT = "new_prospect"
    RETURNING_CUSTOMER = "returning_customer"
    POLICYHOLDER = "policyholder"
    UNKNOWN = "unknown"


class CallChannel(StrEnum):
    VOICE = "voice"
    SMS = "sms"
    WEB_CHAT = "web_chat"


class Intent(StrEnum):
    NEW_QUOTE = "new_quote"
    POLICY_CHANGE = "policy_change"
    CLAIMS_INQUIRY = "claims_inquiry"
    BILLING = "billing"
    SPEAK_TO_AGENT = "speak_to_agent"
    UNKNOWN = "unknown"


class ProductLine(StrEnum):
    AUTO = "auto"
    HOME = "home"
    LIFE = "life"
    RENTERS = "renters"
    UMBRELLA = "umbrella"
    MOTORCYCLE = "motorcycle"
    BOAT = "boat"
    COMMERCIAL = "commercial"


class SessionStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    QUOTE_ACCEPTED = "quote_accepted"
    HANDOFF = "handoff"
    ABANDONED = "abandoned"
    FAILED = "failed"


class OrchestratorNode(StrEnum):
    CALL_INTAKE = "call_intake"
    CALLER_ID = "caller_id"
    INTENT_ROUTER = "intent_router"
    PRODUCT_RECOMMENDATION = "product_recommendation"
    QUOTE_GENERATION = "quote_generation"
    COMPLIANCE = "compliance"
    OBJECTION_HANDLING = "objection_handling"
    HANDOFF = "handoff"


class HandoffQueue(StrEnum):
    SALES = "sales"
    SERVICE = "service"
    CLAIMS = "claims"
    BILLING = "billing"
