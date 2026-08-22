from __future__ import annotations
import re
import requests

from ..models import NOT_STATED

def get_json(url, params=None, headers=None, timeout=20):
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()

def get_text(url, params=None, headers=None, timeout=20):
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text

def post_json(url, json=None, headers=None, timeout=30):
    r = requests.post(url, json=json, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()

_TAGS = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")

def strip_html(text: str | None) -> str:
    """Plain text from a posting body. Several boards ship raw HTML."""
    return _SPACE.sub(" ", _TAGS.sub(" ", text or "")).strip()

def employment_label(*values) -> str:
    """Human label from whatever shape a board states employment type in.

    Takes strings, lists or None; returns NOT_STATED when a board says nothing,
    so an absent field never renders as a guess.
    """
    parts = []
    for value in values:
        for item in (value if isinstance(value, (list, tuple)) else [value]):
            if not item or not isinstance(item, str):
                continue
            # boards state these as FULL_TIME, full-time or FullTime
            spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", item.strip())
            label = spaced.replace("_", " ").replace("-", " ").title()
            if label and label not in parts:
                parts.append(label)
    return ", ".join(parts) if parts else NOT_STATED

# code -> display name, for rendering locations as "City, Country"
COUNTRY_NAMES = {
    "CH": "Switzerland", "DE": "Germany", "AT": "Austria", "NL": "Netherlands",
    "BE": "Belgium", "PL": "Poland", "SE": "Sweden", "NO": "Norway",
    "DK": "Denmark", "FI": "Finland", "FR": "France", "IT": "Italy",
    "ES": "Spain", "GB": "United Kingdom", "IE": "Ireland", "PT": "Portugal",
    "CZ": "Czechia", "EE": "Estonia", "LV": "Latvia", "LT": "Lithuania",
    "LU": "Luxembourg", "IS": "Iceland", "US": "United States", "CA": "Canada",
    "IN": "India", "SG": "Singapore",
}
# the reverse lookup also accepts the local spellings boards actually return
_NAME_TO_CODE = {name.lower(): code for code, name in COUNTRY_NAMES.items()}
_NAME_TO_CODE.update({"sverige": "SE", "schweiz": "CH", "suisse": "CH", "deutschland": "DE",
                      "österreich": "AT", "danmark": "DK", "suomi": "FI", "norge": "NO",
                      "nederland": "NL", "polska": "PL", "usa": "US", "uk": "GB"})

def country_name(value: str | None) -> str:
    """Display name for a country code or local spelling; echoes back what it can't map."""
    v = (value or "").strip()
    # internal buckets, not countries — they must never be printed as a place
    if not v or v.upper() in ("REMOTE", "OTHER"):
        return ""
    if len(v) == 2 and v.upper() in COUNTRY_NAMES:
        return COUNTRY_NAMES[v.upper()]
    return COUNTRY_NAMES.get(_NAME_TO_CODE.get(v.lower(), ""), v)

def country_code(name: str | None) -> str:
    """Two-letter code for a country name, or "" when it is not one we target."""
    v = (name or "").strip()
    if len(v) == 2 and v.upper() in COUNTRY_NAMES:
        return v.upper()
    return _NAME_TO_CODE.get(v.lower(), "")

def format_location(city: str | None = None, country: str | None = None) -> str:
    """"City, Country" when both are stated; whichever half exists otherwise.

    Never invents the missing half — an ad that names no city stays country-only.
    """
    city = (city or "").strip().strip(",")
    country = country_name(country)
    if city and country and city.lower() != country.lower():
        return f"{city}, {country}"
    return city or country or NOT_STATED

# Adzuna serves one country per request and states amounts in that country's
# currency without labelling them, so the country fixes the label.
CURRENCY_BY_COUNTRY = {
    "CH": "CHF", "DE": "EUR", "AT": "EUR", "NL": "EUR", "BE": "EUR", "FR": "EUR",
    "IT": "EUR", "ES": "EUR", "IE": "EUR", "PT": "EUR", "FI": "EUR", "LU": "EUR",
    "PL": "PLN", "SE": "SEK", "NO": "NOK", "DK": "DKK", "GB": "GBP", "US": "USD",
    "CA": "CAD", "IN": "INR",
}
_SALARY_TEXT = re.compile(
    r"(?P<sym>[$€£₹]|\b(?:USD|EUR|CHF|GBP|SEK|NOK|DKK|PLN|INR)\b)?\s*"
    r"(?P<low>\d[\d,. ]*\d|\d)\s*(?P<lowk>k\b)?\s*(?:-|–|to)\s*"
    r"(?P<sym2>[$€£₹]|\b(?:USD|EUR|CHF|GBP|SEK|NOK|DKK|PLN|INR)\b)?\s*"
    r"(?P<high>\d[\d,. ]*\d|\d)\s*(?P<highk>k\b)?"
    r"\s*(?P<sym3>[$€£₹]|\b(?:USD|EUR|CHF|GBP|SEK|NOK|DKK|PLN|INR)\b)?", re.I)
_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR"}

def parse_salary_text(text: str | None):
    """(min, max, currency) from a free-text range like "$120k - $160k".

    Returns (None, None, "") when the text states no parsable amount — a board
    saying "competitive" must not turn into a number.
    """
    m = _SALARY_TEXT.search(text or "")
    if not m:
        return None, None, ""
    def amount(raw, is_k):
        value = float(re.sub(r"[,\s]", "", raw))
        return value * 1000 if is_k else value
    low = amount(m.group("low"), m.group("lowk"))
    high = amount(m.group("high"), m.group("highk"))
    sym = (m.group("sym") or m.group("sym2") or m.group("sym3") or "").strip().upper()
    return low, high, _SYMBOLS.get(sym, sym)
