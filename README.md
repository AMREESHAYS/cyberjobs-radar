# CyberJobs Radar

Personal, free mobile web app that fetches real cybersecurity jobs/internships in
Switzerland + cold-Europe, AI-ranks them to my profile, and serves a verifiable list.
Not for sale. See `docs/superpowers/specs/2026-08-18-cyberjobs-radar-design.md`.

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill ADZUNA_* and GROQ_API_KEY
set -a; source .env; set +a
python -m pipeline.run          # writes data/jobs.json
python -m http.server -d .      # open http://localhost:8000/web/
```

## Tests
```bash
pytest -q
node --test tests/test_filters.mjs
```

## Secrets (GitHub → Settings → Secrets → Actions)
`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `GROQ_API_KEY` (optional `NAV_TOKEN`, `AI_MODEL`, `AI_BASE_URL`).

## Deploy
Enable GitHub Pages (Source: GitHub Actions). The scheduled workflow refreshes
`data/jobs.json` and redeploys `web/`. Install to Android home screen from the browser menu.

**Integrity:** every job links to its real source; AI only condenses posting text;
absent fields show "not stated". Nothing is faked.
