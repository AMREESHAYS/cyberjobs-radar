from __future__ import annotations
import json
import re
from ..models import Job, make_id, NOT_STATED
from . import register
from .base import get_text
from .remote_apis import _COUNTRY_WORDS, _keyword_match, _terms

# Crypto/web3 boards. Neither exposes a usable API or feed, but both render a
# schema.org JobPosting block on every job page, so we read that instead of
# guessing from markup: list page/sitemap -> job urls -> ld+json per job.
HEADERS = {"User-Agent": "cyberjobs-radar/1.0 (personal job search)"}
MAX_JOBS_PER_BOARD = 25  # per run; keeps a cron run to a bounded number of requests

_LD_JSON = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S)
_TAGS = re.compile(r"<[^>]+>")

def _job_posting(html: str) -> dict | None:
    for block in _LD_JSON.findall(html or ""):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        nodes = data.get("@graph", [data]) if isinstance(data, dict) else data
        for node in nodes if isinstance(nodes, list) else [nodes]:
            if isinstance(node, dict) and node.get("@type") == "JobPosting":
                return node
    return None

def _country(text: str) -> str | None:
    t = (text or "").lower()
    for word, code in _COUNTRY_WORDS.items():
        if word in t:
            return code
    return None

def _salary(posting: dict) -> str:
    base = posting.get("baseSalary") or {}
    value = base.get("value") if isinstance(base, dict) else None
    if not isinstance(value, dict):
        return NOT_STATED
    lo, hi = value.get("minValue"), value.get("maxValue")
    if lo is None and hi is None:
        return NOT_STATED
    amount = f"{lo}-{hi}" if lo is not None and hi is not None else str(lo if lo is not None else hi)
    parts = [amount, base.get("currency") or "", (value.get("unitText") or "").lower()]
    return " ".join(p for p in parts if p).strip()

def _location(posting: dict) -> str:
    place = posting.get("jobLocation") or {}
    if isinstance(place, list):
        place = place[0] if place else {}
    address = place.get("address") if isinstance(place, dict) else None
    if not isinstance(address, dict):
        return NOT_STATED
    bits = [address.get(k) or "" for k in ("addressLocality", "addressRegion")]
    country = (address.get("addressCountry") or "").strip()
    # spelled-out country names add information; a bare 2-letter code does not,
    # and cryptovalley stamps "CH" on every posting including US ones
    if country and (len(country) > 2 or not any(bits)):
        bits.append(country)
    return ", ".join(b for b in bits if b) or NOT_STATED

def _to_job(source: str, url: str, posting: dict) -> Job | None:
    title = (posting.get("title") or "").strip()
    if not title or not url:
        return None
    org = posting.get("hiringOrganization") or {}
    location = _location(posting)
    remote = "remote" in location.lower() or posting.get("jobLocationType") == "TELECOMMUTE"
    country = _country(location) or ("REMOTE" if remote else "OTHER")
    return Job(
        id=make_id(source, posting.get("identifier") if isinstance(posting.get("identifier"), str) else None, url),
        title=title,
        company=(org.get("name") if isinstance(org, dict) else None) or NOT_STATED,
        location=location,
        country=country,
        url=url,
        source=source,
        source_type="scraper",
        posted_date=(posting.get("datePosted") or "")[:10] or None,
        remote=remote,
        salary=_salary(posting),
        description=_TAGS.sub(" ", posting.get("description") or "").strip(),
    )

def _harvest(source: str, urls: list[str], get, terms: list[str]) -> list[Job]:
    jobs, seen = [], set()
    for url in urls[:MAX_JOBS_PER_BOARD]:
        try:
            posting = _job_posting(get(url, headers=HEADERS))
        except Exception:  # noqa: BLE001 - one dead job page must not kill the board
            continue
        job = posting and _to_job(source, url, posting)
        # both boards list off-topic roles (a crypto QA job sits on the security
        # page), so keep only postings that actually mention what we search for
        if not job or not _keyword_match(f"{job.title} {job.description}", terms):
            continue
        key = (job.title.lower(), job.company.lower())  # same posting, two slugs
        if key in seen:
            continue
        seen.add(key)
        jobs.append(job)
    return jobs

# --- CryptoValley Jobs (Switzerland) -------------------------------------
# Small Swiss board, no category pages: take job urls from the sitemap and keep
# the ones whose slug matches a search term before spending a request on them.
def fetch_cryptovalley(cfg, get=get_text):
    sitemap = get("https://cryptovalley.jobs/sitemap.xml", headers=HEADERS)
    urls = re.findall(r"<loc>(https://cryptovalley\.jobs/jobs/[^<]+)</loc>", sitemap)
    terms = _terms(cfg)
    wanted = [u for u in urls if _keyword_match(u.rsplit("/", 1)[-1].replace("-", " "), terms)]
    # ponytail: some cryptovalley postings ship an empty ld+json description, so
    # those jobs reach the AI as title+company only. Scrape the page body if that
    # turns out to cost real matches.
    return _harvest("cryptovalley", wanted, get, terms)

# --- CryptoJobsList (global web3) ----------------------------------------
# Has a security category, so the board has already done the filtering.
def fetch_cryptojobslist(cfg, get=get_text):
    page = get("https://cryptojobslist.com/security-jobs", headers=HEADERS)
    paths = re.findall(r'href="(/jobs/[^"?#]+)"', page)
    seen, urls = set(), []
    for path in paths:
        url = "https://cryptojobslist.com" + path
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return _harvest("cryptojobslist", urls, get, _terms(cfg))

register(fetch_cryptovalley)
register(fetch_cryptojobslist)
