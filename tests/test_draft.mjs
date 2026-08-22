import { test } from "node:test";
import assert from "node:assert/strict";
import { buildPrompt, parseDraft, isUsable, DRAFT_SYSTEM } from "../src/draft.js";
import worker from "../src/index.js";

const KEY = "k";
const authed = (path, init = {}) => new Request("https://x.test" + path,
  { ...init, headers: { cookie: `cjr_key=${KEY}`, ...(init.headers || {}) } });

const JOB = { id: "j1", title: "SOC Analyst", company: "Acme", location: "Zurich",
              description: "Watch alerts. 3+ years of SIEM.", skills: ["SIEM"] };

function env({ reply, key = "ai-key" } = {}) {
  const store = new Map();
  const calls = { n: 0 };
  return {
    SITE_KEY: KEY, AI_API_KEY: key, AI_MODEL: "m",
    STATE: { get: async k => JSON.parse(store.get(k) || "null"),
             put: async (k, v) => void store.set(k, v) },
    ASSETS: { fetch: async () => new Response(JSON.stringify({ experience: "student" })) },
    // each test injects its own AI response; no shared global to leak between tests
    FETCH: async () => { calls.n++; return reply ? reply() : new Response("{}"); },
    calls,
  };
}

const aiSays = content => () =>
  new Response(JSON.stringify({ choices: [{ message: { content } }] }));

const GOOD = JSON.stringify({
  gaps: ["3 years of SIEM"], strengths: ["home lab"], cv_bullets: ["Ran a home SOC"],
  cover_letter: "Dear team, I am applying...", honest_note: "You are short on SIEM years.",
});

test("the prompt forbids inventing anything and demands the gaps", () => {
  assert.match(DRAFT_SYSTEM, /Never invent/);
  const p = buildPrompt({ experience: "student" }, JOB);
  assert.match(p, /that is a gap|"gaps"/);
  assert.match(p, /SOC Analyst/);
  assert.match(p, /3\+ years of SIEM/);
});

test("the ad is truncated so one long posting cannot blow the request", () => {
  const p = buildPrompt({}, { title: "t", description: "x".repeat(9000) });
  assert.ok(p.includes("x".repeat(4000)) && !p.includes("x".repeat(4001)));
});

test("parseDraft survives code fences and drops junk fields", () => {
  const d = parseDraft("```json\n" + GOOD + "\n```");
  assert.deepEqual(d.gaps, ["3 years of SIEM"]);
  assert.equal(d.cover_letter, "Dear team, I am applying...");
  assert.equal(isUsable(d), true);
  assert.equal(isUsable(parseDraft('{"gaps":[]}')), false);   // nothing to show
});

test("a draft is generated, then served from cache without calling the model again", async () => {
  const e = env({ reply: aiSays(GOOD) });
  const first = await worker.fetch(authed("/api/draft", { method: "POST", body: JSON.stringify(JOB) }), e);
  const a = await first.json();
  assert.equal(a.cached, false);
  assert.deepEqual(a.gaps, ["3 years of SIEM"]);
  const second = await worker.fetch(authed("/api/draft", { method: "POST", body: JSON.stringify(JOB) }), e);
  assert.equal((await second.json()).cached, true);
  assert.equal(e.calls.n, 1);                   // the second open costs no tokens
});

test("drafting needs the key, like everything else", async () => {
  const res = await worker.fetch(new Request("https://x.test/api/draft", { method: "POST", body: "{}" }), env({}));
  assert.equal(res.status, 401);
});

test("a provider failure is reported, not silently swallowed", async () => {
  const e = env({ reply: () => new Response("rate limited", { status: 429 }) });
  const res = await worker.fetch(authed("/api/draft",
    { method: "POST", body: JSON.stringify({ ...JOB, id: "j-429" }) }), e);
  assert.equal(res.status, 502);
  assert.match((await res.json()).error, /429/);
});

test("a model that returns prose instead of json is reported", async () => {
  const e = env({ reply: aiSays("sure! here you go") });
  const res = await worker.fetch(authed("/api/draft",
    { method: "POST", body: JSON.stringify({ ...JOB, id: "j-prose" }) }), e);
  assert.equal(res.status, 502);
});

test("without an AI key the endpoint says so instead of pretending", async () => {
  const e = env({ key: "" });
  const res = await worker.fetch(authed("/api/draft", { method: "POST", body: JSON.stringify(JOB) }), e);
  assert.equal(res.status, 501);
});

test("a request without a job is rejected before any model call", async () => {
  const e = env({ reply: aiSays(GOOD) });
  const res = await worker.fetch(authed("/api/draft", { method: "POST", body: "{}" }), e);
  assert.equal(res.status, 400);
  assert.equal(e.calls.n, 0);                   // rejected before any model call
});
