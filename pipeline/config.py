from __future__ import annotations
import os
import yaml

_ENV_KEYS = ["ADZUNA_APP_ID", "ADZUNA_APP_KEY", "GROQ_API_KEY", "AI_API_KEY",
             "WEB3CAREER_TOKEN",
             "AI_BASE_URL", "AI_MODEL",
             "GMAIL_USER", "GMAIL_APP_PASSWORD", "DIGEST_TO"]

def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    cfg["secrets"] = {k: os.environ.get(k) for k in _ENV_KEYS}
    return cfg

def load_profile(path: str = "profile.yaml") -> dict:
    # profile.yaml is gitignored, so a fresh clone (and CI without the secret)
    # falls back to the template rather than crashing the whole run
    if not os.path.exists(path):
        path = "profile.example.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
