from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sales_ivr.config import load_config, resolve_path
from sales_ivr.fixtures.loader import build_initial_state, list_fixtures, load_session_fixture
from sales_ivr.llm import reset_llm_client
from sales_ivr.models import IVRState
from sales_ivr.orchestrator import run_session
from sales_ivr.runtime import clear_resource_cache


def _coerce_state(result: IVRState | dict) -> IVRState:
    if isinstance(result, IVRState):
        return result
    return IVRState.model_validate(result)


def run_batch(
    fixtures: list[Path],
    reports_dir: Path,
    *,
    experiment: str | None = None,
) -> dict:
    reports_dir.mkdir(parents=True, exist_ok=True)
    runs = []
    for fixture_path in fixtures:
        clear_resource_cache()
        reset_llm_client()
        session = load_session_fixture(fixture_path)
        started = datetime.now(timezone.utc)
        result = _coerce_state(run_session(build_initial_state(session)))
        ended = datetime.now(timezone.utc)
        quote_monthly = (
            result.session.quote.quote_amount_monthly if result.session.quote else None
        )
        runs.append(
            {
                "fixture": fixture_path.name,
                "session_id": result.session.session_id,
                "status": result.session.status.value,
                "intent": result.session.intent.value,
                "product_id": result.session.selected_product_id,
                "quote_amount_monthly": quote_monthly,
                "handoff_queue": (
                    result.session.handoff.recommended_queue.value
                    if result.session.handoff
                    else None
                ),
                "llm_calls": len(result.llm_usage),
                "total_tokens": sum(u.total_tokens for u in result.llm_usage),
                "audit_nodes": [e.node.value for e in result.audit_trail],
                "duration_ms": int((ended - started).total_seconds() * 1000),
                "experiment": experiment,
            }
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_count": len(runs),
        "experiment": experiment,
        "runs": runs,
    }
    out_path = reports_dir / f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(out_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay IVR session fixtures")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--count", type=int, default=0, help="Limit fixtures (0 = all)")
    parser.add_argument(
        "--experiment",
        default=None,
        help="Optional experiment tag written into the batch report",
    )
    args = parser.parse_args()

    config_path = args.config
    if not config_path.exists():
        config_path = Path(__file__).resolve().parent / "config.yaml"
    config = load_config(config_path)
    fixtures_dir = resolve_path(config, config.paths.fixtures_dir)
    fixtures = list_fixtures(fixtures_dir)
    if args.count > 0:
        fixtures = fixtures[: args.count]

    report = run_batch(fixtures, Path("reports"), experiment=args.experiment)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
