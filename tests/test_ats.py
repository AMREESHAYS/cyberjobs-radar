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

LEVER = [{
    "id": "l1", "text": "Security Engineer",
    "hostedUrl": "https://jobs.lever.co/sonarsource/l1",
    "categories": {"location": "Geneva", "commitment": "Employee / Full-Time"},
    "country": "CH", "createdAt": 1787000000000,
    "descriptionPlain": "Keep the platform safe. 3+ years of experience.",
}, {
    "id": "l2", "text": "Account Based Marketing Manager",
    "hostedUrl": "https://jobs.lever.co/sonarsource/l2",
    "categories": {"location": "London"}, "descriptionPlain": "Sell security tooling.",
}]

def test_lever_maps_a_posting_and_ignores_non_security_titles():
    jobs = ats.fetch_lever({"ats": {"lever": ["sonarsource"]}, "search_terms": ["security"]},
                           get=_get(LEVER))
    assert [j.title for j in jobs] == ["Security Engineer"]   # marketing role stays out
    j = jobs[0]
    assert j.country == "CH" and j.location == "Geneva, Switzerland"
    assert j.employment_type == "Employee / Full Time"
    assert j.posted_date and "3+ years" in j.description

SR_LIST = {"content": [
    {"id": "s1", "name": "Security Analyst", "company": {"name": "Nexthink"},
     "location": {"city": "Lausanne", "country": "ch", "remote": False, "hybrid": True}},
    {"id": "s2", "name": "Frontend Developer", "company": {"name": "Nexthink"},
     "location": {"city": "Madrid", "country": "es"}},
]}
SR_DETAIL = {"jobAd": {"sections": {
    "jobDescription": {"text": "<p>Watch the SOC.</p>"},
    "qualifications": {"text": "<p>2 years of experience.</p>"}}}}

def test_smartrecruiters_fetches_the_body_only_for_matching_titles():
    calls = []
    def get(url, params=None, headers=None, timeout=20):
        calls.append(url)
        return SR_LIST if url.endswith("/postings") else SR_DETAIL
    jobs = ats.fetch_smartrecruiters({"ats": {"smartrecruiters": ["nexthink"]},
                                      "search_terms": ["security"]}, get=get)
    assert len(jobs) == 1                      # the frontend role is never fetched
    assert len([c for c in calls if c.endswith("/s1")]) == 1
    j = jobs[0]
    assert j.country == "CH" and j.location == "Lausanne, Switzerland"
    assert "Watch the SOC." in j.description and "2 years of experience." in j.description

RECRUITEE = {"offers": [{
    "id": 7, "title": "Cyber Security Specialist", "company_name": "Swisscom",
    "city": "Bern", "country_code": "CH",
    "careers_url": "https://swisscom.recruitee.com/o/cyber-security-specialist",
    "description": "<p>Defend the network.</p>", "requirements": "<p>Must have: SIEM.</p>",
    "created_at": "2026-07-31 09:55:40 UTC", "employment_type_code": "fulltime_fixed_term",
}]}

def test_recruitee_joins_description_with_the_requirements_block():
    jobs = ats.fetch_recruitee({"ats": {"recruitee": ["swisscom"]}, "search_terms": ["security"]},
                               get=_get(RECRUITEE))
    j = jobs[0]
    assert j.company == "Swisscom" and j.country == "CH" and j.location == "Bern, Switzerland"
    assert "Defend the network." in j.description and "Must have: SIEM." in j.description
    assert j.employment_type == "Fulltime Fixed Term" and j.posted_date == "2026-07-31"
