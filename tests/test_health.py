import json
from pipeline import health

def test_a_source_returning_nothing_once_is_not_yet_an_alarm():
    report = health.update({}, {"adzuna": 0, "workable": 12})
    assert report["adzuna"]["quiet_runs"] == 1
    assert health.failing(report) == []          # one empty run happens

def test_two_quiet_runs_raise_the_alarm():
    first = health.update({}, {"adzuna": 0})
    second = health.update(first, {"adzuna": 0})
    assert second["adzuna"]["quiet_runs"] == 2
    assert health.failing(second) == ["adzuna"]

def test_a_source_coming_back_clears_its_record():
    quiet = health.update(health.update({}, {"nav": 0}), {"nav": 0})
    assert health.failing(quiet) == ["nav"]
    recovered = health.update(quiet, {"nav": 5})
    assert recovered["nav"]["quiet_runs"] == 0 and health.failing(recovered) == []

def test_an_errored_source_is_distinguished_from_an_empty_one():
    report = health.update({}, {"eures-dk": None, "jobtech": 0})
    assert report["eures-dk"]["errored"] is True
    assert report["jobtech"]["errored"] is False
    assert report["eures-dk"]["quiet_runs"] == 1   # still counts toward the alarm

def test_a_source_that_stops_being_registered_is_forgotten():
    """Retiring an adapter must not leave it flagged as broken forever."""
    previous = {"nav": {"last_count": 3, "quiet_runs": 2}}
    report = health.update(previous, {"adzuna": 7})
    assert "nav" not in report and health.failing(report) == []


def test_check_persists_and_reports(tmp_path):
    path = str(tmp_path / "health.json")
    health.check({"adzuna": 0}, path)
    report, down = health.check({"adzuna": 0}, path)
    assert down == ["adzuna"]
    assert json.load(open(path))["adzuna"]["quiet_runs"] == 2

def test_a_retired_adapter_stops_being_flagged():
    quiet = health.update(health.update({}, {"nav": 0, "adzuna": 5}), {"nav": 0, "adzuna": 5})
    assert health.failing(quiet) == ["nav"]
    after_removal = health.update(quiet, {"adzuna": 5})   # nav no longer registered
    assert "nav" not in after_removal
    assert health.failing(after_removal) == []

def test_a_run_that_fetched_nothing_keeps_the_history():
    previous = {"adzuna": {"last_count": 5, "quiet_runs": 0}}
    assert health.update(previous, {})["adzuna"]["last_count"] == 5
