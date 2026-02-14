import datetime as dt
import hashlib
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import Any

import requests

from app.models import TrendItem

CATEGORY_ORDER = [
    "all",
    "local",
    "india",
    "world",
    "entertainment",
    "health",
    "trending",
    "sports",
    "esports",
    "food",
    "events",
]

CATEGORY_LABELS = {
    "all": "All",
    "local": "Local",
    "india": "India",
    "world": "World",
    "entertainment": "Entertainment",
    "health": "Health",
    "trending": "Trending",
    "sports": "Sports",
    "esports": "Esports",
    "food": "Food",
    "events": "Events",
}

CATEGORY_QUERIES = {
    "local": "local city news breaking updates",
    "india": "India breaking news latest updates",
    "world": "world breaking news latest updates",
    "entertainment": "entertainment celebrity movie music news",
    "health": "health medical public health news",
    "trending": "viral trending breaking news social media",
    "sports": "sports breaking scores tournaments news",
    "esports": "esports tournament gaming league news",
    "food": "food restaurant culinary agriculture news",
    "events": "events festival conference live updates",
}

DEFAULT_REDDIT_SUBREDDITS = [
    "worldnews",
    "news",
    "technology",
    "science",
    "business",
    "politics",
]

CATEGORY_REDDIT_SUBREDDITS = {
    "local": ["news", "usanews"],
    "india": ["india", "indianews"],
    "world": ["worldnews", "news", "geopolitics"],
    "entertainment": ["entertainment", "movies", "television"],
    "health": ["health", "medicine", "science"],
    "trending": ["news", "worldnews", "technology", "sports"],
    "sports": ["sports", "soccer", "cricket", "nba"],
    "esports": ["esports", "valorant", "globaloffensive", "leagueoflegends"],
    "food": ["food", "cooking", "recipes"],
    "events": ["news", "events", "worldnews"],
}

CATEGORY_HINT_BY_SUBREDDIT = {
    "worldnews": "world",
    "news": "local",
    "usanews": "local",
    "india": "india",
    "indianews": "india",
    "entertainment": "entertainment",
    "movies": "entertainment",
    "television": "entertainment",
    "health": "health",
    "medicine": "health",
    "sports": "sports",
    "soccer": "sports",
    "cricket": "sports",
    "nba": "sports",
    "esports": "esports",
    "valorant": "esports",
    "globaloffensive": "esports",
    "leagueoflegends": "esports",
    "food": "food",
    "cooking": "food",
    "recipes": "food",
    "events": "events",
}

CATEGORY_KEYWORDS = {
    "india": {"india", "delhi", "mumbai", "bengaluru", "new delhi", "kolkata"},
    "world": {"world", "global", "europe", "asia", "middle east", "africa"},
    "entertainment": {"movie", "music", "actor", "actress", "hollywood", "bollywood"},
    "health": {"health", "medical", "disease", "vaccine", "hospital", "doctor"},
    "sports": {"sports", "match", "league", "tournament", "goal", "cricket", "nba", "nfl"},
    "esports": {"esports", "valorant", "cs2", "counter-strike", "dota", "league of legends"},
    "food": {"food", "restaurant", "chef", "recipe", "culinary", "dining"},
    "events": {"festival", "summit", "conference", "event", "expo", "concert"},
    "local": {"local", "county", "city council", "statewide", "community"},
}

X_QUERY_BY_CATEGORY = {
    "local": "(local news OR city updates) lang:en -is:retweet",
    "india": "(India news OR India breaking) lang:en -is:retweet",
    "world": "(world news OR global breaking) lang:en -is:retweet",
    "entertainment": "(entertainment OR celebrity OR movie release) lang:en -is:retweet",
    "health": "(health news OR medical update OR WHO) lang:en -is:retweet",
    "trending": "(news OR breaking OR viral) lang:en -is:retweet",
    "sports": "(sports OR match OR finals) lang:en -is:retweet",
    "esports": "(esports OR valorant OR cs2 OR dota2) lang:en -is:retweet",
    "food": "(food news OR restaurant OR culinary) lang:en -is:retweet",
    "events": "(event update OR festival OR conference) lang:en -is:retweet",
}

NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.privacydev.net",
]

NITTER_ACCOUNTS_BY_CATEGORY = {
    "india": ["ndtv", "ANI", "the_hindu"],
    "world": ["Reuters", "BBCWorld", "AP"],
    "entertainment": ["Variety", "RollingStone"],
    "health": ["WHO", "CDCgov"],
    "sports": ["espn", "SkySportsNews"],
    "esports": ["ESPN_Esports", "Dexerto"],
    "food": ["foodnetwork", "bonappetit"],
    "events": ["LiveNation", "Eventbrite"],
    "trending": ["Reuters", "AP", "BBCBreaking"],
    "local": ["ABC", "CBSNews"],
}

REDDIT_HEADERS = {
    "User-Agent": "TrendTruthHackathon/1.2 (by u/public-trend-app)",
}


def get_available_categories() -> list[dict[str, str]]:
    return [{"id": key, "label": CATEGORY_LABELS[key]} for key in CATEGORY_ORDER]


def normalize_category(category: str | None) -> str:
    if not category:
        return "all"
    normalized = category.strip().lower()
    if normalized in CATEGORY_ORDER:
        return normalized
    return "all"


def _safe_get_json(url: str, params: dict[str, Any] | None = None) -> Any | None:
    try:
        response = requests.get(url, params=params, headers=REDDIT_HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def _safe_get_text(url: str, params: dict[str, Any] | None = None, timeout: int = 12) -> str:
    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.text
    except Exception:
        return ""


def _parse_pub_date(date_raw: str) -> dt.datetime:
    if not date_raw:
        return dt.datetime.now(dt.timezone.utc)
    try:
        parsed = parsedate_to_datetime(date_raw)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=dt.timezone.utc)
        return parsed
    except Exception:
        return dt.datetime.now(dt.timezone.utc)


def _infer_category(title: str, fallback: str = "trending") -> str:
    text = title.lower()
    for category, words in CATEGORY_KEYWORDS.items():
        if any(word in text for word in words):
            return category
    return fallback


def _matches_category(title: str, category: str) -> bool:
    if category in ("all", "trending"):
        return True
    words = CATEGORY_KEYWORDS.get(category, set())
    if not words:
        return True
    lower = title.lower()
    return any(word in lower for word in words)


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", title.lower()).strip()


def _make_gnews_id(category: str, url: str, title: str) -> str:
    raw = f"{category}|{url}|{title}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _engagement_from_recency(created_utc: int, floor: int = 10) -> int:
    hours_old = max(1.0, (time.time() - float(created_utc)) / 3600.0)
    score = max(float(floor), 120.0 / hours_old)
    return int(score)


def fetch_reddit_trends(limit: int, category: str) -> list[TrendItem]:
    subreddit_list = CATEGORY_REDDIT_SUBREDDITS.get(category, DEFAULT_REDDIT_SUBREDDITS)
    if category == "all":
        subreddit_list = DEFAULT_REDDIT_SUBREDDITS
    per_sub = max(3, (limit // max(len(subreddit_list), 1)) + 2)
    trends: list[TrendItem] = []

    for subreddit in subreddit_list:
        payload = _safe_get_json(
            f"https://www.reddit.com/r/{subreddit}/hot.json",
            params={"limit": per_sub},
        )
        if not payload:
            continue
        children = payload.get("data", {}).get("children", [])
        for child in children:
            data = child.get("data", {})
            if data.get("stickied"):
                continue
            title = data.get("title", "").strip()
            if not title:
                continue
            if category != "all" and not _matches_category(title, category):
                continue

            score = int(data.get("score", 0))
            comments = int(data.get("num_comments", 0))
            created_utc = int(data.get("created_utc", int(time.time())))
            permalink = data.get("permalink", "")
            url = f"https://www.reddit.com{permalink}" if permalink else data.get("url", "")
            hinted_fallback = (
                category
                if category != "all"
                else CATEGORY_HINT_BY_SUBREDDIT.get(subreddit, "trending")
            )
            item_category = _infer_category(title, fallback=hinted_fallback)

            trends.append(
                TrendItem(
                    id=f"reddit:{data.get('id', '')}",
                    platform="Reddit",
                    category=item_category,
                    title=title,
                    url=url,
                    author=data.get("author", "unknown"),
                    created_utc=created_utc,
                    metrics={
                        "score": score,
                        "comments": comments,
                        "engagement": score + (comments * 2),
                        "subreddit": subreddit,
                    },
                )
            )

    return _dedupe_and_rank(trends, limit)


def fetch_hackernews_trends(limit: int, category: str) -> list[TrendItem]:
    trends: list[TrendItem] = []
    ids_payload = _safe_get_json("https://hacker-news.firebaseio.com/v0/topstories.json")
    if not isinstance(ids_payload, list):
        return trends

    for story_id in ids_payload[: limit * 5]:
        item = _safe_get_json(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json")
        if not item or item.get("type") != "story":
            continue
        title = (item.get("title") or "").strip()
        if not title:
            continue
        if category not in ("all", "trending") and not _matches_category(title, category):
            continue

        score = int(item.get("score", 0))
        comments = int(item.get("descendants", 0))
        created_utc = int(item.get("time", int(time.time())))
        url = item.get("url", f"https://news.ycombinator.com/item?id={story_id}")
        item_category = _infer_category(title, fallback=category if category != "all" else "trending")
        trends.append(
            TrendItem(
                id=f"hn:{story_id}",
                platform="Hacker News",
                category=item_category,
                title=title,
                url=url,
                author=item.get("by", "unknown"),
                created_utc=created_utc,
                metrics={
                    "score": score,
                    "comments": comments,
                    "engagement": score + (comments * 3),
                },
            )
        )
        if len(trends) >= limit:
            break

    return _dedupe_and_rank(trends, limit)


def _google_rss_search(query: str, max_results: int, gl: str) -> list[dict[str, Any]]:
    hl = "en-US"
    ceid = f"{gl}:en"
    rss_url = (
        "https://news.google.com/rss/search?q="
        f"{urllib.parse.quote(query)}&hl={hl}&gl={gl}&ceid={ceid}"
    )
    xml_text = _safe_get_text(rss_url, timeout=12)
    if not xml_text:
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    channel = root.find("channel")
    if channel is None:
        return []

    records: list[dict[str, Any]] = []
    for item in channel.findall("item")[:max_results]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = _parse_pub_date((item.findtext("pubDate") or "").strip())
        source_el = item.find("source")
        source_name = ""
        if source_el is not None:
            source_name = (source_el.text or "").strip()
        if title and link:
            records.append(
                {
                    "title": title,
                    "url": link,
                    "source": source_name or "Google News",
                    "published": pub_date,
                }
            )
    return records


def fetch_google_news_trends(limit: int, category: str) -> list[TrendItem]:
    trends: list[TrendItem] = []
    now = dt.datetime.now(dt.timezone.utc)

    if category == "all":
        buckets = [key for key in CATEGORY_ORDER if key != "all"]
        per_bucket = max(2, (limit // max(len(buckets), 1)) + 1)
        targets = [(cat, CATEGORY_QUERIES[cat]) for cat in buckets]
    else:
        targets = [(category, CATEGORY_QUERIES.get(category, CATEGORY_QUERIES["trending"]))]
        per_bucket = max(4, limit)

    for cat, query in targets:
        gl = "IN" if cat == "india" else "US"
        records = _google_rss_search(query=query, max_results=per_bucket, gl=gl)
        for record in records:
            pub_dt: dt.datetime = record["published"]
            created_utc = int(pub_dt.timestamp())
            recency_engagement = _engagement_from_recency(created_utc, floor=12)
            age_hours = max(1.0, (now - pub_dt).total_seconds() / 3600.0)
            trends.append(
                TrendItem(
                    id=f"gnews:{_make_gnews_id(cat, record['url'], record['title'])}",
                    platform="Google News",
                    category=cat,
                    title=record["title"],
                    url=record["url"],
                    author=record["source"],
                    created_utc=created_utc,
                    metrics={
                        "score": recency_engagement,
                        "comments": 0,
                        "engagement": recency_engagement + int(max(0.0, 24.0 - age_hours)),
                        "source": record["source"],
                    },
                )
            )

    return _dedupe_and_rank(trends, limit)


def fetch_x_api_trends(limit: int, category: str) -> list[TrendItem]:
    bearer = os.getenv("X_BEARER_TOKEN", "").strip()
    if not bearer:
        return []

    query = X_QUERY_BY_CATEGORY.get(category, X_QUERY_BY_CATEGORY["trending"])
    if category == "all":
        query = X_QUERY_BY_CATEGORY["trending"]

    headers = {
        "Authorization": f"Bearer {bearer}",
        "User-Agent": "TrendTruthHackathon/1.2",
    }
    params = {
        "query": query,
        "max_results": min(100, max(10, limit * 2)),
        "tweet.fields": "created_at,public_metrics,author_id",
    }
    try:
        response = requests.get(
            "https://api.twitter.com/2/tweets/search/recent",
            params=params,
            headers=headers,
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    trends: list[TrendItem] = []
    for tweet in payload.get("data", [])[: limit * 2]:
        text = (tweet.get("text", "") or "").replace("\n", " ").strip()
        if not text:
            continue
        metrics = tweet.get("public_metrics", {})
        likes = int(metrics.get("like_count", 0))
        reposts = int(metrics.get("retweet_count", 0))
        replies = int(metrics.get("reply_count", 0))
        quotes = int(metrics.get("quote_count", 0))
        engagement = likes + (reposts * 2) + (replies * 2) + (quotes * 2)
        created_raw = (tweet.get("created_at") or "").replace("Z", "+00:00")
        try:
            created_utc = int(dt.datetime.fromisoformat(created_raw).timestamp())
        except Exception:
            created_utc = int(time.time())

        item_category = _infer_category(text, fallback=category if category != "all" else "trending")
        trends.append(
            TrendItem(
                id=f"x:{tweet.get('id', '')}",
                platform="X",
                category=item_category,
                title=text,
                url=f"https://x.com/i/web/status/{tweet.get('id', '')}",
                author=tweet.get("author_id", "unknown"),
                created_utc=created_utc,
                metrics={
                    "score": likes,
                    "comments": replies,
                    "engagement": engagement,
                    "reposts": reposts,
                    "quotes": quotes,
                },
            )
        )
    return _dedupe_and_rank(trends, limit)


def fetch_x_nitter_fallback(limit: int, category: str) -> list[TrendItem]:
    accounts = NITTER_ACCOUNTS_BY_CATEGORY.get(category, NITTER_ACCOUNTS_BY_CATEGORY["trending"])
    if category == "all":
        accounts = NITTER_ACCOUNTS_BY_CATEGORY["trending"] + NITTER_ACCOUNTS_BY_CATEGORY["sports"]
    accounts = accounts[:3]

    trends: list[TrendItem] = []
    started_at = time.time()
    for account in accounts:
        if (time.time() - started_at) > 4.0:
            break
        if len(trends) >= limit:
            break
        for instance in NITTER_INSTANCES[:1]:
            if (time.time() - started_at) > 4.0:
                break
            rss_url = f"{instance}/{account}/rss"
            xml_text = _safe_get_text(rss_url, timeout=2)
            if not xml_text:
                continue
            try:
                root = ET.fromstring(xml_text)
            except ET.ParseError:
                continue

            channel = root.find("channel")
            if channel is None:
                continue

            for item in channel.findall("item")[:2]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub_date = _parse_pub_date((item.findtext("pubDate") or "").strip())
                if not title or not link:
                    continue
                clean_title = re.sub(r"^[^:]+:\s*", "", title).strip()
                created_utc = int(pub_date.timestamp())
                engagement = _engagement_from_recency(created_utc, floor=8)
                item_category = _infer_category(clean_title, fallback=category if category != "all" else "trending")
                trends.append(
                    TrendItem(
                        id=f"xrss:{_make_gnews_id(item_category, link, clean_title)}",
                        platform="X",
                        category=item_category,
                        title=clean_title,
                        url=link,
                        author=account,
                        created_utc=created_utc,
                        metrics={
                            "score": engagement,
                            "comments": 0,
                            "engagement": engagement,
                            "mode": "nitter_fallback",
                        },
                    )
                )
                if len(trends) >= limit:
                    break

    return _dedupe_and_rank(trends, limit)


def fetch_x_trends(limit: int, category: str) -> tuple[list[TrendItem], str]:
    bearer = os.getenv("X_BEARER_TOKEN", "").strip()
    if bearer:
        items = fetch_x_api_trends(limit, category)
        return items, ("api_ok" if items else "api_error_or_empty")

    fallback_items = fetch_x_nitter_fallback(limit, category)
    if fallback_items:
        return fallback_items, "fallback_rss"
    return [], "fallback_unavailable_missing_token"


def _dedupe_and_rank(trends: list[TrendItem], limit: int) -> list[TrendItem]:
    unique: dict[str, TrendItem] = {}
    for item in trends:
        key = _normalize_title(item.title)
        if not key:
            continue
        existing = unique.get(key)
        if not existing:
            unique[key] = item
            continue
        current_engagement = int(item.metrics.get("engagement", 0))
        existing_engagement = int(existing.metrics.get("engagement", 0))
        if current_engagement > existing_engagement:
            unique[key] = item

    ranked = sorted(
        unique.values(),
        key=lambda x: (int(x.metrics.get("engagement", 0)), int(x.created_utc)),
        reverse=True,
    )
    return ranked[:limit]


def _balanced_all_categories(items: list[TrendItem], limit: int) -> list[TrendItem]:
    if not items:
        return []

    by_category: dict[str, list[TrendItem]] = {}
    for item in items:
        by_category.setdefault(item.category, []).append(item)
    for bucket in by_category.values():
        bucket.sort(
            key=lambda x: (int(x.metrics.get("engagement", 0)), int(x.created_utc)),
            reverse=True,
        )

    selected: list[TrendItem] = []
    selected_ids: set[str] = set()

    # First pass: one top result from each requested category.
    for cat in [c for c in CATEGORY_ORDER if c != "all"]:
        bucket = by_category.get(cat, [])
        if not bucket:
            continue
        top = bucket.pop(0)
        selected.append(top)
        selected_ids.add(top.id)
        if len(selected) >= limit:
            return selected

    # Second pass: fill remaining slots by global rank.
    for item in items:
        if item.id in selected_ids:
            continue
        selected.append(item)
        selected_ids.add(item.id)
        if len(selected) >= limit:
            break

    return selected[:limit]


def fetch_trends(limit: int = 20, category: str = "all") -> tuple[list[TrendItem], dict[str, str]]:
    normalized_category = normalize_category(category)

    if normalized_category == "all":
        reddit_target = max(5, int(limit * 0.24))
        hn_target = max(3, int(limit * 0.16))
        gnews_target = max(8, int(limit * 0.48))
        x_target = max(3, limit - reddit_target - hn_target - gnews_target + 4)
    else:
        reddit_target = max(4, int(limit * 0.28))
        hn_target = max(2, int(limit * 0.12))
        gnews_target = max(7, int(limit * 0.50))
        x_target = max(2, limit - reddit_target - hn_target - gnews_target + 3)

    reddit_items = fetch_reddit_trends(reddit_target, normalized_category)
    hn_items = fetch_hackernews_trends(hn_target, normalized_category)
    gnews_items = fetch_google_news_trends(gnews_target, normalized_category)
    x_items, x_status = fetch_x_trends(x_target, normalized_category)

    ranked_items = _dedupe_and_rank(reddit_items + hn_items + gnews_items + x_items, max(limit * 2, 30))
    if normalized_category == "all":
        all_items = _balanced_all_categories(ranked_items, limit)
    else:
        all_items = ranked_items[:limit]
    source_health = {
        "reddit": f"ok:{len(reddit_items)}" if reddit_items else "empty_or_rate_limited",
        "hacker_news": f"ok:{len(hn_items)}" if hn_items else "empty",
        "google_news": f"ok:{len(gnews_items)}" if gnews_items else "empty_or_rate_limited",
        "x": x_status,
    }
    return all_items, source_health
