from __future__ import annotations
import logging
from datetime import date, timezone, datetime
from .config import load_config, load_profile
from .sources import fetch_all
from .ai import ANALYSIS_VERSION, analyze, build_client
from . import fx, liveness, relevance, store

log = logging.getLogger("run")

# import adapter modules so they register themselves
from .sources import adzuna, jobtech, nav, remote_apis, crypto_boards, eures  # noqa: E402,F401

def prefilter(jobs, cfg):
    targets = set(cfg.get("countries", []))
    return [j for j in jobs if j.country == "REMOTE" or j.country in targets]

def run(cfg, profile, data_path="data/jobs.json", *, fetch=fetch_all,
        client_factory=build_client, analyze_fn=analyze, rates_loader=fx.load_rates,
        prune_fn=liveness.prune, meta_path="data/meta.json", now=None, today=None):
    now = now or datetime.now(timezone.utc)
    today = today or now.date().isoformat()
    fetched, out_of_reach = relevance.drop_out_of_reach(prefilter(fetch(cfg), cfg), cfg)
    if out_of_reach:
        log.info("skipped %d postings above entry level", len(out_of_reach))
    existing = store.load(data_path)
    all_jobs, new_jobs = store.merge(existing, fetched, today)
    # apply the same two rules to what is already stored, so tightening the
    # filters cleans the backlog instead of only affecting future fetches
    all_jobs, stale_seniority = relevance.drop_out_of_reach(all_jobs, cfg)
    all_jobs, duplicates = relevance.dedupe(all_jobs)
    new_jobs = [j for j in new_jobs if j in all_jobs]

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

    # drop postings the board itself now returns as gone, then the age-out net
    surviving, removed = prune_fn(all_jobs)
    kept = store.age_out(surviving, today, cfg.get("age_out_days", 45), keep_ids=set())
    aged_out = len(surviving) - len(kept)
    store.save(data_path, kept)

    summary = {"total": len(kept), "new": len(new_jobs), "scored": scored,
               "removed": len(removed), "aged_out": aged_out,
               "above_level": len(out_of_reach) + len(stale_seniority),
               "duplicates": len(duplicates)}
    store.save_meta(meta_path, {**summary, "generated_at": now.replace(microsecond=0).isoformat()})
    return summary

def main():
    logging.basicConfig(level=logging.INFO)
    cfg = load_config()
    profile = load_profile()
    summary = run(cfg, profile)
    log.info("run complete: %s", summary)
    print(summary)

if __name__ == "__main__":
    main()
