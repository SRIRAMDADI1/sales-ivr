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

from sales_ivr.catalog.jurisdictions import ALL_SET, normalize_state
from sales_ivr.catalog.loader import get_product
from sales_ivr.config import InsuranceProduct
from sales_ivr.pricing.relativities import relativity_for

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
    "claims_count": (
        _Band(0, 0.92, "no prior claims"),
        _Band(1, 1.08, "one prior claim"),
        _Band(2, 1.30, "two prior claims"),
        _Band(math.inf, 1.55, "three or more prior claims"),
    ),
    "roof_age": (
        _Band(5, 0.92, "roof 5 years old or newer"),
        _Band(15, 1.00, "roof 6 to 15 years old"),
        _Band(25, 1.18, "roof 16 to 25 years old"),
        _Band(math.inf, 1.35, "roof over 25 years old"),
    ),
    "protection_class": (
        _Band(3, 0.90, "protection class 1 to 3"),
        _Band(6, 1.00, "protection class 4 to 6"),
        _Band(8, 1.15, "protection class 7 to 8"),
        _Band(math.inf, 1.32, "protection class 9 or higher"),
    ),
    "deductible": (
        _Band(500, 1.12, "deductible of $500 or less"),
        _Band(1_000, 1.00, "deductible of $501 to $1,000"),
        _Band(2_500, 0.90, "deductible of $1,001 to $2,500"),
        _Band(math.inf, 0.82, "deductible over $2,500"),
    ),
    "smoker": (
        _Band(0, 1.00, "non-smoker"),
        _Band(math.inf, 1.45, "smoker"),
    ),
    "occupants": (
        _Band(1, 0.95, "one occupant"),
        _Band(2, 1.00, "two occupants"),
        _Band(4, 1.08, "three or four occupants"),
        _Band(math.inf, 1.18, "five or more occupants"),
    ),
    "units": (
        _Band(1, 1.00, "one unit"),
        _Band(2, 1.08, "two units"),
        _Band(4, 1.18, "three or four units"),
        _Band(10, 1.30, "five to ten units"),
        _Band(math.inf, 1.45, "more than ten units"),
    ),
    "stories": (
        _Band(1, 0.95, "one story"),
        _Band(2, 1.00, "two stories"),
        _Band(math.inf, 1.18, "three or more stories"),
    ),
    "elevation_ft": (
        _Band(5, 1.45, "5 feet of elevation or less"),
        _Band(20, 1.18, "6 to 20 feet of elevation"),
        _Band(50, 1.00, "21 to 50 feet of elevation"),
        _Band(math.inf, 0.88, "above 50 feet of elevation"),
    ),
    "engine_hp": (
        _Band(50, 0.90, "50 horsepower or less"),
        _Band(150, 1.00, "51 to 150 horsepower"),
        _Band(300, 1.15, "151 to 300 horsepower"),
        _Band(math.inf, 1.30, "over 300 horsepower"),
    ),
    "pilot_hours": (
        _Band(100, 1.40, "100 pilot hours or fewer"),
        _Band(500, 1.15, "101 to 500 pilot hours"),
        _Band(1_500, 1.00, "501 to 1,500 pilot hours"),
        _Band(math.inf, 0.90, "over 1,500 pilot hours"),
    ),
    "pet_age": (
        _Band(2, 0.90, "pet age 2 or under"),
        _Band(6, 1.00, "pet age 3 to 6"),
        _Band(10, 1.28, "pet age 7 to 10"),
        _Band(math.inf, 1.55, "pet age 11 or older"),
    ),
    "trip_days": (
        _Band(7, 0.85, "trip of 7 days or fewer"),
        _Band(14, 1.00, "trip of 8 to 14 days"),
        _Band(30, 1.22, "trip of 15 to 30 days"),
        _Band(math.inf, 1.45, "trip longer than 30 days"),
    ),
    "years_in_business": (
        _Band(2, 1.28, "in business 2 years or fewer"),
        _Band(5, 1.10, "in business 3 to 5 years"),
        _Band(15, 1.00, "in business 6 to 15 years"),
        _Band(math.inf, 0.92, "in business more than 15 years"),
    ),
    "num_vehicles": (
        _Band(1, 1.00, "one vehicle"),
        _Band(3, 1.10, "two or three vehicles"),
        _Band(10, 1.25, "four to ten vehicles"),
        _Band(30, 1.40, "eleven to thirty vehicles"),
        _Band(math.inf, 1.55, "more than thirty vehicles"),
    ),
    "benefit_years": (
        _Band(2, 0.85, "benefit period of 2 years or less"),
        _Band(4, 1.00, "benefit period of 3 to 4 years"),
        _Band(6, 1.15, "benefit period of 5 to 6 years"),
        _Band(math.inf, 1.30, "benefit period over 6 years"),
    ),
    "elimination_days": (
        _Band(0, 1.30, "no elimination period"),
        _Band(30, 1.12, "elimination period of 1 to 30 days"),
        _Band(90, 1.00, "elimination period of 31 to 90 days"),
        _Band(180, 0.88, "elimination period of 91 to 180 days"),
        _Band(math.inf, 0.78, "elimination period over 180 days"),
    ),
    "event_guests": (
        _Band(50, 0.85, "50 guests or fewer"),
        _Band(150, 1.00, "51 to 150 guests"),
        _Band(300, 1.20, "151 to 300 guests"),
        _Band(math.inf, 1.40, "more than 300 guests"),
    ),
    "event_days": (
        _Band(1, 0.90, "one-day event"),
        _Band(3, 1.00, "two or three days"),
        _Band(math.inf, 1.22, "longer than three days"),
    ),
    "horse_count": (
        _Band(1, 1.00, "one horse"),
        _Band(5, 1.15, "two to five horses"),
        _Band(20, 1.35, "six to twenty horses"),
        _Band(math.inf, 1.55, "more than twenty horses"),
    ),
    "head_count": (
        _Band(10, 0.90, "10 head or fewer"),
        _Band(50, 1.00, "11 to 50 head"),
        _Band(200, 1.20, "51 to 200 head"),
        _Band(math.inf, 1.45, "more than 200 head"),
    ),
    "project_months": (
        _Band(3, 0.90, "project of 3 months or less"),
        _Band(8, 1.00, "project of 4 to 8 months"),
        _Band(14, 1.15, "project of 9 to 14 months"),
        _Band(math.inf, 1.30, "project longer than 14 months"),
    ),
    "radius_miles": (
        _Band(100, 0.90, "radius of 100 miles or less"),
        _Band(300, 1.00, "radius of 101 to 300 miles"),
        _Band(500, 1.15, "radius of 301 to 500 miles"),
        _Band(math.inf, 1.35, "radius over 500 miles"),
    ),
    "item_count": (
        _Band(1, 0.95, "one scheduled item"),
        _Band(3, 1.00, "two or three scheduled items"),
        _Band(8, 1.15, "four to eight scheduled items"),
        _Band(math.inf, 1.35, "more than eight scheduled items"),
    ),
}

# Names that share a band table with another attribute.
_ALIASES: dict[str, str] = {
    "bike_year": "vehicle_year",
    "rv_year": "vehicle_year",
    "hull_year": "vehicle_year",
    "pilot_age": "driver_age",
    "years_in_practice": "years_in_business",
    "household_vehicles": "num_vehicles",
}

_RATIOS: dict[str, _Ratio] = {
    "annual_revenue": _Ratio(1_000_000, 0.15, 0.90, 1.60, "annual revenue"),
    "square_feet": _Ratio(2_000, 0.10, 0.85, 1.45, "square feet"),
    "trip_cost": _Ratio(2_500, 0.20, 0.80, 1.60, "trip cost"),
    "aircraft_value": _Ratio(150_000, 0.15, 0.85, 1.70, "aircraft value"),
    "annual_payroll": _Ratio(400_000, 0.20, 0.85, 1.80, "annual payroll"),
    "acres": _Ratio(300, 0.12, 0.85, 1.55, "acres"),
    "horse_value": _Ratio(25_000, 0.15, 0.90, 1.65, "horse value"),
    "animal_value": _Ratio(2_000, 0.15, 0.85, 1.60, "average animal value"),
    "contract_value": _Ratio(250_000, 0.18, 0.85, 1.70, "contract value"),
    "project_value": _Ratio(500_000, 0.18, 0.85, 1.75, "project value"),
    "scheduled_value": _Ratio(20_000, 0.12, 0.90, 1.50, "scheduled property value"),
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
    "monthly_benefit": "the selected tier already sets the benefit amount",
    "daily_benefit": "the selected tier already sets the daily benefit",
    "scheduled_items": "item count and the selected tier already reflect the schedule",
    "breed": "no breed rating table in this demo catalog",
    "species": "no species rating table in this demo catalog",
    "pet_breed": "no breed rating table in this demo catalog",
    "destination": "destination is not a rating factor in this demo catalog",
    "aircraft_make": "the aircraft value and tier already reflect the aircraft",
    "construction_type": "no construction-type table in this demo catalog",
    "roof_type": "roof age is the roof rating factor in this demo catalog",
    "flood_zone": "elevation is the flood rating factor in this demo catalog",
    "occupation": "no occupation class table in this demo catalog",
    "business_type": "no business-class table beyond revenue, payroll, and employees",
    "vin": "the vehicle year is the vehicle rating factor",
    "zip": "ZIP code is collected for the application and is not a rating factor here",
    "zip_code": "ZIP code is collected for the application and is not a rating factor here",
    "gender": "this rating plan does not use gender",
    "credit_score": "this rating plan does not use credit",
    "marital_status": "this rating plan does not use marital status",
    "jewelry_value": "the selected tier already sets the scheduled limit",
    "rv_value": "the selected tier already sets the motorhome limit",
    "hull_value": "the selected tier already sets the hull limit",
    "dwelling_limit": "the selected tier already sets the dwelling limit",
    "building_limit": "the selected tier already sets the building limit",
    "contents_limit": "the selected tier already sets the contents limit",
    "naics": "no industry rating table in this demo catalog",
    "specialty": "no medical-specialty table in this demo catalog",
    "crop_type": "no crop-type table in this demo catalog",
    "event_type": "guest count and event length are the event rating factors",
    "bond_type": "contract value is the surety rating factor",
}


@dataclass
class RatedAttribute:
    attribute: str
    value: float | str
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
    premium_basis: str = "monthly"
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
            "premium_basis": self.premium_basis,
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
        lookup = _ALIASES.get(attribute, attribute)
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return SkippedAttribute(attribute, value, "value is not numeric")
        if not math.isfinite(numeric) or numeric < 0:
            return SkippedAttribute(attribute, value, "value must be a non-negative number")

        if lookup in _BANDS:
            multiplier, label = _band_multiplier(_BANDS[lookup], numeric)
            return RatedAttribute(attribute, numeric, multiplier, label)
        if lookup in _RATIOS:
            multiplier, label = _ratio_multiplier(_RATIOS[lookup], numeric)
            return RatedAttribute(attribute, numeric, multiplier, label)
        return SkippedAttribute(
            attribute, value, "not a rating attribute in this catalog; it did not affect the price"
        )

    def calculate(
        self,
        product: InsuranceProduct,
        tier_id: str,
        rating_attributes: dict[str, Any] | None = None,
        state: str | None = None,
    ) -> PremiumBreakdown:
        tier = next((t for t in product.tiers if t.tier_id == tier_id), product.tiers[0])

        rated: list[RatedAttribute] = []
        skipped: list[SkippedAttribute] = []
        for attribute, value in (rating_attributes or {}).items():
            if attribute == "state":
                continue
            outcome = self.rate_attribute(attribute, value)
            if isinstance(outcome, RatedAttribute):
                rated.append(outcome)
            else:
                skipped.append(outcome)

        state_code = None
        if state:
            token = str(state).strip()
            candidate = token.upper() if len(token) == 2 and token.isalpha() else normalize_state(token)
            if candidate not in ALL_SET:
                candidate = normalize_state(token)
            if candidate not in ALL_SET:
                skipped.append(
                    SkippedAttribute("state", state, "not a US state or District of Columbia")
                )
            else:
                state_code = candidate
                multiplier, label = relativity_for(product.product_line.value, state_code)
                rated.append(RatedAttribute("state", state_code, multiplier, label))

        combined = 1.0
        for entry in rated:
            combined *= entry.multiplier
        clamped_value = min(max(combined, MIN_COMBINED_MULTIPLIER), MAX_COMBINED_MULTIPLIER)
        clamped = not math.isclose(clamped_value, combined, rel_tol=1e-9)
        basis = product.premium_basis
        where = f" in {state_code}" if state_code else ""
        if basis == "term":
            amount = round(tier.base_premium_monthly * clamped_value, 2)
            monthly = amount
            annual = amount
            summary = (
                f"{product.name} ({tier.name}){where}: ${amount:.2f} one-time premium "
                f"for the policy term, limit {tier.coverage_limit}"
            )
        else:
            monthly = round(tier.base_premium_monthly * clamped_value, 2)
            annual = round(monthly * 12 * 0.95, 2)  # annual pay discount
            summary = (
                f"{product.name} ({tier.name}){where}: ${monthly:.2f}/mo or ${annual:.2f}/yr, "
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
            premium_basis=basis,
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
        state: str | None = None,
    ) -> PremiumBreakdown:
        product = get_product(products, product_id)
        if product is None:
            raise ValueError(f"Unknown product_id: {product_id}")
        return self.calculate(product, tier_id, rating_attributes, state=state)


def recognized_rating_attributes() -> set[str]:
    """Attribute names the engine rates, ignores on purpose, or aliases."""

    return set(_BANDS) | set(_RATIOS) | set(_NOT_RATED) | set(_ALIASES)


def load_objection_corpus(objections_dir: Path) -> dict[str, str]:
    corpus: dict[str, str] = {}
    for path in sorted(objections_dir.glob("*.md")):
        corpus[path.stem] = path.read_text(encoding="utf-8")
    return corpus
