function clamp01(x) {
  return Math.max(0, Math.min(1, x));
}

const RELATION_WEIGHTS = {
  alleged_abuse: 5,
  trafficking: 5,
  procurement: 4,
  facilitation: 3,
  introduced: 2,
  association: 1,
};

export function computeRiskScores({ people, edges, cases, documents }) {
  const peopleById = new Map(people.map(p => [p.id, p]));

  // degree (for sizing)
  for (const p of people) p._degree = 0;
  for (const e of edges) {
    const a = peopleById.get(e.source);
    const b = peopleById.get(e.target);
    if (a) a._degree++;
    if (b) b._degree++;
  }

  // build doc mention counts
  const docMentions = new Map(); // personId -> count
  for (const d of documents) {
    for (const pid of (d.mentions || [])) {
      docMentions.set(pid, (docMentions.get(pid) || 0) + 1);
    }
  }

  // build case counts
  const caseCounts = new Map();
  for (const c of cases) {
    for (const pid of (c.peopleIds || [])) {
      caseCounts.set(pid, (caseCounts.get(pid) || 0) + 1);
    }
  }

  // raw score
  const raw = new Map();
  for (const p of people) raw.set(p.id, 0);

  for (const e of edges) {
    const w = RELATION_WEIGHTS[e.relationship] ?? 1;
    raw.set(e.source, (raw.get(e.source) || 0) + w);
    raw.set(e.target, (raw.get(e.target) || 0) + w * 0.8);
  }

  for (const p of people) {
    const docs = docMentions.get(p.id) || 0;
    const casesN = (p.caseIds?.length || 0) + (caseCounts.get(p.id) || 0);
    const deg = p._degree || 0;

    let score = raw.get(p.id) || 0;
    score += docs * 1.2;
    score += casesN * 2.0;
    score += Math.sqrt(deg) * 0.8;

    raw.set(p.id, score);
  }

  // normalize
  const vals = [...raw.values()];
  const max = Math.max(...vals, 1);

  for (const p of people) {
    // victims never get a risk score
    if (p.type === "victim") {
      p.risk = 0;
      continue;
    }
    const r = (raw.get(p.id) || 0) / max;
    p.risk = clamp01(r);
  }
}
