// tests/test_filters.mjs   (run with: node --test)
import { test } from "node:test";
import assert from "node:assert";
import { filterJobs, sortByScore } from "../web/filters.js";

const jobs = [
  { id: "1", country: "CH", source: "adzuna", remote: false, score: 90, title: "SOC Analyst", company: "A" },
  { id: "2", country: "REMOTE", source: "remoteok", remote: true, score: 40, title: "Pentester", company: "B" },
  { id: "3", country: "DE", source: "arbeitnow", remote: false, score: null, title: "Baker", company: "C" },
];

test("minScore 0 keeps unscored jobs", () => {
  // regression: unscored (null) jobs must show when no threshold is set
  const r = filterJobs(jobs, { minScore: 0 });
  assert.deepEqual(r.map(j => j.id).sort(), ["1", "2", "3"]);
});

test("positive minScore excludes unscored + below", () => {
  const r = filterJobs(jobs, { minScore: 50 });
  assert.deepEqual(r.map(j => j.id), ["1"]);
});

test("country filter", () => {
  const r = filterJobs(jobs, { country: "CH" });
  assert.deepEqual(r.map(j => j.id), ["1"]);
});

test("remoteOnly + minScore", () => {
  const r = filterJobs(jobs, { remoteOnly: true, minScore: 30 });
  assert.deepEqual(r.map(j => j.id), ["2"]);
});

test("query matches title/company", () => {
  const r = filterJobs(jobs, { query: "pentest" });
  assert.deepEqual(r.map(j => j.id), ["2"]);
});

test("saved view", () => {
  const r = filterJobs(jobs, { view: "saved", savedIds: ["3"] });
  assert.deepEqual(r.map(j => j.id), ["3"]);
});

test("sort null last", () => {
  const r = sortByScore(jobs);
  assert.deepEqual(r.map(j => j.id), ["1", "2", "3"]);
});
