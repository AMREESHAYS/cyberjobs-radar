# CyberJobs Radar — Phase 1 (Backbone) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A free, self-updating mobile PWA that fetches real cybersecurity jobs/internships in Switzerland + cold-Europe from free/official APIs, AI-scores them against the owner's profile, and serves a ranked, verifiable list.

**Architecture:** A Python pipeline runs in GitHub Actions on a cron. It fetches source adapters (soft-failing individually), normalizes to one `Job` schema, dedupes against the committed `data/jobs.json`, AI-scores only new jobs via an OpenAI-compatible client (Groq free), then writes `data/jobs.json`. A static mobile-first PWA on GitHub Pages reads that JSON; saved/applied state lives in `localStorage`.

**Tech Stack:** Python 3.11+, `requests`, `feedparser`, `openai` client, `pyyaml`, `pytest`; vanilla HTML/CSS/JS PWA; GitHub Actions + GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-08-18-cyberjobs-radar-design.md`

## Global Constraints

- Python **3.11+**.
- **Integrity:** every emitted job MUST have a non-empty real `url`. A job without one fails the run loudly. (Spec §2.1, §8)
- **AI never invents:** the model uses only fetched posting text; any absent field is the literal string `"not stated"`. Never guessed. (Spec §2.2)
- Every job carries `source` + `source_type` (`"api"` | `"scraper"`). (Spec §2.3)
- **No secrets committed.** All keys via env / GitHub secrets; `.env.example` documents them. (Spec §5.7)
- Free tiers only; AI runs on **new jobs only**. (Spec §2.4, §5.3)
- Each source adapter fails soft: on any error it logs and returns `[]`, never crashes the run. (Spec §7)
- Mobile-first PWA, installable on Android. (Spec §2.5)

---

## File Structure

```
jobs_hunting/
├── pipeline/
│   ├── __init__.py
│   ├── models.py            # Job dataclass, make_id, NOT_STATED, assert_valid
│   ├── config.py            # load config.yaml, profile.yaml, env/secrets
│   ├── sources/
│   │   ├── __init__.py      # ADAPTERS registry, fetch_all (soft-fail)
│   │   ├── base.py          # get_json / get_text helpers
│   │   ├── adzuna.py
│   │   ├── jobtech.py       # Sweden (official)
│   │   ├── nav.py           # Norway (official, public token)
│   │   └── remote_apis.py   # arbeitnow, jobicy, remoteok, himalayas
│   ├── ai.py                # analyze(job, profile, client, model)
│   ├── store.py             # load, merge/dedupe/age-out, save
│   └── run.py               # orchestrator: main()
├── web/
│   ├── index.html
│   ├── filters.js           # pure: filterJobs, sortByScore (node-testable)
│   ├── app.js               # DOM wiring
│   ├── style.css
│   ├── manifest.webmanifest
│   └── sw.js
├── data/
│   └── jobs.json            # generated; seeded as []
├── profile.yaml
├── config.yaml
├── .env.example
├── requirements.txt
├── tests/
│   ├── fixtures/
│   ├── test_models.py
│   ├── test_sources.py
│   ├── test_ai.py
│   ├── test_store.py
│   ├── test_run.py
│   └── test_filters.mjs
└── .github/workflows/fetch.yml
```

---

### Task 1: Job model + integrity

**Files:**
- Create: `pipeline/__init__.py` (empty), `pipeline/models.py`
- Create: `requirements.txt`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces:
  - `NOT_STATED = "not stated"`
  - `make_id(source: str, source_id: str | None, url: str) -> str`
  - `@dataclass Job` with fields: `id, title, company, location, country, url, source, source_type, posted_date, remote, salary, description, score, score_reason, skills, hiring_process, seniority_fit, first_seen`
  - `Job.to_dict() -> dict` and `Job.from_dict(d: dict) -> Job`
  - `assert_valid(job: Job) -> None` (raises `ValueError` if `url` empty/whitespace)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
import pytest
from pipeline.models import Job, make_id, assert_valid, NOT_STATED

def _job(**kw):
    base = dict(title="SOC Analyst", company="ACME", location="Zurich",
                country="CH", url="https://x.test/1", source="adzuna",
                source_type="api", posted_date="2026-08-01", remote=False,
                salary=NOT_STATED, description="desc")
    base.update(kw)
    base["id"] = make_id(base["source"], "1", base["url"])
    return Job(**base)

def test_make_id_stable_and_unique():
    a = make_id("adzuna", "1", "https://x.test/1")
    b = make_id("adzuna", "1", "https://x.test/1")
    c = make_id("adzuna", "2", "https://x.test/2")
    assert a == b and a != c

def test_roundtrip_dict():
    j = _job()
    assert Job.from_dict(j.to_dict()) == j

def test_assert_valid_rejects_empty_url():
    j = _job(url="   ")
    with pytest.raises(ValueError):
        assert_valid(j)

def test_ai_fields_default_and_not_stated():
    j = _job()
    assert j.score is None
    assert j.hiring_process == NOT_STATED
    assert j.skills == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.models'`

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/models.py
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import hashlib

NOT_STATED = "not stated"

def make_id(source: str, source_id: str | None, url: str) -> str:
    seed = f"{source}:{source_id}" if source_id else url
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]

@dataclass
class Job:
    id: str
    title: str
    company: str
    location: str
    country: str
    url: str
    source: str
    source_type: str  # "api" | "scraper"
    posted_date: str | None = None
    remote: bool | str = False
    salary: str = NOT_STATED
    description: str = ""
    # AI-added
    score: int | None = None
    score_reason: str = ""
    skills: list[str] = field(default_factory=list)
    hiring_process: str = NOT_STATED
    seniority_fit: str = ""
    first_seen: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Job":
        return cls(**d)

def assert_valid(job: Job) -> None:
    if not job.url or not job.url.strip():
        raise ValueError(f"job {job.id!r} from {job.source!r} has no source url")
```

```text
# requirements.txt
requests>=2.31
feedparser>=6.0
openai>=1.40
PyYAML>=6.0
pytest>=8.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline/__init__.py pipeline/models.py requirements.txt tests/test_models.py
git commit -m "feat: Job model + integrity assert"
```

---

### Task 2: Config + profile loading

**Files:**
- Create: `pipeline/config.py`, `config.yaml`, `profile.yaml`, `.env.example`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `load_config(path="config.yaml") -> dict` (merges env: `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `GROQ_API_KEY`, `AI_BASE_URL`, `AI_MODEL`, `NAV_TOKEN` into `cfg["secrets"]`)
  - `load_profile(path="profile.yaml") -> dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from pipeline.config import load_config, load_profile

def test_config_has_countries_and_terms(tmp_path, monkeypatch):
    p = tmp_path / "config.yaml"
    p.write_text("countries: [CH, DE, SE]\nsearch_terms: [security]\nage_out_days: 45\n")
    monkeypatch.setenv("GROQ_API_KEY", "sk-test")
    cfg = load_config(str(p))
    assert cfg["countries"] == ["CH", "DE", "SE"]
    assert cfg["secrets"]["GROQ_API_KEY"] == "sk-test"

def test_profile_loads(tmp_path):
    p = tmp_path / "profile.yaml"
    p.write_text("experience: junior\nneeds_sponsorship: true\nroles: [soc, pentest]\n")
    prof = load_profile(str(p))
    assert prof["needs_sponsorship"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.config'`

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/config.py
from __future__ import annotations
import os
import yaml

_ENV_KEYS = ["ADZUNA_APP_ID", "ADZUNA_APP_KEY", "GROQ_API_KEY",
             "AI_BASE_URL", "AI_MODEL", "NAV_TOKEN"]

def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    cfg["secrets"] = {k: os.environ.get(k) for k in _ENV_KEYS}
    return cfg

def load_profile(path: str = "profile.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
```

```yaml
# config.yaml
countries: [CH, DE, AT, NL, BE, PL, SE, NO, DK, FI, REMOTE]
search_terms:
  - cybersecurity
  - "security engineer"
  - "SOC analyst"
  - "penetration tester"
  - "red team"
  - "application security"
  - "cloud security"
  - DevSecOps
  - "information security"
  - "incident response"
  - "security internship"
age_out_days: 45
ai:
  base_url_default: "https://api.groq.com/openai/v1"
  model_default: "llama-3.3-70b-versatile"
max_new_ai_jobs_per_run: 120   # stay within Groq free limits; excess kept unscored
```

```yaml
# profile.yaml
experience: "student + junior (0-2 years)"
needs_sponsorship: true
open_to_remote_from_india: true
roles:
  - offensive / pentest / red team
  - defensive / SOC / blue team
  - appsec / cloud / devsecops
  - grc / analyst / any
location_targets: [Switzerland, Germany, Austria, Netherlands, Belgium, Poland, Sweden, Norway, Denmark, Finland, remote]
notes: "Indian citizen; prioritize sponsorship / relocation / non-EU-friendly + remote-from-India roles."
```

```text
# .env.example
# Adzuna free key: https://developer.adzuna.com/
ADZUNA_APP_ID=
ADZUNA_APP_KEY=
# Groq free API key: https://console.groq.com/keys
GROQ_API_KEY=
# Optional AI overrides (defaults to Groq llama-3.3-70b). For local Ollama:
#   AI_BASE_URL=http://localhost:11434/v1  AI_MODEL=llama3.1
AI_BASE_URL=
AI_MODEL=
# Optional stable NAV (Norway) token; else fetched from public token endpoint
NAV_TOKEN=
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline/config.py config.yaml profile.yaml .env.example tests/test_config.py
git commit -m "feat: config + profile loading"
```

---

### Task 3: Source base + registry + soft-fail fetch_all

**Files:**
- Create: `pipeline/sources/__init__.py`, `pipeline/sources/base.py`
- Test: `tests/test_sources.py` (first test only; adapters add more later)

**Interfaces:**
- Consumes: `Job` (Task 1).
- Produces:
  - `pipeline/sources/base.py`: `get_json(url, params=None, headers=None, timeout=20) -> dict|list` and `get_text(url, ...) -> str`
  - `pipeline/sources/__init__.py`: `ADAPTERS: list[callable]` where each adapter is `fetch(cfg: dict, get=get_json) -> list[Job]`; and `fetch_all(cfg, adapters=ADAPTERS) -> list[Job]` that wraps each adapter in try/except, logging failures and returning `[]` for the failing one.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sources.py
from pipeline.sources import fetch_all
from pipeline.models import Job, make_id, NOT_STATED

def _mk(url):
    return Job(id=make_id("s", "1", url), title="t", company="c", location="l",
               country="CH", url=url, source="s", source_type="api",
               description="d")

def test_fetch_all_isolates_failures():
    good = lambda cfg, get=None: [_mk("https://ok.test/1")]
    boom = lambda cfg, get=None: (_ for _ in ()).throw(RuntimeError("api down"))
    jobs = fetch_all({}, adapters=[good, boom])
    assert len(jobs) == 1
    assert jobs[0].url == "https://ok.test/1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sources.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.sources'`

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/sources/base.py
from __future__ import annotations
import requests

def get_json(url, params=None, headers=None, timeout=20):
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()

def get_text(url, params=None, headers=None, timeout=20):
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text
```

```python
# pipeline/sources/__init__.py
from __future__ import annotations
import logging
from .base import get_json

log = logging.getLogger("sources")

# adapters appended by their modules (import side-effect) or listed here.
ADAPTERS: list = []

def register(fn):
    ADAPTERS.append(fn)
    return fn

def fetch_all(cfg: dict, adapters=None) -> list:
    adapters = ADAPTERS if adapters is None else adapters
    out = []
    for adapter in adapters:
        name = getattr(adapter, "__name__", repr(adapter))
        try:
            jobs = adapter(cfg) or []
            log.info("%s -> %d jobs", name, len(jobs))
            out.extend(jobs)
        except Exception as e:  # noqa: BLE001 - soft-fail per spec §7
            log.warning("source %s failed: %s", name, e)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sources.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline/sources/__init__.py pipeline/sources/base.py tests/test_sources.py
git commit -m "feat: source base + soft-fail fetch_all"
```

---

### Task 4: Adzuna adapter

**Files:**
- Create: `pipeline/sources/adzuna.py`
- Create: `tests/fixtures/adzuna.json`
- Modify: `tests/test_sources.py` (add adzuna test)

**Interfaces:**
- Consumes: `Job`, `make_id`, `NOT_STATED`, `get_json`.
- Produces: `fetch(cfg, get=get_json) -> list[Job]` (module also registers itself).

- [ ] **Step 1: Write the failing test + fixture**

```json
// tests/fixtures/adzuna.json
{"results": [
  {"id": "111", "title": "Junior SOC Analyst",
   "company": {"display_name": "SecureBank AG"},
   "location": {"display_name": "Zurich, Switzerland", "area": ["Switzerland","Zurich"]},
   "redirect_url": "https://www.adzuna.ch/land/ad/111",
   "created": "2026-08-10T09:00:00Z",
   "description": "Monitor alerts. Visa sponsorship available.",
   "salary_min": 80000, "salary_max": 95000, "contract_time": "full_time"}
]}
```

```python
# tests/test_sources.py  (append)
import json
from pipeline.sources import adzuna

def _fixture_get(payload):
    return lambda url, params=None, headers=None, timeout=20: payload

def test_adzuna_normalizes(tmp_path):
    payload = json.load(open("tests/fixtures/adzuna.json"))
    cfg = {"countries": ["CH"], "search_terms": ["security"],
           "secrets": {"ADZUNA_APP_ID": "a", "ADZUNA_APP_KEY": "b"}}
    jobs = adzuna.fetch(cfg, get=_fixture_get(payload))
    j = jobs[0]
    assert j.company == "SecureBank AG"
    assert j.country == "CH"
    assert j.url == "https://www.adzuna.ch/land/ad/111"
    assert j.source == "adzuna" and j.source_type == "api"
    assert "80000" in j.salary

def test_adzuna_no_keys_returns_empty():
    cfg = {"countries": ["CH"], "search_terms": ["security"], "secrets": {}}
    assert adzuna.fetch(cfg, get=_fixture_get({"results": []})) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sources.py -k adzuna -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.sources.adzuna'`

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/sources/adzuna.py
from __future__ import annotations
from ..models import Job, make_id, NOT_STATED
from . import register
from .base import get_json

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
                remote=False,
                salary=_salary(r),
                description=r.get("description", ""),
            ))
    return jobs

register(fetch)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sources.py -k adzuna -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline/sources/adzuna.py tests/fixtures/adzuna.json tests/test_sources.py
git commit -m "feat: Adzuna source adapter"
```

---

### Task 5: JobTech (Sweden) adapter

**Files:**
- Create: `pipeline/sources/jobtech.py`
- Create: `tests/fixtures/jobtech.json`
- Modify: `tests/test_sources.py`

**Interfaces:**
- Produces: `fetch(cfg, get=get_json) -> list[Job]`. Endpoint `https://jobsearch.api.jobtechdev.se/search`, params `q` + `limit`; no key needed.

- [ ] **Step 1: Write the failing test + fixture**

```json
// tests/fixtures/jobtech.json
{"total": {"value": 1}, "hits": [
  {"id": "abc123", "headline": "Security Engineer (AppSec)",
   "employer": {"name": "Nordic Fintech AB"},
   "workplace_address": {"municipality": "Stockholm", "region": "Stockholm", "country": "Sverige"},
   "webpage_url": "https://arbetsformedlingen.se/annons/abc123",
   "publication_date": "2026-08-12T08:00:00",
   "description": {"text": "Secure our platform. English speaking team."},
   "salary_type": {"label": "Fast lön"}}
]}
```

```python
# tests/test_sources.py  (append)
from pipeline.sources import jobtech

def test_jobtech_normalizes():
    payload = json.load(open("tests/fixtures/jobtech.json"))
    cfg = {"search_terms": ["security"]}
    jobs = jobtech.fetch(cfg, get=_fixture_get(payload))
    j = jobs[0]
    assert j.country == "SE"
    assert j.company == "Nordic Fintech AB"
    assert j.url.endswith("/annons/abc123")
    assert j.source == "jobtech" and j.source_type == "api"
    assert "Secure our platform" in j.description
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sources.py -k jobtech -v`
Expected: FAIL with `ImportError` / `No module named 'pipeline.sources.jobtech'`

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/sources/jobtech.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sources.py -k jobtech -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/sources/jobtech.py tests/fixtures/jobtech.json tests/test_sources.py
git commit -m "feat: JobTech (Sweden) source adapter"
```

---

### Task 6: NAV (Norway) adapter — best-effort, public token

**Files:**
- Create: `pipeline/sources/nav.py`
- Create: `tests/fixtures/nav_feed.json`
- Modify: `tests/test_sources.py`

**Interfaces:**
- Produces: `fetch(cfg, get=get_json) -> list[Job]`. Uses `cfg["secrets"]["NAV_TOKEN"]` if set, else fetches a public token. Fields parsed defensively (NAV schema is best-effort; `source_type="scraper"` to signal lower confidence).

Note: NAV's real feed returns entries whose full ad lives behind a per-entry link. For Phase 1 we normalize whatever summary fields the feed entry exposes and always keep the entry's public ad URL; missing fields degrade to `NOT_STATED`, never crash. Defensive `.get()` with fallbacks is intentional.

- [ ] **Step 1: Write the failing test + fixture**

```json
// tests/fixtures/nav_feed.json
{"content": [
  {"uuid": "no-1", "title": "IT-sikkerhetsanalytiker",
   "businessName": "Oslo Sikkerhet AS",
   "municipal": "Oslo", "published": "2026-08-11T10:00:00",
   "link": "https://arbeidsplassen.nav.no/stillinger/stilling/no-1",
   "description": "Overvake trusler. Vi tilbyr relokalisering."}
]}
```

```python
# tests/test_sources.py  (append)
from pipeline.sources import nav

def test_nav_normalizes_with_token():
    payload = json.load(open("tests/fixtures/nav_feed.json"))
    cfg = {"secrets": {"NAV_TOKEN": "tok"}}
    jobs = nav.fetch(cfg, get=_fixture_get(payload))
    j = jobs[0]
    assert j.country == "NO"
    assert j.company == "Oslo Sikkerhet AS"
    assert j.url.endswith("/stilling/no-1")
    assert j.source == "nav" and j.source_type == "scraper"

def test_nav_no_token_and_no_public_token_returns_empty():
    def failing_get(url, params=None, headers=None, timeout=20):
        raise RuntimeError("no token endpoint")
    assert nav.fetch({"secrets": {}}, get=failing_get) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sources.py -k nav -v`
Expected: FAIL with `No module named 'pipeline.sources.nav'`

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/sources/nav.py
from __future__ import annotations
from ..models import Job, make_id, NOT_STATED
from . import register
from .base import get_json

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
            remote=False,
            salary=NOT_STATED,
            description=r.get("description", ""),
        ))
    return jobs

register(fetch)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sources.py -k nav -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline/sources/nav.py tests/fixtures/nav_feed.json tests/test_sources.py
git commit -m "feat: NAV (Norway) best-effort source adapter"
```

---

### Task 7: Remote/EU API adapters (Arbeitnow, Jobicy, RemoteOK, Himalayas)

**Files:**
- Create: `pipeline/sources/remote_apis.py`
- Create: `tests/fixtures/arbeitnow.json`, `tests/fixtures/remoteok.json`
- Modify: `tests/test_sources.py`

**Interfaces:**
- Produces four registered adapters, each `fetch_*(cfg, get=get_json) -> list[Job]`: `fetch_arbeitnow`, `fetch_jobicy`, `fetch_remoteok`, `fetch_himalayas`. All `source_type="api"`; remote boards set `country="REMOTE"`, `remote=True`. A shared `_keyword_match(text, terms)` keeps only cyber-relevant posts (these boards aren't security-specific).

- [ ] **Step 1: Write the failing test + fixtures**

```json
// tests/fixtures/arbeitnow.json
{"data": [
  {"slug": "sec-eng-1", "title": "Security Engineer",
   "company_name": "BerlinSec GmbH", "location": "Berlin, Germany",
   "remote": false, "url": "https://arbeitnow.com/view/sec-eng-1",
   "created_at": 1754870400, "description": "AppSec role. Visa sponsorship offered.",
   "tags": ["security"]}
]}
```

```json
// tests/fixtures/remoteok.json
[
  {"legal": "disclaimer row"},
  {"id": "ro1", "position": "Penetration Tester", "company": "RemoteRed",
   "url": "https://remoteok.com/remote-jobs/ro1", "date": "2026-08-09T00:00:00+00:00",
   "description": "Red team engagements", "tags": ["security", "pentest"]}
]
```

```python
# tests/test_sources.py  (append)
from pipeline.sources import remote_apis

def test_arbeitnow_keeps_cyber_and_maps_country():
    payload = json.load(open("tests/fixtures/arbeitnow.json"))
    cfg = {"search_terms": ["security", "pentest"]}
    jobs = remote_apis.fetch_arbeitnow(cfg, get=_fixture_get(payload))
    assert jobs[0].country == "DE"
    assert jobs[0].url.endswith("/view/sec-eng-1")

def test_remoteok_skips_legal_row_and_sets_remote():
    payload = json.load(open("tests/fixtures/remoteok.json"))
    cfg = {"search_terms": ["security", "pentest"]}
    jobs = remote_apis.fetch_remoteok(cfg, get=_fixture_get(payload))
    assert len(jobs) == 1
    assert jobs[0].country == "REMOTE" and jobs[0].remote is True

def test_arbeitnow_filters_non_cyber():
    payload = {"data": [{"slug": "x", "title": "Baker", "company_name": "Bread",
                          "location": "Bern, Switzerland", "url": "https://arbeitnow.com/view/x",
                          "description": "bake bread", "tags": []}]}
    jobs = remote_apis.fetch_arbeitnow({"search_terms": ["security"]}, get=_fixture_get(payload))
    assert jobs == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sources.py -k "arbeitnow or remoteok" -v`
Expected: FAIL with `No module named 'pipeline.sources.remote_apis'`

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/sources/remote_apis.py
from __future__ import annotations
import re
from ..models import Job, make_id, NOT_STATED
from . import register
from .base import get_json

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
            location=loc, country=_country_from(loc),
            url=url, source="arbeitnow", source_type="api",
            posted_date=None, remote=bool(r.get("remote")),
            salary=NOT_STATED, description=r.get("description", ""),
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
            salary=NOT_STATED, description=r.get("jobDescription", ""),
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
            salary=NOT_STATED, description=r.get("description", ""),
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
            location="Remote", country="REMOTE",
            url=url, source="himalayas", source_type="api",
            posted_date=None, remote=True,
            salary=NOT_STATED, description=r.get("description", ""),
        ))
    return jobs

for _a in (fetch_arbeitnow, fetch_jobicy, fetch_remoteok, fetch_himalayas):
    register(_a)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sources.py -k "arbeitnow or remoteok" -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline/sources/remote_apis.py tests/fixtures/arbeitnow.json tests/fixtures/remoteok.json tests/test_sources.py
git commit -m "feat: remote/EU API adapters (arbeitnow, jobicy, remoteok, himalayas)"
```

---

### Task 8: AI scoring + summarization

**Files:**
- Create: `pipeline/ai.py`
- Test: `tests/test_ai.py`

**Interfaces:**
- Consumes: `Job`, `NOT_STATED`.
- Produces:
  - `build_client(cfg) -> (client, model)` — OpenAI-compatible; base_url/model from env overrides else Groq defaults. Returns `(None, model)` if no key (AI disabled).
  - `analyze(job: Job, profile: dict, client, model) -> None` — mutates job in place, setting `score, score_reason, skills, hiring_process, seniority_fit`. On any error/missing field: `score=None`, `score_reason="AI unavailable"` (on error) and every absent field coerced to `NOT_STATED` / `[]`. **Never raises, never drops the job.**
  - `PROMPT` constant containing the hard "use only provided text; absent => 'not stated'; never invent" rule.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai.py
import json
from pipeline.ai import analyze
from pipeline.models import Job, make_id, NOT_STATED

class FakeResp:
    def __init__(self, content): self.choices = [type("C", (), {"message": type("M", (), {"content": content})})]

class FakeClient:
    def __init__(self, content): self._c = content; self.chat = self
    @property
    def completions(self): return self
    def create(self, **kw): return FakeResp(self._c)

def _job():
    return Job(id=make_id("s","1","https://x/1"), title="SOC Analyst Intern",
               company="ACME", location="Zurich", country="CH",
               url="https://x/1", source="s", source_type="api",
               description="Monitor SIEM alerts. Sponsorship available.")

def test_analyze_fills_fields_and_preserves_not_stated():
    content = json.dumps({"score": 82, "score_reason": "entry SOC + sponsorship",
                          "skills": ["SIEM", "log analysis"], "hiring_process": NOT_STATED,
                          "seniority_fit": "intern/junior"})
    j = _job()
    analyze(j, {"needs_sponsorship": True}, FakeClient(content), "m")
    assert j.score == 82
    assert j.skills == ["SIEM", "log analysis"]
    assert j.hiring_process == NOT_STATED

def test_analyze_survives_bad_json():
    j = _job()
    analyze(j, {}, FakeClient("not json at all"), "m")
    assert j.score is None
    assert j.score_reason == "AI unavailable"
    assert j.hiring_process == NOT_STATED

def test_analyze_survives_client_error():
    class Boom:
        chat = property(lambda self: self)
        def create(self, **kw): raise RuntimeError("429")
    j = _job()
    # Boom needs chat.completions.create; emulate:
    class Boom2:
        def __init__(self): self.chat = self
        @property
        def completions(self): return self
        def create(self, **kw): raise RuntimeError("429")
    analyze(j, {}, Boom2(), "m")
    assert j.score is None and j.score_reason == "AI unavailable"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ai.py -v`
Expected: FAIL with `No module named 'pipeline.ai'`

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/ai.py
from __future__ import annotations
import json
from .models import Job, NOT_STATED

PROMPT = """You rank cybersecurity job postings for a specific candidate.

CANDIDATE PROFILE (JSON):
{profile}

JOB POSTING (only source of truth — do NOT use outside knowledge):
title: {title}
company: {company}
location: {location}
description:
{description}

Return ONLY a JSON object with these keys:
  "score": integer 0-100 (fit for THIS candidate: role match, entry-level fit,
           and visa-sponsorship / relocation / remote-from-India signals score higher),
  "score_reason": one short sentence,
  "skills": list of required skills EXPLICITLY named in the description,
  "hiring_process": how they hire IF the description states it, else exactly "not stated",
  "seniority_fit": short tag e.g. "intern", "junior", "mid", "senior".

HARD RULES:
- Use ONLY the description text above. Never invent skills, salary, or process.
- If a field is not present in the description, output exactly "not stated"
  (for skills, an empty list). Do not guess or sugarcoat.
Output the JSON object and nothing else."""

def build_client(cfg):
    sec = cfg.get("secrets", {})
    base_url = sec.get("AI_BASE_URL") or cfg.get("ai", {}).get("base_url_default")
    model = sec.get("AI_MODEL") or cfg.get("ai", {}).get("model_default")
    key = sec.get("GROQ_API_KEY") or "ollama"  # local ollama ignores key
    if not base_url:
        return None, model
    from openai import OpenAI
    return OpenAI(base_url=base_url, api_key=key), model

def _coerce(job: Job, data: dict) -> None:
    job.score = data.get("score") if isinstance(data.get("score"), int) else None
    job.score_reason = str(data.get("score_reason") or "")
    sk = data.get("skills")
    job.skills = [str(s) for s in sk] if isinstance(sk, list) else []
    job.hiring_process = str(data.get("hiring_process") or NOT_STATED) or NOT_STATED
    job.seniority_fit = str(data.get("seniority_fit") or "")

def analyze(job: Job, profile: dict, client, model: str) -> None:
    if client is None:
        job.score, job.score_reason = None, "AI disabled"
        return
    prompt = PROMPT.format(profile=json.dumps(profile), title=job.title,
                           company=job.company, location=job.location,
                           description=job.description[:6000])
    try:
        resp = client.chat.completions.create(
            model=model, temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.choices[0].message.content.strip()
        # tolerate code fences
        if raw.startswith("```"):
            raw = raw.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
        data = json.loads(raw)
        _coerce(job, data)
    except Exception:
        job.score, job.score_reason = None, "AI unavailable"
        job.hiring_process = NOT_STATED
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ai.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline/ai.py tests/test_ai.py
git commit -m "feat: AI scoring + summarization with no-invent contract"
```

---

### Task 9: Store — merge, dedupe, age-out

**Files:**
- Create: `pipeline/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: `Job`, `assert_valid`.
- Produces:
  - `load(path) -> list[Job]` (returns `[]` if file missing/empty)
  - `merge(existing: list[Job], fetched: list[Job], today: str) -> tuple[list[Job], list[Job]]` returns `(all_jobs, new_jobs)`. Dedupe by `id`; existing jobs keep their AI fields + `first_seen`; new jobs get `first_seen=today`.
  - `age_out(jobs: list[Job], today: str, max_days: int, keep_ids: set[str]) -> list[Job]`
  - `save(path, jobs: list[Job]) -> None` (calls `assert_valid` on each; writes sorted by score desc, `None` last)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_store.py
from pipeline.store import merge, age_out, save, load
from pipeline.models import Job, make_id

def _j(url, score=None, first_seen=None, source="s"):
    return Job(id=make_id(source, url, url), title="t", company="c", location="l",
               country="CH", url=url, source=source, source_type="api",
               score=score, first_seen=first_seen, description="d")

def test_merge_sets_first_seen_and_keeps_existing_ai():
    existing = [_j("https://a/1", score=90, first_seen="2026-08-01")]
    fetched = [_j("https://a/1"), _j("https://a/2")]
    allj, new = merge(existing, fetched, today="2026-08-18")
    by = {j.url: j for j in allj}
    assert by["https://a/1"].score == 90           # kept
    assert by["https://a/1"].first_seen == "2026-08-01"
    assert by["https://a/2"].first_seen == "2026-08-18"
    assert len(new) == 1 and new[0].url == "https://a/2"

def test_age_out_drops_old_unless_kept():
    jobs = [_j("https://a/1", first_seen="2026-01-01"),
            _j("https://a/2", first_seen="2026-01-01")]
    keep = {jobs[1].id}
    out = age_out(jobs, today="2026-08-18", max_days=45, keep_ids=keep)
    urls = {j.url for j in out}
    assert "https://a/1" not in urls and "https://a/2" in urls

def test_save_load_roundtrip_and_sort(tmp_path):
    p = tmp_path / "jobs.json"
    save(str(p), [_j("https://a/1", score=None), _j("https://a/2", score=50)])
    loaded = load(str(p))
    assert loaded[0].url == "https://a/2"   # higher score first, None last

def test_save_rejects_missing_url(tmp_path):
    import pytest
    p = tmp_path / "jobs.json"
    bad = _j("https://a/1"); bad.url = ""
    with pytest.raises(ValueError):
        save(str(p), [bad])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_store.py -v`
Expected: FAIL with `No module named 'pipeline.store'`

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/store.py
from __future__ import annotations
import json, os
from datetime import date
from .models import Job, assert_valid

def load(path: str) -> list[Job]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read().strip()
    if not raw:
        return []
    return [Job.from_dict(d) for d in json.loads(raw)]

def merge(existing, fetched, today: str):
    by_id = {j.id: j for j in existing}
    new = []
    for j in fetched:
        if j.id in by_id:
            continue  # already known; keep the stored (AI-enriched) version
        j.first_seen = today
        by_id[j.id] = j
        new.append(j)
    return list(by_id.values()), new

def _days_between(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days

def age_out(jobs, today: str, max_days: int, keep_ids: set) -> list:
    out = []
    for j in jobs:
        if j.id in keep_ids:
            out.append(j); continue
        fs = j.first_seen or today
        if _days_between(fs, today) <= max_days:
            out.append(j)
    return out

def save(path: str, jobs) -> None:
    for j in jobs:
        assert_valid(j)
    ordered = sorted(jobs, key=lambda j: (j.score is None, -(j.score or 0)))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([j.to_dict() for j in ordered], f, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_store.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline/store.py tests/test_store.py
git commit -m "feat: store merge/dedupe/age-out with integrity gate on save"
```

---

### Task 10: Orchestrator — run.py

**Files:**
- Create: `pipeline/run.py`
- Create: `data/jobs.json` (seed `[]`)
- Test: `tests/test_run.py`

**Interfaces:**
- Consumes: `load_config`, `load_profile`, `fetch_all`, `analyze`, `build_client`, store funcs.
- Produces:
  - `prefilter(jobs, cfg) -> list[Job]` — keep jobs whose `country` is in `cfg["countries"]` (REMOTE always kept).
  - `run(cfg, profile, data_path="data/jobs.json", *, fetch=fetch_all, client_factory=build_client, analyze_fn=analyze, today=None) -> dict` — full pipeline; returns summary `{"total": n, "new": m, "scored": k}`. Injectable deps for testing.
  - `main()` — loads config/profile, calls `run`, prints summary.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_run.py
from pipeline.run import run, prefilter
from pipeline.models import Job, make_id

def _j(url, country="CH"):
    return Job(id=make_id("s", url, url), title="Security Analyst", company="c",
               location="l", country=country, url=url, source="s",
               source_type="api", description="d")

def test_prefilter_keeps_targets_and_remote():
    cfg = {"countries": ["CH", "REMOTE"]}
    jobs = [_j("https://a/1", "CH"), _j("https://a/2", "US"), _j("https://a/3", "REMOTE")]
    kept = {j.url for j in prefilter(jobs, cfg)}
    assert kept == {"https://a/1", "https://a/3"}

def test_run_scores_only_new(tmp_path):
    data = str(tmp_path / "jobs.json")
    cfg = {"countries": ["CH", "REMOTE"], "age_out_days": 45,
           "max_new_ai_jobs_per_run": 100, "secrets": {}, "ai": {}}
    scored = []
    def fake_fetch(c, **kw): return [_j("https://a/1"), _j("https://a/2")]
    def fake_client_factory(c): return ("CL", "model")
    def fake_analyze(job, prof, client, model): job.score = 77; scored.append(job.url)
    s1 = run(cfg, {}, data_path=data, fetch=fake_fetch,
             client_factory=fake_client_factory, analyze_fn=fake_analyze, today="2026-08-18")
    assert s1["new"] == 2 and s1["scored"] == 2
    # second run: same jobs -> nothing new, nothing re-scored
    scored.clear()
    s2 = run(cfg, {}, data_path=data, fetch=fake_fetch,
             client_factory=fake_client_factory, analyze_fn=fake_analyze, today="2026-08-19")
    assert s2["new"] == 0 and scored == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_run.py -v`
Expected: FAIL with `No module named 'pipeline.run'`

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/run.py
from __future__ import annotations
import logging
from datetime import date, timezone, datetime
from .config import load_config, load_profile
from .sources import fetch_all
from .ai import analyze, build_client
from . import store

log = logging.getLogger("run")

# import adapter modules so they register themselves
from .sources import adzuna, jobtech, nav, remote_apis  # noqa: E402,F401

def prefilter(jobs, cfg):
    targets = set(cfg.get("countries", []))
    return [j for j in jobs if j.country == "REMOTE" or j.country in targets]

def run(cfg, profile, data_path="data/jobs.json", *, fetch=fetch_all,
        client_factory=build_client, analyze_fn=analyze, today=None):
    today = today or datetime.now(timezone.utc).date().isoformat()
    fetched = prefilter(fetch(cfg), cfg)
    existing = store.load(data_path)
    all_jobs, new_jobs = store.merge(existing, fetched, today)

    client, model = client_factory(cfg)
    cap = cfg.get("max_new_ai_jobs_per_run", 120)
    scored = 0
    for job in new_jobs[:cap]:
        analyze_fn(job, profile, client, model)
        scored += 1

    saved_ids = {j.id for j in all_jobs if j.score is not None}  # never age-out enriched? keep simple:
    kept = store.age_out(all_jobs, today, cfg.get("age_out_days", 45), keep_ids=set())
    store.save(data_path, kept)
    return {"total": len(kept), "new": len(new_jobs), "scored": scored}

def main():
    logging.basicConfig(level=logging.INFO)
    cfg = load_config()
    profile = load_profile()
    summary = run(cfg, profile)
    log.info("run complete: %s", summary)
    print(summary)

if __name__ == "__main__":
    main()
```

```json
// data/jobs.json
[]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_run.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the whole suite + commit**

Run: `pytest -q`
Expected: all green.

```bash
git add pipeline/run.py data/jobs.json tests/test_run.py
git commit -m "feat: pipeline orchestrator (run.py)"
```

---

### Task 11: PWA frontend — pure filter logic + DOM + install

**Files:**
- Create: `web/filters.js`, `web/index.html`, `web/app.js`, `web/style.css`, `web/manifest.webmanifest`, `web/sw.js`
- Test: `tests/test_filters.mjs`

**Interfaces:**
- Produces (in `web/filters.js`, ES module, also attached to `window`):
  - `filterJobs(jobs, criteria) -> array` where criteria = `{country, source, remoteOnly, minScore, query, savedIds, appliedIds, view}` (`view` in `"all"|"saved"|"applied"`).
  - `sortByScore(jobs) -> array` (score desc, null last).

**Note:** DOM wiring in `app.js` is verified by eye in the browser; the pure filter/sort logic carries the automated test. Visual polish is applied at execution time via the `frontend-design` skill — this task ships a clean, mobile-first functional baseline.

- [ ] **Step 1: Write the failing test**

```javascript
// tests/test_filters.mjs   (run with: node --test)
import { test } from "node:test";
import assert from "node:assert";
import { filterJobs, sortByScore } from "../web/filters.js";

const jobs = [
  { id: "1", country: "CH", source: "adzuna", remote: false, score: 90, title: "SOC Analyst", company: "A" },
  { id: "2", country: "REMOTE", source: "remoteok", remote: true, score: 40, title: "Pentester", company: "B" },
  { id: "3", country: "DE", source: "arbeitnow", remote: false, score: null, title: "Baker", company: "C" },
];

test("country filter", () => {
  const r = filterJobs(jobs, { country: "CH" });
  assert.deepEqual(r.map(j => j.id), ["1"]);
});

test("remoteOnly + minScore", () => {
  const r = filterJobs(jobs, { remoteOnly: true, minScore: 30 });
  assert.deepEqual(r.map(j => j.id), ["2"]);
});

test("query matches title/company", () => {
  const r = filterJobs(jobs, { query: "pentest" });
  assert.deepEqual(r.map(j => j.id), ["2"]);
});

test("saved view", () => {
  const r = filterJobs(jobs, { view: "saved", savedIds: ["3"] });
  assert.deepEqual(r.map(j => j.id), ["3"]);
});

test("sort null last", () => {
  const r = sortByScore(jobs);
  assert.deepEqual(r.map(j => j.id), ["1", "2", "3"]);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/test_filters.mjs`
Expected: FAIL — cannot find `../web/filters.js`.

- [ ] **Step 3: Write the implementation**

```javascript
// web/filters.js
export function sortByScore(jobs) {
  return [...jobs].sort((a, b) => {
    const av = a.score == null ? -1 : a.score;
    const bv = b.score == null ? -1 : b.score;
    return bv - av;
  });
}

export function filterJobs(jobs, c = {}) {
  const q = (c.query || "").toLowerCase();
  const saved = new Set(c.savedIds || []);
  const applied = new Set(c.appliedIds || []);
  let out = jobs.filter(j => {
    if (c.country && j.country !== c.country) return false;
    if (c.source && j.source !== c.source) return false;
    if (c.remoteOnly && !(j.remote === true || j.country === "REMOTE")) return false;
    if (c.minScore != null && (j.score == null || j.score < c.minScore)) return false;
    if (q && !`${j.title} ${j.company}`.toLowerCase().includes(q)) return false;
    if (c.view === "saved" && !saved.has(j.id)) return false;
    if (c.view === "applied" && !applied.has(j.id)) return false;
    return true;
  });
  return sortByScore(out);
}

if (typeof window !== "undefined") {
  window.filterJobs = filterJobs;
  window.sortByScore = sortByScore;
}
```

```html
<!-- web/index.html -->
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#0b1020">
  <title>CyberJobs Radar</title>
  <link rel="manifest" href="manifest.webmanifest">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header>
    <h1>CyberJobs Radar</h1>
    <input id="q" type="search" placeholder="Search title / company">
  </header>
  <nav id="tabs">
    <button data-view="all" class="active">All</button>
    <button data-view="saved">Saved</button>
    <button data-view="applied">Applied</button>
  </nav>
  <section id="filters">
    <select id="country"><option value="">All countries</option></select>
    <select id="source"><option value="">All sources</option></select>
    <label><input type="checkbox" id="remoteOnly"> Remote only</label>
    <label>Min score <input type="range" id="minScore" min="0" max="100" value="0"></label>
  </section>
  <main id="list" aria-live="polite"></main>
  <script type="module" src="filters.js"></script>
  <script type="module" src="app.js"></script>
</body>
</html>
```

```javascript
// web/app.js
import { filterJobs } from "./filters.js";

const LS = { saved: "cjr_saved", applied: "cjr_applied" };
const getSet = k => new Set(JSON.parse(localStorage.getItem(k) || "[]"));
const putSet = (k, s) => localStorage.setItem(k, JSON.stringify([...s]));
const esc = s => (s || "").replace(/[&<>"]/g, m => ({ "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;" }[m]));

let JOBS = [];
const state = { view: "all", country: "", source: "", remoteOnly: false, minScore: 0, query: "" };

async function boot() {
  JOBS = await fetch("data/jobs.json?" + Date.now()).then(r => r.json()).catch(() => []);
  fillSelect("country", [...new Set(JOBS.map(j => j.country))].sort());
  fillSelect("source", [...new Set(JOBS.map(j => j.source))].sort());
  wire();
  render();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
}

function fillSelect(id, values) {
  const el = document.getElementById(id);
  for (const v of values) { const o = document.createElement("option"); o.value = v; o.textContent = v; el.appendChild(o); }
}

function wire() {
  document.getElementById("q").addEventListener("input", e => { state.query = e.target.value; render(); });
  document.getElementById("country").addEventListener("change", e => { state.country = e.target.value; render(); });
  document.getElementById("source").addEventListener("change", e => { state.source = e.target.value; render(); });
  document.getElementById("remoteOnly").addEventListener("change", e => { state.remoteOnly = e.target.checked; render(); });
  document.getElementById("minScore").addEventListener("input", e => { state.minScore = +e.target.value; render(); });
  document.querySelectorAll("#tabs button").forEach(b =>
    b.addEventListener("click", () => {
      document.querySelectorAll("#tabs button").forEach(x => x.classList.remove("active"));
      b.classList.add("active"); state.view = b.dataset.view; render();
    }));
}

function render() {
  const saved = getSet(LS.saved), applied = getSet(LS.applied);
  const rows = filterJobs(JOBS, { ...state, savedIds: [...saved], appliedIds: [...applied] });
  const list = document.getElementById("list");
  list.innerHTML = rows.length ? "" : "<p class='empty'>No matching jobs.</p>";
  for (const j of rows) list.appendChild(card(j, saved, applied));
}

function card(j, saved, applied) {
  const el = document.createElement("article");
  el.className = "card";
  const score = j.score == null ? "—" : j.score;
  el.innerHTML = `
    <div class="top"><span class="score">${score}</span>
      <h2>${esc(j.title)}</h2></div>
    <p class="co">${esc(j.company)} · <span class="badge">${esc(j.country)}</span>
      <span class="src ${j.source_type}">${esc(j.source)}</span></p>
    <p class="reason">${esc(j.score_reason)}</p>
    <details><summary>Details</summary>
      <p><strong>Skills:</strong> ${esc((j.skills || []).join(", ") || "not stated")}</p>
      <p><strong>Hiring:</strong> ${esc(j.hiring_process || "not stated")}</p>
      <p><strong>Salary:</strong> ${esc(j.salary || "not stated")}</p>
      <p class="desc">${esc((j.description || "").slice(0, 600))}</p>
    </details>
    <div class="actions">
      <a class="apply" href="${esc(j.url)}" target="_blank" rel="noopener">Open source posting ↗</a>
      <button class="save">${saved.has(j.id) ? "★ Saved" : "☆ Save"}</button>
      <button class="applied">${applied.has(j.id) ? "✓ Applied" : "Mark applied"}</button>
    </div>`;
  el.querySelector(".save").addEventListener("click", () => toggle(LS.saved, j.id));
  el.querySelector(".applied").addEventListener("click", () => toggle(LS.applied, j.id));
  return el;
}

function toggle(key, id) {
  const s = getSet(key); s.has(id) ? s.delete(id) : s.add(id); putSet(key, s); render();
}

boot();
```

```css
/* web/style.css */
:root { --bg:#0b1020; --card:#151b2e; --fg:#e7ecff; --mut:#93a0c8; --acc:#5b8cff; --ok:#39d98a; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:15px/1.45 system-ui, sans-serif; padding-bottom:2rem; }
header { position:sticky; top:0; background:var(--bg); padding:.8rem 1rem; z-index:2; }
header h1 { margin:0 0 .5rem; font-size:1.2rem; }
#q, select { width:100%; padding:.6rem .7rem; border-radius:.6rem; border:1px solid #2a3350; background:#0f1526; color:var(--fg); }
#tabs { display:flex; gap:.4rem; padding:0 1rem .5rem; }
#tabs button { flex:1; padding:.5rem; border:0; border-radius:.6rem; background:#1b2338; color:var(--mut); }
#tabs button.active { background:var(--acc); color:#fff; }
#filters { display:grid; grid-template-columns:1fr 1fr; gap:.5rem; padding:0 1rem 1rem; align-items:center; }
#filters label { color:var(--mut); font-size:.85rem; display:flex; align-items:center; gap:.3rem; }
main { padding:0 1rem; display:grid; gap:.7rem; }
.card { background:var(--card); border:1px solid #222c47; border-radius:.9rem; padding:.9rem; }
.top { display:flex; gap:.6rem; align-items:flex-start; }
.top h2 { margin:0; font-size:1rem; }
.score { flex:0 0 auto; min-width:2.2rem; text-align:center; font-weight:700; background:var(--acc); color:#fff; border-radius:.5rem; padding:.15rem .35rem; }
.co { color:var(--mut); margin:.35rem 0; font-size:.85rem; }
.badge { background:#22305a; padding:.05rem .4rem; border-radius:.4rem; }
.src { padding:.05rem .4rem; border-radius:.4rem; font-size:.75rem; }
.src.api { background:#173a2b; color:var(--ok); } .src.scraper { background:#3a2e17; color:#e0b24a; }
.reason { font-size:.9rem; margin:.3rem 0; }
details summary { cursor:pointer; color:var(--acc); }
.desc { color:var(--mut); white-space:pre-wrap; }
.actions { display:flex; flex-wrap:wrap; gap:.5rem; margin-top:.6rem; }
.actions a, .actions button { flex:1; min-width:8rem; text-align:center; padding:.55rem; border-radius:.6rem; border:0; }
.apply { background:var(--ok); color:#04331f; text-decoration:none; font-weight:600; }
.actions button { background:#1b2338; color:var(--fg); }
.empty { color:var(--mut); text-align:center; padding:2rem; }
```

```json
// web/manifest.webmanifest
{
  "name": "CyberJobs Radar",
  "short_name": "CyberJobs",
  "start_url": ".",
  "display": "standalone",
  "background_color": "#0b1020",
  "theme_color": "#0b1020",
  "icons": [
    { "src": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 192 192'%3E%3Crect width='192' height='192' rx='36' fill='%230b1020'/%3E%3Ctext x='96' y='128' font-size='96' text-anchor='middle' fill='%235b8cff'%3E%F0%9F%9B%A1%3C/text%3E%3C/svg%3E", "sizes": "192x192", "type": "image/svg+xml", "purpose": "any" }
  ]
}
```

```javascript
// web/sw.js  — cache last-viewed data for offline
const CACHE = "cjr-v1";
const ASSETS = ["./", "index.html", "style.css", "app.js", "filters.js", "manifest.webmanifest", "data/jobs.json"];
self.addEventListener("install", e => e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil(caches.keys().then(k => Promise.all(k.filter(x => x !== CACHE).map(x => caches.delete(x))))));
self.addEventListener("fetch", e => {
  e.respondWith(
    fetch(e.request).then(r => { const cp = r.clone(); caches.open(CACHE).then(c => c.put(e.request, cp)); return r; })
      .catch(() => caches.match(e.request))
  );
});
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/test_filters.mjs`
Expected: PASS (5 tests).

Then open `web/index.html` against `data/jobs.json` (see Task 12) and eyeball: cards render, filters/tabs work, save/applied persist across reload.

- [ ] **Step 5: Commit**

```bash
git add web/ tests/test_filters.mjs
git commit -m "feat: mobile PWA frontend (filters, cards, install, offline)"
```

---

### Task 12: GitHub Actions cron + Pages + README

**Files:**
- Create: `.github/workflows/fetch.yml`
- Create: `README.md`
- Create: `.gitignore`

**Interfaces:** none (infra). The workflow runs `python -m pipeline.run`, commits changed `data/jobs.json`, and publishes `web/` (+ `data/`) to GitHub Pages.

- [ ] **Step 1: Write `.gitignore` + README**

```text
# .gitignore
.env
__pycache__/
*.pyc
.venv/
```

````markdown
# CyberJobs Radar

Personal, free mobile web app that fetches real cybersecurity jobs/internships in
Switzerland + cold-Europe, AI-ranks them to my profile, and serves a verifiable list.
Not for sale. See `docs/superpowers/specs/2026-08-18-cyberjobs-radar-design.md`.

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill ADZUNA_* and GROQ_API_KEY
set -a; source .env; set +a
python -m pipeline.run          # writes data/jobs.json
python -m http.server -d .      # open http://localhost:8000/web/
```

## Tests
```bash
pytest -q
node --test tests/test_filters.mjs
```

## Secrets (GitHub → Settings → Secrets → Actions)
`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `GROQ_API_KEY` (optional `NAV_TOKEN`, `AI_MODEL`, `AI_BASE_URL`).

## Deploy
Enable GitHub Pages (Source: GitHub Actions). The scheduled workflow refreshes
`data/jobs.json` and redeploys `web/`. Install to Android home screen from the browser menu.

**Integrity:** every job links to its real source; AI only condenses posting text;
absent fields show "not stated". Nothing is faked.
````

- [ ] **Step 2: Write the workflow**

```yaml
# .github/workflows/fetch.yml
name: fetch-and-deploy
on:
  schedule:
    - cron: "0 */12 * * *"   # every 12h
  workflow_dispatch: {}
permissions:
  contents: write
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: true
jobs:
  fetch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - name: Run pipeline
        env:
          ADZUNA_APP_ID: ${{ secrets.ADZUNA_APP_ID }}
          ADZUNA_APP_KEY: ${{ secrets.ADZUNA_APP_KEY }}
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
          NAV_TOKEN: ${{ secrets.NAV_TOKEN }}
          AI_MODEL: ${{ secrets.AI_MODEL }}
          AI_BASE_URL: ${{ secrets.AI_BASE_URL }}
        run: python -m pipeline.run
      - name: Commit refreshed data
        run: |
          git config user.name "github-actions"
          git config user.email "actions@github.com"
          git add data/jobs.json
          git commit -m "chore: refresh jobs data" || echo "no changes"
          git push
      - name: Assemble site
        run: |
          mkdir -p _site/data
          cp -r web/* _site/
          cp data/jobs.json _site/data/jobs.json
      - uses: actions/upload-pages-artifact@v3
        with: { path: _site }
  deploy:
    needs: fetch
    runs-on: ubuntu-latest
    environment: { name: github-pages, url: "${{ steps.d.outputs.page_url }}" }
    steps:
      - id: d
        uses: actions/deploy-pages@v4
```

- [ ] **Step 3: Verify workflow YAML parses**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/fetch.yml'))"`
Expected: no error.

- [ ] **Step 4: Full suite green**

Run: `pytest -q && node --test tests/test_filters.mjs`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/fetch.yml README.md .gitignore
git commit -m "ci: scheduled fetch + Pages deploy; docs"
```

---

## Self-Review

**1. Spec coverage:**
- §2 integrity/no-invent → Tasks 1 (url assert), 8 (AI contract), 9 (save gate). ✓
- §3 profile → Task 2 `profile.yaml`, used in Task 8 scoring. ✓
- §4 architecture (CI cron + static Pages + localStorage) → Tasks 10, 11, 12. ✓
- §5.1 sources (Adzuna, JobTech, NAV, Arbeitnow, Jobicy, RemoteOK, Himalayas) → Tasks 4–7. ✓
- §5.2 schema → Task 1. §5.3 AI fallback (Groq/Ollama) → Task 8 `build_client`. ✓
- §5.4 pipeline steps → Task 10. §5.5 PWA (cards, filters, save/apply, source link, offline) → Task 11. ✓
- §5.7 config/secrets → Task 2, Task 12. §7 soft-fail → Task 3. §8 testing → every task TDD. ✓
- Phase 2 (digest) + Phase 3 (extra scrapers) intentionally out of scope. ✓

**2. Placeholder scan:** no TBD/TODO; all steps carry real code. ✓

**3. Type consistency:** adapters all expose `fetch`/`fetch_*(cfg, get=get_json) -> list[Job]`; `Job` fields identical across tasks; `analyze` mutates in place as consumed by `run`; `filterJobs`/`sortByScore` signatures match the JS test. ✓

Known best-effort corner (`ponytail:`): NAV (Task 6) and the remote-board JSON shapes are coded defensively against documented fields; if a live schema differs, adapters degrade to `[]` or partial rather than crash (soft-fail, Task 3). Upgrade path: pin exact fields once verified against live responses.
