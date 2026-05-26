// agentic-fit showcase explorer: no framework, no build.
const state = { data: null, category: null, metric: "cost", activeModels: new Set(),
                sortKey: "cost_usd", sortDir: 1, libFilter: null };

const $ = (sel) => document.querySelector(sel);
const shortLabel = (id) => id.includes("/") ? id.split("/")[1] : id;
const fmtCost = (v) => (v >= 0.001 ? v.toFixed(3) : v.toFixed(4));
const cellCost = (v) => fmtCost(v).replace(/^0/, ""); // ".004"
const pct = (v) => Math.round(v * 100) + "%";

function cellsFor(category) {
  return state.data.cells.filter((c) => c.category === category);
}
function metricValue(c) { return state.metric === "cost" ? c.cost_usd : c.success_rate; }

// quintile breakpoints over the visible values in the current category
function breakpoints(values) {
  const s = [...values].sort((a, b) => a - b);
  const q = (p) => s[Math.min(s.length - 1, Math.floor(p * s.length))];
  return [q(0.2), q(0.4), q(0.6), q(0.8)];
}
function bucketClass(v, breaks) {
  let b = 1;
  for (const t of breaks) if (v > t) b++;
  return "c" + b;
}

function renderHeatmap() {
  const cat = state.category;
  const libs = state.data.libraries_by_category[cat];
  const models = state.data.models.filter((m) => state.activeModels.has(m));
  const cells = cellsFor(cat).filter((c) => state.activeModels.has(c.model));
  const breaks = breakpoints(cells.map(metricValue));

  const grid = $("#heatmap");
  grid.style.gridTemplateColumns = `110px repeat(${models.length}, minmax(34px, 1fr))`;
  const lookup = {};
  for (const c of cells) lookup[c.model + "|" + c.library] = c;

  let html = `<div class="ch lib-head">Library</div>` +
    models.map((m) => `<div class="ch" title="${m}">${shortLabel(m)}</div>`).join("");
  for (const lib of libs) {
    html += `<div class="rl">${lib}</div>`;
    for (const m of models) {
      const c = lookup[m + "|" + lib];
      if (!c) { html += `<div class="cell empty">·</div>`; continue; }
      const v = metricValue(c);
      const text = state.metric === "cost" ? cellCost(v) : pct(v);
      html += `<div class="cell ${bucketClass(v, breaks)}" data-lib="${lib}" `
            + `title="${shortLabel(m)} · ${lib}: ${state.metric === "cost" ? "$" + fmtCost(v) : pct(v)}">${text}</div>`;
    }
  }
  grid.innerHTML = html;
  grid.querySelectorAll(".cell[data-lib]").forEach((el) =>
    el.addEventListener("click", () => { state.libFilter = el.dataset.lib; renderTable();
      $("#drilldown").scrollIntoView({ behavior: "smooth", block: "nearest" }); }));
  renderLegend();
}

function renderTaskMeta() {
  const t = (state.data.tasks || {})[state.category];
  $("#task-summary").textContent = t ? t.summary : "";
  $("#task-prompt").textContent = t ? t.prompt : "";
  $("#task-libs").textContent = t && t.candidate_libraries.length
    ? "Candidate libraries: " + t.candidate_libraries.join(" · ") : "";
}

function renderLegend() {
  const lo = state.metric === "cost" ? "cheaper" : "lower";
  const hi = state.metric === "cost" ? "pricier" : "higher";
  $("#legend").innerHTML = `<span>${lo}</span>` +
    [1,2,3,4,5].map((n) => `<span class="sw c${n}"></span>`).join("") +
    `<span>${hi}</span>`;
}

function renderTable() {
  const cat = state.category;
  let rows = cellsFor(cat).filter((c) => state.activeModels.has(c.model));
  if (state.libFilter) rows = rows.filter((c) => c.library === state.libFilter);
  rows.sort((a, b) => {
    const x = a[state.sortKey], y = b[state.sortKey];
    const cmp = typeof x === "number" ? x - y : String(x).localeCompare(String(y));
    return cmp * state.sortDir;
  });
  const body = $("#drilldown tbody");
  body.innerHTML = rows.map((c) =>
    `<tr><td>${shortLabel(c.model)}</td><td>${c.library}</td>`
    + `<td class="num">${pct(c.success_rate)}</td>`
    + `<td class="num">$${fmtCost(c.cost_usd)}</td>`
    + `<td class="num">${c.n}</td></tr>`).join("");
  document.querySelectorAll("#drilldown th.sortable").forEach((th) => {
    const active = th.dataset.sort === state.sortKey;
    th.classList.toggle("active", active);
    if (active) th.dataset.dir = state.sortDir;
  });
}

function renderControls() {
  const tabs = $("#category-tabs");
  tabs.innerHTML = state.data.categories.map((c) =>
    `<button data-cat="${c}" class="cat-tab${c === state.category ? " on" : ""}">${c}</button>`).join("");
  tabs.addEventListener("click", (e) => {
    const btn = e.target.closest("button"); if (!btn) return;
    state.category = btn.dataset.cat; state.libFilter = null;
    tabs.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b === btn));
    renderHeatmap(); renderTable(); renderTaskMeta();
  });

  $("#metric-toggle").addEventListener("click", (e) => {
    const btn = e.target.closest("button"); if (!btn) return;
    state.metric = btn.dataset.metric;
    state.sortKey = state.metric === "cost" ? "cost_usd" : "success_rate";
    document.querySelectorAll("#metric-toggle button")
      .forEach((b) => b.classList.toggle("on", b === btn));
    renderHeatmap(); renderTable();
  });

  const box = $("#model-checkboxes");
  box.innerHTML = state.data.models.map((m) =>
    `<label><input type="checkbox" value="${m}" checked>${shortLabel(m)}</label>`).join("");
  box.addEventListener("change", (e) => {
    const cb = e.target; if (cb.checked) state.activeModels.add(cb.value);
    else state.activeModels.delete(cb.value);
    renderHeatmap(); renderTable();
  });

  document.querySelectorAll("#drilldown th.sortable").forEach((th) =>
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      state.sortDir = state.sortKey === key ? -state.sortDir : 1;
      state.sortKey = key; renderTable();
    }));
}

async function init() {
  state.data = await fetch("data.json").then((r) => r.json());
  state.category = state.data.categories.includes("data_validation")
    ? "data_validation" : state.data.categories[0];
  state.data.models.forEach((m) => state.activeModels.add(m));
  renderControls();
  renderHeatmap();
  renderTable();
  renderTaskMeta();
  $("#footer-meta").textContent =
    `Snapshot ${state.data.snapshot} · ${state.data.models.length} models across nine vendors · ${state.data.cells.length} measured cells.`;
}
init();
