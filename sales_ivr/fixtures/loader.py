from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sales_ivr.models import CallSession, CallerUtterance, IVRState


def load_session_fixture(path: Path) -> CallSession:
    data = json.loads(path.read_text(encoding="utf-8"))
    return CallSession.model_validate(data)


def session_from_fixture_dict(data: dict[str, Any]) -> CallSession:
    return CallSession.model_validate(data)


def build_initial_state(session: CallSession) -> IVRState:
    return IVRState(session=session)


def list_fixtures(fixtures_dir: Path) -> list[Path]:
    return sorted(fixtures_dir.glob("*.json"))
