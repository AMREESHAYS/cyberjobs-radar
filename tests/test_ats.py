import json
from pipeline.sources import ats
from pipeline.models import NOT_STATED

def _get(payload, capture=None):
    def get(url, params=None, headers=None, timeout=20):
        if capture is not None:
            capture.append((url, params or {}))
        return payload
    return get

WORKABLE = {"jobs": [{
    "id": "w1", "title": "Junior Security Analyst",
    "company": {"title": "Ikerian AG"},
    "location": {"city": "Basel", "countryName": "Switzerland"},
    "url": "https://jobs.workable.com/view/abc/junior-security-analyst",
    "description": "<p>Join our <b>security</b> team.</p>",
    "requirementsSection": "<ul><li>2+ years of experience</li></ul>",
    "employmentType": "Full-time", "workplace": "hybrid", "created": "2026-08-20T09:00:00Z",
}]}

def test_workable_reads_city_country_and_the_requirements_block():
    jobs = ats.fetch_workable({"countries": ["CH"], "search_terms": ["security"]},
                              get=_get(WORKABLE))
    j = jobs[0]
    assert j.country == "CH" and j.location == "Basel, Switzerland"
    assert j.company == "Ikerian AG" and j.source == "workable"
    assert j.posted_date == "2026-08-20" and j.employment_type == "Full Time"
    assert j.remote is True                      # hybrid still allows remote days
    assert "2+ years of experience" in j.description   # the block that ships separately
    assert "<p>" not in j.description

def test_workable_asks_each_target_country_and_follows_pages():
    calls = []
    ats.fetch_workable({"countries": ["CH", "DE"], "search_terms": ["security"]},
                       get=_get({"jobs": [], "nextPageToken": None}, calls))
    locations = [p["location"] for _, p in calls]
    assert locations == ["switzerland", "germany"]

GREENHOUSE = {"jobs": [
    {"id": 1, "title": "Security Engineer", "company_name": "Proton",
     "absolute_url": "https://job-boards.eu.greenhouse.io/proton/jobs/1",
     "location": {"name": "Geneva, London"}, "updated_at": "2026-08-18T00:00:00Z",
     "content": "&lt;p&gt;Protect our&lt;/p&gt;"},
    {"id": 2, "title": "Channel Sales Lead", "company_name": "Proton",
     "absolute_url": "https://job-boards.eu.greenhouse.io/proton/jobs/2",
     "location": {"name": "London"}, "content": "&lt;p&gt;Sell our security products&lt;/p&gt;"},
]}

def test_greenhouse_unescapes_content_and_judges_by_title():
    jobs = ats.fetch_greenhouse({"ats": {"greenhouse": ["proton"]},
                                 "search_terms": ["security"]}, get=_get(GREENHOUSE))
    assert [j.title for j in jobs] == ["Security Engineer"]  # the sales role stays out
    j = jobs[0]
    assert j.description == "Protect our"      # html-escaped body decoded, tags stripped
    assert j.country == "CH" and j.location.startswith("Geneva")

def test_greenhouse_without_configured_boards_does_nothing():
    assert ats.fetch_greenhouse({"search_terms": ["security"]}, get=_get(GREENHOUSE)) == []

ASHBY = {"jobs": [{
    "id": "a1", "title": "Security Operations Analyst", "jobUrl": "https://jobs.ashbyhq.com/x/a1",
    "location": "Zurich HQ", "employmentType": "FullTime", "isRemote": False,
    "publishedAt": "2026-07-01T10:00:00.000+00:00", "descriptionPlain": "Run the SOC.",
}]}

def test_ashby_resolves_a_city_only_location():
    jobs = ats.fetch_ashby({"ats": {"ashby": ["acme"]}, "search_terms": ["security"]},
                           get=_get(ASHBY))
    j = jobs[0]
    assert j.country == "CH" and j.location == "Zurich, Switzerland"
    assert j.remote is False and j.posted_date == "2026-07-01"
    assert j.employment_type == "Full Time" and j.salary == NOT_STATED
