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

import { yearsRequired, hasFullText, isRemoteJob } from "../web/filters.js";

const job = (o = {}) => ({
  id: o.id || "x", title: "Security Analyst", company: "Acme", country: "CH",
  source: "s", score: null, description: "d", skills: [], ...o,
});

test("yearsRequired reads the lowest number the ad asks for", () => {
  assert.equal(yearsRequired(job({ experience_required: "3+ years" })), 3);
  assert.equal(yearsRequired(job({ experience_required: "2-4 years" })), 2);
  assert.equal(yearsRequired(job({ experience_required: "internship" })), 0);
  assert.equal(yearsRequired(job({ experience_required: "not stated" })), null);
  assert.equal(yearsRequired(job({})), null);
});

test("maxYears keeps ads that never state experience", () => {
  const jobs = [job({ id: "silent" }),
                job({ id: "junior", experience_required: "2 years" }),
                job({ id: "senior", experience_required: "8+ years" })];
  const ids = filterJobs(jobs, { maxYears: 3 }).map(j => j.id);
  assert.deepEqual(ids.sort(), ["junior", "silent"]);  // silence is not a rejection
});

test("sponsorshipOnly keeps only ads that say yes", () => {
  const jobs = [job({ id: "yes", visa_sponsorship: "yes" }),
                job({ id: "no", visa_sponsorship: "no" }),
                job({ id: "silent", visa_sponsorship: "not stated" })];
  assert.deepEqual(filterJobs(jobs, { sponsorshipOnly: true }).map(j => j.id), ["yes"]);
});

test("fullTextOnly hides the teaser-only postings", () => {
  const jobs = [job({ id: "full", description: "x".repeat(900) }),
                job({ id: "teaser", description: "x".repeat(400) })];
  assert.deepEqual(filterJobs(jobs, { fullTextOnly: true }).map(j => j.id), ["full"]);
});

test("internshipOnly matches title or employment type", () => {
  const jobs = [job({ id: "a", title: "Security Internship" }),
                job({ id: "b", employment_type: "Werkstudent" }),
                job({ id: "c" })];
  assert.deepEqual(filterJobs(jobs, { internshipOnly: true }).map(j => j.id).sort(), ["a", "b"]);
});

test("search covers skills and location, and descriptions only when asked", () => {
  const jobs = [job({ id: "skill", skills: ["Kubernetes"] }),
                job({ id: "city", location: "Lausanne, Switzerland" }),
                job({ id: "body", description: "we run Kubernetes clusters" })];
  assert.deepEqual(filterJobs(jobs, { query: "kubernetes" }).map(j => j.id), ["skill"]);
  assert.deepEqual(filterJobs(jobs, { query: "lausanne" }).map(j => j.id), ["city"]);
  const both = filterJobs(jobs, { query: "kubernetes", searchDescriptions: true }).map(j => j.id);
  assert.deepEqual(both.sort(), ["body", "skill"]);
});

test("isRemoteJob and hasFullText stay honest about unknowns", () => {
  assert.equal(isRemoteJob(job({ remote: "not stated" })), false);
  assert.equal(isRemoteJob(job({ remote: "not stated", country: "REMOTE" })), true);
  assert.equal(hasFullText(job({ description: "" })), false);
});

test("hasFullText trusts the flag the build sets, not the truncated preview", () => {
  // the list copy carries a 160-char preview, so length alone would lie
  assert.equal(hasFullText({ description: "x".repeat(160), full_text: true }), true);
  assert.equal(hasFullText({ description: "x".repeat(160), full_text: false }), false);
  assert.equal(hasFullText({ description: "x".repeat(900) }), true);   // no flag: fall back
});

test("fullTextOnly works off the flag once the payload is slim", () => {
  const jobs = [job({ id: "full", description: "short preview", full_text: true }),
                job({ id: "teaser", description: "short preview" })];
  assert.deepEqual(filterJobs(jobs, { fullTextOnly: true }).map(j => j.id), ["full"]);
});
