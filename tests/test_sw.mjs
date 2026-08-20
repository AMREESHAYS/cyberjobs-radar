import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// run sw.js in a stubbed worker global so the caching rule can be exercised
function loadSW() {
  const self = { addEventListener() {} };
  const src = readFileSync(new URL("../web/sw.js", import.meta.url), "utf8");
  new Function("self", "caches", "fetch", src)(self, { open() {} }, () => {});
  return self.shouldCache;
}

const res = (over = {}) => ({
  ok: true, redirected: false, type: "basic",
  headers: { get: () => over.contentType ?? "application/json" }, ...over,
});

test("caches a normal json response", () => {
  assert.equal(loadSW()({ url: "/data/jobs.json" }, res()), true);
});

test("refuses a redirected response (Access sign-in bounce)", () => {
  assert.equal(loadSW()({ url: "/data/jobs.json" }, res({ redirected: true })), false);
});

test("refuses html served in place of json", () => {
  assert.equal(loadSW()({ url: "/data/jobs.json" }, res({ contentType: "text/html" })), false);
});

test("refuses opaque and failed responses", () => {
  const shouldCache = loadSW();
  assert.equal(shouldCache({ url: "/x.json" }, res({ type: "opaque" })), false);
  assert.equal(shouldCache({ url: "/x.json" }, res({ ok: false })), false);
  assert.equal(shouldCache({ url: "/x.json" }, null), false);
});

test("still caches html for the page itself", () => {
  assert.equal(loadSW()({ url: "/index.html" }, res({ contentType: "text/html" })), true);
});
