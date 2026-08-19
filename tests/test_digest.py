import json
from pipeline.digest import select, load_emailed, save_emailed, render_html, run_digest
from pipeline.models import Job, make_id


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
