import json
from pipeline.digest import select, load_emailed, save_emailed, render_html, run_digest
from pipeline.models import Job, make_id, NOT_STATED


def _j(url, score=None, first_seen="2026-08-19", source="jobtech"):
    return Job(id=make_id(source, url, url), title="SOC Analyst", company="ACME",
               location="Zurich", country="CH", url=url, source=source,
               source_type="api", score=score, first_seen=first_seen,
               score_reason="good fit", skills=["SIEM"], description="desc")


def test_select_skips_already_emailed_and_ranks():
    jobs = [_j("https://a/1", 90), _j("https://a/2", 60), _j("https://a/3", 95)]
    out = select(jobs, emailed={jobs[0].id}, min_score=50, cap=10)
    # a/1 already emailed -> excluded; rest ranked desc
    assert [j.url for j in out] == ["https://a/3", "https://a/2"]


def test_select_falls_back_to_unscored_when_no_ai():
    jobs = [_j("https://a/1", None), _j("https://a/2", None)]
    out = select(jobs, emailed=set(), min_score=70, cap=10)
    assert len(out) == 2  # unscored still delivered so digest isn't dead without AI


def test_select_respects_cap():
    jobs = [_j(f"https://a/{i}", 80) for i in range(30)]
    assert len(select(jobs, emailed=set(), min_score=50, cap=25)) == 25


def test_emailed_state_roundtrip_and_cap(tmp_path):
    p = tmp_path / "state.json"
    save_emailed(str(p), {f"id{i}" for i in range(1500)})
    got = load_emailed(str(p))
    assert len(got) == 1000  # capped
    assert load_emailed(str(tmp_path / "missing.json")) == set()


def test_render_html_has_links_and_no_fabrication():
    html = render_html([_j("https://a/1", 90)])
    assert "https://a/1" in html
    assert "SOC Analyst" in html


def test_run_digest_sends_and_records(tmp_path):
    data = tmp_path / "jobs.json"
    data.write_text(json.dumps([_j("https://a/1", 90).to_dict(), _j("https://a/2", 80).to_dict()]))
    state = tmp_path / "state.json"
    sent = {}
    def fake_send(html, subject, to, sender, password):
        sent.update(html=html, subject=subject, to=to)
    cfg = {"secrets": {"GMAIL_USER": "me@gmail.com", "GMAIL_APP_PASSWORD": "pw", "DIGEST_TO": "me@gmail.com"},
           "digest": {"min_score": 50, "cap": 25}}
    s1 = run_digest(cfg, str(data), str(state), send_fn=fake_send)
    assert s1["sent"] == 2 and "SOC Analyst" in sent["html"]
    # second run: same jobs already emailed -> nothing sent
    sent.clear()
    s2 = run_digest(cfg, str(data), str(state), send_fn=fake_send)
    assert s2["sent"] == 0 and sent == {}


def test_run_digest_noop_without_credentials(tmp_path):
    data = tmp_path / "jobs.json"
    data.write_text(json.dumps([_j("https://a/1", 90).to_dict()]))
    state = tmp_path / "state.json"
    called = []
    cfg = {"secrets": {}, "digest": {"min_score": 50, "cap": 25}}
    s = run_digest(cfg, str(data), str(state), send_fn=lambda *a, **k: called.append(1))
    assert s["sent"] == 0 and called == []  # no creds -> never sends

def test_render_states_the_four_facts_and_never_invents_an_office():
    onsite = Job(id="a", title="Security Engineer", company="Acme", location="Zurich",
                 country="CH", url="https://b.test/a", source="adzuna", source_type="api",
                 remote=NOT_STATED, salary="90000 CHF", employment_type="Full Time",
                 description="d")
    html = render_html([onsite])
    for label in ("LOCATION", "WORK MODE", "TYPE", "SALARY"):
        assert label in html
    assert "Zurich" in html and "90000 CHF" in html and "Full Time" in html
    assert "On site" not in html  # adzuna states no remote flag, so neither do we

def test_render_marks_remote_and_absent_fields():
    remote = Job(id="b", title="Security Engineer", company="Acme", location="Europe",
                 country="REMOTE", url="https://b.test/b", source="jobicy", source_type="api",
                 remote=True, description="d")
    html = render_html([remote])
    assert "Remote" in html and "not stated" in html  # salary + type absent, stated as such

def test_render_always_states_sponsorship_and_both_currencies():
    j = Job(id="v", title="Security Engineer", company="Acme", location="Zurich, Switzerland",
            country="CH", url="https://b.test/v", source="adzuna", source_type="api",
            salary="90000-110000 CHF", salary_inr="≈ ₹1.1 Cr year", visa_sponsorship="yes",
            role_summary="Run detection engineering.", expectations="Two years of SOC work.",
            description="d")
    html = render_html([j])
    assert "Sponsorship offered" in html
    assert "90000-110000 CHF (≈ ₹1.1 Cr year)" in html  # their currency first, then INR
    assert "Run detection engineering." in html and "Two years of SOC work." in html

def test_render_says_sponsorship_not_stated_when_the_ad_is_silent():
    j = Job(id="w", title="Security Engineer", company="Acme", location="Zurich, Switzerland",
            country="CH", url="https://b.test/w", source="adzuna", source_type="api",
            description="d")
    html = render_html([j])
    assert "Sponsorship not stated" in html
    assert "No sponsorship" not in html  # silence is never read as a refusal

def test_render_states_experience_and_must_have_skills():
    j = Job(id="e", title="Security Analyst", company="Acme", location="Zurich, Switzerland",
            country="CH", url="https://b.test/e", source="adzuna", source_type="api",
            experience_required="2-4 years", skills=["SIEM", "Python"], description="d")
    html = render_html(j and [j], "2026-08-21T09:30:00+00:00")
    assert "EXPERIENCE" in html and "2-4 years" in html
    assert "Must have: SIEM, Python" in html
    assert "Data refreshed 2026-08-21T09:30:00+00:00" in html

def test_render_without_a_run_stamp_says_nothing_about_freshness():
    j = Job(id="f", title="Security Analyst", company="Acme", location="l", country="CH",
            url="https://b.test/f", source="s", source_type="api", description="d")
    assert "Data refreshed" not in render_html([j])
