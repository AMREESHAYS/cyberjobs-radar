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
