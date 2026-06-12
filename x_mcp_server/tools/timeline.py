"""Timeline and single-post tools."""

from __future__ import annotations

import re

from ..browser import get_session
from ..extract import extract_tweets, normalize_handle
from ..exceptions import ParseError
from ..models import Tweet
from ._common import collect_tweets


async def get_user_tweets(username: str, limit: int = 20) -> list[Tweet]:
    """Fetch a user's most recent posts from their profile timeline.

    Args:
        username: An @handle, plain handle, or full profile URL.
        limit: Maximum number of posts to return (1-100).

    Returns:
        Recent posts, newest first, with text, timestamp, and engagement counts.
    """
    limit = max(1, min(limit, 100))
    handle = normalize_handle(username)
    session = get_session()
    page = await session.new_page()
    try:
        await session.goto(
            page,
            f"https://x.com/{handle}",
            wait_for='article[data-testid="tweet"]',
        )
        return await collect_tweets(page, limit)
    finally:
        await page.close()


async def get_tweet(url_or_id: str) -> Tweet:
    """Fetch a single post by its URL or numeric status id.

    Args:
        url_or_id: A full post URL (e.g. "https://x.com/jack/status/20") or the
            bare numeric status id.

    Returns:
        The post's text, author, timestamp, and engagement counts.
    """
    status_id = _extract_status_id(url_or_id)
    url = url_or_id if url_or_id.startswith("http") else f"https://x.com/i/status/{status_id}"

    session = get_session()
    page = await session.new_page()
    try:
        await session.goto(page, url, wait_for='article[data-testid="tweet"]')
        tweets = await extract_tweets(page, limit=1)
        if not tweets:
            raise ParseError(f"No post content found at {url}")
        return tweets[0]
    finally:
        await page.close()


def _extract_status_id(value: str) -> str:
    m = re.search(r"status/(\d+)", value)
    if m:
        return m.group(1)
    if value.strip().isdigit():
        return value.strip()
    raise ParseError(f"Could not find a status id in '{value}'")
