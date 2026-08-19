from __future__ import annotations
import re
import requests

from ..models import NOT_STATED

def get_json(url, params=None, headers=None, timeout=20):
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()

def get_text(url, params=None, headers=None, timeout=20):
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text

def post_json(url, json=None, headers=None, timeout=30):
    r = requests.post(url, json=json, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()

_TAGS = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")

def strip_html(text: str | None) -> str:
    """Plain text from a posting body. Several boards ship raw HTML."""
    return _SPACE.sub(" ", _TAGS.sub(" ", text or "")).strip()

def employment_label(*values) -> str:
    """Human label from whatever shape a board states employment type in.

    Takes strings, lists or None; returns NOT_STATED when a board says nothing,
    so an absent field never renders as a guess.
    """
    parts = []
    for value in values:
        for item in (value if isinstance(value, (list, tuple)) else [value]):
            if not item or not isinstance(item, str):
                continue
            label = item.replace("_", " ").replace("-", " ").strip().title()
            if label and label not in parts:
                parts.append(label)
    return ", ".join(parts) if parts else NOT_STATED
