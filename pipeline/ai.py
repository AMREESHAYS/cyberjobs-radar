from __future__ import annotations
import json
import logging
from .models import Job, NOT_STATED

# bump when the prompt starts producing a field older rows do not have: run.py
# re-analyses anything below this, so existing jobs pick the new fields up
ANALYSIS_VERSION = 2

PROMPT = """You rank cybersecurity job postings for a specific candidate.

CANDIDATE PROFILE (JSON):
{profile}

JOB POSTING (only source of truth — do NOT use outside knowledge):
title: {title}
company: {company}
location: {location}
description:
{description}

Return ONLY a JSON object with these keys:
  "score": integer 0-100 (fit for THIS candidate: role match, entry-level fit,
           and visa-sponsorship / relocation / remote-from-India signals score higher),
  "score_reason": one short sentence,
  "skills": list of required skills EXPLICITLY named in the description,
  "hiring_process": how they hire IF the description states it, else exactly "not stated",
  "seniority_fit": short tag e.g. "intern", "junior", "mid", "senior",
  "role_summary": one sentence saying what the job actually is day to day,
                  drawn only from the description,
  "expectations": one or two sentences on what they expect from the candidate
                  (experience, qualifications, responsibilities) as stated,
  "visa_sponsorship": EXACTLY one of:
       "yes" - the description says sponsorship/relocation/work permit support is offered,
       "no"  - the description says it is NOT offered, or requires existing
               work authorisation / citizenship for that country,
       "not stated" - the description says nothing either way.

HARD RULES:
- Use ONLY the description text above. Never invent skills, salary, or process.
- If a field is not present in the description, output exactly "not stated"
  (for skills, an empty list). Do not guess or sugarcoat.
- visa_sponsorship is the candidate's hard filter: answer "yes" or "no" ONLY on
  explicit wording in the description. Silence means "not stated", never "no".
Output the JSON object and nothing else."""

def build_client(cfg):
    sec = cfg.get("secrets", {})
    base_url = sec.get("AI_BASE_URL") or cfg.get("ai", {}).get("base_url_default")
    model = sec.get("AI_MODEL") or cfg.get("ai", {}).get("model_default")
    # AI_API_KEY works for any OpenAI-compatible provider (NVIDIA, OpenRouter, ...);
    # GROQ_API_KEY kept as a fallback so existing Groq setups need no change.
    key = sec.get("AI_API_KEY") or sec.get("GROQ_API_KEY")
    if not base_url:
        return None, model
    is_local = "localhost" in base_url or "127.0.0.1" in base_url
    if not key and not is_local:
        return None, model  # hosted provider needs a key; degrade to AI-disabled
    try:
        from openai import OpenAI
    except ImportError:
        return None, model  # openai package not installed; degrade to AI-disabled
    # cap per-request time + retries so a slow/hung provider can't stall the run;
    # analyze() catches timeouts and keeps the job unscored ("AI unavailable")
    return OpenAI(base_url=base_url, api_key=key or "ollama",
                  timeout=45, max_retries=2), model

def _coerce(job: Job, data: dict) -> None:
    job.score = data.get("score") if isinstance(data.get("score"), int) else None
    job.score_reason = str(data.get("score_reason") or "")
    sk = data.get("skills")
    job.skills = [str(s) for s in sk] if isinstance(sk, list) else []
    job.hiring_process = str(data.get("hiring_process") or NOT_STATED) or NOT_STATED
    job.seniority_fit = str(data.get("seniority_fit") or "")
    job.role_summary = str(data.get("role_summary") or NOT_STATED) or NOT_STATED
    job.expectations = str(data.get("expectations") or NOT_STATED) or NOT_STATED
    visa = str(data.get("visa_sponsorship") or "").strip().lower()
    # anything the model improvises collapses to "not stated" rather than a claim
    job.visa_sponsorship = visa if visa in ("yes", "no") else NOT_STATED
    job.analysis_version = ANALYSIS_VERSION

def analyze(job: Job, profile: dict, client, model: str) -> None:
    if client is None:
        job.score, job.score_reason = None, "AI disabled"
        return
    prompt = PROMPT.format(profile=json.dumps(profile), title=job.title,
                           company=job.company, location=job.location,
                           description=job.description[:6000])
    try:
        resp = client.chat.completions.create(
            model=model, temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.choices[0].message.content.strip()
        # tolerate code fences
        if raw.startswith("```"):
            raw = raw.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
        data = json.loads(raw)
        _coerce(job, data)
    except Exception as e:
        # log the real cause (401 bad key vs 404/400 wrong model vs JSON parse)
        # so failures are diagnosable in CI instead of silently "AI unavailable"
        logging.getLogger("ai").warning("analyze failed for %r: %s: %s",
                                        job.title[:40], type(e).__name__, e)
        job.score, job.score_reason = None, "AI unavailable"
        job.hiring_process = NOT_STATED
        job.role_summary = job.expectations = job.visa_sponsorship = NOT_STATED
