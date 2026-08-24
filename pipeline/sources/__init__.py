from __future__ import annotations
import logging
from .base import get_json

log = logging.getLogger("sources")

# adapters appended by their modules (import side-effect) or listed here.
ADAPTERS: list = []

def register(fn):
    ADAPTERS.append(fn)
    return fn

def _source_name(adapter) -> str:
    """adzuna and jobtech each define a plain `fetch`, so the module name
    identifies them; the multi-source modules name their functions instead."""
    fn = getattr(adapter, "__name__", "") or "unknown"
    if fn in ("fetch", "unknown"):
        return (getattr(adapter, "__module__", "") or "unknown").rsplit(".", 1)[-1]
    return fn.replace("fetch_", "")

def fetch_all(cfg: dict, adapters=None, stats=None) -> list:
    """Fetch every source. `stats` collects per-source counts for health checks.

    A failed source yields None rather than 0, so a board that is broken can be
    told apart from one that simply had nothing to return.
    """
    adapters = ADAPTERS if adapters is None else adapters
    out = []
    for adapter in adapters:
        name = _source_name(adapter)
        try:
            jobs = adapter(cfg) or []
            log.info("%s -> %d jobs", name, len(jobs))
            out.extend(jobs)
            if stats is not None:
                stats[name] = len(jobs)
        except Exception as e:  # noqa: BLE001 - soft-fail per spec §7
            log.warning("source %s failed: %s", name, e)
            if stats is not None:
                stats[name] = None
    return out
