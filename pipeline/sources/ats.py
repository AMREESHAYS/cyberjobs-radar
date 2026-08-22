from __future__ import annotations
import html
import re
from urllib.parse import quote
from ..models import Job, make_id, NOT_STATED
from . import register
from .base import (country_code, employment_label, format_location, get_json,
                   strip_html)
from .remote_apis import _keyword_match, _terms

# Applicant tracking systems publish the whole ad, unlike the aggregators:
# Adzuna hands back a 500-character teaser, which left experience, skills and
# sponsorship unextractable for most of the list.
HEADERS = {"User-Agent": "cyberjobs-radar/1.0 (personal job search)"}
WORKABLE_SEARCH = "https://jobs.workable.com/api/v1/jobs"
GREENHOUSE_BOARD = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
ASHBY_BOARD = "https://api.ashbyhq.com/posting-api/job-board/{token}"
LEVER_BOARD = "https://api.lever.co/v0/postings/{token}"
SMARTRECRUITERS_BOARD = "https://api.smartrecruiters.com/v1/companies/{token}/postings"
SMARTRECRUITERS_POSTING = "https://api.smartrecruiters.com/v1/companies/{token}/postings/{job}"
RECRUITEE_BOARD = "https://{token}.recruitee.com/api/offers/"
WORKABLE_PAGES = 3          # 20 per page
_WORKPLACE = {"remote": True, "hybrid": True, "on_site": False, "onsite": False}

def _ats_config(cfg, name):
    return (cfg.get("ats") or {}).get(name) or []

def _keep(job, terms):
    return _keyword_match(f"{job.title} {job.description}", terms)

def _keep_by_title(job, terms):
    """Company boards need the title to match.

    A privacy company's every ad mentions security, so matching on the body
    would pull in its sales and frontend roles too.
    """
    return _keyword_match(job.title, terms)

# --- Workable: searches every company on the platform, no board tokens ------
def fetch_workable(cfg, get=get_json):
    terms = _terms(cfg)
    query = cfg.get("workable_query", "security")
    jobs, seen = [], set()
    for code in cfg.get("countries", []):
        name = {"GB": "united-kingdom"}.get(code) or _country_slug(code)
        if not name:
            continue
        token = None
        for _ in range(WORKABLE_PAGES):
            params = {"query": query, "location": name}
            if token:
                params["pageToken"] = token
            data = get(WORKABLE_SEARCH, params=params, headers=HEADERS)
            for r in data.get("jobs", []):
                job = _from_workable(r)
                if job and job.id not in seen and _keep(job, terms):
                    seen.add(job.id)
                    jobs.append(job)
            token = data.get("nextPageToken")
            if not token:
                break
    return jobs

def _country_slug(code: str) -> str:
    from .base import COUNTRY_NAMES
    name = COUNTRY_NAMES.get((code or "").upper())
    return name.lower().replace(" ", "-") if name else ""

def _from_workable(r: dict) -> Job | None:
    url, title = r.get("url"), (r.get("title") or "").strip()
    if not url or not title:
        return None
    place = r.get("location") or {}
    company = (r.get("company") or {}).get("title") or NOT_STATED
    # the requirements block is where "5+ years" lives, and it ships separately
    body = " ".join(strip_html(r.get(k)) for k in ("description", "requirementsSection") if r.get(k))
    workplace = (r.get("workplace") or "").lower()
    return Job(
        id=make_id("workable", str(r.get("id")), url),
        title=title, company=company,
        location=format_location(place.get("city"), place.get("countryName")),
        country=country_code(place.get("countryName")) or "OTHER",
        url=url, source="workable", source_type="api",
        posted_date=(r.get("created") or "")[:10] or None,
        remote=_WORKPLACE.get(workplace, NOT_STATED),
        salary=NOT_STATED,
        employment_type=employment_label(r.get("employmentType")),
        description=body.strip(),
    )

# --- Greenhouse and Ashby: one board per company, listed in config ----------
def fetch_greenhouse(cfg, get=get_json):
    terms = _terms(cfg)
    jobs = []
    for token in _ats_config(cfg, "greenhouse"):
        data = get(GREENHOUSE_BOARD.format(token=quote(str(token))),
                   params={"content": "true"}, headers=HEADERS)
        for r in data.get("jobs", []):
            url, title = r.get("absolute_url"), (r.get("title") or "").strip()
            if not url or not title:
                continue
            where = (r.get("location") or {}).get("name") or ""
            job = Job(
                id=make_id("greenhouse", str(r.get("id")), url),
                title=title,
                company=r.get("company_name") or str(token),
                location=format_location(_city(where), _country_in(where)),
                country=_country_in(where) or "OTHER",
                url=url, source="greenhouse", source_type="api",
                posted_date=(r.get("updated_at") or r.get("first_published") or "")[:10] or None,
                remote="remote" in where.lower() or NOT_STATED,
                salary=NOT_STATED,
                # greenhouse html-escapes the whole body before serving it
                description=strip_html(html.unescape(r.get("content") or "")),
            )
            if _keep_by_title(job, terms):
                jobs.append(job)
    return jobs

def fetch_ashby(cfg, get=get_json):
    terms = _terms(cfg)
    jobs = []
    for token in _ats_config(cfg, "ashby"):
        data = get(ASHBY_BOARD.format(token=quote(str(token))), headers=HEADERS)
        for r in data.get("jobs", []):
            url = r.get("jobUrl") or r.get("applyUrl")
            title = (r.get("title") or "").strip()
            if not url or not title:
                continue
            where = r.get("location") or ""
            job = Job(
                id=make_id("ashby", str(r.get("id")), url),
                title=title, company=str(token).replace("-", " ").title(),
                location=format_location(_city(where), _country_in(where)),
                country=_country_in(where) or "OTHER",
                url=url, source="ashby", source_type="api",
                posted_date=(r.get("publishedAt") or "")[:10] or None,
                remote=bool(r.get("isRemote")),
                salary=NOT_STATED,
                employment_type=employment_label(r.get("employmentType")),
                description=r.get("descriptionPlain") or strip_html(r.get("descriptionHtml")),
            )
            if _keep_by_title(job, terms):
                jobs.append(job)
    return jobs

# Board locations often name only a city ("Zurich HQ", "Geneva, London").
# The city is stated by the source, so resolving it is reading, not guessing.
CITY_COUNTRY = {
    "zurich": "CH", "zürich": "CH", "geneva": "CH", "genève": "CH", "basel": "CH",
    "bern": "CH", "lausanne": "CH", "zug": "CH", "lugano": "CH", "st. gallen": "CH",
    "berlin": "DE", "munich": "DE", "münchen": "DE", "hamburg": "DE", "frankfurt": "DE",
    "cologne": "DE", "köln": "DE", "stuttgart": "DE", "düsseldorf": "DE", "leipzig": "DE",
    "vienna": "AT", "wien": "AT", "graz": "AT", "linz": "AT", "salzburg": "AT",
    "amsterdam": "NL", "rotterdam": "NL", "utrecht": "NL", "eindhoven": "NL",
    "the hague": "NL", "den haag": "NL", "brussels": "BE", "bruxelles": "BE",
    "antwerp": "BE", "ghent": "BE", "leuven": "BE", "warsaw": "PL", "warszawa": "PL",
    "krakow": "PL", "kraków": "PL", "wroclaw": "PL", "wrocław": "PL", "gdansk": "PL",
    "poznan": "PL", "stockholm": "SE", "gothenburg": "SE", "göteborg": "SE",
    "malmo": "SE", "malmö": "SE", "oslo": "NO", "bergen": "NO", "trondheim": "NO",
    "copenhagen": "DK", "københavn": "DK", "aarhus": "DK", "helsinki": "FI",
    "espoo": "FI", "tampere": "FI", "paris": "FR", "lyon": "FR", "montpellier": "FR",
}

_OFFICE_WORDS = re.compile(r"\b(hq|head ?office|office|remote|hybrid|on ?site)\b", re.I)

def _city(text: str) -> str:
    """First place named in a board location, without the office wording."""
    first = re.split(r"[;,/|]", text or "")[0]
    return _OFFICE_WORDS.sub("", first).strip(" -–") or ""

# --- Lever ---------------------------------------------------------------
def fetch_lever(cfg, get=get_json):
    terms = _terms(cfg)
    jobs = []
    for token in _ats_config(cfg, "lever"):
        rows = get(LEVER_BOARD.format(token=quote(str(token))),
                   params={"mode": "json"}, headers=HEADERS)
        for r in rows if isinstance(rows, list) else []:
            url, title = r.get("hostedUrl") or r.get("applyUrl"), (r.get("text") or "").strip()
            if not url or not title:
                continue
            cats = r.get("categories") or {}
            where = cats.get("location") or ""
            job = Job(
                id=make_id("lever", str(r.get("id")), url),
                title=title, company=str(token).replace("-", " ").title(),
                location=format_location(_city(where), _country_in(where) or r.get("country")),
                country=_country_in(where) or country_code(r.get("country")) or "OTHER",
                url=url, source="lever", source_type="api",
                posted_date=_epoch_day(r.get("createdAt")),
                remote="remote" in where.lower() or NOT_STATED,
                salary=NOT_STATED,
                employment_type=employment_label(cats.get("commitment")),
                description=r.get("descriptionPlain") or strip_html(r.get("description")),
            )
            if _keep_by_title(job, terms):
                jobs.append(job)
    return jobs

def _epoch_day(ms):
    from datetime import datetime, timezone
    try:
        return datetime.fromtimestamp(int(ms) / 1000, timezone.utc).date().isoformat()
    except (TypeError, ValueError):
        return None

# --- SmartRecruiters ------------------------------------------------------
# The list endpoint carries no description, so the ad is fetched only for the
# postings whose title already matches — a handful per company, not all 99.
def fetch_smartrecruiters(cfg, get=get_json):
    terms = _terms(cfg)
    jobs = []
    for token in _ats_config(cfg, "smartrecruiters"):
        slug = quote(str(token))
        data = get(SMARTRECRUITERS_BOARD.format(token=slug),
                   params={"limit": 100}, headers=HEADERS)
        for r in data.get("content", []):
            title = (r.get("name") or "").strip()
            if not title or not _keyword_match(title, terms):
                continue
            place = r.get("location") or {}
            job_id = r.get("id")
            url = f"https://jobs.smartrecruiters.com/{token}/{job_id}"
            try:
                detail = get(SMARTRECRUITERS_POSTING.format(token=slug, job=quote(str(job_id))),
                             headers=HEADERS)
            except Exception:  # noqa: BLE001 - keep the posting, minus its body
                detail = {}
            sections = (detail.get("jobAd") or {}).get("sections") or {}
            body = " ".join(strip_html((sections.get(k) or {}).get("text"))
                            for k in ("jobDescription", "qualifications"))
            jobs.append(Job(
                id=make_id("smartrecruiters", str(job_id), url),
                title=title, company=(r.get("company") or {}).get("name") or str(token),
                location=format_location(place.get("city"), place.get("country")),
                country=country_code(place.get("country")) or "OTHER",
                url=detail.get("applyUrl") or url,
                source="smartrecruiters", source_type="api",
                posted_date=(detail.get("releasedDate") or "")[:10] or None,
                remote=bool(place.get("remote")) or (True if place.get("hybrid") else NOT_STATED),
                salary=NOT_STATED,
                employment_type=employment_label(r.get("experienceLevel", {}).get("id")
                                                 if isinstance(r.get("experienceLevel"), dict) else None),
                description=body.strip(),
            ))
    return jobs

# --- Recruitee ------------------------------------------------------------
def fetch_recruitee(cfg, get=get_json):
    terms = _terms(cfg)
    jobs = []
    for token in _ats_config(cfg, "recruitee"):
        data = get(RECRUITEE_BOARD.format(token=quote(str(token))), headers=HEADERS)
        for r in data.get("offers", []):
            url, title = r.get("careers_url"), (r.get("title") or "").strip()
            if not url or not title:
                continue
            job = Job(
                id=make_id("recruitee", str(r.get("id") or r.get("guid")), url),
                title=title, company=r.get("company_name") or str(token).title(),
                location=format_location(r.get("city"), r.get("country_code") or r.get("country")),
                country=country_code(r.get("country_code")) or "OTHER",
                url=url, source="recruitee", source_type="api",
                posted_date=(r.get("created_at") or "")[:10] or None,
                remote=NOT_STATED, salary=NOT_STATED,
                employment_type=employment_label(r.get("employment_type_code")),
                # requirements is a separate field and is where the must-haves live
                description=" ".join(strip_html(r.get(k)) for k in ("description", "requirements")).strip(),
            )
            if _keep_by_title(job, terms):
                jobs.append(job)
    return jobs

def _country_in(text: str) -> str:
    """Country code from a free-text location: a country name, else a known city."""
    parts = [p.strip() for p in re.split(r"[;,/|]", text or "") if p.strip()]
    for part in parts:
        code = country_code(part)
        if code:
            return code
    for part in parts:
        cleaned = re.sub(r"\b(hq|office|remote|hybrid)\b", "", part, flags=re.I).strip().lower()
        if cleaned in CITY_COUNTRY:
            return CITY_COUNTRY[cleaned]
    return ""

for _adapter in (fetch_workable, fetch_greenhouse, fetch_ashby, fetch_lever,
                 fetch_smartrecruiters, fetch_recruitee):
    register(_adapter)
