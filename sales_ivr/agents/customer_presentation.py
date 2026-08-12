"""CustomerPresentationAgent — turns pipeline JSON into customer-facing copy."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from sales_ivr.llm import run_structured_agent
from sales_ivr.models import IVRState


class CustomerFacingSummary(BaseModel):
    """What a customer should see after the quote pipeline finishes."""

    headline: str
    body: str = Field(description="Plain-language summary for the customer (2–5 short paragraphs).")
    highlights: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "This is a preliminary, non-binding estimate. Final rates depend on "
        "underwriting, eligibility, and state requirements."
    )


SYSTEM = """You are CustomerPresentationAgent for Firstpass Quotes.
Your job: rewrite internal Sales IVR pipeline JSON into clear, friendly copy
a retail insurance customer would want to read.

Rules:
- Speak directly to the customer ("you"), warm and professional.
- Never mention agents, pipelines, tokens, LLM calls, audit trails, or internal node names.
- If a quote exists, lead with the monthly and annual price and what is covered.
- If this is a handoff (claims/billing/speak-to-agent), explain who will help next and what to expect.
- Keep body to 2–5 short paragraphs. Highlights should be 2–5 crisp bullets.
- Include a short non-binding disclaimer.
- Return ONLY JSON matching the schema.
"""


def present_pipeline_result(
    pipeline_payload: dict[str, Any],
    *,
    state: IVRState,
) -> CustomerFacingSummary:
    """LLM agent that converts pipeline output into customer-facing summary."""

    from sales_ivr.llm.client import azure_llm_enabled

    if not azure_llm_enabled():
        return passthrough_customer_summary(pipeline_payload)

    # Strip internal-only fields so the model focuses on customer facts.
    customer_view = {
        "status": pipeline_payload.get("status"),
        "intent": pipeline_payload.get("intent"),
        "caller_type": pipeline_payload.get("caller_type"),
        "customer_id": pipeline_payload.get("customer_id"),
        "verified": pipeline_payload.get("verified"),
        "product_id": pipeline_payload.get("product_id"),
        "quote": pipeline_payload.get("quote"),
        "compliance_passed": pipeline_payload.get("compliance_passed"),
        "handoff": pipeline_payload.get("handoff"),
        "ivr_responses": pipeline_payload.get("ivr_responses"),
    }
    return run_structured_agent(
        agent_name="CustomerPresentationAgent",
        system_prompt=SYSTEM,
        user_payload=customer_view,
        output_model=CustomerFacingSummary,
        state=state,
        enable_tools=False,
        use_capable_model=True,
    )


def passthrough_customer_summary(pipeline_payload: dict[str, Any]) -> CustomerFacingSummary:
    """Echo session input when Azure LLM is not configured (no mock processing)."""

    from sales_ivr.llm.client import get_llm_unavailable_reason

    session = pipeline_payload.get("session_json") or {}
    utterances = session.get("utterances") or []
    lines = [u.get("text", "") for u in utterances if u.get("text")]
    echoed = "\n".join(lines) if lines else json_dumps_compact(session)
    profile = session.get("caller_profile") or {}
    reason = get_llm_unavailable_reason() or (
        "Azure OpenAI is not available (missing key, endpoint, or model deployment)."
    )
    highlights = [
        f"Phone: {session.get('caller_phone') or 'n/a'}",
        f"State: {profile.get('state') or 'n/a'}",
        f"ZIP: {profile.get('zip_code') or 'n/a'}",
    ]
    return CustomerFacingSummary(
        headline="Quote pipeline unavailable — returning your input",
        body=(
            f"No LLM quote pipeline ran.\n\nReason: {reason}\n\n"
            "Here is the session input that would have been processed:\n\n"
            f"{echoed}"
        ),
        highlights=highlights,
        next_steps=[
            "Confirm AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT in sales-ivr/.env",
            "In Azure AI Foundry / OpenAI Studio, deploy a model "
            "(deployment name must match config.yaml → llm.deployment)",
            "Wait a few minutes after creating a new deployment, then restart the app",
        ],
        disclaimer=(
            "Passthrough mode: input was returned as output because Azure OpenAI "
            "could not run (credentials and/or deployment)."
        ),
    )


def json_dumps_compact(data: Any) -> str:
    import json

    return json.dumps(data, indent=2, default=str)


def fallback_customer_summary(pipeline_payload: dict[str, Any]) -> CustomerFacingSummary:
    """Deterministic copy if the presentation agent fails."""

    quote = pipeline_payload.get("quote")
    handoff = pipeline_payload.get("handoff")
    if quote:
        monthly = float(quote.get("monthly") or 0)
        annual = float(quote.get("annual") or 0)
        summary = quote.get("summary") or "coverage tailored to your answers"
        return CustomerFacingSummary(
            headline="Your first pass is ready",
            body=(
                f"Thanks for chatting with Firstpass. Based on what you shared, "
                f"your estimated premium is ${monthly:.2f} per month "
                f"(${annual:.2f} per year).\n\n"
                f"This estimate covers: {summary}. "
                "A licensed specialist can confirm eligibility and finalize your options."
            ),
            highlights=[
                f"${monthly:.2f}/month estimated premium",
                f"${annual:.2f}/year estimated premium",
                f"Product: {pipeline_payload.get('product_id') or 'selected coverage'}",
            ],
            next_steps=[
                "Review the estimate and coverage highlights below.",
                "Reply or call us when you are ready to bind a policy.",
                "Ask any questions about deductibles, discounts, or other products.",
            ],
        )
    if handoff:
        queue = handoff.get("queue") or "service"
        return CustomerFacingSummary(
            headline="We're connecting you with the right specialist",
            body=(
                f"Thanks for reaching out to Firstpass. Based on your request, "
                f"we're routing you to our {queue} team.\n\n"
                f"{handoff.get('summary') or 'A specialist will follow up shortly.'}"
            ),
            highlights=[
                f"Routed to: {queue} team",
                f"Priority: {handoff.get('priority', 'standard')}",
            ],
            next_steps=[
                "Keep your phone nearby for a callback if needed.",
                "Have your policy or claim details ready if you have them.",
            ],
        )
    return CustomerFacingSummary(
        headline="Thanks for contacting Firstpass",
        body=(
            "We've finished reviewing your request. "
            "A team member can help with next steps if you still need assistance."
        ),
        highlights=[],
        next_steps=["Start a new chat anytime for another quote."],
    )


def format_customer_reply(summary: CustomerFacingSummary) -> str:
    parts = [summary.headline, "", summary.body]
    if summary.highlights:
        parts.append("")
        parts.append("Highlights:")
        parts.extend(f"• {item}" for item in summary.highlights)
    if summary.next_steps:
        parts.append("")
        parts.append("Next steps:")
        parts.extend(f"• {item}" for item in summary.next_steps)
    if summary.disclaimer:
        parts.append("")
        parts.append(summary.disclaimer)
    return "\n".join(parts).strip()
