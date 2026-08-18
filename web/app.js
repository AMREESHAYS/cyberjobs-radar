import { filterJobs } from "./filters.js";

const LS = { saved: "cjr_saved", applied: "cjr_applied" };
const getSet = k => new Set(JSON.parse(localStorage.getItem(k) || "[]"));
const putSet = (k, s) => localStorage.setItem(k, JSON.stringify([...s]));
const esc = s => (s || "").replace(/[&<>"]/g, m => ({ "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;" }[m]));

let JOBS = [];
const state = { view: "all", country: "", source: "", remoteOnly: false, minScore: 0, query: "" };

async function boot() {
  JOBS = await fetch("data/jobs.json?" + Date.now()).then(r => r.json()).catch(() => []);
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
    JOBS.length ? `${rows.length} of ${JOBS.length} roles` : "No jobs yet — run the pipeline";
  const list = document.getElementById("list");
  list.innerHTML = rows.length ? "" : "<p class='empty'>Nothing matches these filters yet. Loosen them or check back after the next refresh.</p>";
  for (const j of rows) list.appendChild(card(j, saved, applied));
}

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
    </p>
    <p class="reason">${esc(/^(AI disabled|AI unavailable)$/.test(j.score_reason || "") ? "" : j.score_reason)}</p>
    <details>
      <summary>Details</summary>
      <p><strong>Skills:</strong> ${esc((j.skills || []).join(", ") || "not stated")}</p>
      <p><strong>Hiring:</strong> ${esc(j.hiring_process || "not stated")}</p>
      <p><strong>Salary:</strong> ${esc(j.salary || "not stated")}</p>
      <p class="desc">${esc((j.description || "").slice(0, 600))}</p>
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
