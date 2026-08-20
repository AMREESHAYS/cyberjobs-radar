from __future__ import annotations
from dataclasses import dataclass, field, asdict
import hashlib

NOT_STATED = "not stated"

def make_id(source: str, source_id: str | None, url: str) -> str:
    seed = f"{source}:{source_id}" if source_id else url
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]

@dataclass
class Job:
    id: str
    title: str
    company: str
    location: str
    country: str
    url: str
    source: str
    source_type: str  # "api" | "scraper"
    posted_date: str | None = None
    remote: bool | str = False
    salary: str = NOT_STATED
    salary_min: float | None = None      # structured only when the ad states numbers
    salary_max: float | None = None
    salary_currency: str = ""
    salary_period: str = ""
    salary_inr: str = NOT_STATED         # converted at run time, never fabricated
    employment_type: str = NOT_STATED  # full-time / internship / ... as stated
    description: str = ""
    # AI-added
    score: int | None = None
    score_reason: str = ""
    skills: list[str] = field(default_factory=list)
    hiring_process: str = NOT_STATED
    seniority_fit: str = ""
    role_summary: str = NOT_STATED       # what the role actually is
    expectations: str = NOT_STATED       # what they expect from the candidate
    visa_sponsorship: str = NOT_STATED   # only what the ad states; never inferred
    analysis_version: int = 0            # bumped when the prompt gains fields, to backfill
    first_seen: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Job":
        return cls(**d)

def assert_valid(job: Job) -> None:
    if not job.url or not job.url.strip():
        raise ValueError(f"job {job.id!r} from {job.source!r} has no source url")
