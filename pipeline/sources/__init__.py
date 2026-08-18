from __future__ import annotations
import logging
from .base import get_json

log = logging.getLogger("sources")

# adapters appended by their modules (import side-effect) or listed here.
ADAPTERS: list = []

def register(fn):
    ADAPTERS.append(fn)
    return fn

def fetch_all(cfg: dict, adapters=None) -> list:
    adapters = ADAPTERS if adapters is None else adapters
    out = []
    for adapter in adapters:
        name = getattr(adapter, "__name__", repr(adapter))
        try:
            jobs = adapter(cfg) or []
            log.info("%s -> %d jobs", name, len(jobs))
            out.extend(jobs)
        except Exception as e:  # noqa: BLE001 - soft-fail per spec §7
            log.warning("source %s failed: %s", name, e)
    return out
