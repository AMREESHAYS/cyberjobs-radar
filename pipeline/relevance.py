from __future__ import annotations
import re
from collections import defaultdict

# The boards answer generic security queries with senior roles: 125 of the first
# 160 scored jobs were senior, 7 junior. Titles are filtered here rather than
# left for the AI, so no tokens are spent ranking jobs that are out of reach.
DEFAULT_EXCLUDE = [
    r"\bsenior\b", r"\bsr\.?\b", r"\blead\b", r"\bleader\b", r"\bprincipal\b",
    r"\bstaff\b", r"\bhead\b", r"\bdirector\b", r"\bchief\b", r"\bcto\b", r"\bciso\b",
    r"\bvp\b", r"\bvice president\b", r"\bmanager\b", r"\barchitect\b", r"\bexpert\b",
    r"\bleiter(in)?\b", r"\bteamlead\b", r"\bteam lead\b", r"\bmanagement\b",
    r"\b(1[0-9]|[5-9])\+? ?(years|jahre)\b",
]

def _patterns(cfg):
    raw = cfg.get("exclude_title_patterns") or DEFAULT_EXCLUDE
    return [re.compile(p, re.I) for p in raw]

def is_out_of_reach(title: str, patterns) -> bool:
    """True for titles that advertise a seniority an entry-level candidate cannot claim."""
    t = title or ""
    # "Junior Security Manager" is still worth seeing; an explicit junior marker wins
    if re.search(r"\b(junior|jr\.?|graduate|intern|internship|trainee|entry|einsteiger|"
                 r"werkstudent|praktikum|praktikant|apprentice|starter)\b", t, re.I):
        return False
    return any(p.search(t) for p in patterns)

def drop_out_of_reach(jobs, cfg):
    patterns = _patterns(cfg)
    kept, dropped = [], []
    for j in jobs:
        (dropped if is_out_of_reach(j.title, patterns) else kept).append(j)
    return kept, dropped

# --- duplicates -----------------------------------------------------------
# One posting is often listed once per city: "Security Awareness Specialist"
# appeared 10 times from one employer, differing only in location.
_NOISE = re.compile(r"[^a-z0-9]+")

def _key(job):
    title = _NOISE.sub("", (job.title or "").lower())[:48]
    company = _NOISE.sub("", (job.company or "").lower())[:24]
    return title, company, job.country

def _rank(job):
    # keep the copy carrying the most work and the most text
    return (job.score is not None, job.analysis_version, len(job.description or ""))

def _merge_locations(jobs) -> str:
    seen = []
    for j in jobs:
        loc = (j.location or "").strip()
        if loc and loc not in seen:
            seen.append(loc)
    if not seen:
        return jobs[0].location
    if len(seen) <= 2:
        return " / ".join(seen)
    return f"{seen[0]} +{len(seen) - 1} more locations"

def dedupe(jobs):
    """Collapse the same posting repeated across cities. Returns (kept, dropped)."""
    groups = defaultdict(list)
    for j in jobs:
        groups[_key(j)].append(j)
    kept, dropped = [], []
    for group in groups.values():
        if len(group) == 1:
            kept.append(group[0])
            continue
        group.sort(key=_rank, reverse=True)
        winner, rest = group[0], group[1:]
        winner.location = _merge_locations(group)   # no city is silently lost
        kept.append(winner)
        dropped.extend(rest)
    return kept, dropped
