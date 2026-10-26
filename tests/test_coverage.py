from pathlib import Path

from sales_ivr.catalog.jurisdictions import (
    ALL_CODES,
    ALL_SET,
    EARTHQUAKE,
    MEDIGAP_EXCLUDED,
    MONOPOLISTIC_WC,
    SNOWBELT,
    normalize_state,
)
from sales_ivr.catalog.loader import filter_by_state, load_catalog
from sales_ivr.compliance.loader import list_available_states, load_state_compliance
from sales_ivr.config import load_config
from sales_ivr.models.enums import ProductLine
from sales_ivr.pricing.engine import PricingEngine, recognized_rating_attributes
from sales_ivr.web.chat_service import _normalize_state


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def _products():
    return load_catalog(_root() / "sales_ivr" / "catalog" / "products")


def test_every_state_and_dc_is_appointed():
    config = load_config(_root() / "config.yaml")
    assert list(config.carrier.supported_states) == list(ALL_CODES)
    assert len(ALL_CODES) == 51


def test_catalog_covers_every_line_and_recognizes_its_factors():
    products = _products()
    assert len(products) >= 55
    assert {p.product_line for p in products} == set(ProductLine)
    known = recognized_rating_attributes()
    for product in products:
        assert product.tiers
        assert product.eligible_states
        assert set(product.eligible_states) <= ALL_SET
        for factor in product.required_factors:
            assert factor in known, product.product_id


def test_core_products_are_nationwide_and_specialties_are_not():
    products = _products()
    by_id = {p.product_id: p for p in products}

    for product_id in ("auto-personal", "home-homeowners", "renters-standard", "life-term", "flood-residential"):
        assert set(by_id[product_id].eligible_states) == ALL_SET

    for code in ALL_CODES:
        offered = {p.product_id for p in filter_by_state(products, code)}
        assert "auto-personal" in offered
        assert "home-homeowners" in offered
        assert ("workers-comp" in offered) is (code not in MONOPOLISTIC_WC)
        assert ("medigap-supplement" in offered) is (code not in MEDIGAP_EXCLUDED)
        assert ("earthquake-residential" in offered) is (code in EARTHQUAKE)
        assert ("powersports-snowmobile" in offered) is (code in SNOWBELT)
        if code == "IA":
            assert "boat-yacht" not in offered
        if code == "DC":
            assert "farm-crop" not in offered
        if code == "IA":
            assert "farm-crop" in offered


def test_compliance_pack_for_every_appointed_state():
    compliance_dir = _root() / "sales_ivr" / "compliance" / "disclosures"
    assert list_available_states(compliance_dir) == sorted(ALL_CODES)
    california = load_state_compliance(compliance_dir, "CA")
    assert any(item.disclosure_id == "ca-rate-notice" for item in california.disclosures)
    ohio = load_state_compliance(compliance_dir, "OH")
    assert any("state fund" in note.lower() or "workers" in note.lower() for note in ohio.market_notes)
    florida = load_state_compliance(compliance_dir, "FL")
    assert any("hurricane" in item.text.lower() for item in florida.disclosures)
    for code in ALL_CODES:
        pack = load_state_compliance(compliance_dir, code)
        assert pack.regulator
        assert len(pack.disclosures) >= 3
        assert "guaranteed approval" in pack.prohibited_phrases


def test_state_changes_the_premium_and_omitting_it_does_not():
    engine = PricingEngine()
    products = _products()
    base = engine.calculate_for_product_id(
        products,
        "auto-personal",
        "auto-standard",
        {"driver_age": 40, "vehicle_year": 2019, "annual_mileage": 9000},
    )
    assert base.monthly == 123.84
    florida = engine.calculate_for_product_id(
        products,
        "home-homeowners",
        "home-standard",
        {"year_built": 2015},
        state="FL",
    )
    iowa = engine.calculate_for_product_id(
        products,
        "home-homeowners",
        "home-standard",
        {"year_built": 2015},
        state="Iowa",
    )
    assert florida.monthly > iowa.monthly
    trip = engine.calculate_for_product_id(
        products,
        "travel-trip",
        "trip-standard",
        {"trip_days": 10, "trip_cost": 2500},
        state="CO",
    )
    assert trip.premium_basis == "term"
    assert trip.annual == trip.monthly
    assert "one-time" in trip.summary


def test_state_names_do_not_match_ordinary_words():
    assert normalize_state("I live in New Hampshire") == "NH"
    assert normalize_state("West Virginia") == "WV"
    assert normalize_state("Washington, D.C.") == "DC"
    assert normalize_state("I live in Washington") == "WA"
    assert normalize_state("I moved from Arkansas to Kansas") == "KS"
    assert normalize_state("I live in OH") == "OH"
    assert normalize_state("OH") is None
    assert normalize_state("I am in the market for coverage") is None
    assert normalize_state("Puerto Rico") is None
    assert _normalize_state("California") == "CA"
