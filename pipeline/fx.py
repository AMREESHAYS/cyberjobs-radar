from __future__ import annotations
import json
import logging
import os
from .models import Job, NOT_STATED

# Free, no-key daily rates. Cached to disk so a run still converts if the API is
# down, and so 400+ jobs cost one request.
RATES_URL = "https://open.er-api.com/v6/latest/INR"
log = logging.getLogger("fx")

def load_rates(path: str = "data/fx.json", *, get=None) -> dict:
    """{currency: units per 1 INR}. Falls back to the cached file, then to {}."""
    cached = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                cached = json.load(f)
        except ValueError:
            cached = {}
    if get is None:
        from .sources.base import get_json as get
    try:
        data = get(RATES_URL)
        rates = data.get("rates") or {}
        if rates:
            fresh = {"date": data.get("time_last_update_utc", "")[:16], "rates": rates}
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(fresh, f)
            return fresh
    except Exception as e:  # noqa: BLE001 - stale rates beat no rates
        log.warning("rate refresh failed (%s: %s); using cache", type(e).__name__, e)
    return cached

def _inr(amount: float, currency: str, rates: dict) -> float | None:
    per_inr = (rates.get("rates") or {}).get((currency or "").upper())
    if not per_inr:
        return None
    return amount / per_inr

def _short(value: float) -> str:
    if value >= 1e7:
        return f"{value / 1e7:.1f}".rstrip("0").rstrip(".") + " Cr"
    if value >= 1e5:
        return f"{value / 1e5:.1f}".rstrip("0").rstrip(".") + " L"
    return f"{round(value):,}"

def to_inr(job: Job, rates: dict) -> str:
    """"≈ ₹X–Y <period>" for a stated amount; NOT_STATED when the ad gave none."""
    if job.salary_min is None and job.salary_max is None:
        return NOT_STATED
    low = _inr(job.salary_min, job.salary_currency, rates) if job.salary_min is not None else None
    high = _inr(job.salary_max, job.salary_currency, rates) if job.salary_max is not None else None
    if low is None and high is None:
        return NOT_STATED  # currency we have no rate for; say nothing rather than guess
    amount = f"{_short(low)}–{_short(high)}" if low and high else _short(low or high)
    return " ".join(x for x in (f"≈ ₹{amount}", job.salary_period) if x)

def apply(jobs, rates: dict) -> int:
    converted = 0
    for job in jobs:
        job.salary_inr = to_inr(job, rates)
        if job.salary_inr != NOT_STATED:
            converted += 1
    return converted
