// Gate in front of the static site. Cloudflare Access would be the nicer
// answer, but it needs Zero Trust enabled on the account; this needs nothing
// beyond a Worker secret, and keeps the job list off the open internet.
import { EMPTY, isValidState, mergeState } from "./state.js";
import { DRAFT_SYSTEM, buildPrompt, isUsable, parseDraft } from "./draft.js";

const COOKIE = "cjr_key";
const STATE_KEY = "tracking";
const MAX_STATE_BYTES = 256 * 1024;   // KV's own limit is 25 MB; this is a sane list
const YEAR = 60 * 60 * 24 * 365;

// constant-time-ish compare: same cost whatever the mismatch, so the response
// timing does not leak how much of the key was right
function sameKey(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export function readCookie(header, name) {
  for (const part of (header || "").split(";")) {
    const [k, ...v] = part.trim().split("=");
    if (k === name) return decodeURIComponent(v.join("="));
  }
  return null;
}

// Chrome fetches the manifest and the icons without credentials while deciding
// whether a site is installable, so gating those breaks "Install app". They
// carry no private data — the job list lives in /data.
const PUBLIC = [/^\/manifest\.webmanifest$/, /^\/icons\//, /^\/favicon\.ico$/];

export function isPublicPath(pathname) {
  return PUBLIC.some(rx => rx.test(pathname));
}

export function authorize(request, key) {
  if (!key) return { ok: true, reason: "no key configured — site is public" };
  const url = new URL(request.url);
  if (isPublicPath(url.pathname)) return { ok: true, reason: "installability asset" };
  const supplied = url.searchParams.get("k");
  if (supplied !== null) {
    return sameKey(supplied, key)
      ? { ok: true, setCookie: true, cleanUrl: url.pathname }
      : { ok: false };
  }
  return { ok: sameKey(readCookie(request.headers.get("cookie"), COOKIE), key) };
}

const LOCKED = `<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CyberJobs Radar</title>
<style>
 body{margin:0;min-height:100vh;display:grid;place-items:center;background:#070b18;
      color:#eaf0ff;font:16px/1.5 ui-sans-serif,system-ui,sans-serif}
 .box{background:#111935;border:1px solid #263056;border-radius:18px;padding:28px;max-width:320px}
 h1{font-size:18px;margin:0 0 6px} p{color:#9aa7c7;font-size:13px;margin:0 0 16px}
 input{width:100%;padding:11px 13px;border-radius:11px;border:1px solid #263056;
       background:#0b1226;color:#eaf0ff;font-size:15px;box-sizing:border-box}
 button{width:100%;margin-top:10px;padding:11px;border:0;border-radius:999px;font-weight:700;
        background:linear-gradient(120deg,#4fd6e0,#8b7bff);color:#06111f;font-size:15px}
</style>
<div class="box"><h1>CyberJobs Radar</h1><p>This list is private. Enter the access key.</p>
<form method="GET"><input name="k" type="password" autofocus placeholder="Access key"
 autocomplete="current-password"><button type="submit">Open</button></form></div>`;

async function readState(env) {
  if (!env.STATE) return EMPTY;
  const stored = await env.STATE.get(STATE_KEY, "json");
  return isValidState(stored) ? { ...EMPTY, ...stored } : EMPTY;
}

async function handleState(request, env) {
  const json = (body, status = 200) =>
    new Response(JSON.stringify(body), {
      status, headers: { "content-type": "application/json", "cache-control": "no-store" },
    });

  if (!env.STATE) return json({ error: "state storage not configured" }, 501);

  if (request.method === "GET") {
    return json(await readState(env));
  }
  if (request.method === "PUT") {
    const raw = await request.text();
    if (raw.length > MAX_STATE_BYTES) return json({ error: "state too large" }, 413);
    let incoming;
    try {
      incoming = JSON.parse(raw);
    } catch {
      return json({ error: "invalid json" }, 400);
    }
    if (!isValidState(incoming)) return json({ error: "invalid state" }, 400);
    // merge rather than overwrite, so a stale device cannot erase the other one
    const merged = mergeState(await readState(env), incoming);
    await env.STATE.put(STATE_KEY, JSON.stringify(merged));
    return json(merged);
  }
  return json({ error: "method not allowed" }, 405);
}

// Materials are generated on demand, not for all 600+ jobs: the free tier has a
// daily token budget, and a draft is only wanted for jobs actually being applied
// to. Once made, it is cached so re-opening a job costs nothing.
async function handleDraft(request, env) {
  const json = (body, status = 200) =>
    new Response(JSON.stringify(body), {
      status, headers: { "content-type": "application/json", "cache-control": "no-store" },
    });
  if (request.method !== "POST") return json({ error: "method not allowed" }, 405);
  if (!env.AI_API_KEY) return json({ error: "AI_API_KEY is not set on the Worker" }, 501);

  let job;
  try {
    job = await request.json();
  } catch {
    return json({ error: "invalid json" }, 400);
  }
  if (!job || !job.id || !job.title) return json({ error: "job id and title required" }, 400);

  const cached = !job.refresh && await readDraft(env, job.id);
  if (cached) return json({ ...cached, cached: true });

  const profile = await readProfile(env);
  // the client only holds a truncated preview; draft from the whole ad
  const full = await readFullJob(env, job.id);
  if (full && (full.description || "").length > (job.description || "").length) {
    job = { ...job, description: full.description, skills: full.skills || job.skills };
  }
  const base = (env.AI_BASE_URL || "https://api.groq.com/openai/v1").replace(/\/$/, "");
  // injectable so tests can stub one call without touching a shared global
  const callAI = env.FETCH || fetch;
  let response;
  try {
    response = await callAI(base + "/chat/completions", {
      method: "POST",
      headers: { "content-type": "application/json", authorization: `Bearer ${env.AI_API_KEY}` },
      body: JSON.stringify({
        model: env.AI_MODEL || "openai/gpt-oss-120b",
        temperature: 0.3,
        messages: [
          { role: "system", content: DRAFT_SYSTEM },
          { role: "user", content: buildPrompt(profile, job) },
        ],
      }),
    });
  } catch (e) {
    return json({ error: "could not reach the AI provider" }, 502);
  }
  if (!response.ok) {
    const detail = (await response.text()).slice(0, 300);
    return json({ error: `AI provider said ${response.status}`, detail }, 502);
  }
  let draft;
  try {
    const body = await response.json();
    draft = parseDraft(body.choices?.[0]?.message?.content || "");
  } catch {
    return json({ error: "the model did not return usable JSON" }, 502);
  }
  if (!isUsable(draft)) return json({ error: "the model returned an empty draft" }, 502);

  await writeDraft(env, job.id, draft);
  return json({ ...draft, cached: false });
}

async function readFullJob(env, jobId) {
  try {
    const res = await env.ASSETS.fetch(new Request("https://internal/data/jobs.full.json"));
    if (!res.ok) return null;
    const jobs = await res.json();
    return jobs.find(j => j.id === jobId) || null;
  } catch {
    return null;   // fall back to whatever the client sent
  }
}

async function readProfile(env) {
  try {
    const res = await env.ASSETS.fetch(new Request("https://internal/data/profile.json"));
    return res.ok ? await res.json() : {};
  } catch {
    return {};
  }
}

async function readDraft(env, jobId) {
  if (!env.STATE) return null;
  const state = await readState(env);
  const entry = (state.drafts || {})[jobId];
  return entry && entry.draft ? entry.draft : null;
}

async function writeDraft(env, jobId, draft) {
  if (!env.STATE) return;
  const state = await readState(env);
  state.drafts = { ...(state.drafts || {}), [jobId]: { draft, ts: Date.now() } };
  await env.STATE.put(STATE_KEY, JSON.stringify(state));
}

export default {
  async fetch(request, env) {
    const verdict = authorize(request, env.SITE_KEY);
    if (!verdict.ok) {
      return new Response(LOCKED, {
        status: 401,
        headers: { "content-type": "text/html;charset=utf-8", "cache-control": "no-store" },
      });
    }
    const url = new URL(request.url);
    if (url.pathname === "/api/state") {
      return handleState(request, env);
    }
    if (url.pathname === "/api/draft") {
      return handleDraft(request, env);
    }
    if (verdict.setCookie) {
      // drop the key out of the URL so it stops appearing in history and referrers
      return new Response(null, {
        status: 302,
        headers: {
          location: verdict.cleanUrl,
          "set-cookie": `${COOKIE}=${encodeURIComponent(env.SITE_KEY)}; Max-Age=${YEAR}; Path=/; Secure; HttpOnly; SameSite=Lax`,
          "cache-control": "no-store",
        },
      });
    }
    return env.ASSETS.fetch(request);
  },
};
