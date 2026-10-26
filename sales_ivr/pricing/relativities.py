"""Illustrative jurisdiction factors.

These are not filed rates. They only make a quote in a high-cost state come
out differently from the same risk in a low-cost state. Missing codes use 1.00.
"""

from __future__ import annotations

LINE_GROUP: dict[str, str] = {
    "auto": "auto",
    "motorcycle": "auto",
    "rv": "auto",
    "powersports": "auto",
    "trucking": "auto",
    "aviation": "auto",
    "umbrella": "auto",
    "home": "property",
    "condo": "property",
    "landlord": "property",
    "mobile_home": "property",
    "renters": "property",
    "flood": "property",
    "earthquake": "property",
    "valuables": "property",
    "boat": "property",
    "pet": "property",
    "life": "life",
    "medigap": "life",
    "supplemental": "life",
    "dental": "life",
    "vision": "life",
    "disability": "life",
    "long_term_care": "life",
    "commercial": "commercial",
    "professional": "commercial",
    "cyber": "commercial",
    "surety": "commercial",
    "workers_comp": "workers_comp",
    "farm": "farm",
    "crop": "farm",
    "equine": "farm",
    "travel": "default",
    "identity": "default",
    "event": "default",
}

GROUP_LABEL: dict[str, str] = {
    "auto": "vehicle",
    "property": "property",
    "life": "life and health",
    "commercial": "commercial",
    "workers_comp": "workers compensation",
    "farm": "farm",
    "default": "base",
}

_AUTO: dict[str, float] = {
    "MI": 1.42,
    "LA": 1.36,
    "FL": 1.30,
    "NY": 1.26,
    "NJ": 1.22,
    "NV": 1.20,
    "CA": 1.18,
    "DC": 1.18,
    "DE": 1.18,
    "MA": 1.16,
    "RI": 1.16,
    "CT": 1.14,
    "CO": 1.14,
    "GA": 1.12,
    "KY": 1.12,
    "TX": 1.10,
    "MD": 1.10,
    "SC": 1.08,
    "HI": 1.08,
    "PA": 1.08,
    "AZ": 1.06,
    "ID": 0.84,
    "ME": 0.86,
    "VT": 0.86,
    "ND": 0.86,
    "IA": 0.88,
    "SD": 0.88,
    "WY": 0.88,
    "NE": 0.90,
    "WI": 0.90,
    "OH": 0.92,
    "IN": 0.92,
    "NC": 0.94,
    "KS": 0.94,
    "NH": 0.96,
}

_PROPERTY: dict[str, float] = {
    "FL": 1.48,
    "LA": 1.42,
    "TX": 1.28,
    "OK": 1.26,
    "CO": 1.20,
    "CA": 1.18,
    "MS": 1.16,
    "AL": 1.14,
    "HI": 1.14,
    "SC": 1.12,
    "NY": 1.12,
    "NJ": 1.12,
    "KS": 1.10,
    "NE": 1.08,
    "GA": 1.08,
    "OR": 1.08,
    "NC": 1.06,
    "AR": 1.06,
    "WA": 1.06,
    "ID": 0.86,
    "ME": 0.88,
    "VT": 0.88,
    "IA": 0.90,
    "OH": 0.90,
    "WI": 0.90,
    "IN": 0.92,
}

_LIFE: dict[str, float] = {
    "NY": 1.08,
    "CA": 1.06,
    "NJ": 1.05,
    "FL": 1.04,
    "HI": 1.04,
    "UT": 0.94,
    "ID": 0.94,
    "IA": 0.96,
    "WI": 0.96,
    "NE": 0.97,
}

_COMMERCIAL: dict[str, float] = {
    "NY": 1.18,
    "CA": 1.16,
    "FL": 1.14,
    "NJ": 1.12,
    "LA": 1.10,
    "IL": 1.08,
    "TX": 1.06,
    "DC": 1.06,
    "ID": 0.90,
    "IN": 0.92,
    "IA": 0.92,
    "UT": 0.92,
    "WI": 0.94,
    "NC": 0.96,
}

_WC: dict[str, float] = {
    "CA": 1.32,
    "NY": 1.28,
    "NJ": 1.18,
    "DE": 1.12,
    "CT": 1.10,
    "IL": 1.10,
    "FL": 1.08,
    "MA": 1.08,
    "TX": 0.98,
    "NC": 0.94,
    "WI": 0.92,
    "UT": 0.90,
    "AR": 0.88,
    "IN": 0.86,
}

_FARM: dict[str, float] = {
    "OK": 1.22,
    "KS": 1.18,
    "TX": 1.16,
    "NE": 1.16,
    "ND": 1.14,
    "SD": 1.14,
    "FL": 1.12,
    "IA": 1.08,
    "CA": 1.08,
    "IL": 1.06,
    "MN": 1.04,
    "ID": 0.90,
    "ME": 0.92,
    "VT": 0.92,
    "OH": 0.94,
}

_TABLES: dict[str, dict[str, float]] = {
    "auto": _AUTO,
    "property": _PROPERTY,
    "life": _LIFE,
    "commercial": _COMMERCIAL,
    "workers_comp": _WC,
    "farm": _FARM,
    "default": {},
}


def relativity_for(product_line: str, state: str) -> tuple[float, str]:
    group = LINE_GROUP.get(product_line, "default")
    multiplier = _TABLES.get(group, {}).get(state, 1.0)
    label = GROUP_LABEL.get(group, "base")
    return multiplier, f"{state} {label} jurisdiction factor"
