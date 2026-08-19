from __future__ import annotations
import requests

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
