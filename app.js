const resultsEl = document.getElementById("results");
const statusEl = document.getElementById("status");
const refreshBtn = document.getElementById("refreshBtn");
const limitEl = document.getElementById("limit");
const categoryTabsEl = document.getElementById("categoryTabs");
const sourceHealthEl = document.getElementById("sourceHealth");
const template = document.getElementById("cardTemplate");

const totalTrendsEl = document.getElementById("totalTrends");
const misleadingCountEl = document.getElementById("misleadingCount");
const realCountEl = document.getElementById("realCount");
const avgFakeEl = document.getElementById("avgFake");

const CATEGORIES = [
  { id: "all", label: "All" },
  { id: "local", label: "Local" },
  { id: "india", label: "India" },
  { id: "world", label: "World" },
  { id: "entertainment", label: "Entertainment" },
  { id: "health", label: "Health" },
  { id: "trending", label: "Trending" },
  { id: "sports", label: "Sports" },
  { id: "esports", label: "Esports" },
  { id: "food", label: "Food" },
  { id: "events", label: "Events" },
];

const CATEGORY_LABELS = Object.fromEntries(CATEGORIES.map((c) => [c.id, c.label]));
let selectedCategory = "all";

function verdictClass(verdict) {
  if (verdict === "Likely Real") return "real";
  if (verdict === "Likely Misleading") return "fake";
  return "warn";
}

function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.style.color = isError ? "#8d2519" : "#5d6b72";
}

function clearResults() {
  resultsEl.innerHTML = "";
}

function makeEvidenceLink(article) {
  const anchor = document.createElement("a");
  anchor.href = article.article_url;
  anchor.target = "_blank";
  anchor.rel = "noreferrer";
  anchor.textContent = article.source || "Source";
  return anchor;
}

function renderCategoryTabs() {
  categoryTabsEl.innerHTML = "";
  CATEGORIES.forEach((category) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `tab-btn ${selectedCategory === category.id ? "active" : ""}`;
    btn.textContent = category.label;
    btn.addEventListener("click", () => {
      selectedCategory = category.id;
      renderCategoryTabs();
      runAnalysis(true);
    });
    categoryTabsEl.appendChild(btn);
  });
}

function renderSourceHealth(sourceHealth) {
  sourceHealthEl.innerHTML = "";
  Object.entries(sourceHealth || {}).forEach(([source, status]) => {
    const pill = document.createElement("span");
    const ok = String(status).startsWith("ok") || String(status).includes("fallback");
    pill.className = `source-pill ${ok ? "ok" : "warn"}`;
    pill.textContent = `${source.replace("_", " ")}: ${status}`;
    sourceHealthEl.appendChild(pill);
  });
}

function renderSummary(results) {
  const total = results.length;
  const misleading = results.filter((r) => r.verdict === "Likely Misleading").length;
  const real = results.filter((r) => r.verdict === "Likely Real").length;
  const avgFake = total === 0 ? 0 : results.reduce((sum, r) => sum + r.fake_probability, 0) / total;

  totalTrendsEl.textContent = String(total);
  misleadingCountEl.textContent = String(misleading);
  realCountEl.textContent = String(real);
  avgFakeEl.textContent = `${avgFake.toFixed(1)}%`;
}

function buildCard(item) {
  const node = template.content.cloneNode(true);
  const card = node.querySelector(".card");
  card.querySelector(".platform").textContent = item.trend.platform;
  card.querySelector(".category").textContent = CATEGORY_LABELS[item.trend.category] || item.trend.category;
  card.querySelector(".title").textContent = item.trend.title;

  const verdict = card.querySelector(".verdict");
  verdict.textContent = item.verdict;
  verdict.classList.add(verdictClass(item.verdict));

  const fakeFill = card.querySelector(".fill.fake");
  const spreadFill = card.querySelector(".fill.spread");
  const credibilityFill = card.querySelector(".fill.credibility");
  fakeFill.style.width = `${item.fake_probability}%`;
  spreadFill.style.width = `${item.spread_index}%`;
  credibilityFill.style.width = `${item.credibility_score}%`;

  card.querySelector(".fake-value").textContent = `${item.fake_probability.toFixed(1)}%`;
  card.querySelector(".spread-value").textContent = `${item.spread_index.toFixed(1)} / 100`;
  card.querySelector(".credibility-value").textContent = `${item.credibility_score.toFixed(1)}%`;

  const link = card.querySelector(".origin-link");
  link.href = item.trend.url;

  card.querySelector(
    ".evidence-summary"
  ).textContent = `Credible Hits: ${item.evidence.credible_hits} | Sources: ${item.evidence.source_diversity} | Confidence: ${(item.evidence.confidence * 100).toFixed(1)}%`;

  const reasonList = card.querySelector(".reasons");
  item.reasons.forEach((reason) => {
    const li = document.createElement("li");
    li.textContent = reason;
    reasonList.appendChild(li);
  });

  const evidenceLinks = card.querySelector(".evidence-links");
  item.evidence.articles.slice(0, 4).forEach((article) => {
    evidenceLinks.appendChild(makeEvidenceLink(article));
  });

  return node;
}

function renderCards(results) {
  clearResults();
  if (selectedCategory === "all") {
    const groups = new Map();
    results.forEach((item) => {
      const category = item.trend.category || "trending";
      if (!groups.has(category)) groups.set(category, []);
      groups.get(category).push(item);
    });

    CATEGORIES.filter((c) => c.id !== "all").forEach((category) => {
      const items = groups.get(category.id) || [];
      if (!items.length) return;
      const section = document.createElement("section");
      section.className = "result-section";
      const heading = document.createElement("h2");
      heading.className = "section-head";
      heading.textContent = `${category.label} News`;
      section.appendChild(heading);
      items.forEach((item) => section.appendChild(buildCard(item)));
      resultsEl.appendChild(section);
    });
    return;
  }

  results.forEach((item) => {
    resultsEl.appendChild(buildCard(item));
  });
}

async function runAnalysis(forceRefresh = false) {
  const limit = Number(limitEl.value || 20);
  const refreshParam = forceRefresh ? "&refresh=true" : "";
  setStatus(`Analyzing ${CATEGORY_LABELS[selectedCategory] || selectedCategory} trends...`);
  refreshBtn.disabled = true;

  try {
    const response = await fetch(
      `/api/analyze?limit=${limit}&category=${encodeURIComponent(selectedCategory)}${refreshParam}`
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    renderSummary(data.results || []);
    renderSourceHealth(data.source_health || {});
    renderCards(data.results || []);
    const generated = new Date(data.generated_at).toLocaleString();
    setStatus(`Updated at ${generated}.`);
  } catch (error) {
    setStatus(`Failed to load analysis: ${error.message}`, true);
  } finally {
    refreshBtn.disabled = false;
  }
}

refreshBtn.addEventListener("click", () => runAnalysis(true));
renderCategoryTabs();
runAnalysis(false);

