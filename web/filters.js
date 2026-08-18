// web/filters.js
export function sortByScore(jobs) {
  return [...jobs].sort((a, b) => {
    const av = a.score == null ? -1 : a.score;
    const bv = b.score == null ? -1 : b.score;
    return bv - av;
  });
}

export function filterJobs(jobs, c = {}) {
  const q = (c.query || "").toLowerCase();
  const saved = new Set(c.savedIds || []);
  const applied = new Set(c.appliedIds || []);
  let out = jobs.filter(j => {
    if (c.country && j.country !== c.country) return false;
    if (c.source && j.source !== c.source) return false;
    if (c.remoteOnly && !(j.remote === true || j.country === "REMOTE")) return false;
    // minScore 0 = no filter; a positive threshold excludes unscored + below-threshold jobs
    if (c.minScore && (j.score == null || j.score < c.minScore)) return false;
    if (q && !`${j.title} ${j.company}`.toLowerCase().includes(q)) return false;
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
