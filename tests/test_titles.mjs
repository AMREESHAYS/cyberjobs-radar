import { test } from "node:test";
import assert from "node:assert/strict";
import { cleanTitle, workloadOf, displayTitle, originalTitle } from "../web/titles.js";

test("legal gender tags are stripped in every spelling the boards use", () => {
  for (const [raw, want] of [
    ["Cybersecurity Consultant (m/w/d)", "Cybersecurity Consultant"],
    ["Security Engineer (w/m/d)", "Security Engineer"],
    ["Intern - Cybersecurity (m/f/x)", "Intern - Cybersecurity"],
    ["Security Engineer (all genders)", "Security Engineer"],
    ["Analyste (h/f)", "Analyste"],
    ["Beveiliger (m/v)", "Beveiliger"],
  ]) assert.equal(cleanTitle(raw), want, raw);
});

test("german inflections inside the word are removed, keeping the noun", () => {
  assert.equal(cleanTitle("Informatik Spezialist/-in Detection"), "Informatik Spezialist Detection");
  assert.equal(cleanTitle("Werkstudent*in Security"), "Werkstudent Security");
  assert.equal(cleanTitle("Mitarbeiter:in IT-Sicherheit"), "Mitarbeiter IT-Sicherheit");
});

test("workload is pulled out as a fact instead of cluttering the title", () => {
  assert.equal(workloadOf({ title: "Junior Cyber Engineer 80-100%" }), "80-100%");
  assert.equal(workloadOf({ title: "IT Security Officer (80% - 100%)" }), "80-100%");
  assert.equal(workloadOf({ title: "Security Analyst 60%" }), "60%");
  assert.equal(workloadOf({ title: "Security Analyst" }), "");
  assert.equal(cleanTitle("Junior Cyber Engineer 80-100%"), "Junior Cyber Engineer");
});

test("an english title is left exactly as written", () => {
  assert.equal(cleanTitle("Senior Security Operations Engineer"), "Senior Security Operations Engineer");
  assert.equal(workloadOf({ title: "Security Engineer" }), "");
});

test("the translation is shown, and the original kept for checking", () => {
  const job = { title: "Softwareentwickler (m/w/d) Security", title_en: "Security Software Developer" };
  assert.equal(displayTitle(job), "Security Software Developer");
  assert.equal(originalTitle(job), "Softwareentwickler Security");   // never hidden
});

test("without a translation the ad's own title is shown, and not duplicated", () => {
  const job = { title: "Security Engineer" };
  assert.equal(displayTitle(job), "Security Engineer");
  assert.equal(originalTitle(job), "");     // nothing to compare against
  const same = { title: "Security Engineer", title_en: "Security Engineer" };
  assert.equal(originalTitle(same), "");    // identical, so no noise
});
