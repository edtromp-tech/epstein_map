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
  const [people, edges, cases, documents] = await Promise.all([
    loadJSON("assets/data/people.json"),
    loadJSON("assets/data/edges.json"),
    loadJSON("assets/data/cases.json"),
    loadJSON("assets/data/documents.json"),
  ]);

  // Index helpers
  const peopleById = new Map(people.map(p => [p.id, p]));
  const casesById = new Map(cases.map(c => [c.id, c]));
  const docsById = new Map(documents.map(d => [d.id, d]));

  // Compute automatic risk score
  computeRiskScores({ people, edges, cases, documents });

  // UI state
  const state = {
    filters: {
      victim: true,
      accused: true,
      other: true,
      riskMin: 0,
      degreeLimit: 3,
    }
  };

  // Controls
  const filterVictim = document.getElementById("filterVictim");
  const filterAccused = document.getElementById("filterAccused");
  const filterOther = document.getElementById("filterOther");
  const riskMin = document.getElementById("riskMin");
  const riskMinLabel = document.getElementById("riskMinLabel");

  const degreeLimit = document.getElementById("degreeLimit");
  const degreeLimitLabel = document.getElementById("degreeLimitLabel");

  filterVictim.onchange = () => { state.filters.victim = filterVictim.checked; graph.applyFilters(state.filters); };
  filterAccused.onchange = () => { state.filters.accused = filterAccused.checked; graph.applyFilters(state.filters); };
  filterOther.onchange = () => { state.filters.other = filterOther.checked; graph.applyFilters(state.filters); };

  riskMin.oninput = () => {
    state.filters.riskMin = parseFloat(riskMin.value);
    riskMinLabel.textContent = state.filters.riskMin.toFixed(2);
    graph.applyFilters(state.filters);
  };

  degreeLimit.oninput = () => {
    state.filters.degreeLimit = parseInt(degreeLimit.value, 10);
    degreeLimitLabel.textContent = state.filters.degreeLimit;
    graph.setDegreeLimit(state.filters.degreeLimit);
  };

  document.getElementById("resetBtn").onclick = () => graph.resetView();

  // Search
  const searchInput = document.getElementById("searchInput");
  const searchBtn = document.getElementById("searchBtn");
  function doSearch() {
    const q = (searchInput.value || "").trim().toLowerCase();
    if (!q) return;
    const hit = people.find(p => p.name.toLowerCase().includes(q));
    if (!hit) return toast("No match found.");
    graph.focusPerson(hit.id);
  }
  searchBtn.onclick = doSearch;
  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") doSearch();
  });

  // Details panel renderer
  function renderDetails(personId) {
    const panel = document.getElementById("detailsPanel");
    const p = peopleById.get(personId);
    if (!p) return;

    const typeBadge = p.type === "victim" ? "victim" : (p.type === "accused" ? "accused" : "");
    const riskText = (p.risk ?? 0).toFixed(2);

    // docs mentioning person
    const docIds = new Set();
    for (const d of documents) {
      if ((d.mentions || []).includes(p.id)) docIds.add(d.id);
    }
    // docs from cases
    for (const caseId of (p.caseIds || [])) {
      const c = casesById.get(caseId);
      (c?.documentIds || []).forEach(id => docIds.add(id));
    }

    const docList = [...docIds]
      .map(id => docsById.get(id))
      .filter(Boolean);

    const casesList = (p.caseIds || []).map(id => casesById.get(id)).filter(Boolean);

    panel.innerHTML = `
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

    // Hook doc clicks -> PDF viewer
    panel.querySelectorAll("[data-doc]").forEach(el => {
      el.addEventListener("click", async () => {
        const docId = el.getAttribute("data-doc");
        const doc = docsById.get(docId);
        if (!doc) return;
        // TODO: PDF viewer disabled for now
        // if (pdfViewer) await pdfViewer.load(doc.filePath, doc.title);
      });
    });
  }

  // Init graph
  const graph = initGraph({
    svgId: "graph",
    people,
    edges,
    onPersonClick: (personId) => renderDetails(personId),
  });

  graph.applyFilters(state.filters);

  toast("Loaded. Click a person bubble to explore.");
}
