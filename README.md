<div align="center">

<img src="web/icons/logo.svg" width="112" height="112" alt="CyberJobs Radar">

# CyberJobs Radar

**Real cybersecurity roles across Switzerland, cold Europe and remote — fetched, AI-ranked, and refreshed on a schedule.**

[![fetch](https://github.com/AMREESHAYS/cyberjobs-radar/actions/workflows/fetch.yml/badge.svg)](https://github.com/AMREESHAYS/cyberjobs-radar/actions/workflows/fetch.yml)
![python](https://img.shields.io/badge/python-3.11-4fd6e0)
![sources](https://img.shields.io/badge/sources-12-57e2a5)
![tests](https://img.shields.io/badge/tests-78%20pytest%20%2B%2021%20node-8b7bff)
![licence](https://img.shields.io/badge/licence-personal%20use-9aa7c7)

</div>

---

A personal, free, self-updating mobile PWA. It pulls postings from official employment
services and job boards, ranks each one against my profile, and serves a list where every
row links back to the real posting. Not for sale, single user.

**Integrity rule, enforced in code and tests:** every job carries a real source URL, the AI
only condenses text that was actually fetched, and any field the ad didn't state renders as
`not stated`. Nothing is invented — not a salary, not a city, not a sponsorship claim.

## What each job shows

| | |
|---|---|
| **Score** | 0-100 fit for the profile, with a one-line reason |
| **Experience** | how much the ad asks for, in its own words |
| **Must have** | the skills it lists as required, bonuses excluded |
| **Role** | what the job actually is, condensed from the posting |
| **They expect** | experience and qualifications, as stated |
| **Visa sponsorship** | `yes` / `no` only on explicit wording — silence shows "not stated", never "no" |
| **Location** | `City, Country` |
| **Work mode** | Remote / On site / not stated |
| **Salary** | the ad's own currency, then an INR conversion |
| **Type** | full time, internship, contract, as stated |

## Sources

| Region | Source | Needs a key |
|---|---|---|
| Switzerland, Germany, Austria, Benelux, Poland, France, Italy, Spain | Adzuna | `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` |
| Sweden | JobTech (Arbetsförmedlingen) | no |
| Norway | NAV | no (public token) |
| Denmark, Finland | EURES | no |
| Remote / EU | Arbeitnow, Jobicy, RemoteOK, Himalayas | no |
| Crypto & web3 | CryptoValley, CryptoJobsList | no |
| Crypto & web3 | web3.career | `WEB3CAREER_TOKEN` |

Every adapter fails soft: one dead board never takes down a run.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in whichever keys you have
set -a; source .env; set +a
./run.sh                      # fetch + serve http://localhost:8000/
./run.sh --tunnel             # same, plus a phone-reachable URL via cloudflared
```

With no keys at all you still get Sweden, Denmark, Finland, the remote boards and the crypto
boards. Adzuna keys add Switzerland and Germany onsite; without an AI key jobs are saved
unscored and the score shows `—`.

## Tests

```bash
pytest -q
node --test tests/*.mjs
```

## Configuration

Secrets go in **Settings → Secrets and variables → Actions**.

| Secret | For |
|---|---|
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Switzerland/Germany onsite roles ([free](https://developer.adzuna.com)) |
| `WEB3CAREER_TOKEN` | web3.career ([free](https://web3.career/web3-jobs-api)) |
| `NAV_TOKEN` | optional; Norway falls back to a public token |
| `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL` | any OpenAI-compatible provider |
| `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `DIGEST_TO` | the email digest ([app password](https://myaccount.google.com/apppasswords), not your login) |

Switching AI providers is just those three secrets — Groq, NVIDIA, OpenRouter, or a local
Ollama (`AI_BASE_URL=http://localhost:11434/v1`, no key). `config.yaml` holds the search
terms, target countries, age-out window and the per-run AI budget.

## How it runs

```
sources ──> prefilter ──> merge (keeps AI work, refreshes source fields)
                              │
                              ├──> AI scoring, budgeted per run
                              ├──> INR conversion from daily FX rates
                              └──> data/jobs.json ──> PWA + email digest
```

A GitHub Actions cron runs every 2 hours, commits the refreshed data, and emails new
matches. Each run restamps `data/meta.json`, which the header reads to show how fresh
the list is, and confirms delisted postings against the board before dropping them. `data/digest_state.json` remembers what was already sent, so nothing arrives twice.
Pages hosting stays dormant unless the repo variable `ENABLE_PAGES=true` is set (needs a
public repo, or private with GitHub Pro); otherwise `./run.sh --tunnel` reaches it from a phone.
