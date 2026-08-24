import { filterJobs } from "./filters.js";
import { LEVELS, DOMAINS, sectionCounts, inSection } from "./sections.js";

const LS = { saved: "cjr_saved", applied: "cjr_applied", tracking: "cjr_tracking" };

// Saved/applied live in one document that syncs to the Worker, so a phone and a
// laptop agree. Each entry records when it changed; the newer change wins.
let TRACKING = { saved: {}, applied: {}, notes: {}, updated_at: 0 };
let syncTimer = null;

function loadTracking() {
  try {
    const doc = JSON.parse(localStorage.getItem(LS.tracking) || "null");
    if (doc && typeof doc === "object") return { saved: {}, applied: {}, notes: {}, ...doc };
  } catch { /* fall through to the pre-sync format */ }
  // migrate the original id-array format so nothing saved before this is lost
  const doc = { saved: {}, applied: {}, notes: {}, updated_at: 0 };
  for (const key of ["saved", "applied"]) {
    try {
      for (const id of JSON.parse(localStorage.getItem(LS[key]) || "[]")) {
        doc[key][id] = { on: true, ts: 1 };   // ts 1: any later change wins
      }
    } catch { /* nothing stored */ }
  }
  return doc;
}

function saveTracking() {
  localStorage.setItem(LS.tracking, JSON.stringify(TRACKING));
}

function activeIds(section) {
  return new Set(Object.entries(section || {}).filter(([, v]) => v && v.on).map(([id]) => id));
}

function mergeInto(mine, theirs) {
  const pick = (a, b) => (!a ? b : !b ? a : ((b.ts || 0) > (a.ts || 0) ? b : a));
  const out = { saved: {}, applied: {}, notes: {},
                updated_at: Math.max(mine.updated_at || 0, theirs.updated_at || 0) };
  for (const key of ["saved", "applied", "notes"]) {
    for (const id of new Set([...Object.keys(mine[key] || {}), ...Object.keys(theirs[key] || {})])) {
      out[key][id] = pick((mine[key] || {})[id], (theirs[key] || {})[id]);
    }
  }
  return out;
}

async function pullTracking() {
  try {
    const remote = await fetch("api/state", { headers: { accept: "application/json" } })
      .then(r => (r.ok ? r.json() : null));
    if (remote) {
      TRACKING = mergeInto(TRACKING, remote);
      saveTracking();
    }
  } catch { /* offline: the local copy stands until the next sync */ }
}

function pushTracking() {
  clearTimeout(syncTimer);   // one request per burst of taps, not one per tap
  syncTimer = setTimeout(() => {
    fetch("api/state", {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(TRACKING),
    }).then(r => (r.ok ? r.json() : null))
      .then(merged => { if (merged) { TRACKING = mergeInto(TRACKING, merged); saveTracking(); } })
      .catch(() => { /* stays local; the next change or reload retries */ });
  }, 800);
}
// rows stored before the pipeline started stripping tags still hold raw HTML
const plain = s => (s || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
const esc = s => (s || "").replace(/[&<>"]/g, m => ({ "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;" }[m]));

let JOBS = [];
const state = {
  view: "all", country: "", source: "", query: "",
  remoteOnly: false, sponsorshipOnly: false, internshipOnly: false,
  fullTextOnly: false, searchDescriptions: false,
  minScore: 0, maxYears: null,
  dimension: "level", section: null,   // browse screen until a section is picked
};

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

function showLoading(on) {
  const el = document.getElementById("loading");
  if (el) el.hidden = !on;
}

async function boot() {
  showLoading(true);
  // behind Cloudflare Access an expired session answers with the sign-in page,
  // so a parse failure here means "sign in again", not "no jobs"
  const bust = "?" + Date.now();
  [JOBS, META] = await Promise.all([
    fetch("data/jobs.json" + bust).then(r => r.json()).catch(() => { loadFailed = true; return []; }),
    fetch("data/meta.json" + bust).then(r => r.json()).catch(() => null),
  ]);
  showFreshness();
  TRACKING = loadTracking();
  await pullTracking();
  fillSelect("country", [...new Set(JOBS.map(j => j.country))].sort());
  fillSelect("source", [...new Set(JOBS.map(j => j.source))].sort());
  wire();
  render();
  showLoading(false);
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
  for (const id of ["remoteOnly", "sponsorshipOnly", "internshipOnly", "fullTextOnly", "searchDescriptions"]) {
    document.getElementById(id).addEventListener("change", e => { state[id] = e.target.checked; render(); });
  }
  document.getElementById("maxYears").addEventListener("input", e => {
    const v = +e.target.value;
    state.maxYears = v >= 10 ? null : v;   // the top of the range means "any"
    document.getElementById("maxYearsVal").textContent = state.maxYears === null ? "any" : v;
    render();
  });
  document.getElementById("minScore").addEventListener("input", e => {
    state.minScore = +e.target.value;
    document.getElementById("minScoreVal").textContent = e.target.value;
    render();
  });
  document.getElementById("crumb").addEventListener("click", () => {
    state.section = null;
    window.scrollTo(0, 0);
    render();
  });
  document.querySelectorAll("#tabs button").forEach(b =>
    b.addEventListener("click", () => {
      document.querySelectorAll("#tabs button").forEach(x => x.classList.remove("active"));
      b.classList.add("active"); state.view = b.dataset.view; render();
    }));
}

// A card per job meant 3000 nodes on open. Only a screenful is built; the rest
// arrive as you scroll, so filtering stays instant however long the list gets.
const PAGE = 24;
let visibleRows = [];
let shown = 0;
let sentinelObserver = null;

function render() {
  const browsing = !state.section && state.view === "all";
  document.getElementById("browse").hidden = !browsing;
  document.getElementById("list").hidden = browsing;
  document.getElementById("filters").hidden = browsing;
  document.getElementById("crumb").hidden = !state.section;
  if (browsing) return renderBrowse();
  renderList();
}

function renderBrowse() {
  const wrap = document.getElementById("browse");
  const dims = [["level", "By level", LEVELS], ["domain", "By focus", DOMAINS]];
  wrap.innerHTML = dims.map(([dim, heading]) => {
    const tiles = sectionCounts(JOBS, dim)
      .filter(s => s.count > 0)          // never offer an empty section
      .map(s => `
        <button class="tile" data-dim="${dim}" data-id="${s.id}">
          <b>${esc(s.label)}</b>
          <span class="tile-count">${s.count}</span>
          <span class="tile-hint">${esc(s.hint)}</span>
        </button>`).join("");
    return `<h2 class="browse-head">${heading}</h2><div class="tiles">${tiles}</div>`;
  }).join("");
  document.getElementById("count").textContent =
    JOBS.length ? `${JOBS.length} roles — pick a section` : "No jobs yet";
  wrap.querySelectorAll(".tile").forEach(t => t.addEventListener("click", () => {
    state.dimension = t.dataset.dim;
    state.section = t.dataset.id;
    window.scrollTo(0, 0);
    render();
  }));
}

function renderList() {
  const saved = activeIds(TRACKING.saved), applied = activeIds(TRACKING.applied);
  const pool = state.section
    ? JOBS.filter(j => inSection(j, state.dimension, state.section))
    : JOBS;
  visibleRows = filterJobs(pool, { ...state, savedIds: [...saved], appliedIds: [...applied] });
  const defs = state.dimension === "level" ? LEVELS : DOMAINS;
  const current = defs.find(d => d.id === state.section);
  document.getElementById("crumb").textContent =
    current ? `← All sections · ${current.label}` : "← All sections";
  document.getElementById("count").textContent =
    JOBS.length ? `${visibleRows.length} of ${JOBS.length} roles`
                : loadFailed ? "Could not load jobs" : "No jobs yet — run the pipeline";

  const list = document.getElementById("list");
  list.innerHTML = visibleRows.length ? ""
    : loadFailed
      ? "<p class='empty'>Could not load the job list. If the session expired, <a href='./'>reload to sign in</a>.</p>"
      : "<p class='empty'>Nothing matches these filters yet. Loosen them or check back after the next refresh.</p>";
  shown = 0;
  appendPage(list, saved, applied);
}

function appendPage(list, saved, applied) {
  const slice = visibleRows.slice(shown, shown + PAGE);
  const batch = document.createDocumentFragment();   // one reflow, not twenty-four
  for (const j of slice) batch.appendChild(card(j, saved, applied));
  const old = list.querySelector(".sentinel");
  if (old) old.remove();
  list.appendChild(batch);
  shown += slice.length;

  if (shown < visibleRows.length) {
    const sentinel = document.createElement("div");
    sentinel.className = "sentinel";
    sentinel.textContent = `${visibleRows.length - shown} more…`;
    list.appendChild(sentinel);
    watchSentinel(sentinel, list, saved, applied);
  }
}

function watchSentinel(sentinel, list, saved, applied) {
  if (sentinelObserver) sentinelObserver.disconnect();
  if (typeof IntersectionObserver !== "function") {
    sentinel.addEventListener("click", () => appendPage(list, saved, applied));
    return;   // older browsers get a tap-to-continue instead
  }
  sentinelObserver = new IntersectionObserver(entries => {
    if (entries.some(e => e.isIntersecting)) appendPage(list, saved, applied);
  }, { rootMargin: "600px" });   // fetch the next screenful before it is reached
  sentinelObserver.observe(sentinel);
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
// older rows hold whole sentences as "skills"; trim them so the card stays scannable
const mustHave = j => {
  const skills = (j.skills || []).map(s => s.trim()).filter(Boolean);
  if (!skills.length) return "not stated";
  const short = skills.map(s => (s.length > 42 ? s.slice(0, 41).trimEnd() + "…" : s));
  return short.slice(0, 8).join(" · ") + (short.length > 8 ? ` +${short.length - 8}` : "");
};
// Adzuna's API hands back a 500-char teaser, not the ad. Saying "not stated"
// there would imply the ad is silent, when really we were never shown it.
const isTeaser = j => (j.description || "").length <= 520 && /[…\.]{1,3}$/.test((j.description || "").trim());
const factOrTeaser = (j, value) =>
  (value && value !== "not stated") ? value : (isTeaser(j) ? "see full posting" : "not stated");
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
      <li><span>Experience</span>${esc(factOrTeaser(j, j.experience_required))}</li>
    </ul>
    <p class="role"><span>Must have</span>${esc(mustHave(j) === "not stated" ? factOrTeaser(j, "") : mustHave(j))}</p>
    <p class="role"><span>Role</span>${esc(j.role_summary || "not stated")}</p>
    <p class="role"><span>They expect</span>${esc(j.expectations || "not stated")}</p>
    <p class="reason">${esc(/^(AI disabled|AI unavailable)$/.test(j.score_reason || "") ? "" : j.score_reason)}</p>
    <details>
      <summary>Details</summary>
      <p><strong>Hiring:</strong> ${esc(j.hiring_process || "not stated")}</p>
      <p><strong>Last listed:</strong> ${esc(j.last_seen || j.first_seen || "not stated")}</p>
      <p class="desc">${esc(plain(j.description).slice(0, 600))}</p>
    </details>
    <div class="draft" hidden></div>
    <div class="actions">
      <button class="make-draft">Draft application</button>
      <a class="apply" href="${esc(j.url)}" target="_blank" rel="noopener">Open posting ↗</a>
      <button class="save ${saved.has(j.id) ? "on" : ""}">${saved.has(j.id) ? "★ Saved" : "☆ Save"}</button>
      <button class="applied ${applied.has(j.id) ? "on" : ""}">${applied.has(j.id) ? "✓ Applied" : "Applied?"}</button>
    </div>`;
  el.querySelector(".make-draft").addEventListener("click", ev => makeDraft(j, el, ev.target));
  el.querySelector(".save").addEventListener("click", () => toggle("saved", j.id));
  el.querySelector(".applied").addEventListener("click", () => toggle("applied", j.id));
  return el;
}

async function makeDraft(job, card, button) {
  const panel = card.querySelector(".draft");
  panel.hidden = false;
  panel.innerHTML = "<p class='muted'>Reading the ad and your profile…</p>";
  button.disabled = true;
  try {
    const res = await fetch("api/draft", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        id: job.id, title: job.title, company: job.company, location: job.location,
        description: job.description, skills: job.skills,
        experience_required: job.experience_required,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      panel.innerHTML = `<p class='muted'>${esc(data.error || "Could not draft this one.")}</p>`;
      return;
    }
    panel.innerHTML = renderDraft(data);
    panel.querySelectorAll("button.copy").forEach(b =>
      b.addEventListener("click", () => {
        navigator.clipboard.writeText(b.dataset.text || "");
        b.textContent = "Copied";
        setTimeout(() => { b.textContent = "Copy"; }, 1500);
      }));
  } catch {
    panel.innerHTML = "<p class='muted'>Could not reach the drafting service.</p>";
  } finally {
    button.disabled = false;
  }
}

function renderDraft(d) {
  const list = (label, items) => items && items.length
    ? `<p class="role"><span>${label}</span>${items.map(esc).join(" · ")}</p>` : "";
  const bullets = (d.cv_bullets || []).map(b => `<li>${esc(b)}</li>`).join("");
  return `
    ${d.honest_note ? `<p class="honest">${esc(d.honest_note)}</p>` : ""}
    ${list("Gaps against this ad", d.gaps)}
    ${list("What genuinely matches", d.strengths)}
    ${bullets ? `<p class="role"><span>CV bullets</span></p><ul class="bullets">${bullets}</ul>
       <button class="copy" data-text="${esc((d.cv_bullets || []).join("\n"))}">Copy</button>` : ""}
    ${d.cover_letter ? `<p class="role"><span>Cover letter</span></p>
       <pre class="letter">${esc(d.cover_letter)}</pre>
       <button class="copy" data-text="${esc(d.cover_letter)}">Copy</button>` : ""}
    ${d.cached ? "<p class='muted'>Saved from an earlier draft.</p>" : ""}`;
}

function toggle(section, id) {
  const current = TRACKING[section][id];
  TRACKING[section][id] = { on: !(current && current.on), ts: Date.now() };
  TRACKING.updated_at = Date.now();
  saveTracking();
  pushTracking();
  render();
}

boot();
