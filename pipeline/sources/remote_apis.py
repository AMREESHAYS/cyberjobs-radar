from __future__ import annotations
import re
from ..models import Job, make_id, NOT_STATED
from . import register
from .base import employment_label, format_location, get_json, strip_html

# rough country detection from a free-text location string
_COUNTRY_WORDS = {
    "switzerland": "CH", "schweiz": "CH", "germany": "DE", "deutschland": "DE",
    "austria": "AT", "netherlands": "NL", "belgium": "BE", "poland": "PL",
    "sweden": "SE", "norway": "NO", "denmark": "DK", "finland": "FI",
}

def _country_from(text: str) -> str:
    t = (text or "").lower()
    for word, code in _COUNTRY_WORDS.items():
        if word in t:
            return code
    return "REMOTE"

def _keyword_match(text: str, terms: list[str]) -> bool:
    t = (text or "").lower()
    return any(re.search(re.escape(term.lower()), t) for term in terms)

def _terms(cfg):
    return cfg.get("search_terms", ["security", "cyber", "pentest", "soc"])

def _range_salary(low, high, currency=None, period=None) -> str:
    if low is None and high is None:
        return NOT_STATED
    amount = f"{low}-{high}" if low is not None and high is not None else str(low if low is not None else high)
    return " ".join(x for x in (amount, currency, period) if x)

# --- Arbeitnow: EU/DE board ---
def fetch_arbeitnow(cfg, get=get_json):
    data = get("https://www.arbeitnow.com/api/job-board-api")
    terms = _terms(cfg)
    jobs = []
    for r in data.get("data", []):
        blob = f"{r.get('title','')} {' '.join(r.get('tags',[]))} {r.get('description','')}"
        if not _keyword_match(blob, terms):
            continue
        url = r.get("url")
        if not url:
            continue
        loc = r.get("location", "")
        jobs.append(Job(
            id=make_id("arbeitnow", r.get("slug"), url),
            title=r.get("title", "").strip(),
            company=r.get("company_name", NOT_STATED),
            location=format_location(loc, _country_from(loc)),
            country=_country_from(loc),
            url=url, source="arbeitnow", source_type="api",
            posted_date=None, remote=bool(r.get("remote")),
            salary=NOT_STATED, employment_type=employment_label(r.get("job_types")),
            description=strip_html(r.get("description")),
        ))
    return jobs

# --- Jobicy: remote board ---
def fetch_jobicy(cfg, get=get_json):
    data = get("https://jobicy.com/api/v2/remote-jobs",
               params={"count": 50, "tag": "security"})
    terms = _terms(cfg)
    jobs = []
    for r in data.get("jobs", []):
        blob = f"{r.get('jobTitle','')} {r.get('jobDescription','')}"
        if not _keyword_match(blob, terms):
            continue
        url = r.get("url")
        if not url:
            continue
        jobs.append(Job(
            id=make_id("jobicy", str(r.get("id")), url),
            title=r.get("jobTitle", "").strip(),
            company=r.get("companyName", NOT_STATED),
            location=r.get("jobGeo", "Remote"), country="REMOTE",
            url=url, source="jobicy", source_type="api",
            posted_date=(r.get("pubDate") or "")[:10] or None, remote=True,
            salary=NOT_STATED,
            employment_type=employment_label(r.get("jobType")),
            description=strip_html(r.get("jobDescription")),
        ))
    return jobs

# --- RemoteOK: remote board (first element is a legal/disclaimer row) ---
def fetch_remoteok(cfg, get=get_json):
    data = get("https://remoteok.com/api",
               headers={"User-Agent": "cyberjobs-radar/1.0"})
    terms = _terms(cfg)
    jobs = []
    for r in data:
        if not isinstance(r, dict) or "position" not in r:
            continue  # skip legal/disclaimer row
        blob = f"{r.get('position','')} {' '.join(r.get('tags',[]))} {r.get('description','')}"
        if not _keyword_match(blob, terms):
            continue
        url = r.get("url")
        if not url:
            continue
        jobs.append(Job(
            id=make_id("remoteok", str(r.get("id")), url),
            title=r.get("position", "").strip(),
            company=r.get("company", NOT_STATED),
            location="Remote", country="REMOTE",
            url=url, source="remoteok", source_type="api",
            posted_date=(r.get("date") or "")[:10] or None, remote=True,
            salary=NOT_STATED, employment_type=NOT_STATED,
            description=strip_html(r.get("description")),
        ))
    return jobs

# --- Himalayas: remote board ---
def fetch_himalayas(cfg, get=get_json):
    data = get("https://himalayas.app/jobs/api", params={"limit": 50})
    terms = _terms(cfg)
    jobs = []
    for r in data.get("jobs", []):
        blob = f"{r.get('title','')} {r.get('description','')}"
        if not _keyword_match(blob, terms):
            continue
        url = r.get("applicationLink") or r.get("guid")
        if not url:
            continue
        jobs.append(Job(
            id=make_id("himalayas", str(r.get("guid")), url),
            title=r.get("title", "").strip(),
            company=r.get("companyName", NOT_STATED),
            location=", ".join(r.get("locationRestrictions") or []) or "Remote",
            country="REMOTE",
            url=url, source="himalayas", source_type="api",
            posted_date=(r.get("pubDate") or "")[:10] or None, remote=True,
            salary=_range_salary(r.get("minSalary"), r.get("maxSalary"),
                                 r.get("currency"), r.get("salaryPeriod")),
            salary_min=r.get("minSalary"), salary_max=r.get("maxSalary"),
            salary_currency=r.get("currency") or "", salary_period=r.get("salaryPeriod") or "",
            employment_type=employment_label(r.get("employmentType")),
            description=strip_html(r.get("description")),
        ))
    return jobs

for _a in (fetch_arbeitnow, fetch_jobicy, fetch_remoteok, fetch_himalayas):
    register(_a)
