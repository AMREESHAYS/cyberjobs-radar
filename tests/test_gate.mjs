import { test } from "node:test";
import assert from "node:assert/strict";
import { authorize, readCookie } from "../src/index.js";

const req = (url, cookie) =>
  new Request(url, { headers: cookie ? { cookie } : {} });

test("no configured key leaves the site public", () => {
  assert.equal(authorize(req("https://x.test/"), undefined).ok, true);
});

test("a correct key in the query authorises and sets a cookie", () => {
  const v = authorize(req("https://x.test/?k=s3cret"), "s3cret");
  assert.equal(v.ok, true);
  assert.equal(v.setCookie, true);
  assert.equal(v.cleanUrl, "/");  // key is stripped from the URL
});

test("a wrong key is refused", () => {
  assert.equal(authorize(req("https://x.test/?k=nope"), "s3cret").ok, false);
  assert.equal(authorize(req("https://x.test/?k="), "s3cret").ok, false);
});

test("a valid cookie authorises without the query", () => {
  assert.equal(authorize(req("https://x.test/data/jobs.json", "cjr_key=s3cret"), "s3cret").ok, true);
});

test("no cookie and no key is refused", () => {
  assert.equal(authorize(req("https://x.test/data/jobs.json"), "s3cret").ok, false);
});

test("a wrong cookie is refused", () => {
  assert.equal(authorize(req("https://x.test/", "cjr_key=guess"), "s3cret").ok, false);
});

test("readCookie picks the right value out of several", () => {
  assert.equal(readCookie("a=1; cjr_key=abc%20def; z=9", "cjr_key"), "abc def");
  assert.equal(readCookie("", "cjr_key"), null);
});
