import { test } from "node:test";
import assert from "node:assert/strict";
import { levelOf, domainOf, sectionCounts, inSection, LEVELS, DOMAINS } from "../web/sections.js";

const job = (o = {}) => ({ id: "x", title: "Security Analyst", skills: [], description: "", ...o });

test("internships are their own track, not lumped in with junior roles", () => {
  for (const t of ["Cybersecurity Intern", "Werkstudent Security", "Praktikum IT-Sicherheit",
                   "Duales Studium Cybersicherheit", "Lehre als IT Systemtechniker:in",
                   "Internship - Security Operations", "Stagiair Security"]) {
    assert.equal(levelOf(job({ title: t })), "internship", t);
  }
});

test("an explicit entry marker beats everything else", () => {
  assert.equal(levelOf(job({ title: "Graduate Cyber Analyst" })), "beginner");
  assert.equal(levelOf(job({ title: "Junior SOC Analyst", experience_required: "8 years" })), "beginner");
  assert.equal(levelOf(job({ title: "Cybersecurity Intern", experience_required: "3 years" })), "internship");
});

test("stated years drive the level", () => {
  assert.equal(levelOf(job({ experience_required: "1 year" })), "beginner");
  assert.equal(levelOf(job({ experience_required: "3+ years" })), "intermediate");
  assert.equal(levelOf(job({ experience_required: "6 years" })), "advanced");
  assert.equal(levelOf(job({ experience_required: "10+ years" })), "expert");
});

test("an ad that says nothing lands in Not stated, never a guess", () => {
  assert.equal(levelOf(job({})), "unstated");
  assert.equal(levelOf(job({ title: "Cybersecurity Engineer (m/w/d)" })), "unstated");
});

test("the AI's read is used only when the ad itself is silent", () => {
  assert.equal(levelOf(job({ seniority_fit: "junior" })), "beginner");
  assert.equal(levelOf(job({ seniority_fit: "intern" })), "internship");
  assert.equal(levelOf(job({ seniority_fit: "senior", experience_required: "2 years" })), "intermediate");
});

test("specialisms win over the generic role shape", () => {
  assert.equal(domainOf(job({ title: "Penetration Tester" })), "offensive");
  assert.equal(domainOf(job({ title: "SOC Analyst" })), "soc");
  assert.equal(domainOf(job({ title: "Cloud Security Engineer" })), "cloud");
  assert.equal(domainOf(job({ title: "ISO 27001 Compliance Officer" })), "grc");
});

test("german and dutch compounds are matched, since the boards are local", () => {
  assert.equal(domainOf(job({ title: "Softwareentwickler mit Schwerpunkt Cybersecurity" })), "development");
  assert.equal(domainOf(job({ title: "IT Systemtechniker:in" })), "engineering");
  assert.equal(domainOf(job({ title: "Specialistisch Adviseur Cyber Security" })), "consulting");
  assert.equal(domainOf(job({ title: "Duales Studium Cybersicherheit" })), "apprentice");
});

test("counts cover every job exactly once, in both dimensions", () => {
  const jobs = [job({ title: "Cybersecurity Intern" }), job({ title: "SOC Analyst" }),
                job({ title: "Chef" }), job({ experience_required: "3 years" })];
  for (const [dim, defs] of [["level", LEVELS], ["domain", DOMAINS]]) {
    const counts = sectionCounts(jobs, dim);
    assert.equal(counts.reduce((a, s) => a + s.count, 0), jobs.length, dim);
    assert.equal(counts.length, defs.length, dim);
  }
});

test("inSection filters, and no section means everything", () => {
  const intern = job({ title: "Security Intern" });
  assert.equal(inSection(intern, "level", "internship"), true);
  assert.equal(inSection(intern, "level", "beginner"), false);   // its own section now
  assert.equal(inSection(intern, "level", null), true);
});
