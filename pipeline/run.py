from __future__ import annotations
import logging
from datetime import date, timezone, datetime
from .config import load_config, load_profile
from .sources import fetch_all
from .ai import ANALYSIS_VERSION, analyze, build_client
from . import fx, store

log = logging.getLogger("run")

# import adapter modules so they register themselves
from .sources import adzuna, jobtech, nav, remote_apis, crypto_boards, eures  # noqa: E402,F401

def prefilter(jobs, cfg):
    targets = set(cfg.get("countries", []))
    return [j for j in jobs if j.country == "REMOTE" or j.country in targets]

def run(cfg, profile, data_path="data/jobs.json", *, fetch=fetch_all,
        client_factory=build_client, analyze_fn=analyze, rates_loader=fx.load_rates,
        today=None):
    today = today or datetime.now(timezone.utc).date().isoformat()
    fetched = prefilter(fetch(cfg), cfg)
    existing = store.load(data_path)
    all_jobs, new_jobs = store.merge(existing, fetched, today)

    client, model = client_factory(cfg)
    cap = cfg.get("max_new_ai_jobs_per_run", 120)
    scored = 0
    if client is not None:
        # score any unscored job (new, or ingested unscored before a key was added,
        # or a prior AI failure) so adding/fixing a key backfills existing jobs.
        # jobs analysed by an older prompt are re-run once, so fields added later
        # (role, expectations, visa) reach rows scored before they existed
        to_score = [j for j in all_jobs
                    if j.score is None or j.analysis_version < ANALYSIS_VERSION]
        for job in to_score[:cap]:
            analyze_fn(job, profile, client, model)
            if job.score is not None:
                scored += 1

    # INR conversion runs over everything, so a rate refresh updates old rows too
    fx.apply(all_jobs, rates_loader())

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
