"""Deterministic premium rating.

Agents supply the real-world attributes they gathered from the caller (a driver age of
40, a 2019 vehicle, 9,000 annual miles). This module owns the arithmetic that turns
those attributes into premium multipliers, so a premium is always reproducible from the
catalog plus the attributes, and never depends on a model inventing rate factors.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sales_ivr.catalog.loader import get_product
from sales_ivr.config import InsuranceProduct

# Backstop on the product of all multipliers, so no combination of attributes can
# produce a premium that is absurd on its face.
MIN_COMBINED_MULTIPLIER = 0.5
MAX_COMBINED_MULTIPLIER = 3.0


@dataclass(frozen=True)
class _Band:
    """Applies when the attribute value is <= upper."""

    upper: float
    multiplier: float
    label: str


@dataclass(frozen=True)
class _Ratio:
    """Scales gently with magnitude relative to a reference value."""

    reference: float
    weight: float
    low: float
    high: float
    unit: str


_AGE_BANDS = (
    _Band(20, 1.45, "under 21"),
    _Band(24, 1.30, "21 to 24"),
    _Band(34, 1.05, "25 to 34"),
    _Band(54, 1.00, "35 to 54"),
    _Band(69, 0.95, "55 to 69"),
    _Band(math.inf, 1.15, "70 or older"),
)

_MODEL_YEAR_BANDS = (
    _Band(2007, 0.90, "2007 or older"),
    _Band(2014, 0.95, "2008 to 2014"),
    _Band(2021, 1.00, "2015 to 2021"),
    _Band(math.inf, 1.10, "2022 or newer"),
)

_MILEAGE_BANDS = (
    _Band(5_000, 0.88, "5,000 miles or fewer"),
    _Band(10_000, 0.96, "5,001 to 10,000 miles"),
    _Band(15_000, 1.00, "10,001 to 15,000 miles"),
    _Band(25_000, 1.12, "15,001 to 25,000 miles"),
    _Band(math.inf, 1.25, "over 25,000 miles"),
)

_BANDS: dict[str, tuple[_Band, ...]] = {
    "driver_age": _AGE_BANDS,
    "vehicle_year": _MODEL_YEAR_BANDS,
    "bike_year": _MODEL_YEAR_BANDS,
    "annual_mileage": _MILEAGE_BANDS,
    "year_built": (
        _Band(1969, 1.25, "built before 1970"),
        _Band(1989, 1.10, "built 1970 to 1989"),
        _Band(2009, 1.00, "built 1990 to 2009"),
        _Band(math.inf, 0.92, "built 2010 or later"),
    ),
    # Term life prices age far more steeply than auto.
    "age": (
        _Band(29, 0.80, "under 30"),
        _Band(39, 0.90, "30 to 39"),
        _Band(49, 1.10, "40 to 49"),
        _Band(59, 1.45, "50 to 59"),
        _Band(math.inf, 1.95, "60 or older"),
    ),
    "term_years": (
        _Band(10, 0.90, "10 year term or shorter"),
        _Band(20, 1.00, "11 to 20 year term"),
        _Band(30, 1.15, "21 to 30 year term"),
        _Band(math.inf, 1.30, "term over 30 years"),
    ),
    "employee_count": (
        _Band(5, 0.95, "5 or fewer employees"),
        _Band(20, 1.05, "6 to 20 employees"),
        _Band(100, 1.20, "21 to 100 employees"),
        _Band(math.inf, 1.40, "over 100 employees"),
    ),
    "watercraft_length_ft": (
        _Band(20, 0.92, "20 feet or under"),
        _Band(30, 1.00, "21 to 30 feet"),
        _Band(45, 1.15, "31 to 45 feet"),
        _Band(math.inf, 1.35, "over 45 feet"),
    ),
}

_RATIOS: dict[str, _Ratio] = {
    "annual_revenue": _Ratio(1_000_000, 0.15, 0.90, 1.60, "annual revenue"),
}

# Attributes an agent may reasonably collect but that must not move the premium.
_NOT_RATED: dict[str, str] = {
    "coverage_tier": "the selected tier already sets the coverage level",
    "coverage_amount": "the selected tier already sets the coverage amount",
    "home_value": "the selected tier already sets the dwelling coverage amount",
    "personal_property_value": "the selected tier already sets the property coverage amount",
    "boat_value": "the selected tier already sets the hull coverage amount",
    "underlying_auto_limit": "the selected tier already sets the umbrella limit",
    "underlying_home_limit": "the selected tier already sets the umbrella limit",
    "industry_code": "no industry rating table in this demo catalog",
}


@dataclass
class RatedAttribute:
    attribute: str
    value: float
    multiplier: float
    rationale: str


@dataclass
class SkippedAttribute:
    attribute: str
    value: Any
    reason: str


@dataclass
class PremiumBreakdown:
    """A premium plus the reasoning behind it, so agents can explain and negotiate."""

    monthly: float
    annual: float
    summary: str
    product_id: str
    tier_id: str
    tier_name: str
    coverage_limit: str
    base_premium_monthly: float
    combined_multiplier: float
    rated: list[RatedAttribute] = field(default_factory=list)
    skipped: list[SkippedAttribute] = field(default_factory=list)
    clamped: bool = False

    def as_tool_payload(self) -> dict[str, Any]:
        return {
            "quote_amount_monthly": self.monthly,
            "quote_amount_annual": self.annual,
            "coverage_summary": self.summary,
            "product_id": self.product_id,
            "tier_id": self.tier_id,
            "tier_name": self.tier_name,
            "coverage_limit": self.coverage_limit,
            "base_premium_monthly": self.base_premium_monthly,
            "combined_multiplier": self.combined_multiplier,
            "rating_breakdown": [
                {
                    "attribute": r.attribute,
                    "value": r.value,
                    "multiplier": r.multiplier,
                    "rationale": r.rationale,
                }
                for r in self.rated
            ],
            "attributes_not_rated": [
                {"attribute": s.attribute, "value": s.value, "reason": s.reason}
                for s in self.skipped
            ],
            "combined_multiplier_clamped": self.clamped,
        }


def _band_multiplier(bands: tuple[_Band, ...], value: float) -> tuple[float, str]:
    for band in bands:
        if value <= band.upper:
            return band.multiplier, band.label
    last = bands[-1]
    return last.multiplier, last.label


def _ratio_multiplier(rule: _Ratio, value: float) -> tuple[float, str]:
    raw = 1.0 + ((value / rule.reference) - 1.0) * rule.weight
    multiplier = min(max(raw, rule.low), rule.high)
    return round(multiplier, 4), (
        f"{rule.unit} of {value:,.0f} against a {rule.reference:,.0f} reference"
    )


class PricingEngine:
    """Deterministic premium calculator used by the pricing tool."""

    def rate_attribute(self, attribute: str, value: Any) -> RatedAttribute | SkippedAttribute:
        """Map one real-world attribute to a multiplier, or explain why it was ignored."""

        if attribute in _NOT_RATED:
            return SkippedAttribute(attribute, value, _NOT_RATED[attribute])
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return SkippedAttribute(attribute, value, "value is not numeric")
        if not math.isfinite(numeric) or numeric < 0:
            return SkippedAttribute(attribute, value, "value must be a non-negative number")

        if attribute in _BANDS:
            multiplier, label = _band_multiplier(_BANDS[attribute], numeric)
            return RatedAttribute(attribute, numeric, multiplier, label)
        if attribute in _RATIOS:
            multiplier, label = _ratio_multiplier(_RATIOS[attribute], numeric)
            return RatedAttribute(attribute, numeric, multiplier, label)
        return SkippedAttribute(
            attribute, value, "not a rating attribute in this catalog; it did not affect the price"
        )

    def calculate(
        self,
        product: InsuranceProduct,
        tier_id: str,
        rating_attributes: dict[str, Any] | None = None,
    ) -> PremiumBreakdown:
        tier = next((t for t in product.tiers if t.tier_id == tier_id), product.tiers[0])

        rated: list[RatedAttribute] = []
        skipped: list[SkippedAttribute] = []
        for attribute, value in (rating_attributes or {}).items():
            outcome = self.rate_attribute(attribute, value)
            if isinstance(outcome, RatedAttribute):
                rated.append(outcome)
            else:
                skipped.append(outcome)

        combined = 1.0
        for entry in rated:
            combined *= entry.multiplier
        clamped_value = min(max(combined, MIN_COMBINED_MULTIPLIER), MAX_COMBINED_MULTIPLIER)
        clamped = not math.isclose(clamped_value, combined, rel_tol=1e-9)

        monthly = round(tier.base_premium_monthly * clamped_value, 2)
        annual = round(monthly * 12 * 0.95, 2)  # annual pay discount
        summary = (
            f"{product.name} ({tier.name}): ${monthly:.2f}/mo or ${annual:.2f}/yr, "
            f"limit {tier.coverage_limit}"
        )
        return PremiumBreakdown(
            monthly=monthly,
            annual=annual,
            summary=summary,
            product_id=product.product_id,
            tier_id=tier.tier_id,
            tier_name=tier.name,
            coverage_limit=tier.coverage_limit,
            base_premium_monthly=tier.base_premium_monthly,
            combined_multiplier=round(clamped_value, 4),
            rated=rated,
            skipped=skipped,
            clamped=clamped,
        )

    def calculate_for_product_id(
        self,
        products: list[InsuranceProduct],
        product_id: str,
        tier_id: str,
        rating_attributes: dict[str, Any] | None = None,
    ) -> PremiumBreakdown:
        product = get_product(products, product_id)
        if product is None:
            raise ValueError(f"Unknown product_id: {product_id}")
        return self.calculate(product, tier_id, rating_attributes)


def load_objection_corpus(objections_dir: Path) -> dict[str, str]:
    corpus: dict[str, str] = {}
    for path in sorted(objections_dir.glob("*.md")):
        corpus[path.stem] = path.read_text(encoding="utf-8")
    return corpus
