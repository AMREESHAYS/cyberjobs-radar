// web/filters.js — pure filtering, exercised by tests/test_filters.mjs
export function sortByScore(jobs) {
  return [...jobs].sort((a, b) => {
    const av = a.score == null ? -1 : a.score;
    const bv = b.score == null ? -1 : b.score;
    return bv - av;
  });
}

// "3+ years" / "2-4 years" / "mindestens 5 Jahre" -> the lowest number asked for.
// Returns null when the ad never says, which must not be read as a rejection.
export function yearsRequired(job) {
  const text = (job.experience_required || "").toLowerCase();
  if (!text || text === "not stated") return null;
  // no trailing boundary: "internship" and "praktikum" must match too
  if (/\b(no experience|none|entry|intern|graduate|junior|trainee|praktik|werkstudent)/.test(text)) return 0;
  const nums = text.match(/\d+/g);
  return nums ? Math.min(...nums.map(Number)) : null;
}

export function isRemoteJob(job) {
  return job.remote === true || job.country === "REMOTE";
}

export function hasFullText(job) {
  // the list copy carries a preview, so the flag is authoritative when present
  if (typeof job.full_text === "boolean") return job.full_text;
  return (job.description || "").length > 520;
}

export function filterJobs(jobs, c = {}) {
  const q = (c.query || "").toLowerCase();
  const saved = new Set(c.savedIds || []);
  const applied = new Set(c.appliedIds || []);
  let out = jobs.filter(j => {
    if (c.country && j.country !== c.country) return false;
    if (c.source && j.source !== c.source) return false;
    if (c.remoteOnly && !isRemoteJob(j)) return false;
    // minScore 0 = no filter; a positive threshold excludes unscored + below-threshold jobs
    if (c.minScore && (j.score == null || j.score < c.minScore)) return false;
    if (c.sponsorshipOnly && j.visa_sponsorship !== "yes") return false;
    if (c.fullTextOnly && !hasFullText(j)) return false;
    if (c.internshipOnly && !/intern|praktik|werkstudent|trainee|apprentic/i
        .test(`${j.title} ${j.employment_type || ""}`)) return false;
    if (c.maxYears != null) {
      const years = yearsRequired(j);
      // an ad that never states experience stays in: silence is not a "no"
      if (years != null && years > c.maxYears) return false;
    }
    if (q) {
      const haystack = `${j.title} ${j.company} ${j.location || ""} ` +
        `${(j.skills || []).join(" ")} ${c.searchDescriptions ? j.description || "" : ""}`;
      if (!haystack.toLowerCase().includes(q)) return false;
    }
    if (c.view === "saved" && !saved.has(j.id)) return false;
    if (c.view === "applied" && !applied.has(j.id)) return false;
    return true;
  });
  return sortByScore(out);
}

if (typeof window !== "undefined") {
  window.filterJobs = filterJobs;
  window.sortByScore = sortByScore;
}
