"""Shared session snapshot helpers for LLM agent prompts."""

from __future__ import annotations

from typing import Any

from sales_ivr.models.session import IVRState


def session_snapshot(state: IVRState) -> dict[str, Any]:
    s = state.session
    return {
        "session_id": s.session_id,
        "caller_phone": s.caller_phone,
        "channel": s.channel.value,
        "language": s.language,
        "caller_type": s.caller_type.value,
        "utterances": [{"turn": u.turn, "text": u.text, "confidence": u.confidence} for u in s.utterances],
        "dtmf_digits": s.dtmf_digits,
        "after_hours": s.after_hours,
        "caller_profile": s.caller_profile.model_dump(),
        "existing_policies": [p.model_dump(mode="json") for p in s.existing_policies],
        "intent": s.intent.value,
        "intent_confidence": s.intent_confidence,
        "product_line_hint": s.product_line_hint.value if s.product_line_hint else None,
        "recommended_products": [p.model_dump(mode="json") for p in s.recommended_products],
        "selected_product_id": s.selected_product_id,
        "quote": s.quote.model_dump(mode="json") if s.quote else None,
        "compliance": s.compliance.model_dump(mode="json") if s.compliance else None,
        "status": s.status.value,
        "objection_loop_count": state.objection_loop_count,
        "verification_attempts": state.verification_attempts,
        "verification_failed": state.verification_failed,
        "recalculate_quote": state.recalculate_quote,
        "route_to_handoff": state.route_to_handoff,
        "carrier_config_note": "Demo Insurance Co. supports CA, TX, NY, FL, IL",
    }
