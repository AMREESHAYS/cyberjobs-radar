// German and Austrian ads must be gender-neutral by law, so nearly every title
// carries (m/w/d) or similar, and Swiss ads state the workload as a percentage.
// Neither belongs in a headline; the workload is real information, so it is
// pulled out as its own fact rather than thrown away.
const GENDER_TAG = /[\(\[]?\s*\b(m\s*[\/|]\s*w\s*[\/|]\s*d|w\s*[\/|]\s*m\s*[\/|]\s*d|m\s*[\/|]\s*f\s*[\/|]\s*d|f\s*[\/|]\s*m\s*[\/|]\s*d|m\s*[\/|]\s*f\s*[\/|]\s*x|m\s*[\/|]\s*w\s*[\/|]\s*x|d\s*[\/|]\s*m\s*[\/|]\s*w|all genders|any gender|m\s*[\/|]\s*v|h\s*[\/|]\s*f|m\s*[\/|]\s*f)\b\s*[\)\]]?/gi;
const WORKLOAD = /(\d{2,3})\s*(?:%|Prozent)?\s*[-–]\s*(\d{2,3})\s*%|\b(\d{2,3})\s*%/;
// German also inflects inside the word itself: Spezialist/-in, Werkstudent*in,
// Mitarbeiter:in. Keep the noun, drop the inflection.
const GENDER_SUFFIX = /[\(\[]\s*(in|:in|\*in|_in)\s*[\)\]]/gi;
const GENDER_INFIX = /([A-Za-zÄÖÜäöüß])\s*[\/*:_]\s*-?\s*in\b/g;

/** "80-100%" or "60%" when the ad states a workload, else "". */
export function workloadOf(job) {
  const m = WORKLOAD.exec(`${job.title || ""} ${job.employment_type || ""}`);
  if (!m) return "";
  return m[1] && m[2] ? `${m[1]}-${m[2]}%` : `${m[3]}%`;
}

/** The title without the legal boilerplate. Never rewrites the actual words. */
export function cleanTitle(text) {
  return (text || "")
    .replace(GENDER_TAG, " ")
    .replace(GENDER_SUFFIX, " ")
    .replace(GENDER_INFIX, "$1")
    .replace(WORKLOAD, " ")
    .replace(/[\(\[]\s*[\)\]]/g, " ")     // brackets left empty by the removals
    .replace(/\s*[-–,|]\s*$/, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

/**
 * What to show as the headline: the English translation when the AI made one,
 * otherwise the ad's own title. The original is kept for the details pane, so a
 * translation never hides what the employer actually wrote.
 */
export function displayTitle(job) {
  return cleanTitle(job.title_en || job.title);
}

export function originalTitle(job) {
  const original = cleanTitle(job.title);
  return job.title_en && cleanTitle(job.title_en) !== original ? original : "";
}
