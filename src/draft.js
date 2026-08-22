// Application materials for one job: where you fall short, CV bullets, and a
// cover letter. The integrity rule that governs the rest of the app applies
// hardest here — this text goes out under the candidate's name, so the model
// may only use facts from the profile, and gaps must be named, not papered over.
export const DRAFT_SYSTEM = [
  "You help a specific candidate apply for one specific job.",
  "You may use ONLY facts stated in the CANDIDATE PROFILE and the JOB AD below.",
  "Never invent experience, employers, degrees, certifications, tools or years.",
  "If the ad asks for something the profile does not show, that is a gap: say so plainly.",
  "The cover letter must not claim any skill the profile does not state.",
].join(" ");

export function buildPrompt(profile, job) {
  const ad = [
    `title: ${job.title || ""}`,
    `company: ${job.company || ""}`,
    `location: ${job.location || ""}`,
    job.experience_required && job.experience_required !== "not stated"
      ? `experience asked for: ${job.experience_required}` : "",
    job.skills && job.skills.length ? `skills listed: ${job.skills.join(", ")}` : "",
    `description:\n${(job.description || "").slice(0, 4000)}`,
  ].filter(Boolean).join("\n");

  return [
    "CANDIDATE PROFILE (JSON):",
    JSON.stringify(profile),
    "",
    "JOB AD (the only source of truth about the role):",
    ad,
    "",
    "Return ONLY a JSON object with these keys:",
    '  "gaps": list of short strings — what the ad asks for that the profile does not',
    "          show. Empty list only if there is genuinely nothing missing.",
    '  "strengths": list of short strings — profile facts that genuinely match the ad.',
    '  "cv_bullets": 3-5 CV bullet strings, each rewritten to match this ad using only',
    "          profile facts. No metrics that are not in the profile.",
    '  "cover_letter": a short letter, 150-200 words, plain text, no placeholders like',
    '          "[Your Name]" beyond the sign-off, honest about the gaps.',
    '  "honest_note": one sentence naming the biggest reason this application might be',
    "          rejected, so the candidate decides with open eyes.",
    "Output the JSON object and nothing else.",
  ].join("\n");
}

export function parseDraft(raw) {
  let text = (raw || "").trim();
  if (text.startsWith("```")) {
    text = text.replace(/^```[a-z]*\n?/i, "").replace(/```$/, "").trim();
  }
  const data = JSON.parse(text);
  const list = v => (Array.isArray(v) ? v.map(String).filter(Boolean) : []);
  return {
    gaps: list(data.gaps),
    strengths: list(data.strengths),
    cv_bullets: list(data.cv_bullets),
    cover_letter: typeof data.cover_letter === "string" ? data.cover_letter.trim() : "",
    honest_note: typeof data.honest_note === "string" ? data.honest_note.trim() : "",
  };
}

export function isUsable(draft) {
  return !!draft && (draft.cv_bullets.length > 0 || draft.cover_letter.length > 0);
}
