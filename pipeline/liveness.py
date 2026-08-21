from __future__ import annotations
import logging
import requests

# A job vanishing from a feed does not mean it is gone: boards page their results
# and older postings fall off the first page while still being open. So a job is
# only dropped once the posting itself says it is gone.
log = logging.getLogger("liveness")
DEAD_STATUSES = {404, 410}
MISSING_RUNS_BEFORE_CHECK = 2   # ~4h at a 2h cadence
MAX_CHECKS_PER_RUN = 40         # bounds how long a run can spend on this

def _probe(url: str, timeout: int = 15):
    headers = {"User-Agent": "cyberjobs-radar/1.0 (personal job search)"}
    try:
        r = requests.head(url, timeout=timeout, allow_redirects=True, headers=headers)
        if r.status_code in (403, 405) or r.status_code >= 500:
            # plenty of boards refuse HEAD; fall back before believing the answer
            r = requests.get(url, timeout=timeout, allow_redirects=True, headers=headers)
        return r.status_code
    except requests.RequestException as e:
        log.debug("probe failed for %s: %s", url, e)
        return None  # a network blip is not evidence of a delisting

def is_dead(url: str, probe=_probe) -> bool:
    """True only when the board answers "gone".

    Some boards soft-404 — jobicy serves 200 for a made-up job id — so those
    postings are never removed here and fall to the age-out window instead.
    Guessing from page text would risk deleting live jobs, which is worse.
    """
    return probe(url) in DEAD_STATUSES

def prune(jobs, *, probe=_probe, min_missing=MISSING_RUNS_BEFORE_CHECK,
          cap=MAX_CHECKS_PER_RUN):
    """Drop jobs whose posting is confirmed gone. Returns (kept, removed)."""
    candidates = [j for j in jobs if j.missing_runs >= min_missing]
    # oldest miss first, so a backlog still gets worked through run by run
    candidates.sort(key=lambda j: -j.missing_runs)
    dead = set()
    for job in candidates[:cap]:
        if is_dead(job.url, probe):
            dead.add(job.id)
            log.info("removing delisted job: %s (%s)", job.title[:50], job.url)
    kept = [j for j in jobs if j.id not in dead]
    return kept, [j for j in jobs if j.id in dead]
