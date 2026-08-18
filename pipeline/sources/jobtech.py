from __future__ import annotations
from ..models import Job, make_id, NOT_STATED
from . import register
from .base import get_json

SEARCH = "https://jobsearch.api.jobtechdev.se/search"

def fetch(cfg, get=get_json):
    q = " ".join(cfg.get("search_terms", ["cybersecurity", "security"]))
    data = get(SEARCH, params={"q": q, "limit": 100},
               headers={"accept": "application/json"})
    jobs = []
    for r in data.get("hits", []):
        url = r.get("webpage_url") or (r.get("application_details") or {}).get("url")
        if not url:
            continue
        addr = r.get("workplace_address") or {}
        jobs.append(Job(
            id=make_id("jobtech", str(r.get("id")), url),
            title=(r.get("headline") or "").strip(),
            company=(r.get("employer") or {}).get("name", NOT_STATED),
            location=", ".join(x for x in [addr.get("municipality"), addr.get("region")] if x),
            country="SE",
            url=url,
            source="jobtech", source_type="api",
            posted_date=(r.get("publication_date") or "")[:10] or None,
            remote=False,
            salary=(r.get("salary_type") or {}).get("label", NOT_STATED) or NOT_STATED,
            description=(r.get("description") or {}).get("text", ""),
        ))
    return jobs

register(fetch)
