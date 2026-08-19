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
python -m pipeline.run                 # writes data/jobs.json
# view locally: index.html loads data/jobs.json beside it, so mirror the deploy layout
mkdir -p web/data && cp data/jobs.json web/data/   # local only; CI does this itself
python -m http.server 8000 -d web      # open http://localhost:8000/
```

> Note: `python -m pipeline.run` runs the fetch with whatever keys are in your env.
> With no keys you still get Sweden (JobTech) + remote boards; Switzerland/cold-Europe
> onsite jobs need the free `ADZUNA_*` keys, and AI scoring needs `GROQ_API_KEY`
> (without it jobs are saved unscored — score shows "—").

## One command (fetch + serve + phone)
```bash
./run.sh            # fetch jobs, serve http://localhost:8000/
./run.sh --tunnel   # same, plus a public phone-reachable URL via cloudflared
```

## Email digest (Phase 2)
After each run the workflow emails you new matching jobs. Add these secrets to turn it on
(no-ops without them): `GMAIL_USER`, `GMAIL_APP_PASSWORD` (a Gmail
[app password](https://myaccount.google.com/apppasswords), not your login), `DIGEST_TO`.
Run manually with `python -m pipeline.digest`. `data/digest_state.json` remembers what was
already sent so you never get duplicates.

## Tests
```bash
pytest -q
node --test tests/test_filters.mjs
```

## Secrets (GitHub → Settings → Secrets → Actions)
Jobs: `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` (optional `NAV_TOKEN`).
AI (any OpenAI-compatible provider — pick one):
- **Groq** (free): `GROQ_API_KEY` (or `AI_API_KEY`), no base URL needed.
- **NVIDIA** (free, [build.nvidia.com](https://build.nvidia.com)): `AI_API_KEY=nvapi-...`,
  `AI_BASE_URL=https://integrate.api.nvidia.com/v1`, `AI_MODEL=meta/llama-3.3-70b-instruct`.
- **Local Ollama**: `AI_BASE_URL=http://localhost:11434/v1`, `AI_MODEL=llama3.1` (no key).

`AI_API_KEY` beats `GROQ_API_KEY`; switching providers is just those three secrets.
Digest: `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `DIGEST_TO`.

## Deploy
Enable GitHub Actions once from the repo's **Actions** tab (a new repo gates the first run
behind a click). The 12h cron then refreshes `data/jobs.json` and emails the digest. Pages
hosting is dormant unless you set repo variable `ENABLE_PAGES=true` (needs a public repo, or
private + GitHub Pro); otherwise use `./run.sh --tunnel` to reach it from your phone.

**Integrity:** every job links to its real source; AI only condenses posting text;
absent fields show "not stated". Nothing is faked.
