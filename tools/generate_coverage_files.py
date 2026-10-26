"""Write catalog YAML and per-state compliance packs. Run from the repo root."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sales_ivr.catalog.jurisdictions import (
    ALL_CODES,
    CREDIT_RESTRICTED,
    GENDER_NEUTRAL_AUTO,
    HAIL_TORNADO,
    HURRICANE,
    MEDIGAP_EXCLUDED,
    MONOPOLISTIC_WC,
    NO_FAULT,
    PIP_ADDON,
    REGULATORS,
    STATE_NAMES,
    WC_FUND_NAME,
    WILDFIRE,
)

PRODUCTS = ROOT / "sales_ivr" / "catalog" / "products"
COMPLIANCE = ROOT / "sales_ivr" / "compliance" / "disclosures"


def T(tier_id: str, name: str, premium: float, limit: str) -> dict:
    return {
        "tier_id": tier_id,
        "name": name,
        "base_premium_monthly": premium,
        "coverage_limit": limit,
    }


def P(
    product_id: str,
    line: str,
    name: str,
    description: str,
    region: str,
    factors: list[str],
    tiers: list[dict],
    min_age: int = 18,
    basis: str = "monthly",
) -> dict:
    document = {
        "product_id": product_id,
        "product_line": line,
        "name": name,
        "description": description,
        "eligible_states": [region],
        "min_age": min_age,
        "required_factors": factors,
        "tiers": tiers,
    }
    if basis != "monthly":
        document["premium_basis"] = basis
    return document


PRODUCTS_DATA = [
    P(
        "auto-personal",
        "auto",
        "Personal Auto Insurance",
        "Liability and physical damage for a private passenger auto used for personal driving. "
        "Not a rideshare, motorcycle, or commercial-auto policy.",
        "ALL",
        ["driver_age", "vehicle_year", "annual_mileage"],
        [
            T("auto-basic", "Basic", 89.0, "25/50/25"),
            T("auto-standard", "Standard", 129.0, "50/100/50"),
            T("auto-premium", "Premium", 179.0, "100/300/100"),
        ],
    ),
    P(
        "auto-classic",
        "auto",
        "Classic Auto Insurance",
        "Agreed-value coverage for a collectible private passenger auto, written for limited annual mileage. "
        "Not a daily-driver personal auto policy.",
        "ALL",
        ["driver_age", "vehicle_year", "annual_mileage"],
        [
            T("classic-agreed-25", "Agreed $25k", 55.0, "$25,000 agreed value"),
            T("classic-agreed-50", "Agreed $50k", 85.0, "$50,000 agreed value"),
            T("classic-agreed-100", "Agreed $100k", 120.0, "$100,000 agreed value"),
        ],
    ),
    P(
        "auto-rideshare",
        "auto",
        "Rideshare Gap Insurance",
        "Covers the driver while a rideshare app is on and no passenger or delivery is underway. "
        "It does not replace the transportation network company's coverage during an active trip.",
        "ALL",
        ["driver_age", "vehicle_year", "annual_mileage"],
        [
            T("rideshare-basic", "Basic", 140.0, "50/100/50"),
            T("rideshare-standard", "Standard", 190.0, "100/300/100"),
            T("rideshare-premium", "Premium", 250.0, "250/500/100"),
        ],
    ),
    P(
        "home-homeowners",
        "home",
        "Homeowners Insurance",
        "Dwelling, other structures, personal property, and liability for a home you live in. "
        "Flood and earthquake are separate policies. Wind, hail, hurricane, and wildfire deductibles may apply.",
        "ALL",
        ["year_built", "roof_age", "deductible"],
        [
            T("home-basic", "Basic", 110.0, "$250,000 dwelling"),
            T("home-standard", "Standard", 155.0, "$400,000 dwelling"),
            T("home-premium", "Premium", 210.0, "$600,000 dwelling"),
        ],
    ),
    P(
        "home-condo",
        "condo",
        "Condo Insurance",
        "Walls-in building property, personal property, loss assessment, and liability for a condominium unit you own. "
        "The association's master policy is separate. Flood and earthquake are not included.",
        "ALL",
        ["year_built", "square_feet", "deductible"],
        [
            T("condo-basic", "Basic", 45.0, "$50,000 building property"),
            T("condo-standard", "Standard", 70.0, "$100,000 building property"),
            T("condo-premium", "Premium", 110.0, "$200,000 building property"),
        ],
    ),
    P(
        "home-landlord",
        "landlord",
        "Landlord Dwelling Insurance",
        "Dwelling fire coverage for a residence you rent to others, including premises liability. "
        "It does not cover the tenant's belongings.",
        "ALL",
        ["year_built", "units", "roof_age"],
        [
            T("landlord-basic", "Basic", 95.0, "$250,000 dwelling"),
            T("landlord-standard", "Standard", 150.0, "$450,000 dwelling"),
            T("landlord-premium", "Premium", 230.0, "$750,000 dwelling"),
        ],
    ),
    P(
        "home-mobile",
        "mobile_home",
        "Mobile Home Insurance",
        "Dwelling coverage for a manufactured or mobile home, including listed attached structures. "
        "Flood is not included.",
        "ALL",
        ["year_built", "square_feet", "deductible"],
        [
            T("mobile-basic", "Basic", 70.0, "$75,000 dwelling"),
            T("mobile-standard", "Standard", 105.0, "$150,000 dwelling"),
            T("mobile-premium", "Premium", 155.0, "$250,000 dwelling"),
        ],
    ),
    P(
        "renters-standard",
        "renters",
        "Renters Insurance",
        "Personal property and liability for a tenant. It does not cover the building and it does not include flood.",
        "ALL",
        ["personal_property_value", "coverage_tier", "claims_count"],
        [
            T("renters-basic", "Basic", 18.0, "$20,000 personal property"),
            T("renters-standard", "Standard", 28.0, "$40,000 personal property"),
            T("renters-premium", "Premium", 42.0, "$75,000 personal property"),
        ],
    ),
    P(
        "flood-residential",
        "flood",
        "Residential Flood Insurance",
        "Building and contents coverage for flood. This is not part of a homeowners, condo, or renters policy. "
        "An issued flood policy usually has a waiting period before coverage starts.",
        "ALL",
        ["elevation_ft", "year_built", "deductible"],
        [
            T("flood-basic", "Basic", 65.0, "$150,000 building / $50,000 contents"),
            T("flood-standard", "Standard", 95.0, "$250,000 building / $100,000 contents"),
            T("flood-premium", "Premium", 140.0, "$500,000 building / $200,000 contents"),
        ],
    ),
    P(
        "earthquake-residential",
        "earthquake",
        "Residential Earthquake Insurance",
        "Dwelling damage from earthquake in states where this carrier writes it. "
        "Flood and fire are not earthquake. Issued policies often use a percentage deductible; this estimate prices the limit only.",
        "EARTHQUAKE",
        ["year_built", "stories", "deductible"],
        [
            T("eq-basic", "Basic", 40.0, "$250,000 dwelling"),
            T("eq-standard", "Standard", 75.0, "$400,000 dwelling"),
            T("eq-premium", "Premium", 130.0, "$600,000 dwelling"),
        ],
    ),
    P(
        "umbrella-personal",
        "umbrella",
        "Personal Umbrella Policy",
        "Excess liability above underlying auto and home limits. "
        "It does not pay the underlying deductibles and it does not cover losses the underlying policies exclude.",
        "ALL",
        ["underlying_auto_limit", "underlying_home_limit", "household_vehicles"],
        [
            T("umbrella-1m", "$1M Umbrella", 22.0, "$1,000,000"),
            T("umbrella-2m", "$2M Umbrella", 35.0, "$2,000,000"),
            T("umbrella-5m", "$5M Umbrella", 62.0, "$5,000,000"),
        ],
        min_age=21,
    ),
    P(
        "motorcycle-standard",
        "motorcycle",
        "Motorcycle Insurance",
        "Liability and physical damage for a street motorcycle. Not an off-road ATV or snowmobile policy.",
        "ALL",
        ["driver_age", "bike_year", "annual_mileage"],
        [
            T("moto-basic", "Basic", 45.0, "25/50/10"),
            T("moto-standard", "Standard", 68.0, "50/100/25"),
            T("moto-premium", "Premium", 98.0, "100/300/50"),
        ],
        min_age=21,
    ),
    P(
        "boat-recreational",
        "boat",
        "Recreational Boat Insurance",
        "Hull and liability for a recreational boat. Not a personal watercraft policy and not a yacht policy.",
        "ALL",
        ["watercraft_length_ft", "engine_hp", "hull_year"],
        [
            T("boat-basic", "Basic", 38.0, "$50,000 hull"),
            T("boat-standard", "Standard", 62.0, "$100,000 hull"),
            T("boat-premium", "Premium", 110.0, "$250,000 hull"),
        ],
    ),
    P(
        "boat-pwc",
        "boat",
        "Personal Watercraft Insurance",
        "Hull and liability for a personal watercraft such as a jet ski.",
        "ALL",
        ["driver_age", "engine_hp"],
        [
            T("pwc-basic", "Basic", 32.0, "$15,000 hull"),
            T("pwc-standard", "Standard", 48.0, "$25,000 hull"),
        ],
    ),
    P(
        "boat-yacht",
        "boat",
        "Yacht Insurance",
        "Hull, liability, and uninsured boater coverage for a larger recreational boat kept in coastal or Great Lakes waters. "
        "Not a small-boat policy.",
        "COASTAL",
        ["watercraft_length_ft", "hull_year", "engine_hp"],
        [
            T("yacht-250", "Coastal 250", 180.0, "$250,000 hull"),
            T("yacht-500", "Coastal 500", 320.0, "$500,000 hull"),
            T("yacht-1m", "Coastal 1M", 540.0, "$1,000,000 hull"),
        ],
    ),
    P(
        "rv-motorhome",
        "rv",
        "Motorhome Insurance",
        "Liability and physical damage for a motorhome, including attached residential equipment. Not a travel-trailer contents policy.",
        "ALL",
        ["driver_age", "rv_year", "annual_mileage"],
        [
            T("rv-basic", "Basic", 85.0, "$75,000"),
            T("rv-standard", "Standard", 130.0, "$150,000"),
            T("rv-premium", "Premium", 190.0, "$300,000"),
        ],
    ),
    P(
        "powersports-atv",
        "powersports",
        "ATV Insurance",
        "Off-highway vehicle liability and physical damage. Not a street motorcycle policy.",
        "ALL",
        ["driver_age", "engine_hp"],
        [
            T("atv-basic", "Basic", 22.0, "$8,000"),
            T("atv-standard", "Standard", 36.0, "$15,000"),
        ],
    ),
    P(
        "powersports-snowmobile",
        "powersports",
        "Snowmobile Insurance",
        "Liability and physical damage for a snowmobile in states with a real snow season.",
        "SNOWBELT",
        ["driver_age", "engine_hp"],
        [
            T("snow-basic", "Basic", 25.0, "$10,000"),
            T("snow-standard", "Standard", 40.0, "$18,000"),
        ],
    ),
    P(
        "aviation-private",
        "aviation",
        "Private Aircraft Insurance",
        "Hull and liability for pleasure and business use of a private aircraft. Not airline, charter, or instruction-for-hire operations.",
        "ALL",
        ["pilot_age", "pilot_hours", "aircraft_value"],
        [
            T("aviation-liability", "Liability", 280.0, "$1,000,000 liability"),
            T("aviation-hull-150", "Hull 150", 520.0, "$150,000 hull"),
            T("aviation-hull-500", "Hull 500", 900.0, "$500,000 hull"),
        ],
    ),
    P(
        "life-term",
        "life",
        "Term Life Insurance",
        "Level-premium term life insurance for a fixed period. It has no cash value. "
        "The estimate is not a guarantee of insurability.",
        "ALL",
        ["age", "coverage_amount", "term_years", "smoker"],
        [
            T("life-250k", "250K Term", 35.0, "$250,000"),
            T("life-500k", "500K Term", 58.0, "$500,000"),
            T("life-1m", "1M Term", 95.0, "$1,000,000"),
        ],
    ),
    P(
        "life-whole",
        "life",
        "Whole Life Insurance",
        "Permanent life insurance with a level premium. This quote does not project cash value or dividends.",
        "ALL",
        ["age", "smoker", "coverage_amount"],
        [
            T("whole-50k", "50K Whole Life", 62.0, "$50,000"),
            T("whole-100k", "100K Whole Life", 115.0, "$100,000"),
            T("whole-250k", "250K Whole Life", 260.0, "$250,000"),
        ],
    ),
    P(
        "life-final-expense",
        "life",
        "Final Expense Life Insurance",
        "Smaller permanent life insurance meant for funeral costs. Some issued policies grade the benefit in the first two years; "
        "this estimate assumes a level benefit and is not a promise of simplified-issue approval.",
        "ALL",
        ["age", "smoker"],
        [
            T("final-10k", "10K Final Expense", 28.0, "$10,000"),
            T("final-15k", "15K Final Expense", 38.0, "$15,000"),
            T("final-25k", "25K Final Expense", 55.0, "$25,000"),
        ],
        min_age=50,
    ),
    P(
        "disability-income",
        "disability",
        "Disability Income Insurance",
        "Replaces a portion of income if illness or injury keeps you from working. "
        "This is not workers compensation and not major medical insurance.",
        "ALL",
        ["age", "elimination_days", "benefit_years"],
        [
            T("di-2k", "$2,000 Monthly", 55.0, "$2,000 per month"),
            T("di-4k", "$4,000 Monthly", 95.0, "$4,000 per month"),
            T("di-6k", "$6,000 Monthly", 140.0, "$6,000 per month"),
        ],
    ),
    P(
        "ltc-comprehensive",
        "long_term_care",
        "Long-Term Care Insurance",
        "A daily benefit for long-term care at home or in a facility. Not Medicare and not health insurance.",
        "ALL",
        ["age", "benefit_years", "elimination_days"],
        [
            T("ltc-100", "$100 Daily", 90.0, "$100 per day"),
            T("ltc-150", "$150 Daily", 140.0, "$150 per day"),
            T("ltc-250", "$250 Daily", 210.0, "$250 per day"),
        ],
    ),
    P(
        "dental-individual",
        "dental",
        "Individual Dental Insurance",
        "Preventive, basic, and major dental benefits for an individual or family. Not a medical policy.",
        "ALL",
        ["age", "occupants"],
        [
            T("dental-preventive", "Preventive", 24.0, "preventive services"),
            T("dental-basic", "Basic", 39.0, "preventive and basic services"),
            T("dental-major", "Major", 55.0, "preventive, basic, and major services"),
        ],
    ),
    P(
        "vision-individual",
        "vision",
        "Individual Vision Insurance",
        "Eye exam and eyewear benefits. Not a medical policy.",
        "ALL",
        ["occupants"],
        [
            T("vision-exam", "Exam", 9.0, "annual exam"),
            T("vision-standard", "Standard", 14.0, "exam plus lenses"),
            T("vision-premium", "Premium", 22.0, "exam, lenses, and frames"),
        ],
    ),
    P(
        "supplemental-accident",
        "supplemental",
        "Accident Insurance",
        "Pays scheduled cash benefits for accidental injury. It does not pay benefits for sickness and it is not major medical insurance.",
        "ALL",
        ["age", "occupants"],
        [
            T("accident-basic", "Basic", 19.0, "scheduled accident benefits"),
            T("accident-standard", "Standard", 32.0, "higher scheduled accident benefits"),
            T("accident-family", "Family", 48.0, "family scheduled accident benefits"),
        ],
    ),
    P(
        "supplemental-critical-illness",
        "supplemental",
        "Critical Illness Insurance",
        "Pays a lump sum on a covered diagnosis such as cancer, heart attack, or stroke. "
        "It does not pay medical bills as they are incurred.",
        "ALL",
        ["age", "smoker"],
        [
            T("ci-10k", "$10,000 Lump Sum", 24.0, "$10,000"),
            T("ci-25k", "$25,000 Lump Sum", 41.0, "$25,000"),
            T("ci-50k", "$50,000 Lump Sum", 67.0, "$50,000"),
        ],
    ),
    P(
        "supplemental-hospital",
        "supplemental",
        "Hospital Indemnity Insurance",
        "Pays a set cash amount for a covered hospital stay. It does not pay the hospital bill in full and it is not major medical insurance.",
        "ALL",
        ["age", "occupants"],
        [
            T("hospital-100", "$100 Daily", 18.0, "$100 per day"),
            T("hospital-250", "$250 Daily", 31.0, "$250 per day"),
            T("hospital-500", "$500 Daily", 46.0, "$500 per day"),
        ],
    ),
    P(
        "medigap-supplement",
        "medigap",
        "Medicare Supplement Insurance",
        "Supplement to Original Medicare using standardized plan designs. Not Medicare Advantage and not a Part D drug plan. "
        "Not offered in Massachusetts, Minnesota, or Wisconsin, which use their own benefit structures.",
        "MEDIGAP",
        ["age"],
        [
            T("medigap-ghd", "High-deductible Plan G", 72.0, "high-deductible Plan G"),
            T("medigap-n", "Plan N", 115.0, "standardized Plan N"),
            T("medigap-g", "Plan G", 165.0, "standardized Plan G"),
        ],
        min_age=65,
    ),
    P(
        "pet-accident-illness",
        "pet",
        "Pet Insurance",
        "Accident and illness coverage for a dog or cat, with an optional wellness tier. Not equine or livestock mortality.",
        "ALL",
        ["pet_age", "species"],
        [
            T("pet-accident", "Accident Only", 22.0, "accidents"),
            T("pet-illness", "Accident and Illness", 46.0, "accidents and illnesses"),
            T("pet-wellness", "Wellness", 72.0, "accidents, illnesses, and wellness"),
        ],
    ),
    P(
        "travel-trip",
        "travel",
        "Trip Insurance",
        "Trip cancellation, interruption, and emergency medical benefits for a single trip. "
        "One-time premium. Not a health insurance plan.",
        "ALL",
        ["trip_days", "trip_cost"],
        [
            T("trip-basic", "Basic", 35.0, "cancellation up to trip cost"),
            T("trip-standard", "Standard", 75.0, "cancellation plus emergency medical"),
            T("trip-premium", "Premium", 140.0, "cancellation, medical, and baggage"),
        ],
        basis="term",
    ),
    P(
        "valuables-scheduled",
        "valuables",
        "Scheduled Valuables Insurance",
        "Scheduled coverage for jewelry, fine art, and musical instruments, broader than the special limits inside a homeowners policy.",
        "ALL",
        ["item_count", "coverage_amount"],
        [
            T("valuables-10", "$10,000 Schedule", 12.0, "$10,000 scheduled"),
            T("valuables-25", "$25,000 Schedule", 28.0, "$25,000 scheduled"),
            T("valuables-75", "$75,000 Schedule", 55.0, "$75,000 scheduled"),
        ],
    ),
    P(
        "identity-recovery",
        "identity",
        "Identity Theft Insurance",
        "Expense reimbursement and recovery help after identity theft. Not a business cyber policy.",
        "ALL",
        ["occupants"],
        [
            T("identity-individual", "Individual", 8.0, "$25,000 expense reimbursement"),
            T("identity-family", "Family", 14.0, "$1,000,000 expense reimbursement"),
        ],
    ),
    P(
        "event-wedding",
        "event",
        "Wedding Insurance",
        "Cancellation and postponement, plus event liability, for one wedding. One-time premium.",
        "ALL",
        ["event_guests", "event_days"],
        [
            T("wedding-basic", "Basic", 120.0, "$15,000 cancellation"),
            T("wedding-standard", "Standard", 240.0, "$35,000 cancellation"),
            T("wedding-premium", "Premium", 420.0, "$75,000 cancellation"),
        ],
        basis="term",
    ),
    P(
        "event-liability",
        "event",
        "Special Event Liability",
        "General liability for one short special event. One-time premium. Cancellation coverage is a different policy.",
        "ALL",
        ["event_guests", "event_days"],
        [
            T("event-1m", "$1M Event", 150.0, "$1,000,000 liability"),
            T("event-2m", "$2M Event", 300.0, "$2,000,000 liability"),
            T("event-5m", "$5M Event", 550.0, "$5,000,000 liability"),
        ],
        basis="term",
    ),
    P(
        "commercial-bop",
        "commercial",
        "Business Owners Policy",
        "Property and general liability packaged for a small business. Not professional liability, commercial auto, or workers compensation.",
        "ALL",
        ["annual_revenue", "employee_count", "industry_code"],
        [
            T("bop-basic", "Basic BOP", 145.0, "$500,000 liability"),
            T("bop-standard", "Standard BOP", 220.0, "$1,000,000 liability"),
            T("bop-premium", "Premium BOP", 340.0, "$2,000,000 liability"),
        ],
    ),
    P(
        "commercial-general-liability",
        "commercial",
        "General Liability Insurance",
        "Premises, operations, and products liability for a business. Not professional liability and not auto liability.",
        "ALL",
        ["annual_revenue", "employee_count"],
        [
            T("gl-500", "$500k GL", 75.0, "$500,000 occurrence"),
            T("gl-1m", "$1M GL", 130.0, "$1,000,000 occurrence"),
            T("gl-2m", "$2M GL", 210.0, "$2,000,000 occurrence"),
        ],
    ),
    P(
        "commercial-property",
        "commercial",
        "Commercial Property Insurance",
        "Building and business personal property. Not liability and not flood.",
        "ALL",
        ["square_feet", "year_built", "protection_class"],
        [
            T("cprop-250", "$250k Property", 160.0, "$250,000 building and contents"),
            T("cprop-1m", "$1M Property", 280.0, "$1,000,000 building and contents"),
            T("cprop-2m", "$2M Property", 450.0, "$2,000,000 building and contents"),
        ],
    ),
    P(
        "commercial-auto",
        "commercial",
        "Commercial Auto Insurance",
        "Liability and physical damage for autos titled to or used in a business. Not a personal auto policy.",
        "ALL",
        ["num_vehicles", "annual_mileage", "driver_age"],
        [
            T("cauto-basic", "Basic", 210.0, "50/100/50"),
            T("cauto-standard", "Standard", 360.0, "100/300/100"),
            T("cauto-premium", "Premium", 540.0, "250/500/100"),
        ],
    ),
    P(
        "commercial-umbrella",
        "commercial",
        "Commercial Umbrella Insurance",
        "Excess liability over scheduled commercial general liability and commercial auto. It does not replace those policies.",
        "ALL",
        ["annual_revenue", "employee_count"],
        [
            T("cumb-1m", "$1M Umbrella", 85.0, "$1,000,000"),
            T("cumb-5m", "$5M Umbrella", 140.0, "$5,000,000"),
            T("cumb-10m", "$10M Umbrella", 210.0, "$10,000,000"),
        ],
    ),
    P(
        "commercial-crime",
        "commercial",
        "Commercial Crime Insurance",
        "Employee dishonesty and theft of money or securities. Often excluded from a business owners policy unless scheduled.",
        "ALL",
        ["employee_count", "annual_revenue"],
        [
            T("crime-50", "$50k Crime", 40.0, "$50,000 employee dishonesty"),
            T("crime-100", "$100k Crime", 75.0, "$100,000 employee dishonesty"),
            T("crime-250", "$250k Crime", 120.0, "$250,000 employee dishonesty"),
        ],
    ),
    P(
        "commercial-equipment-breakdown",
        "commercial",
        "Equipment Breakdown Insurance",
        "Mechanical and electrical breakdown of boilers, HVAC, and business equipment. Not ordinary wear and not a maintenance contract.",
        "ALL",
        ["square_feet", "year_built"],
        [
            T("equip-basic", "Basic", 35.0, "$100,000 equipment"),
            T("equip-standard", "Standard", 60.0, "$500,000 equipment"),
            T("equip-premium", "Premium", 95.0, "$1,000,000 equipment"),
        ],
    ),
    P(
        "commercial-inland-marine",
        "commercial",
        "Inland Marine Insurance",
        "Moveable equipment and property away from your premises, including contractors' equipment.",
        "ALL",
        ["scheduled_value", "claims_count"],
        [
            T("im-tools", "Tools", 60.0, "scheduled tools"),
            T("im-contractors", "Contractors Equipment", 110.0, "scheduled contractors equipment"),
            T("im-installation", "Installation Floater", 180.0, "property being installed"),
        ],
    ),
    P(
        "commercial-builders-risk",
        "commercial",
        "Builders Risk Insurance",
        "Course-of-construction property coverage for the project term. One-time premium. Not completed-operations liability.",
        "ALL",
        ["project_value", "project_months"],
        [
            T("builders-250", "$250k Project", 400.0, "$250,000 project"),
            T("builders-1m", "$1M Project", 900.0, "$1,000,000 project"),
            T("builders-5m", "$5M Project", 1800.0, "$5,000,000 project"),
        ],
        basis="term",
    ),
    P(
        "commercial-liquor",
        "commercial",
        "Liquor Liability Insurance",
        "Liability from selling, serving, or furnishing alcohol. Not a substitute for general liability.",
        "ALL",
        ["annual_revenue", "employee_count"],
        [
            T("liquor-500", "$500k Liquor", 130.0, "$500,000"),
            T("liquor-1m", "$1M Liquor", 220.0, "$1,000,000"),
        ],
        min_age=21,
    ),
    P(
        "commercial-flood",
        "flood",
        "Commercial Flood Insurance",
        "Building and contents flood coverage for a business. Not included in a business owners or commercial property policy.",
        "ALL",
        ["elevation_ft", "square_feet"],
        [
            T("cflood-250", "$250k Flood", 140.0, "$250,000 building"),
            T("cflood-500", "$500k Flood", 240.0, "$500,000 building"),
            T("cflood-1m", "$1M Flood", 380.0, "$1,000,000 building"),
        ],
    ),
    P(
        "commercial-directors-officers",
        "commercial",
        "Directors and Officers Insurance",
        "Private-company directors and officers liability. Not employment-practices liability.",
        "ALL",
        ["annual_revenue", "employee_count"],
        [
            T("do-1m", "$1M D&O", 110.0, "$1,000,000"),
            T("do-2m", "$2M D&O", 190.0, "$2,000,000"),
            T("do-5m", "$5M D&O", 320.0, "$5,000,000"),
        ],
    ),
    P(
        "commercial-epli",
        "commercial",
        "Employment Practices Liability",
        "Liability for employment claims such as wrongful termination, harassment, and discrimination. Not workers compensation.",
        "ALL",
        ["employee_count", "claims_count"],
        [
            T("epli-1m", "$1M EPLI", 70.0, "$1,000,000"),
            T("epli-2m", "$2M EPLI", 120.0, "$2,000,000"),
        ],
    ),
    P(
        "cyber-personal",
        "cyber",
        "Personal Cyber Insurance",
        "Help with online fraud, data restoration, and cyber extortion expenses for a household. Not a business cyber policy.",
        "ALL",
        ["occupants"],
        [
            T("pcyber-basic", "Basic", 12.0, "$25,000"),
            T("pcyber-plus", "Plus", 22.0, "$100,000"),
        ],
    ),
    P(
        "cyber-commercial",
        "cyber",
        "Commercial Cyber Insurance",
        "Incident response, data-breach liability, and business interruption from a network security event. "
        "Not a promise to fund a ransom.",
        "ALL",
        ["annual_revenue", "employee_count"],
        [
            T("cyber-1m", "$1M Cyber", 120.0, "$1,000,000"),
            T("cyber-2m", "$2M Cyber", 220.0, "$2,000,000"),
            T("cyber-5m", "$5M Cyber", 380.0, "$5,000,000"),
        ],
    ),
    P(
        "professional-eo",
        "professional",
        "Professional Liability Insurance",
        "Liability for errors in professional services. Not premises bodily-injury general liability.",
        "ALL",
        ["annual_revenue", "years_in_business", "claims_count"],
        [
            T("eo-1m", "$1M E&O", 95.0, "$1,000,000"),
            T("eo-2m", "$2M E&O", 175.0, "$2,000,000"),
            T("eo-5m", "$5M E&O", 290.0, "$5,000,000"),
        ],
    ),
    P(
        "professional-medmal",
        "professional",
        "Medical Professional Liability",
        "Medical professional liability for an individual practitioner. "
        "This demo prices an occurrence-style estimate and is not a claims-made tail quote.",
        "ALL",
        ["years_in_practice", "claims_count"],
        [
            T("medmal-1m", "$1M / $3M", 450.0, "$1,000,000 / $3,000,000"),
            T("medmal-2m", "$2M / $4M", 900.0, "$2,000,000 / $4,000,000"),
            T("medmal-high", "Higher limits", 1600.0, "$5,000,000"),
        ],
    ),
    P(
        "workers-comp",
        "workers_comp",
        "Workers Compensation Insurance",
        "Statutory workers compensation and employers liability where a private carrier can write the coverage. "
        "Not available in North Dakota, Ohio, Washington, or Wyoming, which use state funds.",
        "WC_PRIVATE",
        ["annual_payroll", "employee_count"],
        [
            T("wc-el-100", "EL $100k", 180.0, "statutory plus $100,000 employers liability"),
            T("wc-el-500", "EL $500k", 320.0, "statutory plus $500,000 employers liability"),
            T("wc-el-1m", "EL $1M", 560.0, "statutory plus $1,000,000 employers liability"),
        ],
    ),
    P(
        "trucking-liability",
        "trucking",
        "Trucking Liability Insurance",
        "Auto liability for a for-hire motor carrier. Cargo is a separate policy. Not a personal auto policy.",
        "ALL",
        ["num_vehicles", "radius_miles", "annual_mileage"],
        [
            T("truck-750", "$750k Liability", 480.0, "$750,000 liability"),
            T("truck-1m", "$1M Liability", 820.0, "$1,000,000 liability"),
            T("truck-2m", "$2M Liability", 1400.0, "$2,000,000 liability"),
        ],
    ),
    P(
        "trucking-cargo",
        "trucking",
        "Motor Truck Cargo Insurance",
        "Legal liability for freight in your care, custody, or control. Not auto liability.",
        "ALL",
        ["num_vehicles", "radius_miles", "scheduled_value"],
        [
            T("cargo-100", "$100k Cargo", 90.0, "$100,000 per occurrence"),
            T("cargo-250", "$250k Cargo", 160.0, "$250,000 per occurrence"),
        ],
    ),
    P(
        "farm-farmowners",
        "farm",
        "Farmowners Insurance",
        "Farm dwelling, household personal property, and farm liability. Not crop-yield insurance and not livestock mortality.",
        "AG",
        ["acres", "year_built", "roof_age"],
        [
            T("farm-basic", "Basic", 140.0, "$350,000 dwelling"),
            T("farm-standard", "Standard", 230.0, "$600,000 dwelling"),
            T("farm-premium", "Premium", 360.0, "$1,000,000 dwelling"),
        ],
    ),
    P(
        "farm-livestock",
        "farm",
        "Livestock Mortality Insurance",
        "Mortality coverage for cattle and other livestock. Not crop insurance and not horse mortality.",
        "AG",
        ["head_count", "animal_value"],
        [
            T("livestock-basic", "Basic", 80.0, "named-peril mortality"),
            T("livestock-standard", "Standard", 150.0, "broader mortality"),
            T("livestock-premium", "Premium", 260.0, "mortality plus major medical"),
        ],
    ),
    P(
        "farm-crop",
        "crop",
        "Crop Insurance",
        "Yield-style multi-peril coverage for one growing season. Not livestock and not a farmowners policy. "
        "One-time seasonal premium.",
        "AG",
        ["acres", "crop_type"],
        [
            T("crop-basic", "Basic Yield", 600.0, "50% of expected yield"),
            T("crop-standard", "Standard Yield", 1400.0, "65% of expected yield"),
            T("crop-premium", "Higher Yield", 2800.0, "75% of expected yield"),
        ],
        basis="term",
    ),
    P(
        "equine-mortality",
        "equine",
        "Equine Mortality Insurance",
        "Mortality coverage for a horse. Not a farmowners policy and not pet insurance.",
        "AG",
        ["horse_count", "horse_value"],
        [
            T("equine-mortality", "Mortality", 45.0, "mortality"),
            T("equine-major", "Major Medical", 90.0, "mortality and major medical"),
            T("equine-full", "Full", 160.0, "mortality, major medical, and loss of use"),
        ],
    ),
    P(
        "surety-contract",
        "surety",
        "Contract Surety Bond",
        "Performance and payment bond for a construction contract. A bond is not an insurance policy; "
        "the principal may have to repay the surety. One-time premium estimate, not a credit approval.",
        "ALL",
        ["contract_value", "years_in_business"],
        [
            T("surety-250", "$250k Bond", 750.0, "$250,000 bond"),
            T("surety-1m", "$1M Bond", 1800.0, "$1,000,000 bond"),
            T("surety-5m", "$5M Bond", 4000.0, "$5,000,000 bond"),
        ],
        basis="term",
    ),
]


LEGACY = {
    "CA": {
        "disclosures": [
            (
                "ca-rate-notice",
                "Premiums are based on approved rates filed with the California Department of Insurance.",
            ),
            (
                "ca-non-binding",
                "This quote is an estimate and is not a binding offer of insurance.",
            ),
        ],
        "prohibited": ["guaranteed approval", "lowest price guaranteed"],
    },
    "NY": {
        "disclosures": [
            (
                "ny-licensed",
                "Demo Insurance Co. is licensed in New York. This call may be recorded.",
            ),
            (
                "ny-estimate",
                "Quoted premium is an estimate pending full application review.",
            ),
        ],
        "prohibited": ["instant binding", "no medical review required"],
    },
    "TX": {
        "disclosures": [
            (
                "tx-availability",
                "Coverage availability and rates may vary based on underwriting guidelines.",
            ),
            (
                "tx-non-binding",
                "This is a preliminary quote subject to verification.",
            ),
        ],
        "prohibited": ["no risk", "everyone qualifies"],
    },
    "FL": {
        "disclosures": [
            (
                "fl-hurricane",
                "Property policies may exclude or limit hurricane and flood damage.",
            ),
            (
                "fl-non-binding",
                "This quote is non-binding until application is accepted.",
            ),
        ],
        "prohibited": ["full hurricane coverage included"],
    },
    "IL": {
        "disclosures": [
            (
                "il-privacy",
                "We may use information from consumer reporting agencies for underwriting.",
            ),
            (
                "il-estimate",
                "Premiums shown are estimates only.",
            ),
        ],
        "prohibited": ["no credit check"],
    },
}

NATIONAL_PROHIBITED = [
    "guaranteed approval",
    "lowest price guaranteed",
    "everyone qualifies",
    "instant binding",
    "based on your gender",
    "based on your credit score",
]


def _disclosure(disclosure_id: str, text: str) -> dict:
    return {
        "disclosure_id": disclosure_id,
        "text": text,
        "required_before_quote_acceptance": True,
    }


def build_pack(code: str) -> dict:
    name = STATE_NAMES[code]
    regulator = REGULATORS[code]
    legacy = LEGACY.get(code, {"disclosures": [], "prohibited": []})
    disclosures = [
        _disclosure(disclosure_id, text) for disclosure_id, text in legacy["disclosures"]
    ]
    seen = {item["disclosure_id"] for item in disclosures}

    def add(disclosure_id: str, text: str) -> None:
        if disclosure_id not in seen:
            disclosures.append(_disclosure(disclosure_id, text))
            seen.add(disclosure_id)

    prefix = code.lower()
    add(
        f"{prefix}-non-binding",
        "This quote is an estimate and is not a binder or an offer of insurance until an application is accepted.",
    )
    add(
        f"{prefix}-licensed",
        f"Demo Insurance Co. is appointed in {name}. The {regulator} regulates this transaction. This call may be recorded.",
    )
    add(
        f"{prefix}-rating-limits",
        "This estimate does not use credit, gender, or marital status. It is not a filed rate and underwriting can change it.",
    )
    add(
        f"{prefix}-property-perils",
        "A homeowners, condo, renters, landlord, or mobile-home estimate does not include flood or earthquake. "
        "Wind, hail, hurricane, and wildfire deductibles can be separate when those perils are covered.",
    )
    notes: list[str] = []
    if code in NO_FAULT:
        add(
            f"{prefix}-nofault",
            f"{name} is a no-fault auto state. Personal injury protection may be mandatory, and this quote does not promise to pay every medical bill from a crash.",
        )
        notes.append("No-fault auto state. Do not describe the quote as covering all crash-related medical bills.")
    elif code in PIP_ADDON:
        add(
            f"{prefix}-pip",
            f"{name} may require or commonly include personal injury protection on an auto policy. This quote does not promise to pay every medical bill from a crash.",
        )
        notes.append("PIP may be required. Do not describe the quote as covering all crash-related medical bills.")
    if code in HURRICANE:
        add(
            f"{prefix}-hurricane",
            f"Coastal wind and hurricane deductibles are common in {name}. Do not say a property quote includes full hurricane coverage.",
        )
        notes.append("Hurricane and coastal wind exposure. Separate wind deductibles are common.")
    if code in WILDFIRE:
        notes.append("Wildfire exposure. Do not promise that a property quote has no wildfire deductible or exclusion.")
    if code in HAIL_TORNADO:
        notes.append("Hail and tornado are significant property perils. Wind and hail deductibles may be separate.")
    if code in MONOPOLISTIC_WC:
        fund = WC_FUND_NAME[code]
        add(
            f"{prefix}-wc-fund",
            f"Private workers compensation is not offered in {name}. Employers obtain coverage through {fund}.",
        )
        notes.append(
            f"Monopolistic workers compensation. Do not offer the private workers compensation product. Direct the caller to {fund}."
        )
    if code in MEDIGAP_EXCLUDED:
        add(
            f"{prefix}-medigap",
            f"{name} does not use the NAIC standardized Medicare supplement plans. This carrier's medigap product is not available here.",
        )
        notes.append("Standardized Medicare supplement is not eligible in this state.")
    if code in CREDIT_RESTRICTED:
        notes.append(
            "Credit-based insurance scores are restricted for personal auto and home. This quote does not use credit."
        )
    if code in GENDER_NEUTRAL_AUTO:
        notes.append("Do not describe personal auto rates as based on gender. This rating plan does not use gender.")
    if code not in {"CA", "NY", "TX", "FL", "IL"} and not notes:
        notes.append("Standard appointed state. Product eligibility still varies by line.")

    prohibited: list[str] = []
    for phrase in list(legacy["prohibited"]) + NATIONAL_PROHIBITED:
        if phrase not in prohibited:
            prohibited.append(phrase)
    if code in MONOPOLISTIC_WC:
        prohibited.append("we can write your workers compensation")

    return {
        "state": code,
        "regulator": regulator,
        "market_notes": notes,
        "disclosures": disclosures,
        "prohibited_phrases": prohibited,
    }


def main() -> None:
    PRODUCTS.mkdir(parents=True, exist_ok=True)
    COMPLIANCE.mkdir(parents=True, exist_ok=True)
    written_ids: set[str] = set()
    for document in PRODUCTS_DATA:
        product_id = document["product_id"]
        if product_id in written_ids:
            raise SystemExit(f"duplicate product_id {product_id}")
        written_ids.add(product_id)
        path = PRODUCTS / f"{product_id}.yaml"
        path.write_text(
            yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
    for code in ALL_CODES:
        path = COMPLIANCE / f"{code}.yaml"
        path.write_text(
            yaml.safe_dump(build_pack(code), sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
    print(f"products={len(PRODUCTS_DATA)} states={len(ALL_CODES)}")


if __name__ == "__main__":
    main()
