from pathlib import Path

import pytest

from sales_ivr.config import load_config, resolve_path
from sales_ivr.models import CallSession, IVRState


def test_smoke_import():
    import sales_ivr

    assert sales_ivr.__version__ == "0.1.0"


def test_load_config():
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    config = load_config(config_path)
    assert config.carrier.id == "demo-carrier"
    assert "CA" in config.carrier.supported_states


def test_call_session_validates_phone():
    session = CallSession(session_id="s1", caller_phone="15551234001")
    assert session.caller_phone == "15551234001"


def test_call_session_rejects_bad_phone():
    with pytest.raises(ValueError):
        CallSession(session_id="s1", caller_phone="not-a-phone")


def test_policy_id_validation():
    from sales_ivr.models import ExistingPolicy
    from sales_ivr.models.enums import ProductLine

    policy = ExistingPolicy(
        policy_id="POL-AUTO001",
        product_line=ProductLine.AUTO,
        state="CA",
    )
    assert policy.policy_id == "POL-AUTO001"

    with pytest.raises(ValueError):
        ExistingPolicy(policy_id="bad", product_line=ProductLine.AUTO, state="CA")
