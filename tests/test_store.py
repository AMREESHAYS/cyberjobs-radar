from pipeline.store import merge, age_out, save, load
from pipeline.models import Job, make_id

def _j(url, score=None, first_seen=None, source="s"):
    return Job(id=make_id(source, url, url), title="t", company="c", location="l",
               country="CH", url=url, source=source, source_type="api",
               score=score, first_seen=first_seen, description="d")

def test_merge_sets_first_seen_and_keeps_existing_ai():
    existing = [_j("https://a/1", score=90, first_seen="2026-08-01")]
    fetched = [_j("https://a/1"), _j("https://a/2")]
    allj, new = merge(existing, fetched, today="2026-08-18")
    by = {j.url: j for j in allj}
    assert by["https://a/1"].score == 90           # kept
    assert by["https://a/1"].first_seen == "2026-08-01"
    assert by["https://a/2"].first_seen == "2026-08-18"
    assert len(new) == 1 and new[0].url == "https://a/2"

def test_age_out_drops_old_unless_kept():
    jobs = [_j("https://a/1", first_seen="2026-01-01"),
            _j("https://a/2", first_seen="2026-01-01")]
    keep = {jobs[1].id}
    out = age_out(jobs, today="2026-08-18", max_days=45, keep_ids=keep)
    urls = {j.url for j in out}
    assert "https://a/1" not in urls and "https://a/2" in urls

def test_save_load_roundtrip_and_sort(tmp_path):
    p = tmp_path / "jobs.json"
    save(str(p), [_j("https://a/1", score=None), _j("https://a/2", score=50)])
    loaded = load(str(p))
    assert loaded[0].url == "https://a/2"   # higher score first, None last

def test_save_rejects_missing_url(tmp_path):
    import pytest
    p = tmp_path / "jobs.json"
    bad = _j("https://a/1"); bad.url = ""
    with pytest.raises(ValueError):
        save(str(p), [bad])
