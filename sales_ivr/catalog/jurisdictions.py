"""US states and the District of Columbia, plus eligibility regions.

Postal codes are the only geography the catalog, compliance packs, and web
chat accept. Territories are not appointed.
"""

from __future__ import annotations

import re

# Postal order, with DC after Delaware.
ALL_CODES: tuple[str, ...] = (
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "DC",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
)

ALL_SET = frozenset(ALL_CODES)

STATE_NAMES: dict[str, str] = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "DC": "District of Columbia",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
}

REGULATORS: dict[str, str] = {
    "AL": "Alabama Department of Insurance",
    "AK": "Alaska Division of Insurance",
    "AZ": "Arizona Department of Insurance and Financial Institutions",
    "AR": "Arkansas Insurance Department",
    "CA": "California Department of Insurance",
    "CO": "Colorado Division of Insurance",
    "CT": "Connecticut Insurance Department",
    "DE": "Delaware Department of Insurance",
    "DC": "Department of Insurance, Securities and Banking",
    "FL": "Florida Office of Insurance Regulation",
    "GA": "Georgia Office of the Commissioner of Insurance",
    "HI": "Hawaii Insurance Division",
    "ID": "Idaho Department of Insurance",
    "IL": "Illinois Department of Insurance",
    "IN": "Indiana Department of Insurance",
    "IA": "Iowa Insurance Division",
    "KS": "Kansas Insurance Department",
    "KY": "Kentucky Department of Insurance",
    "LA": "Louisiana Department of Insurance",
    "ME": "Maine Bureau of Insurance",
    "MD": "Maryland Insurance Administration",
    "MA": "Massachusetts Division of Insurance",
    "MI": "Michigan Department of Insurance and Financial Services",
    "MN": "Minnesota Department of Commerce",
    "MS": "Mississippi Insurance Department",
    "MO": "Missouri Department of Commerce and Insurance",
    "MT": "Montana Commissioner of Securities and Insurance",
    "NE": "Nebraska Department of Insurance",
    "NV": "Nevada Division of Insurance",
    "NH": "New Hampshire Insurance Department",
    "NJ": "New Jersey Department of Banking and Insurance",
    "NM": "New Mexico Office of Superintendent of Insurance",
    "NY": "New York Department of Financial Services",
    "NC": "North Carolina Department of Insurance",
    "ND": "North Dakota Insurance Department",
    "OH": "Ohio Department of Insurance",
    "OK": "Oklahoma Insurance Department",
    "OR": "Oregon Division of Financial Regulation",
    "PA": "Pennsylvania Insurance Department",
    "RI": "Rhode Island Insurance Division",
    "SC": "South Carolina Department of Insurance",
    "SD": "South Dakota Division of Insurance",
    "TN": "Tennessee Department of Commerce and Insurance",
    "TX": "Texas Department of Insurance",
    "UT": "Utah Insurance Department",
    "VT": "Vermont Department of Financial Regulation",
    "VA": "Virginia State Corporation Commission Bureau of Insurance",
    "WA": "Washington State Office of the Insurance Commissioner",
    "WV": "West Virginia Offices of the Insurance Commissioner",
    "WI": "Wisconsin Office of the Commissioner of Insurance",
    "WY": "Wyoming Department of Insurance",
}

# Traditional or choice no-fault. PIP is part of the auto contract.
NO_FAULT: frozenset[str] = frozenset(
    {"FL", "HI", "KS", "KY", "MA", "MI", "MN", "NJ", "NY", "ND", "PA", "UT"}
)

# Add-on PIP without a full tort threshold. Still call out medical coverage limits.
PIP_ADDON: frozenset[str] = frozenset({"AR", "DC", "DE", "MD", "OR"})

# Private carriers cannot write workers compensation.
MONOPOLISTIC_WC: frozenset[str] = frozenset({"ND", "OH", "WA", "WY"})

WC_FUND_NAME: dict[str, str] = {
    "ND": "North Dakota Workforce Safety & Insurance",
    "OH": "the Ohio Bureau of Workers' Compensation",
    "WA": "the Washington State Department of Labor & Industries",
    "WY": "Wyoming Workforce Services",
}

# These states do not use the NAIC standardized Medigap plans.
MEDIGAP_EXCLUDED: frozenset[str] = frozenset({"MA", "MN", "WI"})

# Personal auto and home rating does not use credit in this plan, and these
# states restrict credit-based insurance scores.
CREDIT_RESTRICTED: frozenset[str] = frozenset({"CA", "HI"})

# Personal auto rating in this plan is gender-neutral. These states also
# restrict gender as an auto rating factor.
GENDER_NEUTRAL_AUTO: frozenset[str] = frozenset({"CA", "HI", "MA", "MI", "MT", "NC", "PA"})

HURRICANE: frozenset[str] = frozenset(
    {
        "AL",
        "CT",
        "DE",
        "FL",
        "GA",
        "HI",
        "LA",
        "MA",
        "MD",
        "MS",
        "NC",
        "NJ",
        "NY",
        "RI",
        "SC",
        "TX",
        "VA",
    }
)

WILDFIRE: frozenset[str] = frozenset(
    {"AZ", "CA", "CO", "ID", "MT", "NM", "NV", "OK", "OR", "TX", "UT", "WA", "WY"}
)

HAIL_TORNADO: frozenset[str] = frozenset(
    {"AL", "AR", "IA", "IL", "IN", "KS", "KY", "MO", "MS", "NE", "OK", "SD", "TN", "TX"}
)

EARTHQUAKE: frozenset[str] = frozenset(
    {
        "AK",
        "AR",
        "AZ",
        "CA",
        "CO",
        "HI",
        "ID",
        "IL",
        "KY",
        "MO",
        "MS",
        "MT",
        "NM",
        "NV",
        "OK",
        "OR",
        "SC",
        "TN",
        "UT",
        "WA",
        "WY",
    }
)

# Ocean, Gulf, Great Lakes, Alaska, Hawaii, and the District (Potomac).
COASTAL: frozenset[str] = frozenset(
    {
        "AL",
        "AK",
        "CA",
        "CT",
        "DC",
        "DE",
        "FL",
        "GA",
        "HI",
        "IL",
        "IN",
        "LA",
        "MA",
        "MD",
        "ME",
        "MI",
        "MN",
        "MS",
        "NC",
        "NH",
        "NJ",
        "NY",
        "OH",
        "OR",
        "PA",
        "RI",
        "SC",
        "TX",
        "VA",
        "WA",
        "WI",
    }
)

SNOWBELT: frozenset[str] = frozenset(
    {
        "AK",
        "CO",
        "CT",
        "IA",
        "ID",
        "MA",
        "ME",
        "MI",
        "MN",
        "MT",
        "ND",
        "NE",
        "NH",
        "NY",
        "OH",
        "OR",
        "PA",
        "RI",
        "SD",
        "UT",
        "VT",
        "WA",
        "WI",
        "WY",
    }
)

AG: frozenset[str] = ALL_SET - {"DC"}
MEDIGAP: frozenset[str] = ALL_SET - MEDIGAP_EXCLUDED
WC_PRIVATE: frozenset[str] = ALL_SET - MONOPOLISTIC_WC

REGIONS: dict[str, tuple[str, ...]] = {
    "ALL": ALL_CODES,
    "AG": tuple(code for code in ALL_CODES if code in AG),
    "MEDIGAP": tuple(code for code in ALL_CODES if code in MEDIGAP),
    "WC_PRIVATE": tuple(code for code in ALL_CODES if code in WC_PRIVATE),
    "EARTHQUAKE": tuple(code for code in ALL_CODES if code in EARTHQUAKE),
    "COASTAL": tuple(code for code in ALL_CODES if code in COASTAL),
    "SNOWBELT": tuple(code for code in ALL_CODES if code in SNOWBELT),
}

# Two-letter codes that are also ordinary words or city abbreviations.
# Accept them only when the text marks them as a state (uppercase plus a
# nearby cue, a comma, or a ZIP).
AMBIGUOUS_CODES = frozenset(
    {"AL", "CO", "DE", "HI", "ID", "IN", "LA", "MA", "MD", "ME", "OH", "OK", "OR", "PA"}
)

_NAME_TO_CODE = {name.lower(): code for code, name in STATE_NAMES.items()}
_DC_RE = re.compile(
    r"\b(?:district of columbia|washington,?\s+d\.?\s*c\.?|washington\s+dc)\b",
    re.IGNORECASE,
)
_CODE_RE = re.compile(r"\b([A-Za-z]{2})\b")
_CUE_BEFORE_RE = re.compile(
    r"(?:state|live|lives|living|located|resident of|in)\s*$",
    re.IGNORECASE,
)


def expand_eligible_states(tokens: list[str]) -> list[str]:
    """Turn ALL / region tokens / postal codes into a de-duplicated code list."""

    seen: set[str] = set()
    expanded: list[str] = []
    for token in tokens:
        key = str(token).strip().upper()
        if key in {"*", "ALL"}:
            codes: tuple[str, ...] = ALL_CODES
        elif key in REGIONS:
            codes = REGIONS[key]
        elif key in ALL_SET:
            codes = (key,)
        else:
            raise ValueError(f"Unknown state or eligibility region: {token}")
        for code in codes:
            if code not in seen:
                seen.add(code)
                expanded.append(code)
    if not expanded:
        raise ValueError("eligible_states resolved to an empty list")
    return expanded


def _contained(span: tuple[int, int, str], others: list[tuple[int, int, str]]) -> bool:
    start, end, _code = span
    length = end - start
    for other_start, other_end, _other in others:
        if other_start <= start and other_end >= end and (other_end - other_start) > length:
            return True
    return False


def _code_is_explicit(text: str, match: re.Match[str]) -> bool:
    code = match.group(1).upper()
    if code not in ALL_SET:
        return False
    if code not in AMBIGUOUS_CODES:
        return True
    if match.group(1) != match.group(1).upper():
        return False
    before = text[max(0, match.start() - 16) : match.start()]
    after = text[match.end() : match.end() + 12]
    if _CUE_BEFORE_RE.search(before):
        return True
    if re.match(r"\s*,", after):
        return True
    if re.match(r"\s+\d{5}\b", after):
        return True
    return False


def normalize_state(raw: str | None) -> str | None:
    """Resolve a state name or postal code. Returns None when none is named."""

    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None

    spans: list[tuple[int, int, str]] = []
    for match in _DC_RE.finditer(text):
        spans.append((match.start(), match.end(), "DC"))

    lowered = text.lower()
    for name, code in _NAME_TO_CODE.items():
        if code == "DC":
            continue
        for match in re.finditer(rf"\b{re.escape(name)}\b", lowered):
            spans.append((match.start(), match.end(), code))

    for match in _CODE_RE.finditer(text):
        if _code_is_explicit(text, match):
            spans.append((match.start(), match.end(), match.group(1).upper()))

    spans = [span for span in spans if not _contained(span, spans)]
    if not spans:
        return None

    def sort_key(span: tuple[int, int, str]) -> tuple[int, int]:
        start, end, _code = span
        before = text[max(0, start - 16) : start]
        cued = 1 if _CUE_BEFORE_RE.search(before) else 0
        return (cued, start)

    # Prefer a state the speaker is "in"; otherwise the last one named.
    cued = [span for span in spans if sort_key(span)[0] == 1]
    pool = cued or spans
    return max(pool, key=lambda span: span[0])[2]


def supported_states_label() -> str:
    return "all 50 states and the District of Columbia"
