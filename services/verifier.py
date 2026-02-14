import datetime as dt
import urllib.parse
import xml.etree.ElementTree as ET

import requests

from app.models import EvidenceArticle, VerificationEvidence

CREDIBLE_SOURCE_WEIGHTS = {
    "reuters.com": 1.0,
    "apnews.com": 1.0,
    "bbc.com": 0.95,
    "npr.org": 0.95,
    "pbs.org": 0.92,
    "nytimes.com": 0.9,
    "wsj.com": 0.9,
    "washingtonpost.com": 0.9,
    "bloomberg.com": 0.88,
    "financialtimes.com": 0.88,
    "economist.com": 0.88,
    "theguardian.com": 0.87,
    "usatoday.com": 0.8,
    "abcnews.go.com": 0.82,
    "cnn.com": 0.78,
    "cbsnews.com": 0.8,
    "nbcnews.com": 0.8,
    "aljazeera.com": 0.79,
    "forbes.com": 0.72,
    "techcrunch.com": 0.7,
    "theverge.com": 0.7,
}


def _domain_from_url(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _weight_for_domain(domain: str) -> float:
    for candidate, weight in CREDIBLE_SOURCE_WEIGHTS.items():
        if domain.endswith(candidate):
            return weight
    return 0.0


def _parse_pub_date(pub_date: str) -> dt.datetime:
    if not pub_date:
        return dt.datetime.now(dt.timezone.utc)
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            parsed = dt.datetime.strptime(pub_date, fmt)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=dt.timezone.utc)
            return parsed
        except ValueError:
            continue
    return dt.datetime.now(dt.timezone.utc)


def verify_claim(query: str, max_results: int = 12) -> VerificationEvidence:
    rss_url = (
        "https://news.google.com/rss/search?q="
        f"{urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
    )

    articles: list[EvidenceArticle] = []
    try:
        response = requests.get(rss_url, timeout=12)
        response.raise_for_status()
        root = ET.fromstring(response.text)
    except Exception:
        return VerificationEvidence(
            query=query,
            credible_hits=0,
            total_hits=0,
            source_diversity=0,
            confidence=0.0,
            articles=[],
        )

    channel = root.find("channel")
    if channel is None:
        return VerificationEvidence(
            query=query,
            credible_hits=0,
            total_hits=0,
            source_diversity=0,
            confidence=0.0,
            articles=[],
        )

    for item in channel.findall("item")[:max_results]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()

        source_el = item.find("source")
        source_name = ""
        source_url = ""
        if source_el is not None:
            source_name = (source_el.text or "").strip()
            source_url = (source_el.attrib.get("url", "") or "").strip()

        domain = _domain_from_url(source_url) or _domain_from_url(link)
        source_weight = _weight_for_domain(domain)
        articles.append(
            EvidenceArticle(
                title=title,
                source=source_name or domain or "Unknown",
                source_url=source_url,
                article_url=link,
                published_at=_parse_pub_date(pub_date).isoformat(),
                source_weight=source_weight,
            )
        )

    credible_hits = sum(1 for article in articles if article.source_weight >= 0.75)
    weighted_sum = sum(article.source_weight for article in articles)
    diversity = len({article.source for article in articles if article.source_weight > 0})
    total_hits = len(articles)

    if total_hits == 0:
        confidence = 0.0
    else:
        # Mix of number of strong sources, weighted trust, and source diversity.
        confidence = min(
            1.0,
            (credible_hits / max(total_hits, 1)) * 0.55
            + (weighted_sum / max(total_hits, 1)) * 0.35
            + (min(diversity, 6) / 6) * 0.10,
        )

    return VerificationEvidence(
        query=query,
        credible_hits=credible_hits,
        total_hits=total_hits,
        source_diversity=diversity,
        confidence=round(confidence, 4),
        articles=articles[:8],
    )
