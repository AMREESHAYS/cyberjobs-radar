from pipeline.fx import load_rates, to_inr, apply
from pipeline.models import Job, NOT_STATED

def _job(**kw):
    base = dict(id="1", title="t", company="c", location="l", country="CH", url="https://u.test",
                source="s", source_type="api", description="d")
    return Job(**{**base, **kw})

RATES = {"rates": {"CHF": 0.0084, "USD": 0.0104}}  # units per 1 INR

def test_to_inr_renders_a_range_with_the_period():
    j = _job(salary_min=90000, salary_max=110000, salary_currency="CHF", salary_period="year")
    out = to_inr(j, RATES)
    assert out.startswith("≈ ₹") and out.endswith("year") and "Cr" in out

def test_to_inr_is_silent_when_the_ad_stated_no_amount():
    assert to_inr(_job(), RATES) == NOT_STATED

def test_to_inr_is_silent_for_a_currency_with_no_rate():
    j = _job(salary_min=1000, salary_max=2000, salary_currency="XYZ")
    assert to_inr(j, RATES) == NOT_STATED  # no rate, so no number is invented

def test_load_rates_falls_back_to_cache_when_the_api_fails(tmp_path):
    cache = tmp_path / "fx.json"
    cache.write_text('{"date": "old", "rates": {"CHF": 0.009}}')
    def boom(url, params=None, headers=None, timeout=20):
        raise RuntimeError("api down")
    assert load_rates(str(cache), get=boom)["rates"]["CHF"] == 0.009

def test_load_rates_writes_a_cache_it_can_reuse(tmp_path):
    cache = tmp_path / "fx.json"
    fresh = {"time_last_update_utc": "Thu, 20 Aug 2026 00:00", "rates": {"CHF": 0.0084}}
    rates = load_rates(str(cache), get=lambda *a, **k: fresh)
    assert rates["rates"]["CHF"] == 0.0084 and cache.exists()

def test_apply_counts_only_converted_jobs():
    jobs = [_job(salary_min=100, salary_currency="USD"), _job(id="2")]
    assert apply(jobs, RATES) == 1
    assert jobs[1].salary_inr == NOT_STATED
