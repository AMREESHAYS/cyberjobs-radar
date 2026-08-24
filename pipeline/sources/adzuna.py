from __future__ import annotations
import logging
from ..models import Job, make_id, NOT_STATED
from . import register
from .base import (CURRENCY_BY_COUNTRY, employment_label, format_location,
                   get_json, strip_html)
from .remote_apis import _keyword_match, _terms

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

log = logging.getLogger("adzuna")

def _country_page(get, slug, app_id, app_key, what_or, cfg):
    return get(BASE.format(c=slug), params={
        "app_id": app_id, "app_key": app_key,
        "what_and": cfg.get("adzuna_require", "security"),
        "what_or": what_or,
        "what_exclude": cfg.get("adzuna_exclude",
                                "senior lead principal head director chief manager architect "
                                "sales vertrieb verkauf recruiter"),
        "max_days_old": cfg.get("max_days_old", 45),
        "sort_by": "date",
        "results_per_page": 50, "content-type": "application/json",
    })

def fetch(cfg, get=get_json):
    sec = cfg.get("secrets", {})
    app_id, app_key = sec.get("ADZUNA_APP_ID"), sec.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        return []
    # what_or matches ANY of the words given, so feeding it the entry-level
    # vocabulary ("junior", "intern", "trainee") pulled in apprentice roles from
    # every industry — nurses, chefs, machine operators. what_and forces the
    # security word to be present; what_or then broadens within that.
    terms = cfg.get("search_terms") or ["cybersecurity"]
    # a very long what_or has been answered with a 500; keep it to the words that
    # actually broaden the search
    words = [w for w in dict.fromkeys(" ".join(terms).lower().split()) if len(w) > 2]
    what_or = " ".join(words[:12])
    jobs: list[Job] = []
    for code in cfg.get("countries", []):
        slug = _COUNTRY_MAP.get(code)
        if not slug:
            continue
        try:
            data = _country_page(get, slug, app_id, app_key, what_or, cfg)
        except Exception as e:  # noqa: BLE001 - one country must not lose the other eight
            log.warning("adzuna %s failed: %s", slug, e)
            continue
        for r in data.get("results", []):
            url = r.get("redirect_url")
            if not url:
                continue
            area = (r.get("location") or {}).get("area") or []
            # area runs country-first, most specific last
            city = area[-1] if len(area) > 1 else ""
            low, high = r.get("salary_min"), r.get("salary_max")
            blob = f"{r.get('title', '')} {r.get('description', '')}"
            # the API is only as good as its index; verify locally too
            if not _keyword_match(blob, _terms(cfg)):
                continue
            jobs.append(Job(
                id=make_id("adzuna", str(r.get("id")), url),
                title=r.get("title", "").strip(),
                company=(r.get("company") or {}).get("display_name", NOT_STATED),
                location=format_location(city, area[0] if area else code),
                country=code,
                url=url,
                source="adzuna", source_type="api",
                posted_date=(r.get("created") or "")[:10] or None,
                remote=NOT_STATED,  # adzuna states no remote flag
                salary=_salary(r),
                salary_min=float(low) if low else None,
                salary_max=float(high) if high else None,
                salary_currency=CURRENCY_BY_COUNTRY.get(code, ""),
                salary_period="year",
                employment_type=employment_label(r.get("contract_time"), r.get("contract_type")),
                description=strip_html(r.get("description")),
            ))
    return jobs

register(fetch)
