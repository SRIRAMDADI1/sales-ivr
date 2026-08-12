from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from sales_ivr.models.enums import (
    CallChannel,
    CallerType,
    HandoffQueue,
    Intent,
    OrchestratorNode,
    ProductLine,
    SessionStatus,
)

US_STATE_PATTERN = re.compile(r"^[A-Z]{2}$")
POLICY_ID_PATTERN = re.compile(r"^POL-[A-Z0-9]{6,12}$")
PHONE_PATTERN = re.compile(r"^\+?1?\d{10,11}$")


class CallerUtterance(BaseModel):
    """A single caller speech turn in the simulated IVR transcript."""

    turn: int = Field(ge=0)
    text: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    timestamp: datetime | None = None


class IVRResponse(BaseModel):
    """A scripted IVR prompt or response played to the caller."""

    text: str
    node: OrchestratorNode | None = None
    prompt_type: str = "information"


class AgentHandoff(BaseModel):
    """Structured handoff payload between orchestrator nodes (and future agents)."""

    from_node: OrchestratorNode
    to_node: OrchestratorNode
    reason: str
    payload_bytes: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditEntry(BaseModel):
    """Immutable log entry for a node execution in the session."""

    node: OrchestratorNode
    status: str
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMUsage(BaseModel):
    """Token/latency record for one LLM call."""

    agent_name: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    tool_calls: int = 0
    finish_reason: str | None = None


class ExistingPolicy(BaseModel):
    policy_id: str
    product_line: ProductLine
    status: str = "active"
    state: str

    @field_validator("policy_id")
    @classmethod
    def validate_policy_id(cls, value: str) -> str:
        if not POLICY_ID_PATTERN.match(value):
            raise ValueError("policy_id must match POL-XXXXXXXX format")
        return value

    @field_validator("state")
    @classmethod
    def validate_state(cls, value: str) -> str:
        upper = value.upper()
        if not US_STATE_PATTERN.match(upper):
            raise ValueError("state must be a 2-letter US code")
        return upper


class CallerProfile(BaseModel):
    customer_id: str | None = None
    verified: bool = False
    state: str | None = None
    age_band: str | None = None
    household_size: int | None = Field(default=None, ge=1)
    zip_code: str | None = None

    @field_validator("state")
    @classmethod
    def validate_state(cls, value: str | None) -> str | None:
        if value is None:
            return value
        upper = value.upper()
        if not US_STATE_PATTERN.match(upper):
            raise ValueError("state must be a 2-letter US code")
        return upper

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not re.match(r"^\d{5}(-\d{4})?$", value):
            raise ValueError("zip_code must be 5 or 9 digit US format")
        return value


class RecommendedProduct(BaseModel):
    product_id: str
    product_line: ProductLine
    name: str
    score: float = Field(ge=0.0, le=1.0)
    rationale: str


class QuoteResult(BaseModel):
    product_id: str
    product_line: ProductLine
    quote_amount_monthly: float = Field(ge=0)
    quote_amount_annual: float = Field(ge=0)
    coverage_summary: str
    ivr_script: str = ""
    collected_factors: dict[str, Any] = Field(default_factory=dict)


class ComplianceResult(BaseModel):
    disclosures_read: list[str] = Field(default_factory=list)
    compliance_passed: bool = False
    violations: list[str] = Field(default_factory=list)


class HandoffSummary(BaseModel):
    summary: str
    recommended_queue: HandoffQueue
    priority: int = Field(default=3, ge=1, le=5)


class CallSession(BaseModel):
    """Canonical call session — shared contract for all future agents."""

    session_id: str
    caller_phone: str
    channel: CallChannel = CallChannel.VOICE
    language: str = "en-US"
    caller_type: CallerType = CallerType.UNKNOWN
    utterances: list[CallerUtterance] = Field(default_factory=list)
    dtmf_digits: str = ""
    after_hours: bool = False
    caller_profile: CallerProfile = Field(default_factory=CallerProfile)
    existing_policies: list[ExistingPolicy] = Field(default_factory=list)
    intent: Intent = Intent.UNKNOWN
    intent_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    product_line_hint: ProductLine | None = None
    recommended_products: list[RecommendedProduct] = Field(default_factory=list)
    selected_product_id: str | None = None
    quote: QuoteResult | None = None
    compliance: ComplianceResult | None = None
    handoff: HandoffSummary | None = None
    status: SessionStatus = SessionStatus.IN_PROGRESS
    ivr_responses: list[IVRResponse] = Field(default_factory=list)

    @field_validator("caller_phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        normalized = re.sub(r"[\s\-().]", "", value)
        if not PHONE_PATTERN.match(normalized):
            raise ValueError("caller_phone must be a valid US phone number")
        return normalized


class IVRState(BaseModel):
    """LangGraph state object passed between orchestrator nodes."""

    session: CallSession
    next_node: OrchestratorNode | None = None
    objection_loop_count: int = 0
    verification_attempts: int = 0
    recalculate_quote: bool = False
    route_to_handoff: bool = False
    verification_failed: bool = False
    audit_trail: list[AuditEntry] = Field(default_factory=list)
    handoffs: list[AgentHandoff] = Field(default_factory=list)
    llm_usage: list[LLMUsage] = Field(default_factory=list)
    error: str | None = None

    def append_audit(
        self,
        node: OrchestratorNode,
        status: str,
        message: str,
        **metadata: Any,
    ) -> None:
        self.audit_trail.append(
            AuditEntry(node=node, status=status, message=message, metadata=metadata)
        )

    def record_usage(self, usage: LLMUsage) -> None:
        self.llm_usage.append(usage)


def export_json_schema(output_dir: Path) -> dict[str, Path]:
    """Export JSON schemas for core models (used by agents and fixtures)."""

    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, model in [
        ("CallSession", CallSession),
        ("IVRState", IVRState),
        ("CallerUtterance", CallerUtterance),
    ]:
        path = output_dir / f"{name}.schema.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2), encoding="utf-8")
        paths[name] = path
    return paths
