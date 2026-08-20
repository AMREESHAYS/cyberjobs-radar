from __future__ import annotations
from datetime import datetime, timezone
from ..models import Job, make_id, NOT_STATED
from . import register
from .base import employment_label, format_location, get_json, post_json, strip_html
from .remote_apis import _keyword_match, _terms
from urllib.parse import quote

# Denmark and Finland via EURES, the EU's official job mobility portal, which
# aggregates the national employment services (Jobnet for DK, Työmarkkinatori
# for FI). Their own APIs are not usable here: Jobnet's search sits behind
# MitID login, and the Finnish API needs credentials tied to a business ID.
SEARCH_URL = "https://europa.eu/eures/api/jv-searchengine/public/jv-search/search"
DETAILS_URL = "https://europa.eu/eures/portal/jv-se/jv-details/"
DETAILS_API = "https://europa.eu/eures/api/jv-searchengine/public/jv/id/"
HEADERS = {"User-Agent": "cyberjobs-radar/1.0 (personal job search)",
           "Content-Type": "application/json"}
RESULTS_PER_PAGE = 50

def _body(keyword: str, country: str) -> dict:
    # the endpoint rejects a partial body, so every filter list is sent explicitly
    return {
        "resultsPerPage": RESULTS_PER_PAGE, "page": 1, "sortSearch": "MOST_RECENT",
        "keywords": [{"keyword": keyword, "specificSearchCode": "EVERYWHERE"}],
        "publicationPeriod": None, "occupationUris": [], "skillUris": [],
        "requiredExperienceCodes": [], "positionScheduleCodes": [], "sectorCodes": [],
        "educationAndQualificationLevelCodes": [], "positionOfferingCodes": [],
        "locationCodes": [country.lower()], "euresFlagCodes": [], "otherBenefitsCodes": [],
        "requiredLanguages": [], "minNumberPost": None, "sessionId": "cyberjobs-radar",
        "userPreferredLanguage": None, "requestLanguage": "en",
    }

def _date(epoch_ms) -> str | None:
    try:
        return datetime.fromtimestamp(int(epoch_ms) / 1000, timezone.utc).date().isoformat()
    except (TypeError, ValueError):
        return None

def _location(jv: dict, country: str) -> tuple[str, str]:
    location_map = jv.get("locationMap") or {}
    codes = [c for c in location_map if isinstance(c, str)]
    # locationMap keys are uppercase; a posting can list several countries, so
    # prefer the one we actually queried for
    code = next((c for c in codes if c.lower() == country.lower()), codes[0] if codes else None)
    regions = [r for r in (location_map.get(code) or []) if r]
    return (", ".join(regions) or (code or NOT_STATED)), (code or "OTHER")

def _city(jv_id: str, fetch) -> tuple[str, str]:
    """City and country from the per-job endpoint; search results only carry NUTS codes."""
    data = fetch(f"{DETAILS_API}{quote(jv_id)}", params={"lang": "en"}, headers=HEADERS)
    profiles = data.get("jvProfiles") or {}
    profile = profiles.get("en") or next(iter(profiles.values()), {})
    places = profile.get("locations") or []
    place = places[0] if places else {}
    return place.get("cityName") or "", place.get("countryCode") or ""

def _search(cfg, country: str, post, fetch=get_json) -> list[Job]:
    terms = _terms(cfg)
    jobs, seen = [], set()
    for keyword in terms:
        data = post(SEARCH_URL, json=_body(keyword, country), headers=HEADERS)
        for jv in (data.get("jvs") or []):
            jv_id, title = jv.get("id"), (jv.get("title") or "").strip()
            if not jv_id or not title or jv_id in seen:
                continue
            description = strip_html(jv.get("description"))
            # EURES keyword search is loose (a "security" query returns delivery
            # drivers), so every hit is re-checked against our own terms
            if not _keyword_match(f"{title} {description}", terms):
                continue
            seen.add(jv_id)
            location, code = _location(jv, country)
            try:
                city, city_country = _city(jv_id, fetch)
                if city or city_country:
                    location = format_location(city, city_country or code)
            except Exception:  # noqa: BLE001 - a NUTS code beats dropping the job
                location = format_location(location, code)
            employer = jv.get("employer") or {}
            jobs.append(Job(
                id=make_id(f"eures-{country}", jv_id, DETAILS_URL),
                title=title,
                company=employer.get("name") or NOT_STATED,
                location=location,
                country=code.upper(),
                url=f"{DETAILS_URL}{quote(jv_id)}?lang=en",
                source=f"eures-{country}",
                source_type="api",
                posted_date=_date(jv.get("creationDate")),
                remote=NOT_STATED,  # EURES has no remote flag; nothing to claim
                salary=NOT_STATED,
                employment_type=employment_label(jv.get("positionScheduleCodes"),
                                                 jv.get("positionOfferingCode")),
                description=description,
            ))
    return jobs

def fetch_denmark(cfg, get=post_json, fetch=get_json):
    return _search(cfg, "dk", get, fetch)

def fetch_finland(cfg, get=post_json, fetch=get_json):
    return _search(cfg, "fi", get, fetch)

register(fetch_denmark)
register(fetch_finland)
