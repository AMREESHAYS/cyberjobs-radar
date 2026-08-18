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
