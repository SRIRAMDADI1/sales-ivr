from __future__ import annotations

import argparse
import json
from pathlib import Path

from sales_ivr.config import load_config, resolve_path
from sales_ivr.fixtures.loader import build_initial_state, load_session_fixture
from sales_ivr.llm import reset_llm_client
from sales_ivr.models import IVRState
from sales_ivr.orchestrator import run_session
from sales_ivr.runtime import clear_resource_cache


def _coerce_state(result: IVRState | dict) -> IVRState:
    if isinstance(result, IVRState):
        return result
    return IVRState.model_validate(result)


def _print_summary(result: IVRState) -> None:
    session = result.session
    print(f"session_id: {session.session_id}")
    print(f"status: {session.status.value}")
    print(f"intent: {session.intent.value} ({session.intent_confidence:.2f})")
    print(f"caller_type: {session.caller_type.value}")
    if session.caller_profile.customer_id:
        print(
            f"customer: {session.caller_profile.customer_id} "
            f"(verified={session.caller_profile.verified})"
        )
    if session.selected_product_id:
        print(f"product: {session.selected_product_id}")
    if session.quote:
        print(
            f"quote: ${session.quote.quote_amount_monthly:.2f}/mo "
            f"(${session.quote.quote_amount_annual:.2f}/yr)"
        )
    if session.compliance:
        print(f"compliance_passed: {session.compliance.compliance_passed}")
    if session.handoff:
        print(
            f"handoff: queue={session.handoff.recommended_queue.value} "
            f"priority={session.handoff.priority}"
        )
        print(f"handoff_summary: {session.handoff.summary}")
    if result.llm_usage:
        total_tokens = sum(u.total_tokens for u in result.llm_usage)
        total_latency = sum(u.latency_ms for u in result.llm_usage)
        print(
            f"llm_calls: {len(result.llm_usage)}  "
            f"total_tokens: {total_tokens}  latency_ms: {total_latency}"
        )
        for u in result.llm_usage:
            print(
                f"  - {u.agent_name}: tokens={u.total_tokens} "
                f"(in={u.prompt_tokens} out={u.completion_tokens}) "
                f"tools={u.tool_calls} model={u.model} {u.latency_ms}ms"
            )
    print(f"audit_entries: {len(result.audit_trail)}")
    for entry in result.audit_trail:
        print(f"  - {entry.node.value}: {entry.status} — {entry.message}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Sales IVR session fixture")
    parser.add_argument(
        "fixture",
        nargs="?",
        default="auto_quote_ca.json",
        help="Fixture filename under fixtures/sessions/",
    )
    parser.add_argument("--config", type=Path, default=None, help="Path to config.yaml")
    parser.add_argument("--json", action="store_true", help="Print full result JSON")
    args = parser.parse_args()

    clear_resource_cache()
    reset_llm_client()
    config_path = args.config or Path("config.yaml")
    if not config_path.exists():
        config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    config = load_config(config_path)
    fixtures_dir = resolve_path(config, config.paths.fixtures_dir)
    fixture_path = fixtures_dir / args.fixture
    session = load_session_fixture(fixture_path)
    result = _coerce_state(run_session(build_initial_state(session)))

    if args.json:
        print(json.dumps(result.model_dump(mode="json"), indent=2))
    else:
        _print_summary(result)


if __name__ == "__main__":
    main()
