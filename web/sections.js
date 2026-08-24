// Grouping for the browse screen. Both dimensions are derived from fields the
// jobs already carry, so nothing needs re-analysing and nothing is invented:
// a job whose ad states no level lands in "Not stated" rather than a guess.
import { yearsRequired } from "./filters.js";

export const LEVELS = [
  { id: "beginner",     label: "Beginner",     hint: "internships, graduate, junior" },
  { id: "intermediate", label: "Intermediate", hint: "roughly 2-4 years" },
  { id: "advanced",     label: "Advanced",     hint: "roughly 5-8 years" },
  { id: "expert",       label: "Expert",       hint: "9+ years, principal, lead" },
  { id: "unstated",     label: "Not stated",   hint: "the ad never says" },
];

const ENTRY_WORDS = /\b(intern|internship|praktik|werkstudent|graduate|junior|jr\.?|trainee|apprentic|entry[- ]level|einsteiger|student)\b/i;
const EXPERT_WORDS = /\b(principal|lead|head|chief|director|architect|staff|expert)\b/i;
const SENIOR_WORDS = /\b(senior|sr\.?|experienced|erfahren)\b/i;

export function levelOf(job) {
  const title = `${job.title || ""} ${job.employment_type || ""}`;
  if (ENTRY_WORDS.test(title)) return "beginner";       // an explicit marker wins
  const years = yearsRequired(job);
  if (years != null) {
    if (years <= 1) return "beginner";
    if (years <= 4) return "intermediate";
    if (years <= 8) return "advanced";
    return "expert";
  }
  if (EXPERT_WORDS.test(title)) return "expert";
  if (SENIOR_WORDS.test(title)) return "advanced";
  const fit = (job.seniority_fit || "").toLowerCase();
  if (fit.includes("intern") || fit.includes("junior")) return "beginner";
  if (fit.includes("mid")) return "intermediate";
  if (fit.includes("senior")) return "advanced";
  return "unstated";
}

// First match wins, so the narrower specialisms are listed before the broad ones.
export const DOMAINS = [
  { id: "offensive",  label: "Offensive",        hint: "pentest, red team",
    re: /\b(pentest\w*|penetration test\w*|red team\w*|offensive|ethical hack\w*|exploit\w*|bug bounty|osint)/i },
  { id: "appsec",     label: "Application",      hint: "appsec, product, secure code",
    re: /\b(appsec|application security|product security|secure cod\w*|sast|dast|software security|api security)/i },
  { id: "cloud",      label: "Cloud & DevSecOps", hint: "aws, azure, k8s, pipelines",
    re: /\b(cloud security|devsecops|kubernetes|container security|aws|azure|gcp|terraform|platform security)\b/i },
  { id: "soc",        label: "Defensive & SOC",  hint: "monitoring, detection, response",
    re: /\b(soc\b|blue team\w*|detection|siem|incident response|threat hunt\w*|csirt|monitoring|forensic\w*|dfir)/i },
  { id: "threat",     label: "Threat & Malware", hint: "intel, reverse engineering",
    re: /\b(threat intelligence|malware|reverse engineer\w*|exploit dev\w*|vulnerability research)/i },
  { id: "identity",   label: "Identity & Access", hint: "iam, pam, directory",
    re: /\b(iam|identity|access management|pam|privileged access|active directory|okta|sso)\b/i },
  { id: "network",    label: "Network",          hint: "firewall, ids, zero trust",
    re: /\b(firewall|network security|ids|ips|vpn|zero trust|nac|netzwerk)\b/i },
  { id: "grc",        label: "GRC & Compliance", hint: "risk, audit, iso, privacy",
    re: /\b(grc|compliance|iso ?27001|audit|risk|governance|privacy|gdpr|dsgvo|nis2|dora|datenschutz)\b/i },
  { id: "crypto",     label: "Crypto & Web3",    hint: "blockchain, smart contracts",
    re: /\b(blockchain|smart contract|web3|crypto|defi|wallet)\b/i },
  // Most ads are titled plainly ("Security Analyst"), so once the specialisms
  // above have had their say, the shape of the role is the useful split.
  { id: "apprentice", label: "Study & apprenticeship", hint: "duales studium, ausbildung",
    re: /(duales studium|studium|ausbildung|azubi|lehrstelle|praktik|werkstudent)|\b(apprentice|lehre|intern|internship|trainee|graduate)\b/i },
  { id: "consulting", label: "Consulting & advisory", hint: "berater, consultant",
    re: /(berater|beratung|kundenberat|adviseur)|\b(consultant|consulting|advis[oe]r|advisory|presales|customer success)\b/i },
  { id: "development", label: "Security development", hint: "developer, engineer building",
    re: /(entwickler|entwicklung|programmier)|\b(developer|software engineer|full ?stack|backend|frontend)\b/i },
  { id: "analysis",   label: "Analysis",            hint: "analyst roles",
    re: /(analytiker|analyse|wissenschaftlich)|\b(analyst|research|researcher|scientist)\b/i },
  { id: "engineering", label: "Security engineering", hint: "engineer, administrator, ops",
    re: /(ingenieur|techniker|informatiker|spezialist|mitarbeiter|architekt|betreuer|sicherheitsberat)|\b(engineer|administrator|specialist|specialistisch|operations|officer|associate|experte|expert|manager|leader|leitung|systems?|support|sysadmin)\b/i },
  { id: "general",    label: "Everything else",     hint: "no clear focus stated",  re: null },
];

export function domainOf(job) {
  const text = `${job.title || ""} ${(job.skills || []).join(" ")} ` +
    `${job.role_summary || ""} ${job.description || ""}`;
  for (const d of DOMAINS) {
    if (d.re && d.re.test(text)) return d.id;
  }
  return "general";
}

/** [{...section, count}] for one dimension, keeping the declared order. */
export function sectionCounts(jobs, dimension) {
  const defs = dimension === "level" ? LEVELS : DOMAINS;
  const pick = dimension === "level" ? levelOf : domainOf;
  const counts = new Map();
  for (const j of jobs) counts.set(pick(j), (counts.get(pick(j)) || 0) + 1);
  return defs.map(d => ({ ...d, count: counts.get(d.id) || 0 }));
}

export function inSection(job, dimension, id) {
  if (!id) return true;
  return (dimension === "level" ? levelOf(job) : domainOf(job)) === id;
}
