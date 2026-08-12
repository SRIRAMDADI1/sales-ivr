from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class DisclosureRule(BaseModel):
    disclosure_id: str
    text: str
    required_before_quote_acceptance: bool = True


class StateCompliancePack(BaseModel):
    state: str
    disclosures: list[DisclosureRule] = Field(default_factory=list)
    prohibited_phrases: list[str] = Field(default_factory=list)


def load_state_compliance(compliance_dir: Path, state: str) -> StateCompliancePack:
    path = compliance_dir / f"{state.upper()}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No compliance pack for state {state} at {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return StateCompliancePack.model_validate(data)


def list_available_states(compliance_dir: Path) -> list[str]:
    return sorted(p.stem.upper() for p in compliance_dir.glob("*.yaml"))
