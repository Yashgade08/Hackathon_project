import datetime as dt
import os
import re
import time
from typing import Any

import requests

from app.models import TrendItem

REDDIT_SUBREDDITS = [
    "worldnews",
    "news",
    "technology",
    "science",
    "business",
    "politics",
]

REDDIT_HEADERS = {
    "User-Agent": "TrendTruthHackathon/1.0 (by u/public-trend-app)",
}


def _safe_get(url: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    try:
        response = requests.get(url, params=params, headers=REDDIT_HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def fetch_reddit_trends(limit: int) -> list[TrendItem]:
    per_sub = max(4, (limit // max(len(REDDIT_SUBREDDITS), 1)) + 2)
    trends: list[TrendItem] = []

    for subreddit in REDDIT_SUBREDDITS:
        payload = _safe_get(
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

            score = int(data.get("score", 0))
            comments = int(data.get("num_comments", 0))
            created_utc = int(data.get("created_utc", int(time.time())))
            permalink = data.get("permalink", "")
            url = f"https://www.reddit.com{permalink}" if permalink else data.get("url", "")

            trends.append(
                TrendItem(
                    id=f"reddit:{data.get('id', '')}",
                    platform="Reddit",
                    title=data.get("title", ""),
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


def fetch_hackernews_trends(limit: int) -> list[TrendItem]:
    trends: list[TrendItem] = []
    ids_payload = _safe_get("https://hacker-news.firebaseio.com/v0/topstories.json")
    if not isinstance(ids_payload, list):
        return trends

    for story_id in ids_payload[: limit * 2]:
        item = _safe_get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json")
        if not item or item.get("type") != "story":
            continue
        title = item.get("title")
        if not title:
            continue

        score = int(item.get("score", 0))
        comments = int(item.get("descendants", 0))
        created_utc = int(item.get("time", int(time.time())))
        url = item.get("url", f"https://news.ycombinator.com/item?id={story_id}")
        trends.append(
            TrendItem(
                id=f"hn:{story_id}",
                platform="Hacker News",
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


def fetch_x_trends(limit: int) -> list[TrendItem]:
    bearer = os.getenv("X_BEARER_TOKEN", "").strip()
    if not bearer:
        return []

    headers = {
        "Authorization": f"Bearer {bearer}",
        "User-Agent": "TrendTruthHackathon/1.0",
    }
    query = "(news OR breaking OR viral) lang:en -is:retweet"
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
        metrics = tweet.get("public_metrics", {})
        likes = int(metrics.get("like_count", 0))
        reposts = int(metrics.get("retweet_count", 0))
        replies = int(metrics.get("reply_count", 0))
        quotes = int(metrics.get("quote_count", 0))
        engagement = likes + (reposts * 2) + (replies * 2) + (quotes * 2)

        created_at = tweet.get("created_at")
        try:
            dt_obj = dt.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            created_utc = int(dt_obj.timestamp())
        except Exception:
            created_utc = int(time.time())

        tweet_id = tweet.get("id", "")
        author_id = tweet.get("author_id", "unknown")
        trends.append(
            TrendItem(
                id=f"x:{tweet_id}",
                platform="X",
                title=tweet.get("text", "").replace("\n", " ").strip(),
                url=f"https://x.com/i/web/status/{tweet_id}",
                author=author_id,
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


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", title.lower()).strip()


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
        key=lambda x: (
            int(x.metrics.get("engagement", 0)),
            int(x.created_utc),
        ),
        reverse=True,
    )
    return ranked[:limit]


def fetch_trends(limit: int = 20) -> list[TrendItem]:
    reddit_target = max(6, int(limit * 0.5))
    hn_target = max(4, int(limit * 0.25) + 2)
    x_target = max(4, limit - reddit_target - hn_target + 3)

    trends = (
        fetch_reddit_trends(reddit_target)
        + fetch_hackernews_trends(hn_target)
        + fetch_x_trends(x_target)
    )
    return _dedupe_and_rank(trends, limit)
