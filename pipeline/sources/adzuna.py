from __future__ import annotations
from ..models import Job, make_id, NOT_STATED
from . import register
from .base import employment_label, get_json, strip_html

_COUNTRY_MAP = {  # our code -> adzuna country slug
    "CH": "ch", "DE": "de", "AT": "at", "NL": "nl", "BE": "be",
    "PL": "pl", "FR": "fr", "IT": "it", "ES": "es",
}
BASE = "https://api.adzuna.com/v1/api/jobs/{c}/search/1"

def _salary(r):
    lo, hi = r.get("salary_min"), r.get("salary_max")
    if lo and hi:
        return f"{int(lo)}-{int(hi)}"
    return NOT_STATED

def fetch(cfg, get=get_json):
    sec = cfg.get("secrets", {})
    app_id, app_key = sec.get("ADZUNA_APP_ID"), sec.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        return []
    what = " ".join(cfg.get("search_terms", ["cybersecurity"])[:1] or ["cybersecurity"])
    jobs: list[Job] = []
    for code in cfg.get("countries", []):
        slug = _COUNTRY_MAP.get(code)
        if not slug:
            continue
        data = get(BASE.format(c=slug), params={
            "app_id": app_id, "app_key": app_key, "what_or": "cybersecurity security",
            "what": what, "results_per_page": 50, "content-type": "application/json",
        })
        for r in data.get("results", []):
            url = r.get("redirect_url")
            if not url:
                continue
            jobs.append(Job(
                id=make_id("adzuna", str(r.get("id")), url),
                title=r.get("title", "").strip(),
                company=(r.get("company") or {}).get("display_name", NOT_STATED),
                location=(r.get("location") or {}).get("display_name", ""),
                country=code,
                url=url,
                source="adzuna", source_type="api",
                posted_date=(r.get("created") or "")[:10] or None,
                remote=NOT_STATED,  # adzuna states no remote flag
                salary=_salary(r),
                employment_type=employment_label(r.get("contract_time"), r.get("contract_type")),
                description=strip_html(r.get("description")),
            ))
    return jobs

register(fetch)
