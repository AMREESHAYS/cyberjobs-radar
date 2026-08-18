# CyberJobs Radar — Design Spec

**Date:** 2026-08-18
**Owner:** personal use (not for sale)
**One line:** A free, self-updating mobile web app that fetches real cybersecurity jobs & internships in Switzerland and cold-Europe, ranks them against the owner's profile with an open-source AI model, and shows each job's details + how to apply — with a verifiable source link on every listing.

---

## 1. Goal & Non-Goals

### Goal
Give the owner (an Indian citizen, entry-level in cybersecurity, needing visa sponsorship) a single mobile-installable app that surfaces **real, verifiable** cyber roles in Switzerland and cold-Europe, ranked by fit, with enough detail (skills, hiring process, source link) to act.

### Non-Goals
- Not a product to sell. Single user.
- No user accounts, no multi-tenancy, no payments.
- Not a scraper that fabricates or pads data. Empty is empty.
- No native Android app (PWA installs to home screen instead).
- No always-on paid server.

---

## 2. Hard Constraints (non-negotiable)

1. **Data integrity.** Every job carries a real, clickable source URL. Nothing is shown that we can't link back to an origin posting.
2. **AI never invents.** The model only condenses text actually fetched from a posting. Any field not present in the source (e.g. hiring process, salary) is rendered literally as **"not stated"** — never guessed, never sugarcoated.
3. **Source + confidence label** on every job (which adapter produced it; whether it came from a structured API or a fragile scraper).
4. **Free to run.** Total cost target ≤ ₹200/month; in practice ₹0 using free tiers.
5. **Mobile-first.** Usable and installable on Android as a PWA.

---

## 3. Owner Profile (seeds `profile.yaml`, editable)

- **Experience:** student / internship-seeking + junior (0–2 years).
- **Roles of interest:** all cybersecurity — offensive/pentest/red team, defensive/SOC/blue team, AppSec/cloud/DevSecOps, GRC/analyst. Open to any cyber role.
- **Work authorization:** Indian citizen, **needs visa sponsorship**. Prioritize postings that mention sponsorship / relocation / are open to non-EU applicants, and **remote-from-India** roles that sidestep visa entirely.
- **Location targets:** Switzerland (primary), then cold-Europe: Germany, Austria, Netherlands, Belgium, Poland, and Nordics (Sweden, Norway, Denmark, Finland, Iceland) where sources allow — plus remote.

Profile drives AI scoring, not hard filters (except location + the owner's chosen visa preference), so nothing relevant is silently dropped.

---

## 4. Architecture

```
                    GitHub Actions (cron, every ~12h)
                    ┌───────────────────────────────────────┐
   Job sources ───► │  fetch → normalize → dedupe →          │
   (APIs + best-    │  AI score+summarize (new jobs only) →  │
    effort scrapers)│  write jobs.json                       │
                    └───────────────┬───────────────────────┘
                                    │ commit jobs.json
                                    ▼
                         GitHub Pages (static, free)
                                    │
                                    ▼
                      PWA (mobile-first) reads jobs.json
                      saved/applied state → localStorage
```

Two deployables, one repo:
- **Pipeline** (Python) — runs only in CI on a schedule. No always-on server.
- **Frontend PWA** (static HTML/CSS/JS) — served by GitHub Pages, reads the generated `jobs.json`.

Rationale: static + scheduled CI = $0, reachable from the phone anywhere, nothing to keep running. Since it's single-user and read-only from the browser, per-user state (saved/applied) lives in `localStorage` — no backend database or auth needed.

---

## 5. Components

### 5.1 Sources (`pipeline/sources/`, one adapter per source)
Each adapter is self-contained, returns a list of normalized `Job` dicts, and fails soft (logs + returns `[]` on error, never crashes the run).

**Reliable backbone (structured free APIs):**
- **Adzuna** — free app_id + app_key. Country endpoints for `ch, de, at, nl, be, pl, fr, it, es`. Query cybersecurity terms. (Note: Adzuna does **not** cover Nordics — see below.)
- **Arbeitnow** — free public API, strong Germany/EU coverage, visa-sponsorship flags on some posts.
- **Jobicy** — remote jobs API, filter by region/tag.
- **RemoteOK** — remote jobs API, security tag.
- **Himalayas** — remote jobs API.

**Best-effort (flagged fragile, low confidence):**
- Swiss/EU board RSS + company career-page feeds where available (e.g. Swiss startup/tech boards, ETH/EPFL boards).
- Nordic coverage gap: try Nordic-friendly boards (e.g. thehub-style startup feeds) as best-effort since Adzuna lacks Nordics.
- **LinkedIn / Indeed** adapters: included but explicitly marked fragile; respect robots/ToS, expect frequent empty returns, and **never fabricate to compensate.**

Search terms union: cybersecurity, security engineer, SOC analyst, penetration tester, red team, blue team, application security, cloud security, DevSecOps, security analyst, information security, incident response, and "intern"/"internship/Praktikum/Werkstudent" variants.

### 5.2 Normalized Job schema
```
id            # stable hash of (source + source_id | url)
title
company
location      # raw string from source
country       # normalized ISO-ish (CH, DE, ...) or REMOTE
url           # REQUIRED — real source link
source        # adapter name
source_type   # "api" | "scraper"  (confidence signal)
posted_date   # ISO date if known, else null
remote        # bool / "hybrid" if stated
salary        # string or "not stated"
description    # raw fetched text (kept for AI + display)
# --- AI-added fields (see 5.3) ---
score         # 0-100
score_reason  # one line
skills        # list, from source only
hiring_process # string or "not stated"
seniority_fit # short tag
first_seen    # ISO date we first saw it
```

### 5.3 AI (`pipeline/ai.py`)
- **One OpenAI-compatible client.** `base_url` + key chosen by config:
  - Primary (CI path): **Groq free API** (e.g. `llama-3.3-70b-versatile` / `llama-3.1-8b-instant`).
  - Fallback: **OpenRouter** free models.
  - Local option (when run on owner's machine, not CI): **Ollama** (`base_url=http://localhost:11434/v1`).
- Runs **only on jobs new since last run** (cost + time control). Existing jobs keep their prior AI fields.
- Per job, one structured (JSON) call producing: `score`, `score_reason`, `skills`, `hiring_process`, `seniority_fit`.
- **Prompt hard rule:** use only the provided posting text; for any absent field output exactly `"not stated"`; do not infer employer intent or fabricate skills. Scoring rewards role fit, entry-level fit, and sponsorship/remote-from-India signals per the profile.
- On AI failure for a job: keep the job, set `score=null`, `score_reason="AI unavailable"`, still display raw description. Never drop a real job because AI failed.

### 5.4 Pipeline runner (`pipeline/run.py`)
1. Load `profile.yaml` + config.
2. Run all source adapters (concurrently where cheap), collect jobs.
3. Filter to target countries + remote; drop obvious non-cyber by keyword only as a coarse pre-filter (keep borderline for AI).
4. Load previous `jobs.json`; dedupe by `id`; compute new set.
5. AI-process new jobs; merge with retained jobs.
6. Age out stale postings (e.g. > 45 days since `first_seen` and not saved).
7. Write `jobs.json` (sorted by score desc). Commit back via the Action.

### 5.5 Frontend PWA (`web/`)
- Static, mobile-first, installable (manifest + service worker for offline view of last data).
- Reads `jobs.json`.
- **List view:** ranked cards. Each card: title, company, country/remote badge, score + one-line reason, source badge (api/scraper), posted date.
- **Detail view:** summary, required skills, hiring process (or "not stated"), salary, and a prominent **"Open source posting"** link.
- **Filters:** country, role category, remote-only, sponsorship-signal, source, min-score, search box.
- **Save / Applied** toggles per job → `localStorage`; a "Saved" and "Applied" filter.
- Visual design done at implementation time via the frontend-design skill (stylish, not templated). Dark-friendly, thumb-reachable controls.

### 5.6 Email digest (`pipeline/digest.py`) — Phase 2
- After a run, build an email of new high-score jobs since last digest.
- Send via Gmail SMTP using an **app password** stored as a GitHub secret.
- Triggered from the same Actions workflow.

### 5.7 Config & secrets
- `config.yaml` / env: countries list, search terms, AI provider + model, thresholds.
- Secrets as **GitHub repo secrets**: `GROQ_API_KEY`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, (Phase 2) `GMAIL_APP_PASSWORD`, `DIGEST_TO`.
- `.env.example` documents all keys. No secrets committed.

---

## 6. Data Flow (per scheduled run)
1. Cron fires GitHub Action.
2. `run.py` fetches → normalizes → filters → dedupes vs committed `jobs.json`.
3. New jobs → AI scored/summarized (Groq).
4. Merge, age-out, sort, write `jobs.json`.
5. Action commits `jobs.json`; Pages serves it.
6. (Phase 2) digest emailed.
7. Owner opens PWA on Android → sees ranked jobs → opens source links to apply.

---

## 7. Error Handling
- Each adapter isolated: one source failing (network/ToS/format change) logs a warning and yields `[]`; run continues.
- AI failure per-job is non-fatal (job kept, flagged).
- If `jobs.json` write/commit fails, the previous file stays served (no corruption).
- Empty results are shown honestly as "no new matches", never padded.
- Rate limits: adapters back off / cap page counts; AI throttled to stay within Groq free limits (batch/sleep as needed).

---

## 8. Testing
- **Source adapters:** unit tests against recorded sample API/RSS payloads (fixtures) → assert normalization + graceful `[]` on malformed input. No live network in tests.
- **Dedupe & merge:** deterministic tests (new vs seen, age-out, retain-if-saved).
- **AI layer:** test the prompt contract with a stub client — assert "not stated" is preserved and no job is dropped on AI error. No real model calls in CI tests.
- **Frontend:** a smoke check that the PWA renders a fixture `jobs.json`, filters work, and localStorage save/apply persists.
- Integrity assertion in the pipeline itself: every emitted job MUST have a non-empty `url`; violation fails the run loudly.

---

## 9. Build Order (backbone first)
- **Phase 1 (backbone, usable end-to-end):** free APIs (Adzuna, Arbeitnow, Jobicy, RemoteOK, Himalayas) → normalize/dedupe → Groq AI scoring → `jobs.json` → mobile PWA on Pages → GitHub Actions cron.
- **Phase 2:** email digest.
- **Phase 3:** extra scrapers (Swiss/Nordic boards, LinkedIn/Indeed best-effort), each added as an isolated adapter behind the same schema.

---

## 10. Tech Stack
- **Language:** Python 3.11+ (pipeline), vanilla HTML/CSS/JS (PWA — no heavy framework needed for a read-only static app).
- **Libs:** `requests`/`httpx`, `feedparser` (RSS), `openai` client (works for Groq/OpenRouter/Ollama), `pyyaml`. Testing: `pytest`.
- **Infra:** GitHub Actions (cron + commit), GitHub Pages (static host). All free.
