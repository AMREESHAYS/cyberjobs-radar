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


def test_run_backfills_existing_unscored_when_key_added(tmp_path):
    # jobs ingested unscored (no key), then a key is added -> they get scored
    import json
    data = str(tmp_path / "jobs.json")
    old = _j("https://a/1")            # score None, already stored
    with open(data, "w") as f:
        json.dump([old.to_dict()], f)
    cfg = {"countries": ["CH", "REMOTE"], "age_out_days": 45,
           "max_new_ai_jobs_per_run": 100, "secrets": {}, "ai": {}}
    def fake_fetch(c, **kw): return [_j("https://a/1")]   # same job re-fetched, still unscored
    def client_on(c): return ("CL", "model")
    def scorer(job, prof, client, model): job.score = 88
    s = run(cfg, {}, data_path=data, fetch=fake_fetch,
            client_factory=client_on, analyze_fn=scorer, today="2026-08-20")
    assert s["new"] == 0 and s["scored"] == 1   # not new, but backfilled


def test_run_no_score_attempts_when_ai_disabled(tmp_path):
    data = str(tmp_path / "jobs.json")
    cfg = {"countries": ["REMOTE"], "age_out_days": 45,
           "max_new_ai_jobs_per_run": 100, "secrets": {}, "ai": {}}
    def fake_fetch(c, **kw): return [_j("https://a/1")]
    def client_off(c): return (None, "model")          # AI disabled
    called = []
    def scorer(job, prof, client, model): called.append(1)
    s = run(cfg, {}, data_path=data, fetch=fake_fetch,
            client_factory=client_off, analyze_fn=scorer, today="2026-08-20")
    assert s["scored"] == 0 and called == []           # no wasted analyze calls
