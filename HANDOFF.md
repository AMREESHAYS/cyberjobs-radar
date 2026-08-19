# CyberJobs Radar — Handoff

**For the next Claude / developer.** Everything built, where it lives, what works, what's open, and exactly what to do next. Date: 2026-08-19.

---

## 1. What this is

A free, personal, self-updating mobile PWA that fetches **real** cybersecurity jobs/internships in Switzerland + cold-Europe (+ remote), AI-ranks them against the owner's profile, and serves a ranked, verifiable list. Also emails a digest. Not for sale. Single user.

Owner profile: entry-level (intern + junior), open to all cyber roles, **Indian citizen needing visa sponsorship** → sponsorship/remote-from-India signals score higher. Locations: Switzerland first, then Germany/Austria/Netherlands/Belgium/Poland/Nordics + remote.

**Non-negotiable integrity rule (already enforced in code + tests):** every job has a real source URL; the AI only condenses fetched posting text; absent fields render literally as `"not stated"`; nothing is fabricated.

---

## 2. Where everything is

- **Local repo:** `/home/amr/tools/jobs_hunting` (branch `master`).
- **GitHub:** `https://github.com/AMREESHAYS/cyberjobs-radar` — **PRIVATE**. Owner: `AMREESHAYS`. Authenticated via `gh` CLI on this machine.
- **Spec:** `docs/superpowers/specs/2026-08-18-cyberjobs-radar-design.md`
- **Implementation plan:** `docs/superpowers/plans/2026-08-18-cyberjobs-radar-phase1.md`
- **Build ledger (every decision + ruling):** `.superpowers/sdd/2026-08-18-cyberjobs-radar-phase1/progress.md` (git-ignored scratch).

---

## 3. File structure

```
jobs_hunting/
├── pipeline/                  # Python data pipeline (runs in GitHub Actions cron)
│   ├── models.py             # Job dataclass, make_id, NOT_STATED, assert_valid (integrity gate)
│   ├── config.py             # load_config/load_profile; env keys incl AI_API_KEY, GMAIL_*
│   ├── ai.py                 # build_client (any OpenAI-compatible provider) + analyze() (no-invent contract)
│   ├── store.py              # load/merge/dedupe/age-out/save (score-desc, None last)
│   ├── run.py                # orchestrator: fetch→prefilter→merge→score UNSCORED→save
│   ├── digest.py             # Phase 2: dark HTML email of new matches via Gmail SMTP
│   └── sources/              # one adapter per board, each fails soft (returns [] on error)
│       ├── __init__.py       # ADAPTERS registry + fetch_all (soft-fail isolation)
│       ├── base.py           # get_json/get_text helpers
│       ├── adzuna.py         # Adzuna API (CH/DE/AT/NL/BE/PL/FR/IT/ES) — needs ADZUNA_* keys
│       ├── jobtech.py        # JobTech/Arbetsförmedlingen (Sweden, official, no key)
│       ├── nav.py            # NAV (Norway, official, public token) — best-effort
│       └── remote_apis.py    # arbeitnow, jobicy, remoteok, himalayas (remote/EU)
├── web/                       # static mobile PWA (glassy aurora design)
│   ├── index.html            # header, tabs, filters, list; loads data/jobs.json
│   ├── filters.js            # PURE filterJobs/sortByScore (node-testable)
│   ├── app.js                # DOM wiring, localStorage save/applied
│   ├── style.css             # glassmorphism: midnight aurora, cyan/mint/violet
│   ├── manifest.webmanifest  # PWA install
│   └── sw.js                 # service worker, offline cache
├── data/jobs.json            # generated output (committed by CI each run)
├── tests/                    # pytest (Python) + node --test (JS)
│   ├── test_models/config/sources/ai/store/run/digest.py
│   └── test_filters.mjs
├── docs/superpowers/{specs,plans}/…
├── .github/workflows/fetch.yml   # cron every 12h: fetch → digest → commit → (Pages gated)
├── config.yaml               # countries, search_terms, age_out_days, AI defaults, digest, max_new_ai_jobs_per_run=25
├── profile.yaml              # owner profile (drives AI scoring)
├── .env.example              # documents every secret/env var
├── requirements.txt          # requests, feedparser, openai, PyYAML, pytest
├── run.sh                    # one command: fetch + serve + --tunnel (phone access)
└── README.md
```

---

## 4. What is DONE and PROVEN

- **All 12 Phase-1 tasks + Phase 2 digest built.** Suites: **35 pytest + 7 node, all green.**
- **Pipeline proven in CI:** a real GitHub Actions run fetched **live jobs (~50–66)**, all with real URLs, committed `data/jobs.json`. Sources returning data without keys: **JobTech (Sweden), Arbeitnow, Jobicy, Himalayas**. (Adzuna/NAV/RemoteOK return 0 without keys/token or due to UA block — they fail soft.)
- **PWA proven** via headless puppeteer (chromium): **13/13** checks — cards render, tabs (All/Saved/Applied), Save/Applied toggle + persist across reload (localStorage), search/country/source/remote/min-score filters, real external links in new tabs, glass blur applied, 0 console errors. Screenshot eyeballed — glassy aurora design matches brief.
- **Email digest proven:** rendered from real data + screenshotted (dark aurora, gradient CTAs, real links, dedup via `data/digest_state.json`, no-ops without creds).
- **GitHub Actions cron is ACTIVE** (every 12h). Pages deploy is **gated** behind repo variable `ENABLE_PAGES=true` (private repo = no free Pages).
- **AI provider is pluggable:** `build_client` reads `AI_API_KEY` (any OpenAI-compatible endpoint) then falls back to `GROQ_API_KEY`; `AI_BASE_URL`/`AI_MODEL` override. Degrades to AI-disabled (jobs still saved) when no key / package missing / hosted-provider-without-key. Request `timeout=45, max_retries=2` so a slow provider can't stall CI.

---

## 5. What is OPEN / BROKEN (do this first)

### 5a. AI scoring is not working — `401 Invalid API Key` (BLOCKER)
Every job shows `score = null`, reason `"AI unavailable"`. CI log shows:
`AuthenticationError: Error code: 401 - {'message': 'Invalid API Key'}`.
The stored `AI_API_KEY` secret is **invalid**. History: NVIDIA key worked but its free tier rate-limited batch scoring to ~14s/job (impractical); switched provider to **Groq** (`AI_BASE_URL=https://api.groq.com/openai/v1`, `AI_MODEL=llama-3.3-70b-versatile`), but the Groq key that got stored is invalid (owner pasted it as a shell command first, then a value that Groq rejects; the pasted key `gsk_…` is also exposed in the build chat, so assume it's dead).

**Fix (owner must supply a valid key — an agent must NOT enter API keys):**
1. Owner creates a fresh key at **console.groq.com/keys**.
2. Owner runs in a **real terminal** (the `!` in-session shell has no TTY, which is why interactive `gh secret set` stored empty earlier):
   ```
   printf %s 'gsk_VALID_KEY' | gh secret set AI_API_KEY -R AMREESHAYS/cyberjobs-radar
   ```
3. Trigger a run: `gh workflow run fetch.yml -R AMREESHAYS/cyberjobs-radar`
4. Verify (should show non-zero SCORED and reasons that are real sentences):
   ```
   gh api repos/AMREESHAYS/cyberjobs-radar/contents/data/jobs.json --jq '.content' | base64 -d \
     | python -c "import sys,json;d=json.load(sys.stdin);print('scored',len([j for j in d if j.get('score') is not None]),'/',len(d))"
   ```
   If it still fails, read the CI log for the exact error: `gh run view <id> -R AMREESHAYS/cyberjobs-radar --log | grep 'analyze failed'` (this diagnostic logging was added — 401=bad key, 404/400=wrong model id).

Backfill note: `run.py` scores any **unscored** job (not just new), so once the key is valid the whole existing batch fills in over 1–3 cron runs (batch capped at 25/run in `config.yaml`).

### 5b. Coverage gaps (owner action)
- **Switzerland/Germany onsite jobs need `ADZUNA_*` keys** (developer.adzuna.com). Without them you only get Sweden + remote. Set `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` as secrets.
- **Norway (NAV)** works better with a stable token but falls back to a public token.

### 5c. Phone access (owner choice)
Private repo → no free Pages. Options: `./run.sh --tunnel` (cloudflared, from the Kali box), or GitHub Pro + set repo variable `ENABLE_PAGES=true` (workflow already wired for it).

---

## 6. NOT BUILT — Phase 3: crypto/web3 security job boards (requested, pending)
Owner asked to add these as sources (great for Switzerland cyber):
- **crypto-jobs.ch**, **cryptovalley.jobs** — Switzerland, directly on-target.
- **cryptojobslist.com**, **web3.career** — broader.

Next step: for each, check for a JSON API or RSS first (web3.career and cryptojobslist expose feeds/APIs; the two `.ch/.jobs` ones may need RSS or light HTML scrape). Add each as an isolated adapter in `pipeline/sources/` following the exact shape of `remote_apis.py` (`fetch_x(cfg, get=get_json) -> list[Job]`, `register(fetch_x)`, soft-fail, `source_type="api"` or `"scraper"`), with a fixture + test in `tests/test_sources.py` (reuse the `_fixture_get` helper). Keep the integrity rule.

Also unbuilt (low priority, fragile): LinkedIn/Indeed, Denmark (Jobnet), Finland (Työmarkkinatori) best-effort adapters.

---

## 7. Secrets state (repo: AMREESHAYS/cyberjobs-radar)
Set (as Actions secrets): `AI_API_KEY` (INVALID — replace), `AI_BASE_URL` (Groq), `AI_MODEL` (llama-3.3-70b-versatile).
Not set: `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `GROQ_API_KEY` (unused now — using AI_API_KEY path), `NAV_TOKEN`, `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `DIGEST_TO`.
Repo variables: `ENABLE_PAGES` (not set → Pages dormant).
Provider swap = just repoint `AI_API_KEY` + `AI_BASE_URL` + `AI_MODEL`. For Groq: `AI_BASE_URL=https://api.groq.com/openai/v1`. For local Ollama: `AI_BASE_URL=http://localhost:11434/v1`, no key.

**Security:** both a NVIDIA key and a Groq key were pasted in the build chat in plaintext — treat both as compromised; rotate/regenerate them.

---

## 8. How to run / test / deploy
```bash
# local run (no keys = Sweden + remote only, unscored)
python -m pipeline.run                      # writes data/jobs.json
./run.sh            # fetch + serve http://localhost:8000/
./run.sh --tunnel   # + public phone URL via cloudflared

# tests
pytest -q                                   # 35 pass
node --test tests/test_filters.mjs          # 7 pass

# CI
gh workflow run fetch.yml -R AMREESHAYS/cyberjobs-radar
gh run list -R AMREESHAYS/cyberjobs-radar --workflow=fetch.yml --limit 1
```
Note: local viewing mirrors the deploy layout — `mkdir -p web/data && cp data/jobs.json web/data/` (run.sh does this). `openai` package isn't installed in this local env (PEP 668); CI installs it via requirements.txt. Locally, AI degrades off gracefully.

---

## 9. Immediate next actions (ordered)
1. **Owner:** set a valid Groq key (§5a). Then an agent triggers a run and confirms `scored > 0` with real reason sentences.
2. **Agent:** build the Phase 3 crypto-board sources (§6) — recon APIs/RSS, add adapters + tests, keep integrity.
3. **Owner:** add `ADZUNA_*` for Switzerland/Germany onsite; pick phone-access method (§5c).
4. Optional Phase 3+: Denmark/Finland/LinkedIn best-effort adapters; make the `run.py` "scored" counter and any residual cosmetics nicer (see ledger "Known residual").
```
