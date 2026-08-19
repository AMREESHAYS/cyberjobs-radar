from __future__ import annotations
import json, os
from datetime import date
from .models import Job, assert_valid

def load(path: str) -> list[Job]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read().strip()
    if not raw:
        return []
    return [Job.from_dict(d) for d in json.loads(raw)]

# what the AI writes, plus when we first saw the job: never overwritten by a refetch
_ENRICHED = ("score", "score_reason", "skills", "hiring_process", "seniority_fit", "first_seen")

def merge(existing, fetched, today: str):
    by_id = {j.id: j for j in existing}
    new = []
    for j in fetched:
        known = by_id.get(j.id)
        if known is None:
            j.first_seen = today
            by_id[j.id] = j
            new.append(j)
            continue
        # already known: take the freshly fetched source fields (a board can fix a
        # location or add a salary, and new fields need to reach old rows) while
        # keeping everything the AI produced
        for field, value in vars(known).items():
            if field in _ENRICHED:
                setattr(j, field, value)
        by_id[j.id] = j
    return list(by_id.values()), new

def _days_between(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days

def age_out(jobs, today: str, max_days: int, keep_ids: set) -> list:
    out = []
    for j in jobs:
        if j.id in keep_ids:
            out.append(j); continue
        fs = j.first_seen or today
        if _days_between(fs, today) <= max_days:
            out.append(j)
    return out

def save(path: str, jobs) -> None:
    for j in jobs:
        assert_valid(j)
    ordered = sorted(jobs, key=lambda j: (j.score is None, -(j.score or 0)))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([j.to_dict() for j in ordered], f, ensure_ascii=False, indent=2)
