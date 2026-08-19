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

from pipeline.sources import crypto_boards

def _routed_get(routes):
    def get(url, params=None, headers=None, timeout=20):
        if url not in routes:
            raise AssertionError(f"unexpected fetch: {url}")
        return open(routes[url]).read()
    return get

CJL_JOB = ("https://cryptojobslist.com/jobs/blockchain-sr-lead-security-engineer"
           "-plano-tx-united-states-at-jpmorgan-chase-co")

def test_cryptovalley_filters_slugs_and_reads_ld_json():
    get = _routed_get({
        "https://cryptovalley.jobs/sitemap.xml": "tests/fixtures/cryptovalley_sitemap.xml",
        "https://cryptovalley.jobs/jobs/security-engineer-zug-abc123": "tests/fixtures/cryptovalley_job.html",
    })
    jobs = crypto_boards.fetch_cryptovalley({"search_terms": ["security"]}, get=get)
    assert len(jobs) == 1  # account-executive slug never fetched
    j = jobs[0]
    assert j.company == "Solana Foundation"
    assert j.title == "Data Scientist - Fraud Risk"
    assert j.url.endswith("security-engineer-zug-abc123")
    assert j.source == "cryptovalley" and j.source_type == "scraper"
    assert j.posted_date == "2026-08-10"
    assert j.remote is True and j.country == "REMOTE"  # location says "; Remote"
    assert j.location == "New York, NY, USA; Remote"  # board's bogus "CH" code dropped
    assert "<p>" not in j.description and "fraud" in j.description.lower()
    assert j.salary == NOT_STATED

def test_cryptojobslist_dedupes_links_and_maps_salary():
    get = _routed_get({
        "https://cryptojobslist.com/security-jobs": "tests/fixtures/cryptojobslist_security.html",
        CJL_JOB: "tests/fixtures/cryptojobslist_job.html",
    })
    jobs = crypto_boards.fetch_cryptojobslist({}, get=get)
    assert len(jobs) == 1  # duplicate href fetched once, /companies/ link ignored
    j = jobs[0]
    assert j.company == "JPMorgan Chase & Co"
    assert j.url == CJL_JOB
    assert j.location == "Plano, United States"
    assert j.country == "OTHER"  # non-target country, prefilter drops it
    assert j.salary == "180000-250000 USD year"

def test_crypto_boards_skip_pages_without_job_posting():
    get = _routed_get({
        "https://cryptojobslist.com/security-jobs": "tests/fixtures/cryptojobslist_security.html",
        CJL_JOB: "tests/fixtures/cryptovalley_sitemap.xml",  # no ld+json JobPosting
    })
    assert crypto_boards.fetch_cryptojobslist({}, get=get) == []

def test_crypto_boards_drop_off_topic_postings():
    get = _routed_get({
        "https://cryptojobslist.com/security-jobs": "tests/fixtures/cryptojobslist_security.html",
        CJL_JOB: "tests/fixtures/cryptojobslist_job.html",
    })
    assert crypto_boards.fetch_cryptojobslist({"search_terms": ["SOC analyst"]}, get=get) == []

def test_web3career_parses_nested_array_and_links_apply_url():
    payload = json.load(open("tests/fixtures/web3career.json"))
    cfg = {"search_terms": ["security engineer"], "secrets": {"WEB3CAREER_TOKEN": "tok"}}
    jobs = crypto_boards.fetch_web3career(cfg, get=_fixture_get(payload))
    assert len(jobs) == 1  # community manager dropped by keyword filter
    j = jobs[0]
    assert j.url == "https://web3.career/apply/4211?utm_source=api"  # terms require apply_url
    assert j.company == "ZugChain AG" and j.country == "CH" and j.remote is False
    assert j.source == "web3career" and j.source_type == "api"
    assert j.posted_date == "2026-08-11" and j.salary == "$120k - $160k"
    assert "<p>" not in j.description and "pentest" in j.description

def test_web3career_without_token_returns_empty():
    assert crypto_boards.fetch_web3career({"secrets": {}}, get=_fixture_get([])) == []

def test_web3career_tolerates_flat_root_array():
    row = json.load(open("tests/fixtures/web3career.json"))[2][0]
    cfg = {"search_terms": ["security"], "secrets": {"WEB3CAREER_TOKEN": "tok"}}
    jobs = crypto_boards.fetch_web3career(cfg, get=_fixture_get([row]))
    assert len(jobs) == 1 and jobs[0].title == "Smart Contract Security Engineer"

def test_web3career_skips_undated_posting_date():
    payload = json.load(open("tests/fixtures/web3career.json"))
    cfg = {"search_terms": ["community"], "secrets": {"WEB3CAREER_TOKEN": "tok"}}
    jobs = crypto_boards.fetch_web3career(cfg, get=_fixture_get(payload))
    assert jobs[0].posted_date is None  # "yesterday" is not a date

from pipeline.sources import eures

def _post_capture(payload, calls):
    def post(url, json=None, headers=None, timeout=30):
        calls.append(json)
        return payload
    return post

def test_eures_finland_filters_and_maps():
    payload = json.load(open("tests/fixtures/eures_search.json"))
    calls = []
    cfg = {"search_terms": ["security engineer"]}
    jobs = eures.fetch_finland(cfg, get=_post_capture(payload, calls))
    assert calls[0]["locationCodes"] == ["fi"]  # country filter reaches the API
    assert len(jobs) == 1  # the delivery job matched EURES' loose search, not ours
    j = jobs[0]
    assert j.title == "AI Agent Developer & Enablement Specialist"
    assert j.company == "OSTP" and j.country == "FI" and j.location == "FI19A"
    assert j.source == "eures-fi" and j.source_type == "api"
    assert j.url.startswith("https://europa.eu/eures/portal/jv-se/jv-details/")
    assert " " not in j.url.split("/")[-1].split("?")[0]  # id is percent-encoded
    assert j.posted_date == "2026-08-19" and j.remote is False
    assert "<p>" not in j.description

def test_eures_denmark_prefers_queried_country_in_multi_country_posting():
    payload = json.load(open("tests/fixtures/eures_search.json"))
    cfg = {"search_terms": ["cloud security"]}
    jobs = eures.fetch_denmark(cfg, get=_post_capture(payload, []))
    assert len(jobs) == 1
    assert jobs[0].country == "DK" and jobs[0].location == "DK03"  # posting is DE+DK
    assert jobs[0].source == "eures-dk"

def test_eures_dedupes_across_keyword_queries():
    payload = json.load(open("tests/fixtures/eures_search.json"))
    cfg = {"search_terms": ["security engineer", "cloud security"]}
    jobs = eures.fetch_finland(cfg, get=_post_capture(payload, []))
    assert len({j.id for j in jobs}) == len(jobs) == 2  # two queries, no repeats
