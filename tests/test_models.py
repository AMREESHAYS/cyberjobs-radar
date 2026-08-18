import pytest
from pipeline.models import Job, make_id, assert_valid, NOT_STATED

def _job(**kw):
    base = dict(title="SOC Analyst", company="ACME", location="Zurich",
                country="CH", url="https://x.test/1", source="adzuna",
                source_type="api", posted_date="2026-08-01", remote=False,
                salary=NOT_STATED, description="desc")
    base.update(kw)
    base["id"] = make_id(base["source"], "1", base["url"])
    return Job(**base)

def test_make_id_stable_and_unique():
    a = make_id("adzuna", "1", "https://x.test/1")
    b = make_id("adzuna", "1", "https://x.test/1")
    c = make_id("adzuna", "2", "https://x.test/2")
    assert a == b and a != c

def test_roundtrip_dict():
    j = _job()
    assert Job.from_dict(j.to_dict()) == j

def test_assert_valid_rejects_empty_url():
    j = _job(url="   ")
    with pytest.raises(ValueError):
        assert_valid(j)

def test_ai_fields_default_and_not_stated():
    j = _job()
    assert j.score is None
    assert j.hiring_process == NOT_STATED
    assert j.skills == []
