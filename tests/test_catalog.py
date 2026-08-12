from pathlib import Path

from sales_ivr.catalog.loader import filter_by_state, load_catalog
from sales_ivr.compliance.loader import list_available_states, load_state_compliance
from sales_ivr.config import InsuranceProduct, resolve_path
from sales_ivr.pricing.engine import PricingEngine, load_objection_corpus


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_catalog_has_eight_products():
    catalog_dir = _project_root() / "sales_ivr" / "catalog" / "products"
    products = load_catalog(catalog_dir)
    assert len(products) >= 8
    assert all(isinstance(p, InsuranceProduct) for p in products)


def test_filter_catalog_by_state():
    catalog_dir = _project_root() / "sales_ivr" / "catalog" / "products"
    products = load_catalog(catalog_dir)
    ca_products = filter_by_state(products, "CA")
    assert any(p.product_id == "auto-personal" for p in ca_products)


def test_compliance_packs():
    compliance_dir = _project_root() / "sales_ivr" / "compliance" / "disclosures"
    states = list_available_states(compliance_dir)
    assert "CA" in states
    pack = load_state_compliance(compliance_dir, "CA")
    assert len(pack.disclosures) >= 2


def _auto_products():
    return load_catalog(_project_root() / "sales_ivr" / "catalog" / "products")


def test_pricing_engine():
    engine = PricingEngine()
    breakdown = engine.calculate_for_product_id(
        _auto_products(),
        "auto-personal",
        "auto-standard",
        {"driver_age": 40, "vehicle_year": 2019, "annual_mileage": 9000},
    )
    assert breakdown.monthly > 0
    assert breakdown.annual > breakdown.monthly
    assert "Personal Auto" in breakdown.summary
    # 35-54 (1.00) x 2015-2021 (1.00) x 5,001-10,000 miles (0.96)
    assert breakdown.base_premium_monthly == 129.0
    assert breakdown.combined_multiplier == 0.96
    assert breakdown.monthly == 123.84
    assert {r.attribute for r in breakdown.rated} == {
        "driver_age",
        "vehicle_year",
        "annual_mileage",
    }


def test_raw_attributes_stay_within_sane_premium_range():
    """Real-world values must never be multiplied together as if they were multipliers."""

    engine = PricingEngine()
    breakdown = engine.calculate_for_product_id(
        _auto_products(),
        "auto-personal",
        "auto-standard",
        {"driver_age": 19, "vehicle_year": 2024, "annual_mileage": 30000},
    )
    assert breakdown.monthly < 129.0 * 3
    assert breakdown.combined_multiplier <= 3.0


def test_pricing_engine_reports_unrated_attributes():
    engine = PricingEngine()
    breakdown = engine.calculate_for_product_id(
        _auto_products(),
        "auto-personal",
        "auto-standard",
        {"driver_age": 40, "favourite_colour": 7, "coverage_tier": 2},
    )
    assert breakdown.combined_multiplier == 1.0
    skipped = {s.attribute for s in breakdown.skipped}
    assert skipped == {"favourite_colour", "coverage_tier"}


def test_pricing_engine_is_deterministic_across_products():
    engine = PricingEngine()
    products = _auto_products()
    older = engine.calculate_for_product_id(
        products, "home-homeowners", "home-standard", {"year_built": 1965}
    )
    newer = engine.calculate_for_product_id(
        products, "home-homeowners", "home-standard", {"year_built": 2015}
    )
    assert older.monthly > newer.monthly


def test_objection_corpus():
    objections_dir = _project_root() / "sales_ivr" / "knowledge" / "objections"
    corpus = load_objection_corpus(objections_dir)
    assert "price" in corpus
    assert "competitor" in corpus
