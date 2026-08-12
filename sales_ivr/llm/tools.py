"""Tool implementations that LLM agents can call."""

from __future__ import annotations

import json
from typing import Any, Callable

from sales_ivr.catalog.loader import filter_by_line, filter_by_state, get_product
from sales_ivr.compliance.loader import load_state_compliance
from sales_ivr.models.enums import ProductLine
from sales_ivr.pricing.engine import PricingEngine
from sales_ivr.runtime import get_catalog, get_compliance_dir, get_crm, get_objection_corpus

ENGINE = PricingEngine()

ToolHandler = Callable[[dict[str, Any]], str]


def tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "lookup_crm",
                "description": "Look up a customer in the CRM by phone number.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phone": {"type": "string", "description": "Normalized caller phone"}
                    },
                    "required": ["phone"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_products",
                "description": "List insurance products, optionally filtered by state and product line.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "state": {"type": "string"},
                        "product_line": {
                            "type": "string",
                            "enum": [p.value for p in ProductLine],
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calculate_premium",
                "description": (
                    "Calculate a deterministic premium for a product and tier. Returns the "
                    "premium plus a per-attribute rating breakdown you can use to explain "
                    "the price or answer objections."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string"},
                        "tier_id": {"type": "string"},
                        "rating_attributes": {
                            "type": "object",
                            "additionalProperties": {"type": "number"},
                            "description": (
                                "Real-world values you gathered from the caller, keyed by the "
                                "product's required_factors. Pass actual measurements, not "
                                "multipliers: driver_age 40 means 40 years old, vehicle_year "
                                "2019 means a 2019 model, annual_mileage 9000 means 9,000 miles "
                                "a year. Pricing converts these to multipliers itself. Omit "
                                "anything the caller did not tell you rather than guessing."
                            ),
                        },
                    },
                    "required": ["product_id", "tier_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "load_compliance",
                "description": "Load state-specific disclosures and prohibited phrases.",
                "parameters": {
                    "type": "object",
                    "properties": {"state": {"type": "string"}},
                    "required": ["state"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "load_objection_playbook",
                "description": "Load objection-handling playbook text for price, coverage, or competitor.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "objection_type": {
                            "type": "string",
                            "enum": ["price", "coverage", "competitor"],
                        }
                    },
                    "required": ["objection_type"],
                },
            },
        },
    ]


def _lookup_crm(args: dict[str, Any]) -> str:
    phone = args.get("phone", "")
    for customer in get_crm().get("customers", []):
        if customer.get("phone") == phone:
            return json.dumps(customer)
    return json.dumps({"found": False, "phone": phone})


def _list_products(args: dict[str, Any]) -> str:
    products = list(get_catalog())
    state = args.get("state")
    line = args.get("product_line")
    if state:
        products = filter_by_state(products, state)
    if line:
        products = filter_by_line(products, ProductLine(line))
    payload = [
        {
            "product_id": p.product_id,
            "product_line": p.product_line.value,
            "name": p.name,
            "description": p.description,
            "eligible_states": p.eligible_states,
            "tiers": [
                {
                    "tier_id": t.tier_id,
                    "name": t.name,
                    "base_premium_monthly": t.base_premium_monthly,
                    "coverage_limit": t.coverage_limit,
                }
                for t in p.tiers
            ],
            "required_factors": p.required_factors,
        }
        for p in products
    ]
    return json.dumps(payload)


def _calculate_premium(args: dict[str, Any]) -> str:
    products = list(get_catalog())
    # "factors" is the older argument name; accept it so a model using it still gets priced.
    attributes = args.get("rating_attributes") or args.get("factors") or {}
    breakdown = ENGINE.calculate_for_product_id(
        products,
        args["product_id"],
        args["tier_id"],
        attributes,
    )
    return json.dumps(breakdown.as_tool_payload())


def _load_compliance(args: dict[str, Any]) -> str:
    state = args["state"].upper()
    try:
        pack = load_state_compliance(get_compliance_dir(), state)
        return pack.model_dump_json()
    except FileNotFoundError:
        return json.dumps({"error": f"No compliance pack for {state}"})


def _load_objection_playbook(args: dict[str, Any]) -> str:
    corpus = get_objection_corpus()
    key = args.get("objection_type", "price")
    return json.dumps({"objection_type": key, "playbook": corpus.get(key, "")})


HANDLERS: dict[str, ToolHandler] = {
    "lookup_crm": _lookup_crm,
    "list_products": _list_products,
    "calculate_premium": _calculate_premium,
    "load_compliance": _load_compliance,
    "load_objection_playbook": _load_objection_playbook,
}


def run_tool(name: str, arguments_json: str) -> str:
    handler = HANDLERS.get(name)
    if handler is None:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid tool arguments JSON"})
    try:
        return handler(args)
    except Exception as exc:  # noqa: BLE001 — surface tool errors to the agent
        return json.dumps({"error": str(exc)})
