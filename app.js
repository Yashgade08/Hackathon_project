const resultsEl = document.getElementById("results");
const statusEl = document.getElementById("status");
const refreshBtn = document.getElementById("refreshBtn");
const limitEl = document.getElementById("limit");
const template = document.getElementById("cardTemplate");

const totalTrendsEl = document.getElementById("totalTrends");
const misleadingCountEl = document.getElementById("misleadingCount");
const avgFakeEl = document.getElementById("avgFake");

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

function renderSummary(results) {
  const total = results.length;
  const misleading = results.filter((r) => r.verdict === "Likely Misleading").length;
  const avgFake =
    total === 0
      ? 0
      : results.reduce((sum, r) => sum + r.fake_probability, 0) / total;

  totalTrendsEl.textContent = String(total);
  misleadingCountEl.textContent = String(misleading);
  avgFakeEl.textContent = `${avgFake.toFixed(1)}%`;
}

function renderCards(results) {
  clearResults();
  for (const item of results) {
    const node = template.content.cloneNode(true);
    const card = node.querySelector(".card");
    card.querySelector(".platform").textContent = item.trend.platform;
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

    resultsEl.appendChild(node);
  }
}

async function runAnalysis(forceRefresh = false) {
  const limit = Number(limitEl.value || 20);
  const refreshParam = forceRefresh ? "&refresh=true" : "";
  setStatus("Analyzing live trends...");
  refreshBtn.disabled = true;

  try {
    const response = await fetch(`/api/analyze?limit=${limit}${refreshParam}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    renderSummary(data.results);
    renderCards(data.results);
    const generated = new Date(data.generated_at).toLocaleString();
    setStatus(`Updated at ${generated}.`);
  } catch (error) {
    setStatus(`Failed to load analysis: ${error.message}`, true);
  } finally {
    refreshBtn.disabled = false;
  }
}

refreshBtn.addEventListener("click", () => runAnalysis(true));
runAnalysis(false);
