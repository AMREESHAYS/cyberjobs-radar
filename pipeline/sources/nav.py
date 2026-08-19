from __future__ import annotations
from ..models import Job, make_id, NOT_STATED
from . import register
from .base import employment_label, get_json, strip_html

FEED = "https://pam-stilling-feed.nav.no/api/v1/feed"
PUBLIC_TOKEN = "https://pam-stilling-feed.nav.no/api/publicToken"

def _token(cfg, get):
    tok = cfg.get("secrets", {}).get("NAV_TOKEN")
    if tok:
        return tok
    res = get(PUBLIC_TOKEN, headers={"accept": "text/plain"})
    # public token endpoint may return raw string or {"token": "..."}
    if isinstance(res, dict):
        return res.get("token")
    return res

def fetch(cfg, get=get_json):
    try:
        tok = _token(cfg, get)
    except Exception:
        return []
    if not tok:
        return []
    data = get(FEED, headers={"Authorization": f"Bearer {tok}", "accept": "application/json"})
    entries = data.get("content") or data.get("entries") or []
    jobs = []
    for r in entries:
        url = r.get("link") or r.get("url")
        if not url:
            continue
        jobs.append(Job(
            id=make_id("nav", str(r.get("uuid") or r.get("id")), url),
            title=(r.get("title") or "").strip(),
            company=r.get("businessName") or r.get("employer") or NOT_STATED,
            location=r.get("municipal") or r.get("location") or "",
            country="NO",
            url=url,
            source="nav", source_type="scraper",
            posted_date=(r.get("published") or "")[:10] or None,
            remote=NOT_STATED,  # nav states no remote flag
            salary=NOT_STATED,
            employment_type=employment_label(r.get("engagementType"), r.get("extent")),
            description=strip_html(r.get("description")),
        ))
    return jobs

register(fetch)
