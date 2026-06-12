"""Shared helpers for tool implementations."""

from __future__ import annotations

import asyncio

from patchright.async_api import Page

from ..extract import extract_tweets
from ..models import Tweet

_MAX_SCROLLS = 25


async def collect_tweets(page: Page, limit: int) -> list[Tweet]:
    """Scroll the current timeline, de-duplicating, until ``limit`` tweets are found.

    X virtualises its timeline, so we extract after each scroll and accumulate by
    tweet id/url instead of relying on a single snapshot.
    """
    seen: dict[str, Tweet] = {}
    ordered: list[str] = []

    for _ in range(_MAX_SCROLLS):
        for tweet in await extract_tweets(page, limit=10_000):
            key = tweet.id or tweet.url or tweet.text[:48]
            if key and key not in seen:
                seen[key] = tweet
                ordered.append(key)
        if len(ordered) >= limit:
            break
        await page.mouse.wheel(0, 3_000)
        await asyncio.sleep(1.0)

    return [seen[k] for k in ordered[:limit]]
