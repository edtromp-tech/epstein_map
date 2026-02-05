import { initGraph } from "./graph.js";
import { computeRiskScores } from "./risk.js";

async function loadJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Failed to load ${path}`);
  return res.json();
}

function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 2600);
}

export async function mainApp({ pdfViewer }) {
  /* -------------------------------------------------------
   * Load data
   * ----------------------------------------------------- */
  const [people, edges, cases, documents] = await Promise.all([
    loadJSON("assets/data/people.json"),
    loadJSON("assets/data/edges.json"),
    loadJSON("assets/data/cases.json"),
    loadJSON("assets/data/documents.json"),
  ]);

  const peopleById = new Map(people.map(p => [p.id, p]));
  const casesById = new Map(cases.map(c => [c.id, c]));
  const docsById = new Map(documents.map(d => [d.id, d]));

  computeRiskScores({ people, edges, cases, documents });

  /* -------------------------------------------------------
   * UI State
   * ----------------------------------------------------- */
  const state = {
    filters: {
      victim: true,
      accused: true,
      other: true,
      riskMin: 0,
      degreeLimit: 3,
    }
  };

  /* -------------------------------------------------------
   * DOM references
   * ----------------------------------------------------- */
  const dom = {
    filterVictim: document.getElementById("filterVictim"),
    filterAccused: document.getElementById("filterAccused"),
    filterOther: document.getElementById("filterOther"),
    riskMin: document.getElementById("riskMin"),
    riskMinLabel: document.getElementById("riskMinLabel"),
    degreeLimit: document.getElementById("degreeLimit"),
    degreeLimitLabel: document.getElementById("degreeLimitLabel"),
    resetBtn: document.getElementById("resetBtn"),

    searchInput: document.getElementById("searchInput"),
    searchBtn: document.getElementById("searchBtn"),

    layout: document.querySelector(".layout"),
    filtersBanner: document.getElementById("filtersBanner"),
    bannerToggleBtn: document.getElementById("bannerToggleBtn"),
    toggleFullscreenBtn: document.getElementById("toggleFullscreenBtn"),

    detailsPanel: document.getElementById("detailsPanel"),
  };

  /* -------------------------------------------------------
   * Render: Person Details
   * ----------------------------------------------------- */
  function renderDetails(personId) {
    const p = peopleById.get(personId);
    if (!p) return;

    const typeBadge = p.type === "victim" ? "victim" :
                      p.type === "accused" ? "accused" : "";

    const riskText = (p.risk ?? 0).toFixed(2);

    // Collect documents mentioning this person
    const docIds = new Set();

    for (const d of documents) {
      if ((d.mentions || []).includes(p.id)) docIds.add(d.id);
    }

    for (const caseId of (p.caseIds || [])) {
      const c = casesById.get(caseId);
      (c?.documentIds || []).forEach(id => docIds.add(id));
    }

    const docList = [...docIds].map(id => docsById.get(id)).filter(Boolean);
    const casesList = (p.caseIds || []).map(id => casesById.get(id)).filter(Boolean);

    dom.detailsPanel.innerHTML = `
      <h3>Person</h3>
      <div class="personName">${p.name}</div>

      <div class="badges">
        <span class="badge ${typeBadge}">${p.type.toUpperCase()}</span>
        <span class="badge">Risk: ${riskText}</span>
        <span class="badge">Links: ${(p._degree ?? 0)}</span>
      </div>

      <div class="kv">
        <div class="k">Notes</div><div class="v">${p.notes || "—"}</div>
        <div class="k">Tags</div><div class="v">${(p.tags || []).join(", ") || "—"}</div>
      </div>

      <h3 style="margin-top:14px;">Cases</h3>
      ${casesList.length ? `
        <div class="docList">
          ${casesList.map(c => `
            <div class="docLink">
              <div class="docTitle">${c.title}</div>
              <div class="docMeta">${c.summary || ""}</div>
            </div>
          `).join("")}
        </div>
      ` : `<div class="empty">No cases linked.</div>`}

      <h3 style="margin-top:14px;">Documents</h3>
      ${docList.length ? `
        <div class="docList">
          ${docList.map(d => `
            <div class="docLink" data-doc="${d.id}">
              <div class="docTitle">${d.title}</div>
              <div class="docMeta">${d.source || ""}${d.date ? " • " + d.date : ""}</div>
            </div>
          `).join("")}
        </div>
      ` : `<div class="empty">No documents linked.</div>`}
    `;

    dom.detailsPanel.querySelectorAll("[data-doc]").forEach(el => {
      el.addEventListener("click", async () => {
        const docId = el.getAttribute("data-doc");
        const doc = docsById.get(docId);
        if (!doc) return;
        // PDF viewer disabled for now
        // if (pdfViewer) await pdfViewer.load(doc.filePath, doc.title);
      });
    });
  }

  /* -------------------------------------------------------
   * Graph initialization
   * ----------------------------------------------------- */
  const graph = initGraph({
    svgId: "graph",
    people,
    edges,
    onPersonClick: renderDetails,
  });

  graph.applyFilters(state.filters);

  /* -------------------------------------------------------
   * Event bindings
   * ----------------------------------------------------- */

  // Filters
  dom.filterVictim.onchange = () => {
    state.filters.victim = dom.filterVictim.checked;
    graph.applyFilters(state.filters);
  };

  dom.filterAccused.onchange = () => {
    state.filters.accused = dom.filterAccused.checked;
    graph.applyFilters(state.filters);
  };

  dom.filterOther.onchange = () => {
    state.filters.other = dom.filterOther.checked;
    graph.applyFilters(state.filters);
  };

  dom.riskMin.oninput = () => {
    state.filters.riskMin = parseFloat(dom.riskMin.value);
    dom.riskMinLabel.textContent = state.filters.riskMin.toFixed(2);
    graph.applyFilters(state.filters);
  };

  dom.degreeLimit.oninput = () => {
    state.filters.degreeLimit = parseInt(dom.degreeLimit.value, 10);
    dom.degreeLimitLabel.textContent = state.filters.degreeLimit;
    graph.setDegreeLimit(state.filters.degreeLimit);
  };

  dom.resetBtn.onclick = () => graph.resetView();

  // Search
  function doSearch() {
    const q = (dom.searchInput.value || "").trim().toLowerCase();
    if (!q) return;

    const hit = people.find(p => p.name.toLowerCase().includes(q));
    if (!hit) return toast("No match found.");

    graph.focusPerson(hit.id);
  }

  dom.searchBtn.onclick = doSearch;
  dom.searchInput.addEventListener("keydown", e => {
    if (e.key === "Enter") doSearch();
  });

  // Filters banner
  dom.bannerToggleBtn.onclick = e => {
    e.stopPropagation();
    const expanded = dom.filtersBanner.classList.toggle("expanded");
    dom.filtersBanner.setAttribute("aria-hidden", expanded ? "false" : "true");
    dom.bannerToggleBtn.setAttribute("aria-expanded", expanded ? "true" : "false");
  };

  document.addEventListener("click", e => {
    if (!dom.filtersBanner.contains(e.target) &&
        !dom.bannerToggleBtn.contains(e.target)) {
      dom.filtersBanner.classList.remove("expanded");
      dom.filtersBanner.setAttribute("aria-hidden", "true");
      dom.bannerToggleBtn.setAttribute("aria-expanded", "false");
    }
  });

  document.addEventListener("keydown", e => {
    if (e.key === "Escape") {
      dom.filtersBanner.classList.remove("expanded");
      dom.filtersBanner.setAttribute("aria-hidden", "true");
      dom.bannerToggleBtn.setAttribute("aria-expanded", "false");
    }
  });

  // Fullscreen
  dom.toggleFullscreenBtn.onclick = () => {
    const active = dom.toggleFullscreenBtn.classList.toggle("active");
    dom.layout.classList.toggle("fullscreen", active);
  };

  /* -------------------------------------------------------
   * Startup toast
   * ----------------------------------------------------- */
  toast("Loaded. Click a person bubble to explore.");
}
