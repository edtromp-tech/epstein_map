function colorForType(type) {
  if (type === "victim") return getCss("--victim");
  if (type === "accused") return getCss("--accused");
  return getCss("--other");
}

function getCss(varName) {
  return getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
}

function riskGlow(risk) {
  // risk 0..1 => glow radius
  const r = Math.max(0, Math.min(1, risk ?? 0));
  return 6 + r * 28;
}

export function initGraph({ svgId, people, edges, onPersonClick }) {
  const svg = d3.select(`#${svgId}`);
  const width = svg.node().clientWidth;
  const height = svg.node().clientHeight;

  svg.attr("viewBox", [0, 0, width, height]);

  const g = svg.append("g");

  // Zoom
  const zoom = d3.zoom()
    .scaleExtent([0.2, 4])
    .on("zoom", (event) => g.attr("transform", event.transform));

  svg.call(zoom);

  // Build map for filtering
  const peopleById = new Map(people.map(p => [p.id, p]));

  // D3 expects link source/target as objects or ids
  const links = edges.map(e => ({
    ...e,
    source: e.source,
    target: e.target,
    weight: e.weight ?? 1
  }));

  // Simulation
  const sim = d3.forceSimulation(people)
    .force("link", d3.forceLink(links).id(d => d.id).distance(80).strength(0.12))
    .force("charge", d3.forceManyBody().strength(-260))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collision", d3.forceCollide().radius(d => 14 + Math.sqrt(d._degree || 0) * 2));

  // defs for glow
  const defs = svg.append("defs");

  function ensureGlowFilter(id, risk) {
    const existing = defs.select(`#${id}`);
    if (!existing.empty()) return;

    const blur = riskGlow(risk);

    const filter = defs.append("filter")
      .attr("id", id)
      .attr("x", "-50%")
      .attr("y", "-50%")
      .attr("width", "200%")
      .attr("height", "200%");

    filter.append("feGaussianBlur")
      .attr("in", "SourceGraphic")
      .attr("stdDeviation", blur)
      .attr("result", "blur");

    filter.append("feColorMatrix")
      .attr("in", "blur")
      .attr("type", "matrix")
      .attr("values", `
        1 0 0 0 0
        0 0 0 0 0
        0 0 0 0 0
        0 0 0 0.9 0
      `)
      .attr("result", "redBlur");

    const merge = filter.append("feMerge");
    merge.append("feMergeNode").attr("in", "redBlur");
    merge.append("feMergeNode").attr("in", "SourceGraphic");
  }

  // Links
  const link = g.append("g")
    .attr("stroke-width", 1)
    .selectAll("line")
    .data(links)
    .join("line")
    .attr("stroke", "rgba(160,190,230,.18)")
    .attr("stroke-linecap", "round")
    .attr("stroke-width", d => Math.max(1, Math.sqrt(d.weight)));

  // Nodes
  const node = g.append("g")
    .selectAll("circle")
    .data(people)
    .join("circle")
    .attr("r", d => 10 + Math.sqrt(d._degree || 0) * 1.2)
    .attr("fill", d => colorForType(d.type))
    .attr("stroke", "rgba(255,255,255,.10)")
    .attr("stroke-width", 1.2)
    .attr("cursor", "pointer")
    .each(function(d){
      const filterId = `glow_${d.id}`;
      ensureGlowFilter(filterId, d.risk);
      if ((d.risk ?? 0) > 0.08 && d.type !== "victim") {
        d3.select(this).attr("filter", `url(#${filterId})`);
      }
    })
    .call(d3.drag()
      .on("start", (event, d) => {
        if (!event.active) sim.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on("drag", (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on("end", (event, d) => {
        if (!event.active) sim.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      })
    );

  // Labels (optional)
  const label = g.append("g")
    .selectAll("text")
    .data(people)
    .join("text")
    .text(d => d.name)
    .attr("font-size", 10)
    .attr("fill", "rgba(255,255,255,.55)")
    .attr("pointer-events", "none");

  node.on("click", (event, d) => {
    onPersonClick?.(d.id);
    focusPerson(d.id);
  });

  sim.on("tick", () => {
    // helper to handle links whose source/target might still be IDs
    const coord = (nodeOrId, axis) => {
      if (!nodeOrId) return 0;
      if (typeof nodeOrId === "object") return nodeOrId[axis] ?? 0;
      const p = peopleById.get(nodeOrId);
      return p ? (p[axis] ?? 0) : 0;
    };

    link
      .attr("x1", d => coord(d.source, "x"))
      .attr("y1", d => coord(d.source, "y"))
      .attr("x2", d => coord(d.target, "x"))
      .attr("y2", d => coord(d.target, "y"));

    node
      .attr("cx", d => d.x)
      .attr("cy", d => d.y);

    label
      .attr("x", d => d.x + 12)
      .attr("y", d => d.y + 4);
  });

  // Filtering
  let currentDegreeLimit = 3;
  let selectedId = null;

  function bfsWithin(sourceId, maxDepth) {
    const adj = new Map();
    for (const e of edges) {
      if (!adj.has(e.source)) adj.set(e.source, []);
      if (!adj.has(e.target)) adj.set(e.target, []);
      adj.get(e.source).push(e.target);
      adj.get(e.target).push(e.source);
    }

    const seen = new Set([sourceId]);
    const q = [{ id: sourceId, depth: 0 }];

    while (q.length) {
      const { id, depth } = q.shift();
      if (depth >= maxDepth) continue;
      for (const nxt of (adj.get(id) || [])) {
        if (seen.has(nxt)) continue;
        seen.add(nxt);
        q.push({ id: nxt, depth: depth + 1 });
      }
    }
    return seen;
  }

  function applyFilters(filters) {
    const allowedTypes = new Set();
    if (filters.victim) allowedTypes.add("victim");
    if (filters.accused) allowedTypes.add("accused");
    if (filters.other) allowedTypes.add("other");

    const riskMin = filters.riskMin ?? 0;

    let allowedByDegree = null;
    if (selectedId) allowedByDegree = bfsWithin(selectedId, currentDegreeLimit);

    node.style("display", d => {
      const typeOk = allowedTypes.has(d.type);
      const riskOk = (d.type === "victim") ? true : ((d.risk ?? 0) >= riskMin);
      const degOk = allowedByDegree ? allowedByDegree.has(d.id) : true;
      return (typeOk && riskOk && degOk) ? null : "none";
    });

    label.style("display", d => {
      const typeOk = allowedTypes.has(d.type);
      const riskOk = (d.type === "victim") ? true : ((d.risk ?? 0) >= riskMin);
      const degOk = allowedByDegree ? allowedByDegree.has(d.id) : true;
      return (typeOk && riskOk && degOk) ? null : "none";
    });
    // build a map of visible node ids for reliable link visibility checks
    const visibleMap = new Map();
    node.each(function(d) {
      const isVisible = d3.select(this).style("display") !== "none";
      visibleMap.set(d.id, isVisible);
    });

    link.style("display", d => {
      const a = typeof d.source === "string" ? d.source : d.source.id;
      const b = typeof d.target === "string" ? d.target : d.target.id;
      const aOk = peopleById.get(a);
      const bOk = peopleById.get(b);

      const aVisible = !!visibleMap.get(a);
      const bVisible = !!visibleMap.get(b);

      return (aOk && bOk && aVisible && bVisible) ? null : "none";
    });
  }

  function setDegreeLimit(n) {
    currentDegreeLimit = n;
    applyFilters({
      victim: document.getElementById("filterVictim").checked,
      accused: document.getElementById("filterAccused").checked,
      other: document.getElementById("filterOther").checked,
      riskMin: parseFloat(document.getElementById("riskMin").value),
    });
  }

  function focusPerson(id) {
    selectedId = id;

    node.attr("stroke-width", d => d.id === id ? 2.5 : 1.2)
        .attr("stroke", d => d.id === id ? "rgba(255,255,255,.55)" : "rgba(255,255,255,.10)");

    const target = peopleById.get(id);
    if (!target) return;

    const transform = d3.zoomIdentity
      .translate(width / 2 - target.x * 1.4, height / 2 - target.y * 1.4)
      .scale(1.4);

    svg.transition().duration(450).call(zoom.transform, transform);

    setDegreeLimit(currentDegreeLimit);
  }

  function resetView() {
    selectedId = null;
    node.attr("stroke-width", 1.2).attr("stroke", "rgba(255,255,255,.10)");
    svg.transition().duration(400).call(zoom.transform, d3.zoomIdentity);
    applyFilters({
      victim: true, accused: true, other: true,
      riskMin: parseFloat(document.getElementById("riskMin").value)
    });
  }

  return {
    applyFilters,
    setDegreeLimit,
    focusPerson,
    resetView
  };
}
