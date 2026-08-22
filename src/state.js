// Saved / applied / notes, shared between devices.
//
// Two devices edit the same list offline, so this cannot be last-writer-wins on
// the whole document — unsaving a job on the phone must not be undone by the
// laptop pushing an older copy. Every entry carries the time it changed and the
// newer one wins, per job.
export const EMPTY = { saved: {}, applied: {}, notes: {}, updated_at: 0 };

function newerOf(a, b) {
  if (!a) return b;
  if (!b) return a;
  return (b.ts || 0) > (a.ts || 0) ? b : a;
}

function mergeSection(mine = {}, theirs = {}) {
  const out = {};
  for (const id of new Set([...Object.keys(mine), ...Object.keys(theirs)])) {
    out[id] = newerOf(mine[id], theirs[id]);
  }
  return out;
}

export function mergeState(mine = EMPTY, theirs = EMPTY) {
  return {
    saved: mergeSection(mine.saved, theirs.saved),
    applied: mergeSection(mine.applied, theirs.applied),
    notes: mergeSection(mine.notes, theirs.notes),
    updated_at: Math.max(mine.updated_at || 0, theirs.updated_at || 0),
  };
}

/** Ids currently switched on, i.e. whose latest change was "on". */
export function activeIds(section = {}) {
  return Object.entries(section).filter(([, v]) => v && v.on).map(([id]) => id);
}

export function isValidState(value) {
  return !!value && typeof value === "object" && !Array.isArray(value) &&
    ["saved", "applied", "notes"].every(k => !(k in value) ||
      (typeof value[k] === "object" && value[k] !== null && !Array.isArray(value[k])));
}
