"""Search tools."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from ..browser import get_session
from ..models import Tweet
from ._common import collect_tweets

_XQUIK_SEARCH_URL = "https://xquik.com/api/v1/x/tweets/search"


def _as_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return None


def _as_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _extract_xquik_tweets(payload: object) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        raise RuntimeError("Xquik search returned an invalid response shape.")
    tweets = payload.get("tweets")
    if not isinstance(tweets, list):
        raise RuntimeError("Xquik search returned an invalid response shape.")
    if not all(isinstance(item, Mapping) for item in tweets):
        raise RuntimeError("Xquik search returned an invalid response shape.")
    return tweets


def _tweet_from_xquik(item: Mapping[str, Any]) -> Tweet:
    author_value = item.get("author")
    author = author_value if isinstance(author_value, Mapping) else {}
    handle = _as_string(author.get("userName"))
    if handle:
        handle = handle.lstrip("@")

    tweet_id = _as_string(item.get("id"))
    url = _as_string(item.get("url"))
    if not url and tweet_id and handle:
        url = f"https://x.com/{handle}/status/{tweet_id}"

    return Tweet(
        id=tweet_id,
        url=url,
        author_handle=f"@{handle}" if handle else None,
        author_name=_as_string(author.get("name")),
        text=_as_string(item.get("text")) or "",
        created_at=_as_string(item.get("createdAt")),
        reply_count=_as_int(item.get("replyCount")),
        repost_count=_as_int(item.get("retweetCount")),
        like_count=_as_int(item.get("likeCount")),
        view_count=_as_int(item.get("viewCount")),
    )


def _xquik_search_sync(query: str, limit: int, latest: bool, api_key: str) -> list[Tweet]:
    params = urlencode(
        {
            "q": query,
            "queryType": "Latest" if latest else "Top",
            "limit": limit,
        }
    )
    request = Request(
        f"{_XQUIK_SEARCH_URL}?{params}",
        headers={
            "Accept": "application/json",
            "User-Agent": "mcp-server-x",
            "x-api-key": api_key,
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Xquik search failed with HTTP {exc.code}.") from exc
    except URLError as exc:
        raise RuntimeError(f"Xquik search failed: {exc.reason}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError("Xquik search returned an invalid JSON response.") from exc

    return [_tweet_from_xquik(item) for item in _extract_xquik_tweets(payload)]


async def _search_xquik(query: str, limit: int, latest: bool) -> list[Tweet] | None:
    api_key = os.getenv("XQUIK_API_KEY", "").strip()
    if not api_key:
        return None
    return await asyncio.to_thread(_xquik_search_sync, query, limit, latest, api_key)


async def search_tweets(query: str, limit: int = 20, latest: bool = True) -> list[Tweet]:
    """Search X for posts matching a query.

    Args:
        query: A search query. Supports X's search operators (e.g.
            'from:jack', '#python', '"exact phrase"', 'min_faves:100').
        limit: Maximum number of posts to return (1-100).
        latest: If true, use the "Latest" tab (chronological); otherwise "Top".

    Returns:
        Matching posts with text, author, timestamp, and engagement counts.
    """
    limit = max(1, min(limit, 100))
    xquik_tweets = await _search_xquik(query, limit, latest)
    if xquik_tweets is not None:
        return xquik_tweets

    tab = "live" if latest else "top"
    url = f"https://x.com/search?q={quote(query, safe='')}&src=typed_query&f={tab}"

    session = get_session()
    page = await session.new_page()
    try:
        await session.goto(page, url, wait_for='article[data-testid="tweet"]')
        return await collect_tweets(page, limit)
    finally:
        await page.close()
