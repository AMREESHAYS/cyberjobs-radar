from pipeline.liveness import is_dead, prune
from pipeline.models import Job

def _job(jid, missing=0, url=None):
    return Job(id=jid, title=f"job {jid}", company="c", location="l", country="CH",
               url=url or f"https://b.test/{jid}", source="s", source_type="api",
               description="d", missing_runs=missing)

def test_is_dead_only_on_gone_statuses():
    assert is_dead("u", probe=lambda url, timeout=15: 404) is True
    assert is_dead("u", probe=lambda url, timeout=15: 410) is True
    assert is_dead("u", probe=lambda url, timeout=15: 200) is False
    assert is_dead("u", probe=lambda url, timeout=15: 403) is False   # blocked, not gone
    assert is_dead("u", probe=lambda url, timeout=15: 500) is False   # broken, not gone
    assert is_dead("u", probe=lambda url, timeout=15: None) is False  # network blip

def test_prune_keeps_jobs_still_listed_by_a_source():
    jobs = [_job("a", missing=0), _job("b", missing=1)]
    probed = []
    kept, removed = prune(jobs, probe=lambda url, timeout=15: probed.append(url) or 404)
    assert probed == []          # nothing missing long enough to be worth checking
    assert removed == [] and len(kept) == 2

def test_prune_removes_only_confirmed_dead_postings():
    jobs = [_job("gone", missing=3), _job("alive", missing=3), _job("fresh", missing=0)]
    status = {"https://b.test/gone": 404, "https://b.test/alive": 200}
    kept, removed = prune(jobs, probe=lambda url, timeout=15: status[url])
    assert [j.id for j in removed] == ["gone"]
    assert {j.id for j in kept} == {"alive", "fresh"}

def test_prune_caps_how_many_it_checks_per_run():
    jobs = [_job(str(i), missing=2) for i in range(10)]
    calls = []
    kept, removed = prune(jobs, probe=lambda url, timeout=15: calls.append(url) or 200, cap=3)
    assert len(calls) == 3 and len(kept) == 10

def test_prune_works_through_the_longest_missing_first():
    jobs = [_job("recent", missing=2), _job("stale", missing=9)]
    order = []
    prune(jobs, probe=lambda url, timeout=15: order.append(url) or 200, cap=1)
    assert order == ["https://b.test/stale"]
