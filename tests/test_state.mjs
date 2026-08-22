import { test } from "node:test";
import assert from "node:assert/strict";
import { mergeState, activeIds, isValidState, EMPTY } from "../src/state.js";
import worker from "../src/index.js";

const KEY = "k";
const authed = (path, init = {}) =>
  new Request("https://x.test" + path, { ...init, headers: { cookie: `cjr_key=${KEY}`, ...(init.headers || {}) } });

function fakeEnv() {
  const store = new Map();
  return { SITE_KEY: KEY, STATE: {
    get: async k => JSON.parse(store.get(k) || "null"),
    put: async (k, v) => void store.set(k, v),
  } };
}

test("a newer change wins per job, in both directions", () => {
  const phone = { saved: { a: { on: true, ts: 200 } } };
  const laptop = { saved: { a: { on: false, ts: 100 }, b: { on: true, ts: 150 } } };
  const merged = mergeState(laptop, phone);
  assert.equal(merged.saved.a.on, true);            // the stale unsave loses
  assert.deepEqual(activeIds(merged.saved).sort(), ["a", "b"]);

  const later = mergeState(phone, { saved: { a: { on: false, ts: 300 } } });
  assert.deepEqual(activeIds(later.saved), []);     // a genuine later unsave wins
});

test("merging never drops a device's own entries", () => {
  const merged = mergeState({ applied: { x: { on: true, ts: 1 } } },
                            { applied: { y: { on: true, ts: 2 } } });
  assert.deepEqual(activeIds(merged.applied).sort(), ["x", "y"]);
});

test("isValidState rejects shapes that would corrupt the store", () => {
  assert.equal(isValidState({ saved: {} }), true);
  assert.equal(isValidState(EMPTY), true);
  for (const bad of [null, "text", 42, [], { saved: [] }, { notes: "x" }]) {
    assert.equal(isValidState(bad), false, JSON.stringify(bad));
  }
});

test("the api round-trips and merges instead of overwriting", async () => {
  const env = fakeEnv();
  await worker.fetch(authed("/api/state", { method: "PUT", body: JSON.stringify({ saved: { a: { on: true, ts: 1 } } }) }), env);
  await worker.fetch(authed("/api/state", { method: "PUT", body: JSON.stringify({ saved: { b: { on: true, ts: 2 } } }) }), env);
  const res = await worker.fetch(authed("/api/state"), env);
  const body = await res.json();
  assert.deepEqual(activeIds(body.saved).sort(), ["a", "b"]);  // second push kept the first
});

test("the api refuses junk and oversized payloads", async () => {
  const env = fakeEnv();
  assert.equal((await worker.fetch(authed("/api/state", { method: "PUT", body: "not json" }), env)).status, 400);
  assert.equal((await worker.fetch(authed("/api/state", { method: "PUT", body: '["nope"]' }), env)).status, 400);
  assert.equal((await worker.fetch(authed("/api/state", { method: "PUT", body: "x".repeat(300000) }), env)).status, 413);
  assert.equal((await worker.fetch(authed("/api/state", { method: "DELETE" }), env)).status, 405);
});

test("tracking data needs the key, like everything else", async () => {
  const env = fakeEnv();
  const res = await worker.fetch(new Request("https://x.test/api/state"), env);
  assert.equal(res.status, 401);
});

test("without a KV binding the api says so rather than failing silently", async () => {
  const res = await worker.fetch(authed("/api/state"), { SITE_KEY: KEY });
  assert.equal(res.status, 501);
});
