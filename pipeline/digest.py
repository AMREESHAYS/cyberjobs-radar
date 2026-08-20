"""Phase 2: email digest of new matching jobs.

Runs after the pipeline. Selects jobs not yet emailed, renders a dark modern
HTML email, sends via Gmail SMTP. No-ops silently when credentials are absent,
so it is safe to wire into CI before secrets are set. Never fabricates: every
row links to a real posting; missing fields already carry "not stated".
"""
from __future__ import annotations
import json
import os
import smtplib
from email.mime.text import MIMEText
from .models import Job, NOT_STATED

_STATE_CAP = 1000


def load_emailed(path: str) -> set[str]:
    if not os.path.exists(path):
        return set()
    try:
        return set(json.load(open(path, encoding="utf-8")).get("emailed", []))
    except Exception:
        return set()


def save_emailed(path: str, ids: set[str]) -> None:
    kept = list(ids)[-_STATE_CAP:]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    json.dump({"emailed": kept}, open(path, "w", encoding="utf-8"))


def select(jobs: list[Job], emailed: set[str], min_score: int, cap: int) -> list[Job]:
    fresh = [j for j in jobs
             if j.id not in emailed and (j.score is None or j.score >= min_score)]
    fresh.sort(key=lambda j: (j.score is None, -(j.score or 0)))
    return fresh[:cap]


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_VISA_STYLE = {
    "yes": ("#57e2a5", "rgba(87,226,165,0.16)", "Sponsorship offered"),
    "no": ("#ff97a8", "rgba(255,111,133,0.14)", "No sponsorship"),
}

def _visa_chip(j: Job) -> str:
    colour, background, label = _VISA_STYLE.get(
        j.visa_sponsorship, ("#9aa7c7", "rgba(154,167,199,0.12)", "Sponsorship not stated"))
    return (f'<span style="display:inline-block;padding:2px 8px;border-radius:999px;'
            f'background:{background};color:{colour};font-size:11px;">{label}</span>')

def _salary_text(j: Job) -> str:
    stated = j.salary if j.salary and j.salary != NOT_STATED else ""
    inr = j.salary_inr if j.salary_inr and j.salary_inr != NOT_STATED else ""
    if not stated and not inr:
        return NOT_STATED
    return stated + (f" ({inr})" if inr else "")

def _work_mode(j: Job) -> str:
    # same rule as the web card: never infer an office from an address
    if j.remote is True or j.country == "REMOTE":
        return "Remote"
    return "On site" if j.remote is False else NOT_STATED


def render_html(jobs: list[Job]) -> str:
    # email clients drop backdrop-filter, so glass is faked with solid dark cards
    # + an aurora gradient banner (linear-gradient renders in most clients).
    rows = []
    for j in jobs:
        score = "—" if j.score is None else str(j.score)
        skills = _esc(", ".join(j.skills) if j.skills else NOT_STATED)
        facts = "".join(
            f'<td style="padding:2px 10px 2px 0;">'
            f'<div style="color:#5a6690;font-size:10px;letter-spacing:.06em;">{label}</div>'
            f'<div style="color:#d6deff;font-size:12px;">{_esc(value)}</div></td>'
            for label, value in (
                ("LOCATION", j.location or NOT_STATED),
                ("WORK MODE", _work_mode(j)),
                ("TYPE", j.employment_type or NOT_STATED),
                ("SALARY", _salary_text(j)),
            ))
        reason = "" if j.score_reason in ("AI disabled", "AI unavailable") else _esc(j.score_reason)
        rows.append(f"""
        <tr><td style="padding:0 0 14px;">
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#111935;border:1px solid #263056;border-radius:16px;">
            <tr><td style="padding:16px 18px;">
              <table width="100%"><tr>
                <td width="52" valign="top">
                  <div style="width:44px;height:44px;line-height:44px;text-align:center;border-radius:50%;
                    background:#0c1430;border:1px solid #3a5;color:#57e2a5;font-weight:700;font-size:16px;">{score}</div>
                </td>
                <td valign="top" style="padding-left:12px;">
                  <div style="color:#eaf0ff;font-size:16px;font-weight:700;">{_esc(j.title)}</div>
                  <div style="color:#9aa7c7;font-size:13px;padding:4px 0;">
                    {_esc(j.company)} · <span style="color:#8b7bff;">{_esc(j.country)}</span> · {_esc(j.source)}</div>
                  <div style="padding:2px 0 6px;">{_visa_chip(j)}</div>
                  {'<div style="color:#d6deff;font-size:13px;">' + reason + '</div>' if reason else ''}
                  <table width="100%" style="margin-top:8px;"><tr>{facts}</tr></table>
                  <div style="color:#c7d2f5;font-size:12px;padding-top:8px;">
                    <span style="color:#5a6690;">ROLE </span>{_esc(j.role_summary or NOT_STATED)}</div>
                  <div style="color:#c7d2f5;font-size:12px;padding-top:4px;">
                    <span style="color:#5a6690;">THEY EXPECT </span>{_esc(j.expectations or NOT_STATED)}</div>
                  <div style="color:#9aa7c7;font-size:12px;padding-top:8px;">Skills: {skills}</div>
                  <a href="{_esc(j.url)}" style="display:inline-block;margin-top:12px;padding:9px 16px;border-radius:999px;
                    background:linear-gradient(120deg,#4fd6e0,#8b7bff);color:#06111f;font-weight:700;
                    font-size:13px;text-decoration:none;">Open posting →</a>
                </td>
              </tr></table>
            </td></tr>
          </table>
        </td></tr>""")
    body = "".join(rows)
    return f"""<!doctype html><html><body style="margin:0;background:#070b18;padding:0;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#070b18;">
        <tr><td align="center" style="padding:24px 12px;">
          <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
            <tr><td style="padding:0 0 18px;">
              <div style="background:linear-gradient(120deg,#241a5e,#12224e);border-radius:18px;padding:22px 20px;">
                <div style="color:#eaf0ff;font-size:22px;font-weight:800;">CyberJobs Radar</div>
                <div style="color:#9aa7c7;font-size:13px;padding-top:4px;">
                  {len(jobs)} new cybersecurity {'role' if len(jobs)==1 else 'roles'} matched your profile</div>
              </div>
            </td></tr>
            {body}
            <tr><td style="padding:8px 4px 0;color:#5a6690;font-size:11px;">
              Every link goes to the real posting. Fields the ad didn't state show "not stated".</td></tr>
          </table>
        </td></tr>
      </table></body></html>"""


def send_email(html: str, subject: str, to: str, sender: str, password: str) -> None:
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(sender, password)
        s.sendmail(sender, [to], msg.as_string())


def run_digest(cfg: dict, data_path: str, state_path: str, *, send_fn=send_email) -> dict:
    sec = cfg.get("secrets", {})
    sender = sec.get("GMAIL_USER") or sec.get("DIGEST_TO")
    password = sec.get("GMAIL_APP_PASSWORD")
    to = sec.get("DIGEST_TO") or sender
    if not (sender and password and to):
        return {"sent": 0, "reason": "no credentials"}

    dcfg = cfg.get("digest", {})
    jobs = [Job.from_dict(d) for d in json.load(open(data_path, encoding="utf-8"))]
    emailed = load_emailed(state_path)
    picks = select(jobs, emailed, dcfg.get("min_score", 70), dcfg.get("cap", 25))
    if not picks:
        return {"sent": 0, "reason": "nothing new"}

    subject = f"CyberJobs Radar — {len(picks)} new match{'es' if len(picks) != 1 else ''}"
    send_fn(render_html(picks), subject, to, sender, password)
    save_emailed(state_path, emailed | {j.id for j in picks})
    return {"sent": len(picks)}


def main():
    from .config import load_config
    cfg = load_config()
    print(run_digest(cfg, "data/jobs.json", "data/digest_state.json"))


if __name__ == "__main__":
    main()
