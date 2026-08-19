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
    employment_type: str = NOT_STATED  # full-time / internship / ... as stated
    description: str = ""
    # AI-added
    score: int | None = None
    score_reason: str = ""
    skills: list[str] = field(default_factory=list)
    hiring_process: str = NOT_STATED
    seniority_fit: str = ""
    first_seen: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Job":
        return cls(**d)

def assert_valid(job: Job) -> None:
    if not job.url or not job.url.strip():
        raise ValueError(f"job {job.id!r} from {job.source!r} has no source url")
