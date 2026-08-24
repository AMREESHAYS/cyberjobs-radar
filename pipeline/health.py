from __future__ import annotations
import json
import logging
import os

# Sources fail soft, which is right — one dead board must not stop a run — but it
# also means a board can stop returning anything and nobody notices. This keeps a
# running count of empty fetches per source and names the ones that have gone
# quiet, so a broken key or a changed API surfaces instead of silently shrinking
# the list.
log = logging.getLogger("health")
QUIET_RUNS_BEFORE_ALARM = 2

def load(path: str = "data/source_health.json") -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f) or {}
    except ValueError:
        return {}

def update(previous: dict, counts: dict) -> dict:
    """Fold this run's per-source counts into the running record."""
    report = {}
    for name, count in counts.items():
        was = previous.get(name) or {}
        quiet = 0 if count else (was.get("quiet_runs", 0) + 1)
        report[name] = {
            "last_count": count,
            "quiet_runs": quiet,
            "last_ok": name if count else was.get("last_ok"),
            "errored": count is None,
        }
    # keep sources that did not run this time, so their history is not lost
    for name, was in previous.items():
        report.setdefault(name, was)
    return report

def failing(report: dict, threshold: int = QUIET_RUNS_BEFORE_ALARM) -> list:
    return sorted(name for name, s in report.items()
                  if s.get("quiet_runs", 0) >= threshold)

def save(path: str, report: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)

def check(counts: dict, path: str = "data/source_health.json") -> tuple[dict, list]:
    report = update(load(path), counts)
    save(path, report)
    down = failing(report)
    for name in down:
        log.warning("source %s has returned nothing for %d runs", name, report[name]["quiet_runs"])
    return report, down
