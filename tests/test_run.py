import json
from pipeline.run import run, prefilter
from pipeline.ai import ANALYSIS_VERSION
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
    def fake_analyze(job, prof, client, model):
        job.score = 77
        job.analysis_version = ANALYSIS_VERSION  # real analyze() stamps this
        scored.append(job.url)
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

def test_run_converts_stated_salaries_to_inr(tmp_path):
    from pipeline.models import Job, NOT_STATED
    path = tmp_path / "jobs.json"
    paid = Job(id="p1", title="Security Engineer", company="Acme", location="Zurich, Switzerland",
               country="CH", url="https://b.test/p1", source="s", source_type="api",
               salary="90000-110000", salary_min=90000, salary_max=110000,
               salary_currency="CHF", salary_period="year", description="d")
    silent = Job(id="p2", title="Security Engineer", company="Acme", location="Zurich, Switzerland",
                 country="CH", url="https://b.test/p2", source="s", source_type="api",
                 description="d")
    rates = {"rates": {"CHF": 0.0084}}  # 1 INR = 0.0084 CHF
    run({"countries": ["CH"]}, {}, str(path),
        fetch=lambda cfg: [paid, silent],
        client_factory=lambda cfg: (None, "m"),
        rates_loader=lambda: rates, today="2026-08-20")
    saved = {j["id"]: j for j in json.load(open(path))}
    assert saved["p1"]["salary_inr"].startswith("≈ ₹") and "year" in saved["p1"]["salary_inr"]
    assert saved["p2"]["salary_inr"] == NOT_STATED  # no stated amount, no invented one

def test_run_rescores_jobs_that_predate_the_role_fields(tmp_path):
    from pipeline.models import Job, NOT_STATED
    path = tmp_path / "jobs.json"
    old = Job(id="o1", title="Security Engineer", company="Acme", location="Zurich, Switzerland",
              country="CH", url="https://b.test/o1", source="s", source_type="api",
              description="d", score=70, score_reason="fits", first_seen="2026-08-01")
    json.dump([old.to_dict()], open(path, "w"))
    analysed = []
    def fake_analyze(job, profile, client, model):
        analysed.append(job.id)
        job.role_summary = "Runs the SOC."
        job.analysis_version = ANALYSIS_VERSION
    run({"countries": ["CH"]}, {}, str(path), fetch=lambda cfg: [],
        client_factory=lambda cfg: ("client", "m"), analyze_fn=fake_analyze,
        rates_loader=lambda: {}, today="2026-08-20")
    assert analysed == ["o1"]  # already scored, but missing the newer fields
    saved = json.load(open(path))[0]
    assert saved["role_summary"] == "Runs the SOC." and saved["score"] == 70
