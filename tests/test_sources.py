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
