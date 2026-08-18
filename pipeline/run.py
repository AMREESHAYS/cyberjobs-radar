from __future__ import annotations
import logging
from datetime import date, timezone, datetime
from .config import load_config, load_profile
from .sources import fetch_all
from .ai import analyze, build_client
from . import store

log = logging.getLogger("run")

# import adapter modules so they register themselves
from .sources import adzuna, jobtech, nav, remote_apis  # noqa: E402,F401

def prefilter(jobs, cfg):
    targets = set(cfg.get("countries", []))
    return [j for j in jobs if j.country == "REMOTE" or j.country in targets]

def run(cfg, profile, data_path="data/jobs.json", *, fetch=fetch_all,
        client_factory=build_client, analyze_fn=analyze, today=None):
    today = today or datetime.now(timezone.utc).date().isoformat()
    fetched = prefilter(fetch(cfg), cfg)
    existing = store.load(data_path)
    all_jobs, new_jobs = store.merge(existing, fetched, today)

    client, model = client_factory(cfg)
    cap = cfg.get("max_new_ai_jobs_per_run", 120)
    scored = 0
    for job in new_jobs[:cap]:
        analyze_fn(job, profile, client, model)
        scored += 1

    saved_ids = {j.id for j in all_jobs if j.score is not None}  # never age-out enriched? keep simple:
    kept = store.age_out(all_jobs, today, cfg.get("age_out_days", 45), keep_ids=set())
    store.save(data_path, kept)
    return {"total": len(kept), "new": len(new_jobs), "scored": scored}

def main():
    logging.basicConfig(level=logging.INFO)
    cfg = load_config()
    profile = load_profile()
    summary = run(cfg, profile)
    log.info("run complete: %s", summary)
    print(summary)

if __name__ == "__main__":
    main()
