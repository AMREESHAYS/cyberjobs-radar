import { filterJobs } from "./filters.js";

const LS = { saved: "cjr_saved", applied: "cjr_applied" };
const getSet = k => new Set(JSON.parse(localStorage.getItem(k) || "[]"));
const putSet = (k, s) => localStorage.setItem(k, JSON.stringify([...s]));
// rows stored before the pipeline started stripping tags still hold raw HTML
const plain = s => (s || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
const esc = s => (s || "").replace(/[&<>"]/g, m => ({ "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;" }[m]));

let JOBS = [];
const state = { view: "all", country: "", source: "", remoteOnly: false, minScore: 0, query: "" };

let loadFailed = false;
let META = null;

// "3 minutes ago" beats a raw timestamp for the question actually being asked:
// is what I am looking at current?
function since(iso) {
  const then = Date.parse(iso);
  if (!then) return "";
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

function showFreshness() {
  const el = document.getElementById("freshness");
  if (!el) return;
  if (!META || !META.generated_at) { el.textContent = ""; return; }
  const when = new Date(META.generated_at);
  const bits = [`Updated ${since(META.generated_at)}`];
  if (META.new) bits.push(`${META.new} new`);
  if (META.removed) bits.push(`${META.removed} closed`);
  el.textContent = bits.join(" · ");
  el.title = when.toLocaleString();  // exact date and time on hover/long-press
}

async function boot() {
  // behind Cloudflare Access an expired session answers with the sign-in page,
  // so a parse failure here means "sign in again", not "no jobs"
  const bust = "?" + Date.now();
  [JOBS, META] = await Promise.all([
    fetch("data/jobs.json" + bust).then(r => r.json()).catch(() => { loadFailed = true; return []; }),
    fetch("data/meta.json" + bust).then(r => r.json()).catch(() => null),
  ]);
  showFreshness();
  fillSelect("country", [...new Set(JOBS.map(j => j.country))].sort());
  fillSelect("source", [...new Set(JOBS.map(j => j.source))].sort());
  wire();
  render();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
}

function fillSelect(id, values) {
  const el = document.getElementById(id);
  for (const v of values) { const o = document.createElement("option"); o.value = v; o.textContent = v; el.appendChild(o); }
}

function wire() {
  document.getElementById("q").addEventListener("input", e => { state.query = e.target.value; render(); });
  document.getElementById("country").addEventListener("change", e => { state.country = e.target.value; render(); });
  document.getElementById("source").addEventListener("change", e => { state.source = e.target.value; render(); });
  document.getElementById("remoteOnly").addEventListener("change", e => { state.remoteOnly = e.target.checked; render(); });
  document.getElementById("minScore").addEventListener("input", e => {
    state.minScore = +e.target.value;
    document.getElementById("minScoreVal").textContent = e.target.value;
    render();
  });
  document.querySelectorAll("#tabs button").forEach(b =>
    b.addEventListener("click", () => {
      document.querySelectorAll("#tabs button").forEach(x => x.classList.remove("active"));
      b.classList.add("active"); state.view = b.dataset.view; render();
    }));
}

function render() {
  const saved = getSet(LS.saved), applied = getSet(LS.applied);
  const rows = filterJobs(JOBS, { ...state, savedIds: [...saved], appliedIds: [...applied] });
  document.getElementById("count").textContent =
    JOBS.length ? `${rows.length} of ${JOBS.length} roles`
                : loadFailed ? "Could not load jobs" : "No jobs yet — run the pipeline";
  const list = document.getElementById("list");
  list.innerHTML = rows.length ? ""
    : loadFailed
      ? "<p class='empty'>Could not load the job list. If the session expired, <a href='./'>reload to sign in</a>.</p>"
      : "<p class='empty'>Nothing matches these filters yet. Loosen them or check back after the next refresh.</p>";
  for (const j of rows) list.appendChild(card(j, saved, applied));
}

// only claim "Remote" when a source actually said so — everything else keeps
// showing the stated location rather than asserting an office
const isRemote = j => j.remote === true || j.country === "REMOTE";
const workMode = j => isRemote(j) ? "Remote" : (j.remote === false ? "On site" : "not stated");
// sponsorship decides whether the job is reachable at all, so it is always shown
const VISA = { yes: ["visa yes", "Sponsorship offered"], no: ["visa no", "No sponsorship"] };
const visaChip = j => {
  const [cls, label] = VISA[j.visa_sponsorship] || ["visa unknown", "Sponsorship not stated"];
  return `<span class="${cls}">${label}</span>`;
};
const salaryText = j => {
  const stated = j.salary && j.salary !== "not stated" ? j.salary : "";
  const inr = j.salary_inr && j.salary_inr !== "not stated" ? j.salary_inr : "";
  if (!stated && !inr) return "not stated";
  return stated + (inr ? ` (${inr})` : "");
};

function card(j, saved, applied) {
  const el = document.createElement("article");
  el.className = "card";
  const hasScore = j.score != null;
  el.innerHTML = `
    <div class="top">
      <span class="score ${hasScore ? "" : "na"}">${hasScore ? j.score : "—"}</span>
      <h2>${esc(j.title)}</h2>
    </div>
    <p class="co">
      ${esc(j.company)}
      <span class="badge">${esc(j.country)}</span>
      <span class="src ${j.source_type}">${esc(j.source)}</span>
      ${j.remote === true ? '<span class="badge">remote</span>' : ""}
      ${visaChip(j)}
    </p>
    <ul class="facts">
      <li><span>Location</span>${esc(j.location && j.location !== "not stated" ? j.location : "not stated")}</li>
      <li><span>Work mode</span>${workMode(j)}</li>
      <li><span>Type</span>${esc(j.employment_type || "not stated")}</li>
      <li><span>Salary</span>${esc(salaryText(j))}</li>
      <li><span>Experience</span>${esc(j.experience_required || "not stated")}</li>
    </ul>
    <p class="role"><span>Must have</span>${esc((j.skills || []).join(" · ") || "not stated")}</p>
    <p class="role"><span>Role</span>${esc(j.role_summary || "not stated")}</p>
    <p class="role"><span>They expect</span>${esc(j.expectations || "not stated")}</p>
    <p class="reason">${esc(/^(AI disabled|AI unavailable)$/.test(j.score_reason || "") ? "" : j.score_reason)}</p>
    <details>
      <summary>Details</summary>
      <p><strong>Hiring:</strong> ${esc(j.hiring_process || "not stated")}</p>
      <p><strong>Last listed:</strong> ${esc(j.last_seen || j.first_seen || "not stated")}</p>
      <p class="desc">${esc(plain(j.description).slice(0, 600))}</p>
    </details>
    <div class="actions">
      <a class="apply" href="${esc(j.url)}" target="_blank" rel="noopener">Open posting ↗</a>
      <button class="save ${saved.has(j.id) ? "on" : ""}">${saved.has(j.id) ? "★ Saved" : "☆ Save"}</button>
      <button class="applied ${applied.has(j.id) ? "on" : ""}">${applied.has(j.id) ? "✓ Applied" : "Applied?"}</button>
    </div>`;
  el.querySelector(".save").addEventListener("click", () => toggle(LS.saved, j.id));
  el.querySelector(".applied").addEventListener("click", () => toggle(LS.applied, j.id));
  return el;
}

function toggle(key, id) {
  const s = getSet(key); s.has(id) ? s.delete(id) : s.add(id); putSet(key, s); render();
}

boot();
