from pipeline.sources import fetch_all
from pipeline.models import Job, make_id, NOT_STATED

def _mk(url):
    return Job(id=make_id("s", "1", url), title="t", company="c", location="l",
               country="CH", url=url, source="s", source_type="api",
               description="d")

def test_fetch_all_isolates_failures():
    good = lambda cfg, get=None: [_mk("https://ok.test/1")]
    boom = lambda cfg, get=None: (_ for _ in ()).throw(RuntimeError("api down"))
    jobs = fetch_all({}, adapters=[good, boom])
    assert len(jobs) == 1
    assert jobs[0].url == "https://ok.test/1"
